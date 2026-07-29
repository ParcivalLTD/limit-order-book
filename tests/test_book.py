"""Matching engine tests.

The engine is the one component where a subtle bug would silently invalidate
every experiment downstream, so the invariants are pinned explicitly: price
priority, time priority within a level, the maker's price on the print,
quantity conservation, and a book that never stays crossed.
"""

import pytest

from lob.book import OrderBook, Side


@pytest.fixture
def book() -> OrderBook:
    return OrderBook()


def test_resting_orders_do_not_trade(book):
    book.submit("a", Side.BUY, 10, 99)
    _, trades = book.submit("b", Side.SELL, 10, 101)
    assert trades == []
    assert (book.best_bid, book.best_ask, book.spread) == (99, 101, 2)
    assert book.mid == 100


def test_price_priority_best_level_fills_first(book):
    book.submit("far", Side.BUY, 10, 98)
    book.submit("near", Side.BUY, 10, 99)

    _, trades = book.submit("taker", Side.SELL, 10, 98)

    assert len(trades) == 1
    assert trades[0].price == 99
    assert trades[0].maker_id == "near"


def test_time_priority_within_a_level_is_fifo(book):
    book.submit("first", Side.BUY, 5, 100)
    book.submit("second", Side.BUY, 5, 100)

    _, trades = book.submit("taker", Side.SELL, 7, 100)

    assert [(t.maker_id, t.quantity) for t in trades] == [("first", 5), ("second", 2)]
    assert book.depth_at(Side.BUY, 100) == 3


def test_trade_prints_at_the_makers_price(book):
    book.submit("maker", Side.SELL, 10, 100)

    # An aggressive buy priced through the offer still pays the resting price.
    _, trades = book.submit("taker", Side.BUY, 10, 105)

    assert trades[0].price == 100
    assert trades[0].taker_side is Side.BUY


def test_partial_fill_rests_the_remainder(book):
    book.submit("maker", Side.SELL, 4, 100)

    order_id, trades = book.submit("taker", Side.BUY, 10, 100)

    assert sum(t.quantity for t in trades) == 4
    assert order_id is not None
    assert book.depth_at(Side.BUY, 100) == 6
    assert book.best_ask is None


def test_market_order_walks_levels_then_discards_remainder(book):
    book.submit("m1", Side.SELL, 3, 100)
    book.submit("m2", Side.SELL, 3, 101)

    order_id, trades = book.submit("taker", Side.BUY, 10, price=None)

    assert [t.price for t in trades] == [100, 101]
    assert sum(t.quantity for t in trades) == 6
    assert order_id is None  # a market order never rests
    assert book.best_bid is None


def test_market_order_into_an_empty_book_does_nothing(book):
    order_id, trades = book.submit("taker", Side.BUY, 10, price=None)
    assert (order_id, trades) == (None, [])


def test_cancel_removes_liquidity_and_is_idempotent(book):
    order_id, _ = book.submit("a", Side.BUY, 10, 100)

    assert book.cancel(order_id) is True
    assert book.best_bid is None
    assert book.cancel(order_id) is False


def test_cancel_all_only_touches_the_named_agent(book):
    book.submit("mm", Side.BUY, 5, 99)
    book.submit("mm", Side.SELL, 5, 101)
    book.submit("other", Side.BUY, 5, 98)

    assert book.cancel_all("mm") == 2
    assert book.best_bid == 98
    assert book.best_ask is None


def test_book_is_never_left_crossed(book):
    book.submit("a", Side.SELL, 5, 100)
    book.submit("b", Side.BUY, 5, 100)
    assert book.best_bid is None or book.best_ask is None or book.best_bid < book.best_ask


def test_quantity_is_conserved_across_a_multi_level_sweep(book):
    for price in (100, 101, 102):
        book.submit("mm", Side.SELL, 4, price)

    _, trades = book.submit("taker", Side.BUY, 9, price=None)

    filled = sum(t.quantity for t in trades)
    remaining = sum(book.depth_at(Side.SELL, p) for p in (100, 101, 102))
    assert filled + remaining == 12


def test_signed_quantity_is_equal_and_opposite(book):
    book.submit("maker", Side.SELL, 5, 100)
    _, trades = book.submit("taker", Side.BUY, 5, price=None)
    trade = trades[0]

    assert trade.signed_quantity_for("taker") == 5
    assert trade.signed_quantity_for("maker") == -5
    assert trade.signed_quantity_for("bystander") == 0


def test_rejects_nonsense_orders(book):
    with pytest.raises(ValueError):
        book.submit("a", Side.BUY, 0, 100)
    with pytest.raises(ValueError):
        book.submit("a", Side.BUY, 5, -1)


def test_snapshot_is_ordered_best_first(book):
    for price in (98, 100, 99):
        book.submit("a", Side.BUY, 1, price)
    for price in (103, 101, 102):
        book.submit("a", Side.SELL, 1, price)

    assert [p for p, _ in book.snapshot(Side.BUY)] == [100, 99, 98]
    assert [p for p, _ in book.snapshot(Side.SELL)] == [101, 102, 103]
