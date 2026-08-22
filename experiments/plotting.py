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


def save_adverse_selection(rows: list[dict]) -> Path:
    """P&L against the informed arrival rate, with volume on a second axis.

    The volume series is the whole reason this figure has a twin axis: it rises
    monotonically while the P&L falls, and putting them on the same picture is
    the clearest way to show that fill rate is not a health metric.
    """
    x = [r["informed_intensity"] for r in rows]

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.errorbar(
        x, [r["total_mean"] for r in rows], yerr=[r["total_stderr"] for r in rows],
        color=TOTAL_C, marker="o", capsize=3, label="total",
    )
    ax.plot(x, [r["edge_mean"] for r in rows], color=EDGE_C, marker="s", label="edge")
    _style(ax, "informed arrival rate", "P&L per session", "More toxic flow, more volume, less money")

    twin = ax.twinx()
    twin.plot(
        x, [r["volume_mean"] for r in rows],
        color=VOLUME_C, marker="^", linestyle="--", alpha=0.85, label="volume",
    )
    twin.set_ylabel("contracts traded")

    handles = ax.get_legend_handles_labels()[0] + twin.get_legend_handles_labels()[0]
    labels = ax.get_legend_handles_labels()[1] + twin.get_legend_handles_labels()[1]
    ax.legend(handles, labels, frameon=False, fontsize=9, loc="center left")

    fig.tight_layout()
    return _save(fig, "adverse_selection.png")


def save_markout_curves(curves: dict[float, dict[int, float]]) -> Path:
    """Average P&L per contract h steps after each fill, one line per spread."""
    fig, ax = plt.subplots(figsize=(7, 4.2))
    colours = {1.0: EDGE_C, 4.0: TOTAL_C, 8.0: VOLUME_C}

    for hs, curve in sorted(curves.items()):
        horizons = sorted(curve)
        ax.plot(
            horizons, [curve[h] for h in horizons],
            marker="o", color=colours.get(hs), label=f"half spread {hs:.0f}",
        )

    _style(ax, "horizon h (steps after fill)", "P&L per contract", "Markout is flat: the damage lands immediately")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    return _save(fig, "markout.png")


def save_inventory_skew(rows: list[dict]) -> Path:
    """The skew result: risk falls as expected, and the mean rises unexpectedly."""
    skew = [r["skew"] for r in rows]

    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.2))

    left.plot(skew, [r["total_mean"] for r in rows], color=TOTAL_C, marker="o", label="total")
    left.plot(skew, [r["edge_mean"] for r in rows], color=EDGE_C, marker="s", label="edge")
    left.fill_between(
        skew,
        [r["total_mean"] - r["total_std"] for r in rows],
        [r["total_mean"] + r["total_std"] for r in rows],
        color=TOTAL_C, alpha=0.12, label="+/- 1 sd across sessions",
    )
    _style(left, "inventory skew", "P&L per session", "The gain lands in edge, not position")
    left.legend(frameon=False, fontsize=9)

    right.plot(skew, [r["mean_over_std"] for r in rows], color=TOTAL_C, marker="o", label="mean / std")
    best = max(rows, key=lambda r: r["mean_over_std"])
    right.axvline(best["skew"], color=TOTAL_C, linestyle=":", alpha=0.6)
    _style(right, "inventory skew", "mean / std across sessions", "Risk-adjusted return, and the position it carries")

    twin = right.twinx()
    twin.plot(
        skew, [r["max_abs_inventory"] for r in rows],
        color=POSITION_C, marker="^", linestyle="--", label="avg peak |inventory|",
    )
    twin.set_ylabel("avg peak |inventory|")
    right.legend(frameon=False, fontsize=9, loc="lower right")
    twin.legend(frameon=False, fontsize=9, loc="upper right")

    fig.tight_layout()
    return _save(fig, "inventory_skew.png")
