"""Figures for the three experiments.

Matplotlib only, Agg backend, no seaborn: these run headless from `run_all.py`
and the figures are committed, so the fewer moving parts the better.

One convention worth stating, because it is the point of most of these plots:
wherever a chart shows P&L it shows `edge` alongside it. The total on its own
is the number that fooled me early on, and a figure that only plotted the total
would reproduce exactly that mistake for the reader.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

FIGURES = Path(__file__).resolve().parent.parent / "figures"

TOTAL_C = "#1f4e79"
EDGE_C = "#c1440e"
POSITION_C = "#7f7f7f"
VOLUME_C = "#2a9d5c"


def _save(fig, name: str) -> Path:
    FIGURES.mkdir(exist_ok=True)
    path = FIGURES / name
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")
    return path


def _style(ax, xlabel: str, ylabel: str, title: str) -> None:
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=10, loc="left")
    ax.grid(alpha=0.25, linewidth=0.6)
    ax.axhline(0, color="black", linewidth=0.8, alpha=0.5)


def save_spread_sweep(rows: list[dict]) -> Path:
    """P&L against half spread, decomposed, with the volume trade-off beside it."""
    hs = [r["half_spread"] for r in rows]
    total = [r["total_mean"] for r in rows]
    err = [r["total_stderr"] for r in rows]

    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.2))

    left.errorbar(hs, total, yerr=err, color=TOTAL_C, marker="o", capsize=3, label="total")
    left.plot(hs, [r["edge_mean"] for r in rows], color=EDGE_C, marker="s", label="edge")
    left.plot(
        hs, [r["position_mean"] for r in rows],
        color=POSITION_C, marker="^", linestyle="--", label="position",
    )
    best = max(rows, key=lambda r: r["total_mean"])
    left.axvline(best["half_spread"], color=TOTAL_C, linestyle=":", alpha=0.6)
    _style(left, "half spread (ticks)", "P&L per session", "P&L splits into edge and position")
    left.legend(frameon=False, fontsize=9)

    # The trade-off that creates the interior optimum: per-contract profitability
    # keeps rising while the volume it applies to collapses.
    right.plot(hs, [r["volume_mean"] for r in rows], color=VOLUME_C, marker="o", label="volume")
    _style(right, "half spread (ticks)", "contracts traded", "Volume falls as edge per contract rises")
    twin = right.twinx()
    twin.plot(
        hs, [r["edge_per_contract"] for r in rows],
        color=EDGE_C, marker="s", linestyle="--", label="edge / contract",
    )
    twin.set_ylabel("edge per contract")
    twin.axhline(0, color=EDGE_C, linewidth=0.6, alpha=0.4)
    right.legend(frameon=False, fontsize=9, loc="upper right")
    twin.legend(frameon=False, fontsize=9, loc="center right")

    fig.tight_layout()
    return _save(fig, "spread_sweep.png")
