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

from .book import OrderBook


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
