"""
Per-chip 455 nm VVg triplet plot + photovoltage subtractions.

VVg sweeps drive a constant source-drain current (Ids = 10 uA here) and measure
the drain-source voltage V_ds vs gate voltage Vg. Under illumination V_ds shifts,
so the photoresponse is a *photovoltage* dV_ds = V_on - V_off (the voltage analog
of the IVg photocurrent I_on - I_off).

Methodology mirrors scripts/IVg Analysis/plot_ivg_365nm_triplet_compare.py
(same plot style, insets, savgol smoothing) adapted from current -> voltage.

Outputs (2 figures):

1. Per-chip OFF -> ON -> OFF triplet at 455 nm (raw V_ds vs Vg, two zoom insets).
2. Per-chip photovoltage subtractions (2)-(1), (3)-(2), (3)-(1) vs Vg, raw faded
   + savgol-smoothed bold over the forward leg, with one zoom inset.

Only chip 81 has a light VVg sweep (seq 204), bracketed by dark sweeps 203/205.

Run from the repo root:
    python "scripts/VVg Analysis/plot_vvg_455nm_triplet_compare.py"
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import yaml
from scipy.signal import savgol_filter

from src.core.utils import read_measurement_parquet
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style
from src.plotting.transconductance import auto_select_savgol_params

ENCAP_PATH = Path("config/encap_characteristics.yaml")
WAVELENGTH_NM = 455
# VVg measures voltage, so insets center on the V_ds peak (Vg ~ 0) and a
# positive-Vg point; the photovoltage dip sits near Vg ~ +0.7 V.
INSET_VG_CENTER = 0.0  # V — center of inset zoom window (V_ds peak)
INSET_VG_HALFWIDTH = 0.3  # V — half-width of Vg window in inset


@dataclass(frozen=True)
class Triplet:
    chip_number: int
    date: str
    off_before: int
    on: int
    off_after: int
    # Left inset (around the V_ds peak / negative-Vg side)
    inset_vg: float = INSET_VG_CENTER
    inset_halfwidth: float = INSET_VG_HALFWIDTH
    # (x0, y0, w, h) in axes-fraction
    inset_bbox: tuple[float, float, float, float] = (0.55, 0.55, 0.2, 0.2)
    # Right inset (positive-Vg side)
    inset2_vg: float = 2.5
    inset2_halfwidth: float = INSET_VG_HALFWIDTH
    inset2_bbox: tuple[float, float, float, float] = (0.78, 0.55, 0.2, 0.2)


# 455 nm triplets per chip (off_before, on, off_after)
TRIPLETS: list[Triplet] = [
    Triplet(
        81,
        "2025-10-29",
        203,
        204,
        205,
    ),
]


def _history_path(chip_number: int) -> Path:
    return Path(f"data/02_stage/chip_histories/Alisson{chip_number}_history.parquet")


def _load_seq(hist: pl.DataFrame, seq: int) -> pl.DataFrame:
    row = hist.filter(pl.col("seq") == seq).row(0, named=True)
    return read_measurement_parquet(row["parquet_path"])


def _triplet_available(triplet: Triplet) -> bool:
    """True if all three of the triplet's VVg seqs exist in the chip history.

    Guards against stale seq numbers after a history rebuild — a missing
    seq means this triplet is skipped (with a warning) rather than crashing.
    """
    path = _history_path(triplet.chip_number)
    if not path.exists():
        print(f"[warn] no history for Alisson{triplet.chip_number}; skipping")
        return False
    hist = pl.read_parquet(path).filter(pl.col("proc") == "VVg")
    present = set(hist["seq"].to_list())
    needed = {triplet.off_before, triplet.on, triplet.off_after}
    missing = sorted(needed - present)
    if missing:
        print(
            f"[warn] Alisson{triplet.chip_number}: VVg seqs {missing} not in "
            f"history; skipping this triplet"
        )
        return False
    return True


def _load_materials() -> dict[int, str]:
    raw = yaml.safe_load(ENCAP_PATH.read_text())
    materials: dict[int, str] = {}
    for k, v in raw.items():
        # Skip shared blocks (`geometry:`, `materials:`) — only per-chip
        # entries are keyed by an integer chip number.
        try:
            chip = int(k)
        except (TypeError, ValueError):
            continue
        if isinstance(v, dict):
            materials[chip] = v.get("material", "?")
    return materials


def _forward_sweep_slice(vg: np.ndarray) -> slice:
    """Monotonic ascending leg V_min -> V_max of the full sweep.

    The VVg sweep here is a single loop 0 -> Vmin -> Vmax -> 0; this returns the
    single-valued up-leg from Vmin through 0 to Vmax (cleanest for vs-Vg plots).
    """
    i_min = int(np.argmin(vg))
    after = vg[i_min:]
    i_max_rel = int(np.argmax(after))
    return slice(i_min, i_min + i_max_rel + 1)


def _label(chip_number: int, materials: dict[int, str]) -> str:
    mat = materials.get(chip_number, "?")
    return f"{chip_number} ({mat})"


def _y_range_in_window(
    curves: list[tuple[np.ndarray, np.ndarray]],
    vg_center: float,
    vg_half: float,
) -> tuple[float, float]:
    """Min/max of all y values whose Vg is within [center-half, center+half]."""
    vals: list[float] = []
    for vg, y in curves:
        m = (vg >= vg_center - vg_half) & (vg <= vg_center + vg_half)
        if m.any():
            vals.extend(y[m].tolist())
    if not vals:
        return 0.0, 1.0
    return float(np.min(vals)), float(np.max(vals))


def _add_zoom_inset(
    ax,
    curves: list[tuple[np.ndarray, np.ndarray, str, dict]],
    vg_center: float,
    vg_half: float,
    bbox: tuple[float, float, float, float],
    *,
    y_fmt: str = "%.2f",
) -> None:
    """Draw a zoom inset on `ax` showing `curves` within
    [vg_center - vg_half, vg_center + vg_half], placed at axes-fraction `bbox`."""
    from matplotlib.ticker import FixedLocator, FormatStrFormatter

    xy_curves = [(vg, y) for vg, y, _, _ in curves]
    y_lo, y_hi = _y_range_in_window(xy_curves, vg_center, vg_half)
    y_pad = 0.08 * (y_hi - y_lo) if y_hi > y_lo else 0.05 * abs(y_hi or 1.0)
    x_lo = vg_center - vg_half
    x_hi = vg_center + vg_half

    axins = ax.inset_axes(list(bbox))
    for vg, y, _, kw in curves:
        axins.plot(vg, y, **kw)
    axins.axvline(vg_center, color="k", linewidth=0.6, alpha=0.4, linestyle="-")
    axins.set_xlim(x_lo, x_hi)
    axins.set_ylim(y_lo - y_pad, y_hi + y_pad)

    frac = 0.20
    xa, xb = axins.get_xlim()
    ya, yb = axins.get_ylim()
    axins.xaxis.set_major_locator(
        FixedLocator([xa + frac * (xb - xa), xb - frac * (xb - xa)])
    )
    axins.yaxis.set_major_locator(
        FixedLocator([ya + frac * (yb - ya), yb - frac * (yb - ya)])
    )
    axins.xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
    axins.yaxis.set_major_formatter(FormatStrFormatter(y_fmt))
    axins.tick_params(axis="both", labelsize=39, length=4, pad=3)
    for spine in axins.spines.values():
        spine.set_linewidth(0.8)

    ax.indicate_inset_zoom(axins, edgecolor="0.4", alpha=0.6, linewidth=0.8)


def _draw_triplet_on_ax(
    ax,
    triplet: Triplet,
    materials: dict[int, str],
    *,
    show_legend: bool = True,
    show_title: bool = False,
) -> None:
    """Draw OFF -> ON -> OFF triplet (with two insets) onto a given axes."""
    hist = pl.read_parquet(_history_path(triplet.chip_number))
    hist = hist.filter(pl.col("proc") == "VVg")

    off1 = _load_seq(hist, triplet.off_before)
    on = _load_seq(hist, triplet.on)
    off2 = _load_seq(hist, triplet.off_after)

    curves: list[tuple[np.ndarray, np.ndarray, str, dict]] = [
        (
            off1["Vg (V)"].to_numpy(),
            off1["VDS (V)"].to_numpy() * 1e3,
            "(1) OFF (before)",
            {"linewidth": 3.7, "linestyle": "--"},
        ),
        (
            on["Vg (V)"].to_numpy(),
            on["VDS (V)"].to_numpy() * 1e3,
            "(2) ON",
            {"linewidth": 3.3},
        ),
        (
            off2["Vg (V)"].to_numpy(),
            off2["VDS (V)"].to_numpy() * 1e3,
            "(3) OFF (after)",
            {"linewidth": 3.7, "linestyle": ":"},
        ),
    ]

    for vg, y, label, kw in curves:
        ax.plot(vg, y, label=label, **kw)

    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{V_{ds}\\ (mV)}$")
    if show_title:
        ax.set_title(_label(triplet.chip_number, materials))
    ax.set_ylim(bottom=0)
    if show_legend:
        ax.legend(loc="best")

    _add_zoom_inset(
        ax,
        curves,
        triplet.inset_vg,
        triplet.inset_halfwidth,
        triplet.inset_bbox,
        y_fmt="%.2f",
    )
    _add_zoom_inset(
        ax,
        curves,
        triplet.inset2_vg,
        triplet.inset2_halfwidth,
        triplet.inset2_bbox,
        y_fmt="%.2f",
    )


def _draw_photovoltage_subtractions_on_ax(
    ax,
    triplet: Triplet,
    materials: dict[int, str],
    *,
    show_legend: bool = True,
    show_title: bool = False,
) -> None:
    """Draw all 3 photovoltage subtractions (2)-(1), (3)-(2), (3)-(1) onto a
    given axes, with raw faded + savgol-smoothed bold over the forward leg."""
    hist = pl.read_parquet(_history_path(triplet.chip_number))
    hist = hist.filter(pl.col("proc") == "VVg")

    off1 = _load_seq(hist, triplet.off_before)
    on = _load_seq(hist, triplet.on)
    off2 = _load_seq(hist, triplet.off_after)

    vg1 = off1["Vg (V)"].to_numpy()
    v1 = off1["VDS (V)"].to_numpy()
    vg2 = on["Vg (V)"].to_numpy()
    v2 = on["VDS (V)"].to_numpy()
    vg3 = off2["Vg (V)"].to_numpy()
    v3 = off2["VDS (V)"].to_numpy()

    n = min(len(vg1), len(vg2), len(vg3))
    if not (
        np.allclose(vg1[:n], vg2[:n], atol=1e-6)
        and np.allclose(vg2[:n], vg3[:n], atol=1e-6)
    ):
        print(
            f"[warn] Vg arrays not aligned for Alisson{triplet.chip_number}; "
            f"subtracting by sample index anyway"
        )
    vg = vg2[:n]

    subs: list[tuple[np.ndarray, str, dict]] = [
        ((v2[:n] - v1[:n]) * 1e3, "(2)-(1)", {"linewidth": 3.7, "linestyle": "-"}),
        ((v3[:n] - v2[:n]) * 1e3, "(3)-(2)", {"linewidth": 3.3, "linestyle": "--"}),
        ((v3[:n] - v1[:n]) * 1e3, "(3)-(1)", {"linewidth": 3.7, "linestyle": ":"}),
    ]

    # Plot raw faded + smoothed bold, both restricted to the forward leg.
    s = _forward_sweep_slice(vg)
    vg_fwd = vg[s]
    for v_ph, label, kw in subs:
        vph_fwd = v_ph[s]
        (line_full,) = ax.plot(
            vg_fwd,
            vph_fwd,
            linewidth=0.6,
            alpha=0.3,
            **{k: v for k, v in kw.items() if k == "linestyle"},
        )
        color = line_full.get_color()
        window, polyorder = auto_select_savgol_params(vg_fwd, vph_fwd, "auto")
        vph_smooth = np.asarray(
            savgol_filter(vph_fwd, window_length=window, polyorder=polyorder)
        )
        ax.plot(vg_fwd, vph_smooth, color=color, label=label, **kw)

    ax.axhline(0.0, color="k", linewidth=0.5, alpha=0.5)
    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{\\Delta V_{ds}\\ (mV)}$")
    if show_title:
        ax.set_title(_label(triplet.chip_number, materials))
    if show_legend:
        ax.legend(loc="lower right")


def plot_chip_triplet(
    triplet: Triplet, materials: dict[int, str], config: PlotConfig
) -> None:
    fig, ax = plt.subplots(figsize=(20, 20))
    _draw_triplet_on_ax(ax, triplet, materials)
    fig.tight_layout()

    filename = (
        f"Alisson{triplet.chip_number}_VVg_triplet_{WAVELENGTH_NM}nm_{triplet.date}"
    )
    out = config.get_output_path(
        filename,
        chip_number=triplet.chip_number,
        procedure="VVg",
        special_type="triplets",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi)
    plt.close(fig)
    print(f"saved {out}")


def plot_chip_photovoltage_subtractions(
    triplet: Triplet, materials: dict[int, str], config: PlotConfig
) -> None:
    fig, ax = plt.subplots(figsize=(20, 20))
    _draw_photovoltage_subtractions_on_ax(ax, triplet, materials)
    fig.tight_layout()

    filename = (
        f"Alisson{triplet.chip_number}_VVg_photovoltage_subs_"
        f"{WAVELENGTH_NM}nm_{triplet.date}"
    )
    out = config.get_output_path(
        filename,
        chip_number=triplet.chip_number,
        procedure="VVg",
        metadata={"has_light": True},
        special_type="photovoltage",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi)
    plt.close(fig)
    print(f"saved {out}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    materials = _load_materials()

    triplets = [t for t in TRIPLETS if _triplet_available(t)]
    if not triplets:
        print("[error] no triplets with complete VVg seqs; nothing to plot")
        return

    for t in triplets:
        plot_chip_triplet(t, materials, config)
        plot_chip_photovoltage_subtractions(t, materials, config)


if __name__ == "__main__":
    main()
