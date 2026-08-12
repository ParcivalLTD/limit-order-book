"""The shared harness: one place that decides what "a session" means.

Every experiment varies one parameter and holds the rest fixed. If each of them
built its own `Simulation` the fixed part would drift between studies, and the
three tables in the README would stop being comparable to each other. So the
baseline lives here exactly once, and the experiments pass overrides.

Two knobs are worth explaining because the README's numbers depend on them:

`N_STEPS = 8000` is long enough that the value process delivers a few hundred
jumps, which is what the adverse selection results are actually measuring. Much
shorter and the edge term is dominated by however many jumps happened to land.

`N_SEEDS = 20` is not a lot, but the position term has a large variance and the
useful quantity is the mean of `edge`, which is far better behaved. Every
reported figure carries a standard error for this reason.
"""

from __future__ import annotations

from lob.agents import BackgroundLiquidity, InformedTrader, MarketMaker, NoiseTrader
from lob.market import Simulation, SimulationResult, ValueProcess

N_STEPS = 8_000
N_SEEDS = 20

# The baseline. Deviating from these in an experiment is fine; deviating from
# them silently in two experiments in different ways is how you get two results
# that cannot be read against each other.
HALF_SPREAD = 4.0
INVENTORY_SKEW = 0.0
INFORMED_INTENSITY = 0.25
NOISE_INTENSITY = 0.55


def run_session(
    seed: int = 0,
    half_spread: float = HALF_SPREAD,
    inventory_skew: float = INVENTORY_SKEW,
    informed_intensity: float = INFORMED_INTENSITY,
    noise_intensity: float = NOISE_INTENSITY,
    n_steps: int = N_STEPS,
) -> SimulationResult:
    """One trading session against a fresh book and a fresh value process.

    The `ValueProcess` is constructed per call rather than shared: it carries
    mutable state in `self.value`, so reusing one across sessions would make
    the results depend on the order they were run in.
    """
    sim = Simulation(
        market_maker=MarketMaker(
            half_spread=half_spread,
            inventory_skew=inventory_skew,
        ),
        takers=[
            NoiseTrader(intensity=noise_intensity),
            InformedTrader(intensity=informed_intensity),
        ],
        background=BackgroundLiquidity(),
        n_steps=n_steps,
        value_process=ValueProcess(),
        seed=seed,
    )
    return sim.run()


def run_many(n_seeds: int = N_SEEDS, **kwargs) -> list[SimulationResult]:
    """The same configuration over `n_seeds` seeds.

    Seeds are 0..n_seeds-1 rather than random, so a re-run of any table in the
    README reproduces it exactly. Sessions are independent and this loop is the
    obvious place to parallelise; it has not been, and that is why the full run
    takes minutes rather than seconds.
    """
    return [run_session(seed=seed, **kwargs) for seed in range(n_seeds)]
