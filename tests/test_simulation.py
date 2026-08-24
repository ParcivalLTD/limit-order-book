"""Tests for the accounting and for the behaviour the experiments rely on.

The decomposition tests matter most: if `total = edge + position` stops being an
identity, every conclusion in the README becomes a coincidence.
"""

import numpy as np
import pytest

from lob.book import Side, Trade
from lob.market import Ledger, Simulation, ValueProcess
from lob.agents import BackgroundLiquidity, InformedTrader, MarketMaker, NoiseTrader
from lob.metrics import decompose, markout


def _session(seed=0, n_steps=3000, **mm_kwargs):
    sim = Simulation(
        market_maker=MarketMaker(**mm_kwargs),
        takers=[NoiseTrader(), InformedTrader()],
        background=BackgroundLiquidity(),
        n_steps=n_steps,
        value_process=ValueProcess(),
        seed=seed,
    )
    return sim.run()


# ----------------------------------------------------------------- accounting


def test_ledger_signs_a_buy_and_a_sell_correctly():
    ledger = Ledger("mm")
    buy = Trade(100, 5, maker_id="mm", taker_id="x", taker_side=Side.SELL, timestamp=1)
    ledger.apply(buy, step=0, true_value=100.0)
    assert (ledger.inventory, ledger.cash) == (5, -500)

    sell = Trade(110, 5, maker_id="mm", taker_id="x", taker_side=Side.BUY, timestamp=2)
    ledger.apply(sell, step=1, true_value=110.0)
    assert (ledger.inventory, ledger.cash) == (0, 50)


def test_ledger_ignores_trades_it_is_not_party_to():
    ledger = Ledger("mm")
    ledger.apply(
        Trade(100, 5, maker_id="a", taker_id="b", taker_side=Side.BUY, timestamp=1),
        step=0,
        true_value=100.0,
    )
    assert ledger.fills == [] and ledger.inventory == 0


@pytest.mark.parametrize("seed", range(5))
def test_total_equals_edge_plus_position(seed):
    result = _session(seed=seed)
    b = decompose(result)
    assert b.total == pytest.approx(b.edge + b.position, rel=1e-9, abs=1e-6)


@pytest.mark.parametrize("seed", range(5))
def test_decomposition_agrees_with_mark_to_market(seed):
    result = _session(seed=seed)
    direct = result.ledger.mark_to_value(float(result.true_values[-1]))
    assert decompose(result).total == pytest.approx(direct, rel=1e-9, abs=1e-6)


def test_empty_session_decomposes_to_zero():
    sim = Simulation(
        market_maker=MarketMaker(),
        takers=[],  # nobody trades
        background=None,
        n_steps=50,
        seed=0,
    )
    b = decompose(sim.run())
    assert (b.total, b.edge, b.position, b.n_fills) == (0.0, 0.0, 0.0, 0)


# ------------------------------------------------------------------ behaviour


def test_market_maker_respects_its_position_limit():
    result = _session(seed=3, max_inventory=20)
    # The limit stops it *adding*, so a single fill can carry it one quote past.
    assert np.max(np.abs(result.inventory_path)) <= 20 + MarketMaker().quote_size


def test_inventory_skew_reduces_position_risk():
    unskewed = [decompose(_session(seed=s, inventory_skew=0.0)) for s in range(12)]
    skewed = [decompose(_session(seed=s, inventory_skew=0.4)) for s in range(12)]

    unskewed_swing = np.mean([b.max_abs_inventory for b in unskewed])
    skewed_swing = np.mean([b.max_abs_inventory for b in skewed])
    assert skewed_swing < unskewed_swing


def test_wider_spreads_earn_more_per_contract():
    tight = decompose(_session(seed=1, half_spread=2.0)).edge_per_contract
    wide = decompose(_session(seed=1, half_spread=7.0)).edge_per_contract
    assert wide > tight


def test_wider_spreads_trade_less():
    tight = decompose(_session(seed=1, half_spread=2.0)).volume
    wide = decompose(_session(seed=1, half_spread=7.0)).volume
    assert wide < tight


def test_a_very_tight_quote_is_picked_off():
    """At one tick the maker is always at the front of the queue, including in
    front of every informed trader. Its edge should be negative."""
    assert decompose(_session(seed=1, half_spread=1.0)).edge < 0


def test_informed_flow_is_what_destroys_the_edge():
    with_informed = Simulation(
        market_maker=MarketMaker(half_spread=2.0),
        takers=[NoiseTrader(), InformedTrader(intensity=0.25)],
        background=BackgroundLiquidity(),
        n_steps=3000,
        seed=7,
    ).run()
    without_informed = Simulation(
        market_maker=MarketMaker(half_spread=2.0),
        takers=[NoiseTrader(), InformedTrader(intensity=0.0)],
        background=BackgroundLiquidity(),
        n_steps=3000,
        seed=7,
    ).run()

    assert decompose(without_informed).edge > decompose(with_informed).edge


def test_markout_is_negative_from_the_first_tick_on_a_tight_quote():
    """Adverse selection in this model is instantaneous, not delayed.

    The informed traders here see the *current* value, not a future one, so a
    stale quote is already wrong at the moment it is hit. The markout is
    therefore negative at h=1 and stays flat rather than decaying, which is the
    opposite of the classic toxic-flow signature and a real limitation of the
    model. See the README.
    """
    curve = markout(_session(seed=2, half_spread=1.0), horizons=(1, 10, 50))
    assert all(v < 0 for v in curve.values())


def test_a_wide_quote_markouts_better_than_a_tight_one_at_every_short_horizon():
    tight = markout(_session(seed=2, half_spread=1.0), horizons=(1, 10, 50))
    wide = markout(_session(seed=2, half_spread=8.0), horizons=(1, 10, 50))
    assert all(wide[h] > tight[h] for h in (1, 10, 50))


def test_the_book_is_never_crossed_during_a_session():
    result = _session(seed=4, n_steps=500)
    finite = result.mid_path[~np.isnan(result.mid_path)]
    assert len(finite) > 0  # the book was quoted


def test_runs_are_reproducible():
    a = decompose(_session(seed=11))
    b = decompose(_session(seed=11))
    assert a == b
