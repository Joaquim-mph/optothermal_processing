"""Chip-80 dark transfer-curve comparison: 2026-04-28 vs 2026-07-01.

Documents the ~2 V left-shift of the transfer curve between the two
responsivity sessions and shows that the fixed-bias operating points used for
the It measurements (Vg = 0 V in April, Vg = -2 V in July) both sit at the
peak-transconductance point of their respective curves.

Outputs (in figs/drift_unified_67_72_74_75_80_81/):
  - combined 1x2 panel: I(Vg) | gm(Vg)
  - standalone I(Vg) figure
  - standalone gm(Vg) figure

Vertical dotted markers + dots flag the operating point used in each session.

Run from repo root:
    .venv/bin/python "scripts/spectral plots/plot_chip80_transfer_shift_apr_jul.py"
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes

from src.core.utils import read_measurement_parquet
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

OUTPUT_DIR = Path("figs/drift_unified_67_72_74_75_80_81")

# Same colour convention as the old-vs-new responsivity figure: April = "old"
# (C3), July = "new" (C2).
SESSIONS = [
    {
        "tag": "Apr",
        "label": r"Old",
        "op_vg": 0.0,
        "color": "C3",
        "path": "data/02_stage/raw_measurements/proc=IVg/date=2026-04-28/"
        "run_id=d1e762d30df2b0e4/part-000.parquet",
    },
    {
        "tag": "Jul",
        "label": r"New",
        "op_vg": -2.0,
        "color": "C2",
        "path": "data/02_stage/raw_measurements/proc=IVg/date=2026-07-01/"
        "run_id=fd6cd72def7d9c5d/part-000.parquet",
    },
]

LEGEND_FONTSIZE_BUMP = 2.0


def _legend_fontsize(relative: str = "small") -> float:
    from matplotlib.font_manager import font_scalings
    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


def forward_branch(vg: np.ndarray, i: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return the longer monotonic branch of a dual-direction sweep, sorted by
    Vg with duplicate gate voltages collapsed (mean current)."""
    turn = int(np.argmax(vg)) if vg[0] < vg[-1] else int(np.argmin(vg))
    a = np.arange(0, turn + 1)
    b = np.arange(turn, len(vg))
    idx = a if len(a) >= len(b) else b
    vg, i = vg[idx], i[idx]
    order = np.argsort(vg)
    vg, i = vg[order], i[order]
    uvg, inv = np.unique(np.round(vg, 3), return_inverse=True)
    ui = np.array([i[inv == k].mean() for k in range(len(uvg))])
    return uvg, ui


def load_sessions() -> list[dict]:
    """Load each session's forward-branch Vg, I (uA) and gm (uS)."""
    out = []
    for s in SESSIONS:
        m = read_measurement_parquet(Path(s["path"]))
        vg = m["Vg (V)"].to_numpy().astype(float)
        i = m["I (A)"].to_numpy().astype(float)
        vg, i = forward_branch(vg, i)
        out.append({
            **s,
            "vg": vg,
            "i_uA": i * 1e6,
            "gm_uS": np.gradient(i, vg) * 1e6,
        })
    return out


def _op_index(vg: np.ndarray, op_vg: float) -> int:
    return int(np.argmin(np.abs(vg - op_vg)))


def _cnp(d: dict) -> float:
    """Charge-neutrality point: Vg of minimum current on the forward branch."""
    return float(d["vg"][int(np.argmin(d["i_uA"]))])


def draw_current_cnp_aligned(ax: Axes, data: list[dict], *, legend: bool = True) -> None:
    """I(Vg) for both sessions with each curve shifted so its CNP sits at 0 V,
    i.e. the gate-voltage shift between sessions is removed. Dots mark each
    session's operating point in the CNP-referenced frame."""
    for d in data:
        cnp = _cnp(d)
        vg_rel = d["vg"] - cnp
        offset = d["op_vg"] - cnp
        sign = "-" if offset < 0 else "+"
        ax.plot(vg_rel, d["i_uA"], color=d["color"], linestyle="-",
                label=f"{d['label']} "
                      f"($V_g = \\mathrm{{CNP}} {sign} {abs(offset):.1f}$ V)")
        j = _op_index(d["vg"], d["op_vg"])
        ax.plot([vg_rel[j]], [d["i_uA"][j]], color=d["color"], marker="o",
                markersize=8, markeredgecolor="k", zorder=5)
    ax.axvline(0.0, color="0.5", linestyle=":", alpha=0.6, lw=1.2)
    ax.set_xlabel(r"$V_g - V_\mathrm{CNP}$ (V)")
    ax.set_ylabel(r"$I$ ($\mu$A)")
    ax.set_box_aspect(1.0)
    if legend:
        ax.legend(loc="best", framealpha=0.9, fontsize=_legend_fontsize())


def draw_current(ax: Axes, data: list[dict], *, legend: bool = True) -> None:
    for d in data:
        ax.plot(d["vg"], d["i_uA"], color=d["color"], linestyle="-",
                label=f"{d['label']} ($V_g={d['op_vg']:g}$ V)")
        j = _op_index(d["vg"], d["op_vg"])
        ax.plot([d["vg"][j]], [d["i_uA"][j]], color=d["color"], marker="o",
                markersize=8, markeredgecolor="k", zorder=5)
        ax.axvline(d["op_vg"], color=d["color"], linestyle=":", alpha=0.6, lw=1.2)
    ax.set_xlabel(r"$V_g$ (V)")
    ax.set_ylabel(r"$I$ ($\mu$A)")
    ax.set_box_aspect(1.0)
    if legend:
        ax.legend(loc="best", framealpha=0.9, fontsize=_legend_fontsize())


def draw_gm(ax: Axes, data: list[dict], *, legend: bool = True) -> None:
    for d in data:
        ax.plot(d["vg"], d["gm_uS"], color=d["color"], linestyle="-",
                label=f"{d['label']} ($V_g={d['op_vg']:g}$ V)")
        j = _op_index(d["vg"], d["op_vg"])
        ax.plot([d["vg"][j]], [d["gm_uS"][j]], color=d["color"], marker="o",
                markersize=8, markeredgecolor="k", zorder=5)
        ax.axvline(d["op_vg"], color=d["color"], linestyle=":", alpha=0.6, lw=1.2)
    ax.set_xlabel(r"$V_g$ (V)")
    ax.set_ylabel(r"$g_m = \mathrm{d}I/\mathrm{d}V_g$ ($\mu$S)")
    ax.set_box_aspect(1.0)
    if legend:
        ax.legend(loc="best", framealpha=0.9, fontsize=_legend_fontsize())


def save(fig, names: tuple[str, ...], config: PlotConfig) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        out = OUTPUT_DIR / name
        fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
        print(f"saved {out}")
    plt.close(fig)


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    data = load_sessions()

    # Combined 1x2: current | transconductance.
    fig, (ax_i, ax_gm) = plt.subplots(1, 2, figsize=(2 * side, side))
    draw_current(ax_i, data)
    draw_gm(ax_gm, data)
    fig.tight_layout()
    save(fig, (
        "alisson80_transfer_shift_apr_vs_jul_2026-07-01.pdf",
        "alisson80_transfer_shift_apr_vs_jul_2026-07-01.png",
    ), config)

    # Standalone current figure.
    fig, ax = plt.subplots(1, 1, figsize=(side, side))
    draw_current(ax, data)
    fig.tight_layout()
    save(fig, (
        "alisson80_transfer_current_apr_vs_jul_2026-07-01.pdf",
        "alisson80_transfer_current_apr_vs_jul_2026-07-01.png",
    ), config)

    # Standalone transconductance figure.
    fig, ax = plt.subplots(1, 1, figsize=(side, side))
    draw_gm(ax, data)
    fig.tight_layout()
    save(fig, (
        "alisson80_transfer_gm_apr_vs_jul_2026-07-01.pdf",
        "alisson80_transfer_gm_apr_vs_jul_2026-07-01.png",
    ), config)

    # CNP-aligned current figure: both curves shifted so CNP -> 0 V, removing
    # the gate-voltage shift so the intrinsic transfer shapes can be compared.
    fig, ax = plt.subplots(1, 1, figsize=(side, side))
    draw_current_cnp_aligned(ax, data)
    fig.tight_layout()
    save(fig, (
        "alisson80_transfer_cnp_aligned_apr_vs_jul_2026-07-01.pdf",
        "alisson80_transfer_cnp_aligned_apr_vs_jul_2026-07-01.png",
    ), config)


if __name__ == "__main__":
    main()
