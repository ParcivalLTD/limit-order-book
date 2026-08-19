"""What informed flow costs, and at what point it makes the business impossible.

Holds the quote fixed and turns up the proportion of order flow that knows where
the value is. The interesting output is not that P&L falls, which is obvious, but
where it crosses zero: below that intensity the spread pays for the picking off,
above it no fixed spread does.

Run: python -m experiments.adverse_selection
"""

from __future__ import annotations

import numpy as np

from lob.metrics import markout, summarise
from .common import run_many, run_session
from .plotting import save_adverse_selection, save_markout_curves

INTENSITIES = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 0.9]
HALF_SPREAD = 4.0
N_SEEDS = 20


def main() -> dict:
    rows = []
    print(f"Fixed half spread {HALF_SPREAD:.0f}, {N_SEEDS} seeds per point.\n")
    print(f"{'informed':>9} {'total P&L':>12} {'stderr':>8} {'edge':>10} "
          f"{'position':>10} {'volume':>9} {'edge/ct':>8}")
    print("-" * 72)

    for intensity in INTENSITIES:
        stats = summarise(
            run_many(n_seeds=N_SEEDS, half_spread=HALF_SPREAD, informed_intensity=intensity)
        )
        rows.append({"informed_intensity": intensity, **stats})
        print(f"{intensity:>9.2f} {stats['total_mean']:>12.0f} {stats['total_stderr']:>8.0f} "
              f"{stats['edge_mean']:>10.0f} {stats['position_mean']:>10.0f} "
              f"{stats['volume_mean']:>9.0f} {stats['edge_per_contract']:>8.3f}")

    crossing = next((r for r in rows if r["edge_mean"] < 0), None)
    if crossing:
        print(f"\nEdge goes negative once informed flow reaches "
              f"{crossing['informed_intensity']:.2f}. At a half spread of "
              f"{HALF_SPREAD:.0f} the maker cannot charge its way out beyond that.")
    else:
        print("\nEdge stayed positive across the whole range tested.")

    # Markout curves at three spreads, to show the same effect per fill.
    curves = {}
    for hs in (1.0, 4.0, 8.0):
        horizons = (1, 5, 10, 25, 50)
        per_seed = [markout(run_session(seed=s, half_spread=hs), horizons) for s in range(10)]
        curves[hs] = {h: float(np.mean([c[h] for c in per_seed])) for h in horizons}

    print("\nMarkout, average P&L per contract h steps after each fill:")
    header = "  ".join(f"h={h:<5}" for h in (1, 5, 10, 25, 50))
    print(f"{'half spread':>12}  {header}")
    for hs, curve in curves.items():
        cells = "  ".join(f"{curve[h]:>7.3f}" for h in (1, 5, 10, 25, 50))
        print(f"{hs:>12.0f}  {cells}")

    save_adverse_selection(rows)
    save_markout_curves(curves)
    return {"rows": rows, "markout": curves}


if __name__ == "__main__":
    main()
