"""Differential test: the OCaml engine must behave exactly like the Python one.

Generates random order streams, runs each through lob/book.py (the original
Python engine) and through the OCaml `replay` executable, and compares the
outputs line by line: resting order ids, every trade (price, quantity, maker,
taker, side, timestamp), cancel results, and the full book after every step.

Run from the repository root:

    (cd ocaml && dune build)
    python ocaml/diff/differential.py --streams 2000
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lob.book import OrderBook, Side  # noqa: E402

REPLAY = REPO / "ocaml" / "_build" / "default" / "bin" / "replay.exe"
AGENTS = ["a", "b", "c", "mm"]


def random_stream(rng: random.Random, length: int, allow_invalid: bool) -> list[str]:
    ops = []
    for _ in range(length):
        r = rng.random()
        agent = rng.choice(AGENTS)
        if r < 0.62:
            qty = rng.randint(1, 20)
            price = rng.randint(95, 105)
            if allow_invalid and rng.random() < 0.03:
                qty, price = rng.choice([(0, price), (qty, 0), (qty, -3)])
            ops.append(f"S {agent} {rng.choice('BS')} {qty} {price}")
        elif r < 0.75:
            ops.append(f"S {agent} {rng.choice('BS')} {rng.randint(1, 30)} M")
        elif r < 0.95:
            ops.append(f"C {rng.randint(1, length)}")
        else:
            ops.append(f"X {agent}")
    return ops


def python_replay(ops: list[str]) -> list[str]:
    book = OrderBook()
    out = []

    def levels(side: Side) -> str:
        return ",".join(f"{p}@{q}" for p, q in book.snapshot(side))

    for op in ops:
        parts = op.split()
        if parts[0] == "S":
            _, agent, side, qty, price = parts
            side = Side.BUY if side == "B" else Side.SELL
            try:
                oid, trades = book.submit(
                    agent, side, int(qty), None if price == "M" else int(price)
                )
                ts = ";".join(
                    f"{t.price},{t.quantity},{t.maker_id},{t.taker_id},"
                    f"{'B' if t.taker_side is Side.BUY else 'S'},{t.timestamp}"
                    for t in trades
                )
                result = f"S {'-' if oid is None else oid} [{ts}]"
            except ValueError:
                result = "E"
        elif parts[0] == "C":
            result = f"C {'true' if book.cancel(int(parts[1])) else 'false'}"
        else:
            result = f"X {book.cancel_all(parts[1])}"
        out.append(f"{result} | B:{levels(Side.BUY)} A:{levels(Side.SELL)}")
    return out


def ocaml_replay(ops: list[str]) -> list[str]:
    run = subprocess.run(
        [str(REPLAY)], input="\n".join(ops) + "\n", capture_output=True, text=True, check=True
    )
    return run.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--streams", type=int, default=2000)
    parser.add_argument("--length", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--allow-invalid", action="store_true",
                        help="also send zero quantities and non-positive prices")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    total_ops = total_trades = 0
    for n in range(args.streams):
        ops = random_stream(rng, args.length, args.allow_invalid)
        py, ml = python_replay(ops), ocaml_replay(ops)
        for i, (a, b) in enumerate(zip(py, ml)):
            if a != b:
                print(f"MISMATCH in stream {n} at op {i}: {ops[i]}")
                print("  ops so far:", ops[: i + 1])
                print(f"  python: {a}\n  ocaml:  {b}")
                return 1
        if len(py) != len(ml):
            print(f"length mismatch in stream {n}")
            return 1
        total_ops += len(ops)
        for line in py:
            if line.startswith("S "):
                inside = line[line.index("[") + 1 : line.index("]")]
                total_trades += len(inside.split(";")) if inside else 0
    print(f"identical on {args.streams} streams, {total_ops} operations, {total_trades} trades")
    return 0


if __name__ == "__main__":
    sys.exit(main())
