"""The world the market maker trades in: a latent value process and a step loop.

The model has one asset with a true value V_t that nobody posts and nobody can
observe directly. Informed traders see it. Everyone else, including our market
maker, only sees the tape and has to infer it. That asymmetry is the entire
source of adverse selection in this simulator, so it is worth being explicit
about where it lives: `ValueProcess.value` is private information, and
`MarketState.public_estimate` is what the uninformed get.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .book import OrderBook, Side, Trade


@dataclass
class ValueProcess:
    """A random walk in continuous value with occasional jumps.

    The diffusion moves the value gently enough that quoted spreads absorb it.
    The jumps are what pick a stale quote off: they are large relative to a
    typical spread and arrive without warning.
    """

    initial: float = 1000.0
    diffusion_sigma: float = 0.35
    jump_probability: float = 0.02
    jump_size: float = 12.0

    def __post_init__(self) -> None:
        self.value = float(self.initial)

    def step(self, rng: np.random.Generator) -> float:
        self.value += rng.normal(0.0, self.diffusion_sigma)
        if rng.random() < self.jump_probability:
            self.value += rng.choice([-1.0, 1.0]) * abs(
                rng.normal(self.jump_size, self.jump_size * 0.3)
            )
        return self.value


@dataclass
class MarketState:
    """Everything an agent is allowed to look at, plus the one thing it is not.

    `true_value` is passed around for bookkeeping and for the informed traders.
    Uninformed agents are on their honour not to read it, which in a simulator
    is enforced by code review rather than by the type system.
    """

    step: int
    true_value: float
    public_estimate: float
    book: OrderBook


@dataclass
class FillRecord:
    """One of the market maker's fills, stamped with the true value at the time.

    Storing V at execution is what makes the P&L decomposition in `metrics.py`
    possible: it separates "what I charged over fair" from "what the position
    did afterwards".
    """

    step: int
    price: int
    signed_quantity: int  # + when the maker bought, - when it sold
    true_value: float
    was_maker: bool


class Ledger:
    """Tracks cash, inventory and per-fill history for one agent."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.cash = 0.0
        self.inventory = 0
        self.fills: list[FillRecord] = []

    def apply(self, trade: Trade, step: int, true_value: float) -> None:
        dq = trade.signed_quantity_for(self.agent_id)
        if dq == 0:
            return
        self.cash -= dq * trade.price
        self.inventory += dq
        self.fills.append(
            FillRecord(
                step=step,
                price=trade.price,
                signed_quantity=dq,
                true_value=true_value,
                was_maker=(trade.maker_id == self.agent_id),
            )
        )

    def mark_to_value(self, true_value: float) -> float:
        return self.cash + self.inventory * true_value


@dataclass
class SimulationResult:
    ledger: Ledger
    trades: list[Trade]
    true_values: np.ndarray
    inventory_path: np.ndarray
    mid_path: np.ndarray

    @property
    def total_pnl(self) -> float:
        return self.ledger.mark_to_value(float(self.true_values[-1]))

    @property
    def n_fills(self) -> int:
        return len(self.ledger.fills)


@dataclass
class Simulation:
    """One trading session.

    Order within a step matters and is deliberate: liquidity is refreshed
    before flow arrives, so quotes are always exposed to at least one round of
    trading before they can be pulled. A market maker that could cancel after
    seeing the order would never lose money, which is not a market.
    """

    market_maker: object
    takers: list  # agents that consume liquidity
    background: object | None = None
    n_steps: int = 20_000
    value_process: ValueProcess = field(default_factory=ValueProcess)
    ewma_alpha: float = 0.05
    seed: int = 0

    def run(self) -> SimulationResult:
        rng = np.random.default_rng(self.seed)
        book = OrderBook()
        ledger = Ledger(self.market_maker.agent_id)

        public_estimate = self.value_process.value
        all_trades: list[Trade] = []
        true_values = np.empty(self.n_steps)
        inventory_path = np.empty(self.n_steps)
        mid_path = np.full(self.n_steps, np.nan)

        for step in range(self.n_steps):
            v = self.value_process.step(rng)
            state = MarketState(
                step=step, true_value=v, public_estimate=public_estimate, book=book
            )

            if self.background is not None:
                self.background.act(state, rng)
            self.market_maker.act(state, rng)

            step_trades: list[Trade] = []
            for taker in self.takers:
                step_trades.extend(taker.act(state, rng))

            for trade in step_trades:
                ledger.apply(trade, step, v)
            all_trades.extend(step_trades)

            # The public estimate is the tape, not the truth. It only updates
            # when something prints, which is why it lags through a jump.
            for trade in step_trades:
                public_estimate += self.ewma_alpha * (trade.price - public_estimate)

            self.market_maker.inventory = ledger.inventory
            true_values[step] = v
            inventory_path[step] = ledger.inventory
            mid = book.mid
            if mid is not None:
                mid_path[step] = mid

        return SimulationResult(
            ledger=ledger,
            trades=all_trades,
            true_values=true_values,
            inventory_path=inventory_path,
            mid_path=mid_path,
        )
