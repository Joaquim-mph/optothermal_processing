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


def load_chip_curve(
    chip_number: int,
    seqs: list[int],
    label: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (wavelengths_nm, delta_current_uA) for one chip's wl sweep."""
    history_path = ENRICHED_DIR / f"Alisson{chip_number}_history.parquet"
    if not history_path.exists():
        raise FileNotFoundError(
            f"Enriched history not found for chip {chip_number} at {history_path}. "
            f"Run: biotite enrich-history {chip_number}"
        )

    history = pl.read_parquet(history_path)

    after_seq = history.filter(pl.col("seq").is_in(seqs))
    after_proc = after_seq.filter(pl.col("proc") == "It")
    after_light = after_proc.filter(pl.col("has_light") == True)

    if after_light.height == 0:
        raise ValueError(
            f"[{label}] no rows survived filtering. "
            f"seq match: {after_seq.height}, "
            f"proc==It: {after_proc.height}, "
            f"has_light: {after_light.height}"
        )

    rows = after_light

    if "delta_current" in rows.columns:
        if rows["delta_current"].dtype == pl.Utf8:
            rows = rows.with_columns(pl.col("delta_current").cast(pl.Float64))
        rows = rows.filter(
            pl.col("delta_current").is_not_null() & pl.col("delta_current").is_not_nan()
        )

    if "delta_current" not in rows.columns or rows.height == 0:
        delta_values: list[float | None] = []
        base_rows = after_light
        for row in base_rows.iter_rows(named=True):
            from src.core.utils import read_measurement_parquet

            parquet_path = Path(row.get("parquet_path") or row.get("source_file") or "")
            if not parquet_path.exists():
                delta_values.append(None)
                continue
            measurement = read_measurement_parquet(parquet_path)
            delta_values.append(
                _extract_delta_current_from_its(measurement, row)
            )
        rows = base_rows.with_columns(pl.Series("delta_current", delta_values))
        rows = rows.filter(pl.col("delta_current").is_not_null())

    if rows.height == 0:
        raise ValueError(
            f"[{label}] could not resolve delta_current for any row "
            f"(enriched column empty and fallback extractor returned None for all rows)."
        )

    rows = rows.sort("wavelength_nm")

    wavelengths_nm = rows["wavelength_nm"].to_numpy()
    delta_current_uA = np.abs(rows["delta_current"].to_numpy()) * 1e6

    print(
        f"[{label}] chip={chip_number} n_points={rows.height} "
        f"wl_range=[{wavelengths_nm.min():.0f}, {wavelengths_nm.max():.0f}] nm "
        f"|Δi|_range=[{delta_current_uA.min():.3g}, {delta_current_uA.max():.3g}] µA"
    )

    return wavelengths_nm, delta_current_uA


def main() -> None:
    curves: list[tuple[str, np.ndarray, np.ndarray]] = []
    for chip in CHIPS:
        wl, di = load_chip_curve(chip["chip_number"], chip["seqs"], chip["label"])
        curves.append((chip["label"], wl, di))


if __name__ == "__main__":
    main()
