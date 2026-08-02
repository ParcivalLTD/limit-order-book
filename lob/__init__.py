"""A limit order book, a market maker, and the flow that trades against it.

The package is deliberately four small modules with a one-way dependency chain:

    book -> market -> agents
                   -> metrics

`book` knows nothing about value or agents; it only matches orders. `market`
owns the latent value process and the step loop. `agents` decide what to quote
and what to take. `metrics` reads a finished session and says what happened.

Nothing here imports from `experiments`, so the engine can be used without
dragging matplotlib in.
"""

from .book import Order, OrderBook, Side, Trade

__all__ = ["Order", "OrderBook", "Side", "Trade"]
