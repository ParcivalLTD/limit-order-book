"""The agents.

Two so far:

- `MarketMaker` quotes both sides off the tape. It is the subject of the study.
- `NoiseTrader` buys and sells for reasons outside the model. It is the flow a
  market maker wants.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .book import Side, Trade
from .market import MarketState


@dataclass
class MarketMaker:
    """Quotes a symmetric spread around its estimate of fair value.

    bid = fair - half_spread
    ask = fair + half_spread

    Its only risk control is the hard position limit. Note that the limit pulls
    just the quote that would make the position worse; the other side stays up.
    """

    agent_id: str = "mm"
    half_spread: float = 4.0
    quote_size: int = 5
    max_inventory: int = 60

    inventory: int = 0
    _resting: list[int] = field(default_factory=list)

    def act(self, state: MarketState, rng: np.random.Generator) -> None:
        book = state.book
        for order_id in self._resting:
            book.cancel(order_id)
        self._resting = []

        centre = state.public_estimate
        bid = int(round(centre - self.half_spread))
        ask = int(round(centre + self.half_spread))
        if ask <= bid:  # never quote a crossed or locked market
            ask = bid + 1

        # Stop adding to a position that is already at the limit. Note this only
        # pulls the quote that would make things worse; the other side stays up.
        if self.inventory < self.max_inventory:
            oid, _ = book.submit(self.agent_id, Side.BUY, self.quote_size, bid)
            if oid is not None:
                self._resting.append(oid)
        if self.inventory > -self.max_inventory:
            oid, _ = book.submit(self.agent_id, Side.SELL, self.quote_size, ask)
            if oid is not None:
                self._resting.append(oid)


@dataclass
class NoiseTrader:
    """Uninformed market orders. Arrives with probability `intensity` each step.

    This is the flow that pays the spread and asks for nothing back. A market
    maker's gross edge is roughly (half spread) x (noise volume it wins).
    """

    agent_id: str = "noise"
    intensity: float = 0.55
    size_low: int = 1
    size_high: int = 6

    def act(self, state: MarketState, rng: np.random.Generator) -> list[Trade]:
        if rng.random() > self.intensity:
            return []
        side = Side.BUY if rng.random() < 0.5 else Side.SELL
        size = int(rng.integers(self.size_low, self.size_high + 1))
        _, trades = state.book.submit(self.agent_id, side, size, price=None)
        return trades
