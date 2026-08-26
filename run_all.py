"""Run the whole study: tests, then every experiment, then the figures.

    python run_all.py

Takes a few minutes. Every number in the README comes from this script.
"""

import subprocess
import sys
import time

from experiments import adverse_selection, inventory_skew, spread_sweep
from experiments.common import run_session
from experiments.plotting import save_session_trace


def banner(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def main() -> None:
    start = time.time()

    banner("TESTS")
    if subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"]).returncode:
        sys.exit("tests failed; not running experiments on a broken engine")

    banner("EXPERIMENT 1  How wide should the quote be?")
    spread_sweep.main()

    banner("EXPERIMENT 2  What does informed flow cost?")
    adverse_selection.main()

    banner("EXPERIMENT 3  What does inventory skew buy?")
    inventory_skew.main()

    banner("FIGURES")
    save_session_trace(run_session(seed=0, half_spread=4.0))

    print(f"\nDone in {time.time() - start:.0f}s. Figures in figures/.")


if __name__ == "__main__":
    main()
