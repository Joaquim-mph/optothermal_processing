"""Generate explanatory diagrams for the It and IVg measurement procedures.

Uses real measurements (kept stylistically minimal -- annotated phases, no
numeric tick values) so the figures are pedagogical sketches grounded in
actual device behavior:

  * It  -- Alisson74, seq 28 (365 nm, Vg = -0.5 V): clean 60 s dark / 60 s
           illumination / 60 s relaxation structure.
  * IVg -- Alisson80, seq 1 (first IVg, dark, 0 -> -5 -> +5 -> -5 -> 0 V).

Outputs PDFs next to this script unless --out-dir is given.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet

CURVE_COLOR = "crimson"
SHADE_COLOR = "#c8a2d8"
SHADE_ALPHA = 0.35

REPO_ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = REPO_ROOT / "data" / "02_stage" / "chip_histories"


def _style_axes(ax: plt.Axes) -> None:
    ax.grid(True, which="major", axis="both", linewidth=0.6, alpha=0.5)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)


def _load_measurement(chip_name: str, seq: int) -> pl.DataFrame:
    history = pl.read_parquet(HISTORY_DIR / f"{chip_name}_history.parquet")
    row = history.filter(pl.col("seq") == seq).row(0, named=True)
    return read_measurement_parquet(row["parquet_path"])


def draw_it_diagram(out_path: Path, show: bool) -> None:
    """It procedure: dark baseline, illumination rise, dark relaxation."""
    data = _load_measurement("Alisson74", 28)
    t_full = data["t (s)"].to_numpy()
    i_full = data["I (A)"].to_numpy() * 1e6
    vl_full = data["VL (V)"].to_numpy()

    t_min = 20.0
    crop = t_full >= t_min
    t = t_full[crop]
    i = i_full[crop]
    vl = vl_full[crop]

    on_mask = vl > 0.1
    transitions = np.diff(on_mask.astype(int))
    t_on = float(t[np.where(transitions == 1)[0][0] + 1])
    t_off = float(t[np.where(transitions == -1)[0][0] + 1])

    i_dark = float(i[(t >= t_on - 5) & (t < t_on)].mean())
    i_light = float(i[(t >= t_off - 5) & (t < t_off)].mean())

    fig, ax = plt.subplots(figsize=(6.5, 3.2))

    ax.axvspan(t_on, t_off, color=SHADE_COLOR, alpha=SHADE_ALPHA, lw=0)
    ax.plot(t, i, color=CURVE_COLOR, lw=2.4)

    i_lo, i_hi = float(i.min()), float(i.max())
    span = i_hi - i_lo
    ax.set_xlim(t.min(), t.max())
    ax.set_ylim(i_lo - 0.1 * span, i_hi + 0.45 * span)

    ax.set_yticks(sorted([i_dark, i_light]))
    ax.set_yticklabels(
        [r"$I_{L}$", r"$I_{D}$"] if i_light < i_dark else [r"$I_{D}$", r"$I_{L}$"]
    )
    ax.set_xticks([])

    ax.set_xlabel(r"$t\,(\mathrm{s})$", fontsize=13)
    ax.set_ylabel(r"$I_{DS}\,(\mu\mathrm{A})$", fontsize=13)

    y_label = i_hi + 0.3 * span
    ax.text(
        (t.min() + t_on) / 2,
        y_label,
        r"$\mathbf{i.}$ Dark",
        ha="center",
        va="center",
        fontsize=12,
    )
    ax.text(
        (t_on + t_off) / 2,
        y_label,
        r"$\mathbf{ii.}$ Illumination",
        ha="center",
        va="center",
        fontsize=12,
    )
    ax.text(
        (t_off + t.max()) / 2,
        y_label,
        r"$\mathbf{iii.}$ Relaxation",
        ha="center",
        va="center",
        fontsize=12,
    )

    ax.axvline(t_on, color="black", lw=0.6, alpha=0.6)
    ax.axvline(t_off, color="black", lw=0.6, alpha=0.6)

    _style_axes(ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)


def draw_ivg_diagram(out_path: Path, show: bool) -> None:
    """IVg procedure: V_G(t) sweep on top, I_DS vs V_G transfer below."""
    data = _load_measurement("Alisson81", 1)
    vg = data["Vg (V)"].to_numpy()
    i = data["I (A)"].to_numpy() * 1e6
    sample_idx = np.arange(vg.size)

    v_start = float(data["vg_start_v"][0])
    v_end = float(data["vg_end_v"][0])

    fig, axes = plt.subplots(2, 1, figsize=(5.5, 6.0))
    ax_top, ax_bot = axes

    ax_top.plot(sample_idx, vg, color=CURVE_COLOR, lw=2.4)
    x_pad = 0.03 * (sample_idx[-1] - sample_idx[0])
    ax_top.set_xlim(sample_idx[0] - x_pad, sample_idx[-1] + x_pad)
    pad = 0.08 * (v_end - v_start)
    ax_top.set_ylim(v_start - pad, v_end + pad)
    ax_top.set_yticks([v_start, 0, v_end])
    ax_top.set_yticklabels([r"$V_{\mathrm{start}}$", "0", r"$V_{\mathrm{end}}$"])
    ax_top.set_xticks([])
    ax_top.set_xlabel(r"$t\,(\mathrm{s})$", fontsize=13)
    ax_top.set_ylabel(r"$V_{G}\,(\mathrm{V})$", fontsize=13)
    _style_axes(ax_top)
    ax_top.grid(False)
    for v in (v_start, v_end):
        ax_top.axhline(v, color="gray", lw=0.6, alpha=0.5, zorder=0)

    ax_bot.plot(vg, i, color=CURVE_COLOR, lw=2.4)
    ax_bot.set_xlim(v_start - 0.5, v_end + 0.5)
    ax_bot.set_xticks([v_start, 0, v_end])
    ax_bot.set_xticklabels([r"$V_{\mathrm{start}}$", "0", r"$V_{\mathrm{end}}$"])
    ax_bot.set_yticks([])
    ax_bot.set_xlabel(r"$V_{G}\,(\mathrm{V})$", fontsize=13)
    ax_bot.set_ylabel(r"$I_{DS}\,(\mu\mathrm{A})$", fontsize=13)
    _style_axes(ax_bot)
    ax_bot.grid(False)
    for v in (v_start, v_end):
        ax_bot.axvline(v, color="gray", lw=0.6, alpha=0.5, zorder=0)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent,
        help="Directory to write PDFs into (default: script directory)",
    )
    parser.add_argument(
        "--show", action="store_true", help="Display windows interactively"
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    draw_it_diagram(args.out_dir / "it_procedure.pdf", args.show)
    draw_ivg_diagram(args.out_dir / "ivg_procedure.pdf", args.show)


if __name__ == "__main__":
    main()
