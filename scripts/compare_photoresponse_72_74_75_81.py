"""
Overlay same-power wavelength-sweep photoresponse for four chips:
  * Alisson72 (hBN)
  * Alisson74 (biotite)
  * Alisson75 (biotite, sparse: 365/455/565 nm only)
  * Alisson81 (biotite)

Produces two PNGs under figs/compare/:
  * alisson72_74_75_81_ITS_photoresponse_vs_wavelength.png          (linear)
  * alisson72_74_75_81_ITS_photoresponse_vs_wavelength_semilogy.png (log y)

Run from the repo root:
    python scripts/compare_photoresponse_72_74_75_81.py

Prereq: biotite full-pipeline (or enrich-history for each chip).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

import subprocess

from src.core.utils import read_measurement_parquet
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
        "chip_number": 74,
        "label": "74 (biotite)",
        "seqs": [5, 7, 9, 11, 13, 17, 20, 22, 24, 28],
    },
    {
        "chip_number": 75,
        "label": "75 (biotite)",
        "seqs": [62, 64, 69, 71, 73, 75, 77, 81, 83, 85],
    },
    {
        "chip_number": 81,
        "label": "81 (biotite)",
        "seqs": [4, 6, 8, 10, 12, 14, 16, 18, 33, 35],
    },
]


def run_its_suite(chip_number: int, seqs: list[int]) -> None:
    """Invoke `biotite plot-its-suite` for one chip's wavelength sweep."""
    seq_arg = ",".join(str(s) for s in seqs)
    tag = f"alisson{chip_number}_same_pwr_wl_sweep"
    cmd = [
        "biotite", "plot-its-suite", str(chip_number),
        "--seq", seq_arg,
        "--tag", tag,
        "--legend", "wavelength",
        "--photoresponse-x", "wavelength",
    ]
    print(f"[chip {chip_number}] $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


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


def make_figure(
    curves: list[tuple[str, np.ndarray, np.ndarray]],
    axtype: str,
    output_path: Path,
    config: PlotConfig,
) -> Path:
    """Draw one overlay figure and save it. axtype is 'linear' or 'semilogy'."""
    fig, ax = plt.subplots(figsize=config.figsize_derived)

    for label, wl, di_uA in curves:
        ax.plot(wl, di_uA, "o-", label=label)

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Δ Current (µA)")

    if axtype == "semilogy":
        ax.set_yscale("log")
    elif axtype != "linear":
        raise ValueError(f"axtype must be 'linear' or 'semilogy', got {axtype!r}")

    ax.legend(loc="best", framealpha=0.9)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")
    return output_path


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    curves: list[tuple[str, np.ndarray, np.ndarray]] = []
    for chip in CHIPS:
        wl, di = load_chip_curve(chip["chip_number"], chip["seqs"], chip["label"])
        curves.append((chip["label"], wl, di))

    for chip in CHIPS:
        run_its_suite(chip["chip_number"], chip["seqs"])

    base = OUTPUT_DIR / "alisson72_74_75_81_ITS_photoresponse_vs_wavelength"
    make_figure(curves, "linear", base.with_suffix(".png"), config)
    make_figure(
        curves,
        "semilogy",
        base.with_name(base.name + "_semilogy").with_suffix(".png"),
        config,
    )


if __name__ == "__main__":
    main()
