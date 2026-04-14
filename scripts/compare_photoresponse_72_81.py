"""
Overlay same-power wavelength-sweep photoresponse for Alisson72 (hBN)
and Alisson81 (biotite).

Produces two PNGs under figs/compare/:
  * alisson72_vs_81_ITS_photoresponse_vs_wavelength.png          (linear)
  * alisson72_vs_81_ITS_photoresponse_vs_wavelength_semilogy.png (log y)

Run from the repo root:
    python scripts/compare_photoresponse_72_81.py

Prereq: biotite enrich-history 72 and biotite enrich-history 81.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style
from src.plotting.its_photoresponse import _extract_delta_current_from_its

ENRICHED_DIR = Path("data/03_derived/chip_histories_enriched")
OUTPUT_DIR = Path("figs/compare")

CHIPS = [
    {
        "chip_number": 72,
        "label": "72 (hBN)",
        "seqs": [11, 16, 20, 24, 26, 28, 30, 32, 34, 36],
    },
    {
        "chip_number": 81,
        "label": "81 (biotite)",
        "seqs": [4, 6, 8, 10, 12, 14, 16, 18, 33, 35],
    },
]


def main() -> None:
    pass


if __name__ == "__main__":
    main()
