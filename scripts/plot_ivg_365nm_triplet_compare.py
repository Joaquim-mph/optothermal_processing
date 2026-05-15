"""
Per-chip 365 nm IVg triplet plots + cross-chip photocurrent comparison.

Outputs (4 figures total):

1-3. One figure per chip showing the OFF -> ON -> OFF triplet at 365 nm
     (raw I_ds vs Vg).
4.   Overlay of photocurrent (I_on - I_off) vs Vg at 365 nm for all 3 chips,
     one trace per chip, labelled by material from
     config/encap_characteristics.yaml.

Run from the repo root:
    python scripts/plot_ivg_365nm_triplet_compare.py
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
WAVELENGTH_NM = 365
INSET_VG_CENTER = -2.6  # V — center of inset zoom window
INSET_VG_HALFWIDTH = 0.1  # V — half-width of Vg window in inset


@dataclass(frozen=True)
class Triplet:
    chip_number: int
    date: str
    off_before: int
    on: int
    off_after: int
    # Left inset (around CNP / negative-Vg side)
    inset_vg: float = INSET_VG_CENTER
    inset_halfwidth: float = INSET_VG_HALFWIDTH
    # (x0, y0, w, h) in axes-fraction
    inset_bbox: tuple[float, float, float, float] = (0.55, 0.08, 0.2, 0.2)  # (x,y,w,h)
    # Right inset (positive-Vg side, default ~2.5 V, bottom-right)
    inset2_vg: float = 2.5
    inset2_halfwidth: float = INSET_VG_HALFWIDTH
    inset2_bbox: tuple[float, float, float, float] = (0.78, 0.08, 0.2, 0.2)


# 365 nm triplets per chip (off_before, on, off_after)
TRIPLETS: list[Triplet] = [
    Triplet(
        74,
        "2026-04-21",
        56,
        57,
        58,
        inset_vg=-3.6,
        # (x0, y0, w, h) in axes-fraction
        inset_bbox=(0.08, 0.25, 0.2, 0.2),  # upper-middle
        inset2_vg=2.5,
        inset2_bbox=(0.75, 0.28, 0.2, 0.2),  # bottom-right
    ),
    Triplet(
        72,
        "2026-04-28",
        88,
        89,
        90,
        inset_vg=-1.5,
        # (x0, y0, w, h) in axes-fraction
        inset_bbox=(0.12, 0.25, 0.2, 0.2),  # bottom-left
        inset2_vg=2.25,
        inset2_bbox=(0.7, 0.25, 0.2, 0.2),  # bottom-right
    ),
    Triplet(
        80,
        "2026-05-04",
        122,
        123,
        124,
        # (x0, y0, w, h) in axes-fraction
        inset_bbox=(0.12, 0.25, 0.2, 0.2),  # upper-right
        inset2_vg=2.25,
        inset2_bbox=(0.7, 0.25, 0.2, 0.2),  # bottom-right
    ),
]


def _history_path(chip_number: int) -> Path:
    return Path(f"data/02_stage/chip_histories/Alisson{chip_number}_history.parquet")


def _load_seq(hist: pl.DataFrame, seq: int) -> pl.DataFrame:
    row = hist.filter(pl.col("seq") == seq).row(0, named=True)
    return read_measurement_parquet(row["parquet_path"])


def _triplet_available(triplet: Triplet) -> bool:
    """True if all three of the triplet's IVg seqs exist in the chip history.

    Guards against stale seq numbers after a history rebuild — a missing
    seq means this triplet is skipped (with a warning) rather than crashing.
    """
    path = _history_path(triplet.chip_number)
    if not path.exists():
        print(f"[warn] no history for Alisson{triplet.chip_number}; skipping")
        return False
    hist = pl.read_parquet(path).filter(pl.col("proc") == "IVg")
    present = set(hist["seq"].to_list())
    needed = {triplet.off_before, triplet.on, triplet.off_after}
    missing = sorted(needed - present)
    if missing:
        print(
            f"[warn] Alisson{triplet.chip_number}: IVg seqs {missing} not in "
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


def _first_half_sweep(vg: np.ndarray) -> slice:
    """0 -> Vgmin -> 0 -> Vgmax -> 0 (first half of full IVg sweep)."""
    i_max = int(np.argmax(vg))
    tail = vg[i_max:]
    below = np.where(tail <= 0.0)[0]
    end = i_max + int(below[0]) if below.size else len(vg) - 1
    return slice(0, end + 1)


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
    y_fmt: str = "%.0f",
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
    """Draw OFF -> ON -> OFF triplet (with inset) onto a given axes."""
    hist = pl.read_parquet(_history_path(triplet.chip_number))
    hist = hist.filter(pl.col("proc") == "IVg")

    off1 = _load_seq(hist, triplet.off_before)
    on = _load_seq(hist, triplet.on)
    off2 = _load_seq(hist, triplet.off_after)

    curves: list[tuple[np.ndarray, np.ndarray, str, dict]] = [
        (
            off1["Vg (V)"].to_numpy(),
            off1["I (A)"].to_numpy() * 1e6,
            "(1) OFF (before)",
            {"linewidth": 3.7, "linestyle": "--"},
        ),
        (
            on["Vg (V)"].to_numpy(),
            on["I (A)"].to_numpy() * 1e6,
            "(2) ON",
            {"linewidth": 3.3},
        ),
        (
            off2["Vg (V)"].to_numpy(),
            off2["I (A)"].to_numpy() * 1e6,
            "(3) OFF (after)",
            {"linewidth": 3.7, "linestyle": ":"},
        ),
    ]

    for vg, y, label, kw in curves:
        ax.plot(vg, y, label=label, **kw)

    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
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
        y_fmt="%.0f",
    )
    _add_zoom_inset(
        ax,
        curves,
        triplet.inset2_vg,
        triplet.inset2_halfwidth,
        triplet.inset2_bbox,
        y_fmt="%.0f",
    )


def _draw_photocurrent_subtractions_on_ax(
    ax,
    triplet: Triplet,
    materials: dict[int, str],
    *,
    show_legend: bool = True,
    show_title: bool = False,
    show_inset: bool = False,
) -> None:
    """Draw all 3 photocurrent subtractions (2)-(1), (2)-(3), (3)-(1) onto a
    given axes, with smoothed forward sweep + a zoom inset."""
    hist = pl.read_parquet(_history_path(triplet.chip_number))
    hist = hist.filter(pl.col("proc") == "IVg")

    off1 = _load_seq(hist, triplet.off_before)
    on = _load_seq(hist, triplet.on)
    off2 = _load_seq(hist, triplet.off_after)

    vg1 = off1["Vg (V)"].to_numpy()
    i1 = off1["I (A)"].to_numpy()
    vg2 = on["Vg (V)"].to_numpy()
    i2 = on["I (A)"].to_numpy()
    vg3 = off2["Vg (V)"].to_numpy()
    i3 = off2["I (A)"].to_numpy()

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
        ((i2[:n] - i1[:n]) * 1e6, "(2)-(1)", {"linewidth": 3.7, "linestyle": "-"}),
        ((i3[:n] - i2[:n]) * 1e6, "(3)-(2)", {"linewidth": 3.3, "linestyle": "--"}),
        ((i3[:n] - i1[:n]) * 1e6, "(3)-(1)", {"linewidth": 3.7, "linestyle": ":"}),
    ]

    # Plot raw faded + smoothed bold, both restricted to the first-half sweep.
    s = _first_half_sweep(vg)
    vg_half = vg[s]
    smoothed_curves: list[tuple[np.ndarray, np.ndarray, str, dict]] = []
    for i_ph, label, kw in subs:
        iph_half = i_ph[s]
        (line_full,) = ax.plot(
            vg_half,
            iph_half,
            linewidth=0.6,
            alpha=0.3,
            **{k: v for k, v in kw.items() if k == "linestyle"},
        )
        color = line_full.get_color()
        window, polyorder = auto_select_savgol_params(vg_half, iph_half, "auto")
        iph_smooth = np.asarray(
            savgol_filter(iph_half, window_length=window, polyorder=polyorder)
        )
        ax.plot(vg_half, iph_smooth, color=color, label=label, **kw)
        smoothed_curves.append((vg_half, iph_smooth, label, {**kw, "color": color}))

    ax.axhline(0.0, color="k", linewidth=0.5, alpha=0.5)
    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{I_{ph}\\ (\\mu A)}$")
    if show_title:
        ax.set_title(_label(triplet.chip_number, materials))
    if show_legend:
        ax.legend(loc="lower right")

    if not show_inset:
        return

    # Inset: zoom around triplet.inset_vg using the smoothed curves.
    vg_center = triplet.inset_vg
    xy_curves = [(v, y) for v, y, _, _ in smoothed_curves]
    y_lo, y_hi = _y_range_in_window(xy_curves, vg_center, INSET_VG_HALFWIDTH)
    y_pad = 0.08 * (y_hi - y_lo) if y_hi > y_lo else 0.05 * abs(y_hi or 1.0)
    x_lo = vg_center - INSET_VG_HALFWIDTH
    x_hi = vg_center + INSET_VG_HALFWIDTH

    axins = ax.inset_axes(list(triplet.inset_bbox))
    for v, y, _, kw in smoothed_curves:
        axins.plot(v, y, **kw)
    axins.axvline(vg_center, color="k", linewidth=0.6, alpha=0.4, linestyle="-")
    axins.set_xlim(x_lo, x_hi)
    axins.set_ylim(y_lo - y_pad, y_hi + y_pad)

    from matplotlib.ticker import FixedLocator, FormatStrFormatter

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
    axins.yaxis.set_major_formatter(FormatStrFormatter("%.1f"))
    axins.tick_params(axis="both", labelsize=39, length=4, pad=3)
    for spine in axins.spines.values():
        spine.set_linewidth(0.8)

    ax.indicate_inset_zoom(axins, edgecolor="0.4", alpha=0.6, linewidth=0.8)


def plot_chip_photocurrent_subtractions(
    triplet: Triplet, materials: dict[int, str], config: PlotConfig
) -> None:
    fig, ax = plt.subplots(figsize=(20, 20))
    _draw_photocurrent_subtractions_on_ax(ax, triplet, materials)
    fig.tight_layout()

    filename = (
        f"Alisson{triplet.chip_number}_IVg_photocurrent_subs_"
        f"{WAVELENGTH_NM}nm_{triplet.date}"
    )
    out = config.get_output_path(
        filename,
        chip_number=triplet.chip_number,
        procedure="IVg",
        metadata={"has_light": True},
        special_type="photocurrent",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi)
    plt.close(fig)
    print(f"saved {out}")


def plot_chip_triplet(
    triplet: Triplet, materials: dict[int, str], config: PlotConfig
) -> None:
    fig, ax = plt.subplots(figsize=(20, 20))
    _draw_triplet_on_ax(ax, triplet, materials)
    fig.tight_layout()

    filename = (
        f"Alisson{triplet.chip_number}_IVg_triplet_{WAVELENGTH_NM}nm_{triplet.date}"
    )
    out = config.get_output_path(
        filename,
        chip_number=triplet.chip_number,
        procedure="IVg",
        special_type="triplets",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi)
    plt.close(fig)
    print(f"saved {out}")


def plot_photocurrent_overlay(
    triplets: list[Triplet], materials: dict[int, str], config: PlotConfig
) -> None:
    fig, ax = plt.subplots(figsize=(20, 20))

    for t in triplets:
        hist = pl.read_parquet(_history_path(t.chip_number))
        hist = hist.filter(pl.col("proc") == "IVg")

        off = _load_seq(hist, t.off_before)
        on = _load_seq(hist, t.on)

        vg_off = off["Vg (V)"].to_numpy()
        i_off = off["I (A)"].to_numpy()
        vg_on = on["Vg (V)"].to_numpy()
        i_on = on["I (A)"].to_numpy()

        n = min(len(vg_off), len(vg_on))
        if not np.allclose(vg_off[:n], vg_on[:n], atol=1e-6):
            print(
                f"[warn] Vg arrays not aligned for Alisson{t.chip_number}; "
                f"subtracting by sample index anyway"
            )

        vg = vg_on[:n]
        i_photo = (i_on[:n] - i_off[:n]) * 1e6  # µA

        s = _first_half_sweep(vg)
        vg_half = vg[s]
        iph_half = i_photo[s]

        (line_full,) = ax.plot(vg_half, iph_half, linewidth=0.6, alpha=0.3)
        color = line_full.get_color()

        window, polyorder = auto_select_savgol_params(vg_half, iph_half, "auto")
        iph_smooth = np.asarray(
            savgol_filter(iph_half, window_length=window, polyorder=polyorder)
        )
        ax.plot(
            vg_half,
            iph_smooth,
            color=color,
            label=_label(t.chip_number, materials),
            linewidth=3.7,
        )

    ax.axhline(0.0, color="k", linewidth=0.5, alpha=0.5)
    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{I_{ph} = I_{(2)} - I_{(1)}\\ (\\mu A)}$")
    ax.legend(title="Chip (material)", loc="lower right")
    fig.tight_layout()

    filename = f"Compare_IVg_photocurrent_{WAVELENGTH_NM}nm"
    out = config.get_output_path(
        filename,
        procedure="IVg",
        metadata={"has_light": True},
        special_type="photocurrent",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi)
    plt.close(fig)
    print(f"saved {out}")


def plot_triplets_grid_1x3(
    triplets: list[Triplet], materials: dict[int, str], config: PlotConfig
) -> None:
    """1x3 grid (one column per chip), each panel matching the standalone
    triplet plots in size and inset content."""
    n = len(triplets)
    fig, axes = plt.subplots(1, n, figsize=(20 * n, 20))

    for ax, t in zip(axes, triplets):
        _draw_triplet_on_ax(ax, t, materials, show_legend=True, show_title=False)

    fig.tight_layout()

    filename = f"Compare_IVg_triplets_grid_{WAVELENGTH_NM}nm_1x{n}"
    out = config.get_output_path(
        filename,
        procedure="IVg",
        special_type="triplets",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi)
    plt.close(fig)
    print(f"saved {out}")


def plot_74_72_triplet_photocurrent_2x2(
    triplets: list[Triplet], materials: dict[int, str], config: PlotConfig
) -> None:
    """2x2 grid for chips 74 and 72: triplet plots (with insets) on the top
    row, the respective photocurrent subtractions on the bottom row."""
    by_chip = {t.chip_number: t for t in triplets}
    chips = [74, 72]
    missing = [c for c in chips if c not in by_chip]
    if missing:
        print(f"[warn] no triplet configured for chips {missing}; skipping 2x2 grid")
        return

    fig, axes = plt.subplots(2, 2, figsize=(40, 40))

    for col, chip in enumerate(chips):
        t = by_chip[chip]
        _draw_triplet_on_ax(
            axes[0, col], t, materials, show_legend=True, show_title=False
        )
        _draw_photocurrent_subtractions_on_ax(
            axes[1, col], t, materials, show_legend=True, show_title=False
        )

    fig.tight_layout()

    filename = f"Compare_IVg_triplet_photocurrent_2x2_7472_{WAVELENGTH_NM}nm"
    out = config.get_output_path(
        filename,
        procedure="IVg",
        special_type="triplets",
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
        print("[error] no triplets with complete IVg seqs; nothing to plot")
        return

    for t in triplets:
        plot_chip_triplet(t, materials, config)
        plot_chip_photocurrent_subtractions(t, materials, config)

    plot_photocurrent_overlay(triplets, materials, config)
    plot_triplets_grid_1x3(triplets, materials, config)
    plot_74_72_triplet_photocurrent_2x2(triplets, materials, config)


if __name__ == "__main__":
    main()
