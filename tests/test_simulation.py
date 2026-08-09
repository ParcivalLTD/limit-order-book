"""Tests for the accounting and for the behaviour the experiments rely on.

The decomposition tests matter most: if `total = edge + position` stops being an
identity, every conclusion in the README becomes a coincidence.
"""

import pytest

from lob.book import Side, Trade
from lob.market import Ledger, Simulation, ValueProcess
from lob.agents import InformedTrader, MarketMaker, NoiseTrader
from lob.metrics import decompose


def _session(seed=0, n_steps=3000, **mm_kwargs):
    sim = Simulation(
        market_maker=MarketMaker(**mm_kwargs),
        takers=[NoiseTrader(), InformedTrader()],
        background=None,
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
