r"""Turning a pile of fills into the two numbers that actually explain the session.

The headline P&L of a market maker tells you almost nothing on its own. A good
session and a bad session can print the same number for opposite reasons: one
charged a fat spread and got run over, the other charged nothing and got lucky
on the drift. So every result here is split into

    total = edge + position

which is an identity, not an approximation. The derivation, since it is short:

    total  = cash + q_T * V_T
           = -sum_i(p_i * dq_i) + V_T * sum_i(dq_i)
           = sum_i dq_i * (V_T - p_i)
           = sum_i dq_i * (v_i - p_i)   +   sum_i dq_i * (V_T - v_i)
             \_____ edge _____/             \____ position ____/

where dq_i is the signed inventory change of fill i, p_i its price, v_i the true
value at the moment it happened, and V_T the true value at the end.

`edge` is what the maker charged over fair at the instant of trading. It is the
number that goes negative when the flow is toxic, and it is the one to watch:
it is the part of the P&L the maker controls.

`position` is what the inventory it was left holding did afterwards. It has mean
near zero over many sessions and a large variance, which is exactly why
inventory skew is worth paying for.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .market import SimulationResult


@dataclass(frozen=True)
class PnLBreakdown:
    total: float
    edge: float
    position: float
    n_fills: int
    volume: int
    final_inventory: int
    max_abs_inventory: int
    edge_per_contract: float

    def __str__(self) -> str:
        return (
            f"total {self.total:>10.1f} | edge {self.edge:>10.1f} | "
            f"position {self.position:>10.1f} | fills {self.n_fills:>5d} | "
            f"volume {self.volume:>6d} | edge/contract {self.edge_per_contract:>7.3f}"
        )


def decompose(result: SimulationResult) -> PnLBreakdown:
    fills = result.ledger.fills
    final_value = float(result.true_values[-1])

    if not fills:
        return PnLBreakdown(0.0, 0.0, 0.0, 0, 0, 0, 0, 0.0)

    dq = np.array([f.signed_quantity for f in fills], dtype=float)
    price = np.array([f.price for f in fills], dtype=float)
    value = np.array([f.true_value for f in fills], dtype=float)

    edge = float(np.sum(dq * (value - price)))
    position = float(np.sum(dq * (final_value - value)))
    volume = int(np.sum(np.abs(dq)))

    return PnLBreakdown(
        total=edge + position,
        edge=edge,
        position=position,
        n_fills=len(fills),
        volume=volume,
        final_inventory=result.ledger.inventory,
        max_abs_inventory=int(np.max(np.abs(result.inventory_path))),
        edge_per_contract=edge / volume,
    )
