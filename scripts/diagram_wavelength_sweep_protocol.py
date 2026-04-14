"""
Diagram explaining the wavelength-sweep measurement protocol used on
Alisson72 and Alisson81 (same-power wavelength sweep).

Produces one PNG under figs/compare/:
  * wavelength_sweep_protocol.png

Upper panel: one real It trace (chip 72, seq=11, 850 nm) annotated with
the 60 s dark / 60 s light / 60 s relaxation structure.
Lower panel: the 10 wavelengths swept per chip, in the order they were
measured, colored by wavelength. The per-wavelength laser drive voltage
(V_L) is shown under each bar; these values come from the laser
calibration and are chosen so that the irradiated optical power is the
same at every wavelength.

Run from the repo root:
    python scripts/diagram_wavelength_sweep_protocol.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.plotting.config import PlotConfig
from src.plotting.plot_utils import ensure_standard_columns
from src.plotting.styles import set_plot_style

HISTORY_DIR = Path("data/03_derived/chip_histories_enriched")
OUTPUT_PATH = Path("figs/compare/wavelength_sweep_protocol.png")

REFERENCE_CHIP = 81
REFERENCE_SEQ = 33

SWEEP_ORDER = [850, 680, 625, 590, 565, 505, 455, 405, 385, 365]


def load_reference_trace() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    history = pl.read_parquet(HISTORY_DIR / f"Alisson{REFERENCE_CHIP}_history.parquet")
    row = history.filter(pl.col("seq") == REFERENCE_SEQ).row(0, named=True)
    m = ensure_standard_columns(read_measurement_parquet(Path(row["parquet_path"])))
    return (
        m["t"].to_numpy(),
        m["I"].to_numpy() * 1e6,
        m["VL"].to_numpy(),
        row,
    )


def load_sweep_laser_voltages(chip_number: int, seqs: list[int]) -> dict[float, float]:
    history = pl.read_parquet(HISTORY_DIR / f"Alisson{chip_number}_history.parquet")
    sub = history.filter(pl.col("seq").is_in(seqs)).select(
        ["wavelength_nm", "laser_voltage_v"]
    )
    return {float(w): float(v) for w, v in sub.iter_rows()}


def wavelength_to_color(wavelength_nm: float) -> tuple[float, float, float]:
    cmap = plt.get_cmap("turbo_r")
    lo, hi = 360.0, 870.0
    x = (wavelength_nm - lo) / (hi - lo)
    return cmap(float(np.clip(x, 0.0, 1.0)))[:3]


def draw_protocol_panel(ax, t: np.ndarray, i_uA: np.ndarray, vl: np.ndarray, meta: dict) -> None:
    on_mask = vl > 0.1
    transitions = np.where(np.diff(on_mask.astype(int)) != 0)[0]
    t_on = float(t[transitions[0] + 1])
    t_off = float(t[transitions[1] + 1])

    ax.axvspan(t_on, t_off, color="#ffd966", alpha=0.35, zorder=0, label="Laser ON")
    ax.plot(t, i_uA, color="#1f77b4", linewidth=1.4)

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Drain current $I_d$ (µA)")

    y_top = float(i_uA.max())
    y_bot = float(i_uA.min())
    y_span = y_top - y_bot
    text_y = y_top + 0.08 * y_span
    ax.set_ylim(y_bot - 0.05 * y_span, y_top + 0.22 * y_span)

    label_style = dict(ha="center", va="center", fontsize=9)
    ax.text((0 + t_on) / 2, text_y, "dark baseline\n60 s", **label_style)
    ax.text((t_on + t_off) / 2, text_y, f"laser ON\n60 s @ λ (V$_L$ per λ)", **label_style)
    ax.text((t_off + t[-1]) / 2, text_y, "relaxation\n60 s", **label_style)

    ax.set_xlim(t[0], t[-1])

    info = (
        f"chip {REFERENCE_CHIP}, seq {REFERENCE_SEQ}, λ = {meta['wavelength_nm']:.0f} nm\n"
        f"$V_{{ds}}$ = {meta['vds_v']:.2f} V, $V_g$ = {meta['vg_fixed_v']:.2f} V, "
        f"$V_L$ = {meta['laser_voltage_v']:.2f} V"
    )
    ax.text(
        0.02, 0.04, info, transform=ax.transAxes,
        fontsize=8, va="bottom", ha="left",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#999", alpha=0.85),
    )

    ax.legend(loc="upper right", framealpha=0.9, fontsize=8)


def draw_sequence_panel(ax, laser_v_72: dict[float, float], laser_v_81: dict[float, float]) -> None:
    n = len(SWEEP_ORDER)
    x = np.arange(n)
    width = 0.8

    for idx, wl in enumerate(SWEEP_ORDER):
        color = wavelength_to_color(wl)
        ax.bar(idx, 1.0, width=width, color=color, edgecolor="#333", linewidth=0.6)
        ax.text(
            idx, 0.5, f"{wl:.0f} nm",
            ha="center", va="center", fontsize=8, fontweight="bold",
            color="white" if wl < 520 or wl > 700 else "black",
        )
        v72 = laser_v_72.get(float(wl))
        v81 = laser_v_81.get(float(wl))
        v_text = []
        if v72 is not None:
            v_text.append(f"72: {v72:.2f}")
        if v81 is not None:
            v_text.append(f"81: {v81:.2f}")
        ax.text(
            idx, -0.18, "\n".join(v_text),
            ha="center", va="top", fontsize=7, color="#333",
        )

    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(-0.6, 1.15)
    ax.set_yticks([])
    ax.set_xticks([])
    for spine in ("top", "right", "left", "bottom"):
        ax.spines[spine].set_visible(False)

    ax.annotate(
        "", xy=(n - 0.7, 1.08), xytext=(-0.3, 1.08),
        arrowprops=dict(arrowstyle="->", color="#666", lw=1),
    )
    ax.text((n - 1) / 2, 1.12, "measurement order (time →)",
            ha="center", va="bottom", fontsize=8, color="#444")
    ax.text(
        (n - 1) / 2, -0.5,
        "V$_L$ per wavelength (V) — set from laser calibration to hold irradiated power constant",
        ha="center", va="top", fontsize=7.5, color="#444",
    )


def main() -> None:
    config = PlotConfig()
    set_plot_style("minimal")

    t, i_uA, vl, meta = load_reference_trace()
    laser_v_72 = load_sweep_laser_voltages(72, [11, 16, 20, 24, 26, 28, 30, 32, 34, 36])
    laser_v_81 = load_sweep_laser_voltages(81, [4, 6, 8, 10, 12, 14, 16, 18, 33, 35])

    fig = plt.figure(figsize=(9.5, 6.5))
    gs = fig.add_gridspec(2, 1, height_ratios=[2.2, 1.0], hspace=0.45)

    ax_trace = fig.add_subplot(gs[0])
    ax_seq = fig.add_subplot(gs[1])

    draw_protocol_panel(ax_trace, t, i_uA, vl, meta)
    draw_sequence_panel(ax_seq, laser_v_72, laser_v_81)

    ax_trace.set_title("One wavelength measurement (It, 3 min)", fontsize=11, pad=8)
    ax_seq.set_title("Wavelength sweep (same protocol repeated 10×)", fontsize=11, pad=8)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
