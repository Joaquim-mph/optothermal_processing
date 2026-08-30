"""Transconductance (gm = dI/dVg) plotting functions."""

from __future__ import annotations
import logging

from pathlib import Path
from typing import Optional
import numpy as np
import matplotlib.pyplot as plt
import polars as pl

from src.core.utils import read_measurement_parquet
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.plot_utils import (
    get_chip_label,
    segment_voltage_sweep,
    _savgol_derivative_corrected,
    _raw_derivative,
    ensure_standard_columns,
    # Moved to plot_utils so the derived-metrics pipeline can reuse it without
    # importing matplotlib. Re-exported here: callers still do
    # `from src.plotting.transconductance import auto_select_savgol_params`.
    auto_select_savgol_params,
)

__all__ = ["auto_select_savgol_params", "plot_ivg_transconductance"]

logger = logging.getLogger(__name__)





def plot_ivg_transconductance(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    smoothing_window: int = 5,       # kept for signature compatibility (unused here)
    min_segment_length: int = 10,
    config: Optional[PlotConfig] = None,
):
    """
    Plot transconductance (dI/dVg) for all IVg measurements.

    Uses numpy.gradient (same as PyQtGraph) to compute gm.
    Segments are computed to avoid reversal artifacts, then joined
    in original sweep order (no sorting). NaNs separate segments.

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame with IVg experiments
    base_dir : Path
        Base directory containing measurement files
    tag : str
        Tag for output filename
    smoothing_window : int
        Kept for signature compatibility (unused in gradient method)
    min_segment_length : int
        Minimum points per segment before computing derivative
    config : PlotConfig, optional
        Plot configuration (theme, DPI, output paths, etc.)

    Notes
    -----
    - gm is computed per-segment: gm_seg = np.gradient(i_seg, vg_seg)
    - Duplicate VG values in a segment are removed before gradient to avoid div-by-zero.
    - Output units: gm shown in µS.
    """
    # Initialize config with defaults
    config = config or PlotConfig()

    # Apply plot style from config
    from src.plotting.shared.styles import set_plot_style
    set_plot_style(config.theme)

    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        logger.info("no IVg measurements to plot")
        return

    fig, ax = plt.subplots(figsize=config.figsize_voltage_sweep)
    curves_plotted = 0

    for meas_idx, row in enumerate(ivg.iter_rows(named=True)):
        path = base_dir / row["source_file"]
        if not path.exists():
            logger.warning(f"missing file: {path}")
            continue

        d = read_measurement_parquet(path)

        # Normalize column names (handle both formats)
        d = ensure_standard_columns(d)

        if not {"VG", "I"} <= set(d.columns):
            logger.warning(f"{path} lacks VG/I; got {d.columns}")
            continue

        vg = d["VG"].to_numpy()
        i = d["I"].to_numpy()

        # Segment to avoid derivative artifacts at reversals
        segments = segment_voltage_sweep(vg, i, min_segment_length)
        if len(segments) == 0:
            logger.warning(f"{path.name}: no valid segments found")
            continue

        # Legend label per measurement
        base_lbl = f"#{int(row['file_idx'])} {'light' if row.get('has_light', False) else 'dark'}"
        if bool(row.get("Laser toggle", False)):
            wl = row.get("Laser wavelength", None)
            if wl is not None and str(wl) != "nan":
                try:
                    base_lbl += f" λ={float(wl):.0f} nm"
                except (TypeError, ValueError):
                    pass

        # Compute gm per segment with numpy.gradient; join in original order
        vg_join = []
        gm_join = []
        for (vg_seg, i_seg, _dir) in segments:
            if vg_seg.size < 2:
                continue

            # Remove consecutive duplicate VG to prevent div-by-zero in gradient
            keep = np.hstack(([True], np.diff(vg_seg) != 0))
            vg_clean = vg_seg[keep]
            i_clean  = i_seg[keep]
            if vg_clean.size < 2:
                continue

            # PyQtGraph-style derivative
            gm_seg = np.gradient(i_clean, vg_clean)  # A/V (Siemens)

            if len(vg_join) > 0:
                vg_join.append(np.array([np.nan])); gm_join.append(np.array([np.nan]))
            vg_join.append(vg_clean)
            gm_join.append(gm_seg)

        if not vg_join:
            continue

        vg_concat = np.concatenate(vg_join)
        gm_concat = np.concatenate(gm_join)

        ax.plot(vg_concat, gm_concat * 1e6, label=base_lbl)  # µS
        curves_plotted += 1

    if curves_plotted == 0:
        logger.warning("no transconductance curves plotted")
        plt.close(fig)
        return

    ax.set_xlabel("VG (V)")
    ax.set_ylabel("Transconductance gm (µS)")
    chipnum = int(df['chip_number'][0])  # Use snake_case column name from history
    chip_group = None
    if "chip_group" in df.columns:
        chip_group = df["chip_group"][0]
    prefix = f"{chip_group}{chipnum}" if chip_group else f"encap{chipnum}"
    chip_group = None
    if "chip_group" in df.columns:
        chip_group = df["chip_group"][0]
    prefix = f"{chip_group}{chipnum}" if chip_group else f"encap{chipnum}"
    ax.set_title(f"{prefix} — Transconductance (np.gradient, joined, no sort)")
    ax.legend()
    ax.axhline(y=0, color='k', linestyle=':')

    plt.tight_layout()

    # Determine illumination status for subcategory
    illumination_metadata = None
    if "has_light" in df.columns:
        has_light_values = df["has_light"].unique().to_list()
        has_light_values = [v for v in has_light_values if v is not None]

        if len(has_light_values) == 1:
            illumination_metadata = {"has_light": has_light_values[0]}
        elif len(has_light_values) > 1:
            from src.plotting.shared.plot_utils import print_warning
            print_warning("Mixed illumination experiments - saving to Transconductance root folder")

    filename = f"{prefix}_gm_{tag}"
    out = config.get_output_path(
        filename,
        chip_number=chipnum,
        procedure="Transconductance",
        metadata=illumination_metadata,
        create_dirs=True
    )
    plt.savefig(out, dpi=config.dpi)
    logger.info(f"saved {out}")
    plt.close(fig)


def plot_ivg_transconductance_savgol(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    min_segment_length: int = 10,
    window_length: int = 9,
    polyorder: int = 3,
    show_raw: bool = True,
    raw_alpha: float = 0.5,
    config: Optional[PlotConfig] = None,
):
    """
    Plot transconductance (dI/dVg) using Savitzky-Golay derivative.

    Shows both raw (transparent) and filtered (solid) transconductance.

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame
    base_dir : Path
        Base directory containing measurement files
    tag : str
        Tag to append to filename
    min_segment_length : int
        Minimum points per segment (before derivative)
    window_length : int
        Sav-Gol window length (odd, >=3). Auto-adjusted if too large.
    polyorder : int
        Sav-Gol polynomial order (>=1, < window_length)
    show_raw : bool
        If True, show raw derivative as transparent background
    raw_alpha : float
        Transparency for raw derivative (0-1)
    config : PlotConfig, optional
        Plot configuration (theme, DPI, output paths, etc.)
    """
    # Initialize config with defaults
    config = config or PlotConfig()

    # Apply plot style from config
    from src.plotting.shared.styles import set_plot_style
    set_plot_style(config.theme)

    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        logger.info("no IVg measurements to plot")
        return

    fig, ax = plt.subplots(figsize=config.figsize_voltage_sweep)
    curves_plotted = 0

    # Let matplotlib handle colors (respects your color cycle configuration)
    # We'll use prop_cycle to get default colors
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']

    for meas_idx, row in enumerate(ivg.iter_rows(named=True)):
        path = base_dir / row["source_file"]
        if not path.exists():
            logger.warning(f"missing file: {path}")
            continue

        d = read_measurement_parquet(path)

        # Normalize column names (handle both formats)
        d = ensure_standard_columns(d)

        if not {"VG", "I"} <= set(d.columns):
            logger.warning(f"{path} lacks VG/I; got {d.columns}")
            continue

        vg = d["VG"].to_numpy()
        i = d["I"].to_numpy()

        segments = segment_voltage_sweep(vg, i, min_segment_length)
        if len(segments) == 0:
            logger.warning(f"{path.name}: no valid segments found")
            continue

        # Build label
        base_lbl = f"#{int(row['file_idx'])} {'light' if row.get('has_light', False) else 'dark'}"
        if bool(row.get("Laser toggle", False)):
            wl = row.get("Laser wavelength", None)
            if wl is not None and str(wl) != "nan":
                try:
                    base_lbl += f" λ={float(wl):.0f} nm"
                except (TypeError, ValueError):
                    pass

        # Lists to collect segments
        vg_raw_parts = []
        gm_raw_parts = []
        vg_filt_parts = []
        gm_filt_parts = []

        for (vg_seg, i_seg, _dir) in segments:
            if vg_seg.size < 3:
                continue

            # Calculate raw derivative
            gm_raw = _raw_derivative(vg_seg, i_seg)

            # Calculate filtered derivative (CORRECTED)
            gm_filt = _savgol_derivative_corrected(
                vg_seg, i_seg,
                window_length=window_length,
                polyorder=polyorder
            )

            if gm_filt.size == 0:
                continue

            # Add NaN separator between segments (creates gaps in plot)
            if len(vg_raw_parts) > 0:
                vg_raw_parts.append(np.array([np.nan]))
                gm_raw_parts.append(np.array([np.nan]))
                vg_filt_parts.append(np.array([np.nan]))
                gm_filt_parts.append(np.array([np.nan]))

            vg_raw_parts.append(vg_seg)
            gm_raw_parts.append(gm_raw)
            vg_filt_parts.append(vg_seg)
            gm_filt_parts.append(gm_filt)

        if not vg_raw_parts:
            continue

        # Concatenate all segments
        vg_concat = np.concatenate(vg_raw_parts)
        gm_raw_concat = np.concatenate(gm_raw_parts)
        gm_filt_concat = np.concatenate(gm_filt_parts)

        # Get color for this measurement
        color = color_cycle[meas_idx % len(color_cycle)]

        # Plot raw (transparent background) if requested
        if show_raw:
            ax.plot(
                vg_concat, gm_raw_concat * 1e6,  # µS
                linestyle=':',
                label=None  # Don't add to legend
            )

        # Plot filtered (solid foreground)
        ax.plot(
            vg_concat, gm_filt_concat * 1e6,  # µS
            label=base_lbl
        )

        curves_plotted += 1

    if curves_plotted == 0:
        logger.warning("no transconductance curves plotted")
        plt.close(fig)
        return

    ax.set_xlabel("VG (V)")
    ax.set_ylabel("Transconductance gm (µS)")

    chipnum = int(df['chip_number'][0])  # Use snake_case column name from history

    ax.legend()

    plt.tight_layout()

    # Determine illumination status for subcategory
    illumination_metadata = None
    if "has_light" in df.columns:
        has_light_values = df["has_light"].unique().to_list()
        has_light_values = [v for v in has_light_values if v is not None]

        if len(has_light_values) == 1:
            illumination_metadata = {"has_light": has_light_values[0]}
        elif len(has_light_values) > 1:
            from src.plotting.shared.plot_utils import print_warning

            print_warning("Mixed illumination experiments - saving to Transconductance root folder")

    chip_group = None
    if "chip_group" in df.columns:
        chip_group = df["chip_group"][0]
    prefix = f"{chip_group}{chipnum}" if chip_group else f"encap{chipnum}"

    filename = f"{prefix}_gm_savgol_{tag}"
    out = config.get_output_path(
        filename,
        chip_number=chipnum,
        procedure="Transconductance",
        metadata=illumination_metadata,
        create_dirs=True
    )
    plt.savefig(out, dpi=config.dpi)
    logger.info(f"saved {out}")
    plt.close(fig)
