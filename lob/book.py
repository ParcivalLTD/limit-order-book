"""A limit order book with price-time priority.

Prices are integer ticks throughout. Floating point prices in a matching engine
invite equality bugs, so the book never sees a float.

"""

from __future__ import annotations

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
