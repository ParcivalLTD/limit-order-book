"""A limit order book with price-time priority.

Prices are integer ticks throughout. Floating point prices in a matching engine
invite equality bugs, so the book never sees a float.

Each side keeps a dict mapping price -> deque of resting orders. The deque gives
FIFO time priority within a level in O(1) at both ends.
"""

from __future__ import annotations

import itertools
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class Side(Enum):
    BUY = 1
    SELL = -1

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY

    @property
    def sign(self) -> int:
        """+1 for a buy, -1 for a sell. Handy for signing inventory changes."""
        return self.value


@dataclass
class Order:
    """A resting or incoming order. `price is None` means a market order."""

    order_id: int
    agent_id: str
    side: Side
    quantity: int
    price: int | None = None
    timestamp: int = 0

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"quantity must be positive, got {self.quantity}")
        if self.price is not None and self.price <= 0:
            raise ValueError(f"price must be positive, got {self.price}")


@dataclass(frozen=True)
class Trade:
    """One fill. `maker` was resting, `taker` crossed the spread to hit it.

    The trade always prints at the maker's price: the taker gets any price
    improvement, which is what a real book does and what makes queue position
    worth having.
    """

    price: int
    quantity: int
    maker_id: str
    taker_id: str
    taker_side: Side
    timestamp: int

    def signed_quantity_for(self, agent_id: str) -> int:
        """Change in `agent_id`'s inventory from this trade. 0 if uninvolved."""
        if agent_id == self.taker_id:
            return self.taker_side.sign * self.quantity
        if agent_id == self.maker_id:
            return self.taker_side.opposite.sign * self.quantity
        return 0


class OrderBook:
    """A single-instrument book. Not thread safe; the simulation is single threaded."""

    def __init__(self) -> None:
        self._levels: dict[Side, dict[int, deque[Order]]] = {Side.BUY: {}, Side.SELL: {}}
        self._orders: dict[int, Order] = {}
        self._ids = itertools.count(1)
        self.time = 0

    # ------------------------------------------------------------------ state

    def _best(self, side: Side) -> int | None:
        """Best price on `side`, or None if that side is empty.

        Scans the live price keys, so this is O(number of levels). Fine while
        the book is shallow; the first thing to fix if it stops being.
        """
        prices = [price for price, queue in self._levels[side].items() if queue]
        if not prices:
            return None
        return max(prices) if side is Side.BUY else min(prices)

    @property
    def best_bid(self) -> int | None:
        return self._best(Side.BUY)

    @property
    def best_ask(self) -> int | None:
        return self._best(Side.SELL)

    @property
    def mid(self) -> float | None:
        bid, ask = self.best_bid, self.best_ask
        return None if bid is None or ask is None else (bid + ask) / 2

    @property
    def spread(self) -> int | None:
        bid, ask = self.best_bid, self.best_ask
        return None if bid is None or ask is None else ask - bid

    def depth_at(self, side: Side, price: int) -> int:
        return sum(o.quantity for o in self._levels[side].get(price, ()))

    def open_order_ids(self, agent_id: str) -> list[int]:
        return [oid for oid, o in self._orders.items() if o.agent_id == agent_id]

    def snapshot(self, side: Side) -> list[tuple[int, int]]:
        """(price, resting quantity) from best to worst. For tests and debugging."""
        prices = [p for p, q in self._levels[side].items() if q]
        prices.sort(reverse=side is Side.BUY)
        return [(p, self.depth_at(side, p)) for p in prices]

    # ------------------------------------------------------------------ writes

    def submit(
        self,
        agent_id: str,
        side: Side,
        quantity: int,
        price: int | None = None,
    ) -> tuple[int | None, list[Trade]]:
        """Submit an order.

        Returns the resting order id (None if nothing rested) and the trades it
        caused. A market order that cannot be fully filled has its remainder
        cancelled rather than resting, since it has no price to rest at.
        """
        self.time += 1
        order = Order(
            order_id=next(self._ids),
            agent_id=agent_id,
            side=side,
            quantity=quantity,
            price=price,
            timestamp=self.time,
        )
        trades = self._match(order)
        if order.quantity > 0 and order.price is not None:
            self._rest(order)
            return order.order_id, trades
        return None, trades

    def cancel(self, order_id: int) -> bool:
        """Remove a resting order. Returns False if it was already gone."""
        order = self._orders.pop(order_id, None)
        if order is None:
            return False
        level = self._levels[order.side].get(order.price)
        if level is not None:
            try:
                level.remove(order)
            except ValueError:
                pass
            if not level:
                del self._levels[order.side][order.price]
        return True

    def cancel_all(self, agent_id: str) -> int:
        ids = self.open_order_ids(agent_id)
        return sum(self.cancel(oid) for oid in ids)

    # ---------------------------------------------------------------- internals

    def _crosses(self, incoming: Order, resting_price: int) -> bool:
        if incoming.price is None:  # a market order crosses anything
            return True
        if incoming.side is Side.BUY:
            return incoming.price >= resting_price
        return incoming.price <= resting_price

    def _match(self, incoming: Order) -> list[Trade]:
        """Walk the opposite side, consuming levels best-first and FIFO within."""
        trades: list[Trade] = []
        book_side = incoming.side.opposite
        levels = self._levels[book_side]

        while incoming.quantity > 0:
            best = self._best(book_side)
            if best is None or not self._crosses(incoming, best):
                break

            queue = levels[best]
            while queue and incoming.quantity > 0:
                resting = queue[0]
                filled = min(resting.quantity, incoming.quantity)
                resting.quantity -= filled
                incoming.quantity -= filled

                trades.append(
                    Trade(
                        price=best,  # the maker's price
                        quantity=filled,
                        maker_id=resting.agent_id,
                        taker_id=incoming.agent_id,
                        taker_side=incoming.side,
                        timestamp=self.time,
                    )
                )

                if resting.quantity == 0:
                    queue.popleft()
                    self._orders.pop(resting.order_id, None)

            if not queue:
                del levels[best]

        return trades

    def _rest(self, order: Order) -> None:
        levels = self._levels[order.side]
        if order.price not in levels:
            levels[order.price] = deque()
        levels[order.price].append(order)
        self._orders[order.order_id] = order
