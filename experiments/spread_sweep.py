"""How wide should the quote be?

Sweeps the market maker's half spread and measures P&L across many seeds. The
question the plot answers is why there is an interior optimum at all, and the
answer is that the two failure modes sit at opposite ends:

  too tight  - the maker wins the queue every time, including against every
               informed trader. Edge per contract goes negative.
  too wide   - the background liquidity providers undercut it, so it is rarely
               at the top of the book and barely trades. Edge per contract is
               excellent and total P&L is nearly zero.

Run: python -m experiments.spread_sweep
"""

from __future__ import annotations

import numpy as np

from lob.metrics import summarise
from .common import run_many
from .plotting import save_spread_sweep

HALF_SPREADS = [1, 2, 3, 4, 5, 6, 8, 10, 13]
N_SEEDS = 20


def main() -> dict:
    rows = []
    print(f"{'half spread':>12} {'total P&L':>12} {'stderr':>8} "
          f"{'edge':>10} {'position':>10} {'volume':>9} {'edge/ct':>8}")
    print("-" * 76)

    for hs in HALF_SPREADS:
        stats = summarise(run_many(n_seeds=N_SEEDS, half_spread=float(hs)))
        rows.append({"half_spread": hs, **stats})
        print(f"{hs:>12} {stats['total_mean']:>12.0f} {stats['total_stderr']:>8.0f} "
              f"{stats['edge_mean']:>10.0f} {stats['position_mean']:>10.0f} "
              f"{stats['volume_mean']:>9.0f} {stats['edge_per_contract']:>8.3f}")

    best = max(rows, key=lambda r: r["total_mean"])
    print(f"\nBest total P&L at half spread {best['half_spread']} "
          f"({best['total_mean']:.0f} +/- {best['total_stderr']:.0f} per session).")

    first_positive = next((r for r in rows if r["edge_mean"] > 0), None)
    if first_positive:
        print(f"Edge first turns positive at half spread {first_positive['half_spread']}: "
              f"below that the maker is paying for its own fills.")

    save_spread_sweep(rows)
    return {"rows": rows, "best": best}


if __name__ == "__main__":
    main()
