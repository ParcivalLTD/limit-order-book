# The matching engine, ported to OCaml

A second implementation of `lob/book.py`, written in OCaml with Jane Street's
`Base` library, and checked against the Python engine on random order streams.

I ported it with AI assistance, as my first OCaml program, to learn the language
on a problem I already understood. The interesting parts were not the syntax but
what the type system and immutability changed about the design.

```sh
cd ocaml && dune build && dune test && cd ..     # 15 ported tests + properties
python ocaml/diff/differential.py --streams 2000 # Python vs OCaml, from the repo root
```

## What changed in the port

**A resting order cannot be a market order.** In Python every `Order` has
`price: int | None`, so "a market order resting in the book" is representable and
has to be prevented by code. In OCaml the incoming order type is
`Limit of int | Market`, and a resting order has no price field at all: its price
is the key of the level it sits in.

**No heap, no lazy deletion.** Python finds the best price with a heap per side,
and because heaps cannot delete arbitrary elements, empty levels are skipped
lazily. Here each side is a balanced map (`Map.M(Int).t`) from price to queue, so
the best bid is `Map.max_elt`, the best ask `Map.min_elt`, and an emptied level is
simply removed. The invariant "no level is ever empty" is maintained in one
function, `set_level`.

**The book is immutable.** `submit` returns a new book and leaves the old one
intact, which made the property tests easy: compare the book before and after
every order. Queues are persistent two-list FIFO queues (`Fqueue`).

**Errors are values.** Python raises `ValueError` on a zero quantity; here
`submit` returns `Or_error.t`, so the caller has to handle rejection.

## How it is tested

- `test/test_book.ml` — the 15 tests from `tests/test_book.py`, one for one, as
  expect tests.
- `test/test_properties.ml` — QCheck generates 5,000 random order streams and
  checks after every order: filled quantity left the opposite side exactly,
  limit orders are fully accounted for, the book is never crossed, and fills walk
  away from the best price.
- `diff/differential.py` — sends the same random streams through both engines
  and requires identical output after every operation: order ids, every trade
  (price, quantity, maker, taker, side, timestamp), cancels, and the full book.
  Identical on 2,000 streams, 400,000 operations, ~219,000 trades.

Breaking the engine on purpose (best bid from the wrong end, LIFO queues, an
off-by-one in the crossing rule, a stale cancel index) fails both the unit tests
and the differential test.

## One difference the differential test found

With `--allow-invalid`, the outputs diverge after the first rejected order. In
Python, `submit` advances the clock and takes an order id *before* the order is
validated, so a rejected order still shifts every later timestamp by one. The
OCaml version leaves the book unchanged on rejection. I kept the OCaml behaviour;
the Python fix is to validate before incrementing.

## Layout

```
src/side.ml        Buy | Sell
src/trade.ml       one fill, and who gained or lost inventory
src/fqueue.ml      persistent FIFO queue (two lists)
src/book.ml        the book: levels, matching, cancel
test/              expect tests and QCheck properties
bin/replay.ml      reads orders on stdin, prints results (for the differential test)
diff/              the Python-vs-OCaml differential test
```
