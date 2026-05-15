"""
Step-time ladder on Alisson68 (2026-05-12, dark).

Three IVgs at three step_time_s settings.

    seq 71  step=1.0  s  18:09
    seq 73  step=0.5  s  18:21
    seq 74  step=0.01 s  18:27   (fast)

(In the manifest step_time_s = 0 actually means the instrument floor, 0.01 s.)
(seq 72 was a degraded sweep at 18:20 — ~½ the µ of neighbours — and was skipped.)

All four: Vg in [-5,5] V, 0.05 V step, Vds=0.1 V, dark.

Outputs (figs/Encap68/IVg/step_time_ladder/):
    Alisson68_step_time_ladder_2026-05-12_I.png
    Alisson68_step_time_ladder_2026-05-12_gm.png

Run from repo root:
    python "scripts/IVg Analysis/step_time_ladder_alisson68_2026-05-12.py"
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.cnp_parabola import split_full_range_legs
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.plot_utils import (
    _savgol_derivative_corrected,
    ensure_standard_columns,
)
from src.plotting.shared.styles import set_plot_style
from src.plotting.transconductance import auto_select_savgol_params

HISTORY_PATH = Path("data/03_derived/chip_histories_enriched/Alisson68_history.parquet")
MANIFEST_PATH = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
OUTPUT_DIR = Path("figs/Encap68/IVg/step_time_ladder")
OUTPUT_PATH_I = OUTPUT_DIR / "Alisson68_step_time_ladder_2026-05-12_I.png"
OUTPUT_PATH_GM = OUTPUT_DIR / "Alisson68_step_time_ladder_2026-05-12_gm.png"
DATE_LOCAL = "2026-05-12"

# step_time_s = 0 in the manifest is the instrument floor (0.01 s).
# Trimmed magma ramp so step time increases from purple to orange
# without hitting the very-dark or very-light ends of the colormap.
_CMAP = mpl.colormaps["magma"]
_SAMPLES = np.linspace(0.15, 0.85, 3)
SELECTION = [
    {"seq": 74, "step_s": 0.01, "label": "step = 0.01 s", "color": _CMAP(_SAMPLES[0]), "linestyle": "-"},
    {"seq": 73, "step_s": 0.5,  "label": "step = 0.5 s",  "color": _CMAP(_SAMPLES[1]), "linestyle": "-"},
    {"seq": 71, "step_s": 1.0,  "label": "step = 1.0 s",  "color": _CMAP(_SAMPLES[2]), "linestyle": "-"},
]


def _load_ivg(seq: int) -> tuple[np.ndarray, np.ndarray, dict]:
    history = pl.read_parquet(HISTORY_PATH)
    manifest = pl.read_parquet(MANIFEST_PATH).select(["run_id", "step_time_s"])
    row = (
        history.filter(
            (pl.col("proc") == "IVg")
            & (pl.col("date_local") == DATE_LOCAL)
            & (pl.col("seq") == seq)
        )
        .join(manifest, on="run_id", how="left")
    )
    if row.height != 1:
        raise ValueError(f"seq {seq}: expected 1 row, got {row.height}")
    rec = row.row(0, named=True)

    measurement = ensure_standard_columns(read_measurement_parquet(Path(rec["parquet_path"])))
    if not {"VG", "I"} <= set(measurement.columns):
        raise ValueError(f"seq {seq}: missing VG/I columns. Got: {measurement.columns}")

    vg = measurement["VG"].to_numpy()
    i_uA = measurement["I"].to_numpy() * 1e6
    hyst = (rec["cnp_backward"] or 0.0) - (rec["cnp_forward"] or 0.0)
    print(
        f"seq {seq}: step={rec['step_time_s'] or 0.01:g}s "
        f"CNP_fwd={rec['cnp_forward']:+.3f} V "
        f"CNP_back={rec['cnp_backward']:+.3f} V "
        f"hyst={hyst:+.3f} V "
        f"n_points={len(vg)}"
    )
    return vg, i_uA, rec


def _plot_curve(ax, curve: dict, vg: np.ndarray, i_uA: np.ndarray) -> None:
    legs = split_full_range_legs(vg, i_uA)
    first = True
    for vg_leg, i_leg, _direction in legs:
        ax.plot(
            vg_leg,
            i_leg,
            label=curve["label"] if first else None,
            color=curve["color"],
            linestyle=curve["linestyle"],
            linewidth=2.7,
        )
        first = False


def _finalize_iv_axes(ax) -> None:
    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
    ax.set_ylim(bottom=0)
    ax.legend(loc="best", framealpha=0.9)


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    curves = {c["seq"]: (_load_ivg(c["seq"])[:2]) for c in SELECTION}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(20, 20))
    for curve in SELECTION:
        vg, i_uA = curves[curve["seq"]]
        _plot_curve(ax, curve, vg, i_uA)
    _finalize_iv_axes(ax)
    plt.tight_layout()
    plt.savefig(OUTPUT_PATH_I, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {OUTPUT_PATH_I}")

    fig, ax = plt.subplots(figsize=(20, 20))
    for curve in SELECTION:
        vg, i_uA = curves[curve["seq"]]
        first = True
        for vg_leg, i_leg, _direction in split_full_range_legs(vg, i_uA):
            window, polyorder = auto_select_savgol_params(vg_leg, i_leg, "auto")
            gm = _savgol_derivative_corrected(
                vg_leg, i_leg, window_length=window, polyorder=polyorder
            )
            ax.plot(
                vg_leg,
                gm,
                color=curve["color"],
                linestyle=curve["linestyle"],
                linewidth=2.7,
                label=curve["label"] if first else None,
            )
            first = False
    ax.axhline(0.0, color="k", linewidth=0.5, alpha=0.5)
    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{dI_{ds}/dV_g\\ (\\mu A/V)}$")
    ax.legend(loc="best", framealpha=0.9)
    plt.tight_layout()
    plt.savefig(OUTPUT_PATH_GM, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {OUTPUT_PATH_GM}")


if __name__ == "__main__":
    main()
