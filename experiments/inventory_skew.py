"""What does inventory skew buy, and what does it cost?

Skewing quotes against the position is the cheapest risk control a market maker
has: shift both sides down when long so the book is keener to sell than to buy.
It is not free. Every skewed quote is a quote posted away from where the maker
thinks fair value is, so edge per contract falls.

The number to look at is not mean P&L, which barely moves. It is the ratio of
mean to standard deviation across sessions. Two strategies earning the same
amount are not equally good if one of them does it while carrying four times the
position.

Run: python -m experiments.inventory_skew
"""

from __future__ import annotations

import numpy as np

from lob.metrics import decompose, summarise
from .common import run_many
from .plotting import save_inventory_skew

SKEWS = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8]
HALF_SPREAD = 4.0
N_SEEDS = 20


def main() -> dict:
    rows = []
    print(f"Fixed half spread {HALF_SPREAD:.0f}, {N_SEEDS} seeds per point.\n")
    print(f"{'skew':>6} {'total P&L':>12} {'std':>10} {'mean/std':>9} "
          f"{'edge':>10} {'position sd':>12} {'|inv| max':>10}")
    print("-" * 76)

    for skew in SKEWS:
        results = run_many(n_seeds=N_SEEDS, half_spread=HALF_SPREAD, inventory_skew=skew)
        stats = summarise(results)
        max_inv = float(np.mean([decompose(r).max_abs_inventory for r in results]))
        rows.append({"skew": skew, "max_abs_inventory": max_inv, **stats})
        print(f"{skew:>6.2f} {stats['total_mean']:>12.0f} {stats['total_std']:>10.0f} "
              f"{stats['mean_over_std']:>9.2f} {stats['edge_mean']:>10.0f} "
              f"{stats['position_std']:>12.0f} {max_inv:>10.0f}")

    best = max(rows, key=lambda r: r["mean_over_std"])
    flat = rows[0]
    print(f"\nBest risk-adjusted result at skew {best['skew']}: "
          f"mean/std {best['mean_over_std']:.2f} against {flat['mean_over_std']:.2f} unskewed.")
    print(f"Average peak position falls from {flat['max_abs_inventory']:.0f} "
          f"to {best['max_abs_inventory']:.0f} contracts.")

    save_inventory_skew(rows)
    return {"rows": rows, "best": best}


if __name__ == "__main__":
    main()
