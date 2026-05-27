"""
Step-time ladder across encaps 68, 75, 76, 80 (post-2026-05-12, dark).

Three back-to-back IVgs per chip at step_time_s ∈ {0.01, 0.1, 1.0} s.
All sweeps: Vg ∈ [-5, 5] V, 0.05 V step, Vds = 0.1 V, dark.

    Encap68  2026-05-18  seq 133/134/135
    Encap75  2026-05-20  seq 109/110/111
    Encap76  2026-05-20  seq  20/ 21/ 22
    Encap80  2026-05-25  seq 167/168/169

(Manifest step_time_s = 0 actually means the instrument floor, 0.01 s.)

Methodology follows scripts/IVg Analysis/step_time_ladder_alisson68_2026-05-12.py
— same color logic, same leg splitter, same plot styling. Difference: one IVg
figure per chip (no g_m), plus a ΔV_CNP table across the four chips.

Outputs (figs/step_time_ladder_multichip_post-may-12/):
    Alisson{68,75,76,80}_step_time_ladder_<date>_I.pdf
    delta_vcnp_vs_step_time.csv

Run from repo root:
    python "scripts/IVg Analysis/step_time_ladder_multichip_post-may-12.py"
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
from src.plotting.shared.plot_utils import ensure_standard_columns
from src.plotting.shared.styles import set_plot_style

HISTORY_DIR = Path("data/03_derived/chip_histories_enriched")
MANIFEST_PATH = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
OUTPUT_DIR = Path("figs/step_time_ladder_multichip_post-may-12")
CSV_PATH = OUTPUT_DIR / "delta_vcnp_vs_step_time.csv"

LADDERS = [
    {"chip": 68, "date": "2026-05-18", "seqs": {0.01: 133, 0.1: 134, 1.0: 135}},
    {"chip": 75, "date": "2026-05-20", "seqs": {0.01: 109, 0.1: 110, 1.0: 111}},
    {"chip": 76, "date": "2026-05-20", "seqs": {0.01: 20,  0.1: 21,  1.0: 22 }},
    {"chip": 80, "date": "2026-05-25", "seqs": {0.01: 167, 0.1: 168, 1.0: 169}},
]

# Same trimmed-magma ramp as the reference, but keyed by step_time so the
# same step value uses the same color in every chip panel.
_CMAP = mpl.colormaps["magma"]
_SAMPLES = np.linspace(0.15, 0.85, 3)
STEP_ORDER = [0.01, 0.1, 1.0]
COLORS = {step: _CMAP(_SAMPLES[i]) for i, step in enumerate(STEP_ORDER)}
LABELS = {0.01: "step = 0.01 s", 0.1: "step = 0.1 s", 1.0: "step = 1.0 s"}


def _load_ivg(history: pl.DataFrame, date: str, seq: int) -> dict:
    """Return {vg, i_uA, cnp_forward, cnp_backward, step_time_s, n}."""
    row = history.filter(
        (pl.col("proc") == "IVg")
        & (pl.col("date_local") == date)
        & (pl.col("seq") == seq)
    )
    if row.height != 1:
        raise ValueError(f"date {date} seq {seq}: expected 1 row, got {row.height}")
    rec = row.row(0, named=True)

    measurement = ensure_standard_columns(read_measurement_parquet(Path(rec["parquet_path"])))
    if not {"VG", "I"} <= set(measurement.columns):
        raise ValueError(f"seq {seq}: missing VG/I. Got: {measurement.columns}")

    vg = measurement["VG"].to_numpy()
    i_uA = measurement["I"].to_numpy() * 1e6
    step = rec["step_time_s"] or 0.01
    cnp_f = rec.get("cnp_forward")
    cnp_b = rec.get("cnp_backward")
    return {
        "vg": vg,
        "i_uA": i_uA,
        "cnp_forward": cnp_f,
        "cnp_backward": cnp_b,
        "step_time_s": step,
        "n": len(vg),
    }


def _plot_curve(ax, vg: np.ndarray, i_uA: np.ndarray, color, label: str) -> None:
    first = True
    for vg_leg, i_leg, _direction in split_full_range_legs(vg, i_uA):
        ax.plot(
            vg_leg, i_leg,
            label=label if first else None,
            color=color, linestyle="-", linewidth=2.7,
        )
        first = False


def _finalize_iv_axes(ax, title: str) -> None:
    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
    ax.set_ylim(bottom=0)
    ax.set_title(title)
    ax.legend(loc="best", framealpha=0.9)


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = pl.read_parquet(MANIFEST_PATH).select(["run_id", "step_time_s"])

    rows = []  # for the ΔV_CNP table

    for ladder in LADDERS:
        chip = ladder["chip"]
        date = ladder["date"]
        history = (
            pl.read_parquet(HISTORY_DIR / f"Alisson{chip}_history.parquet")
            .join(manifest, on="run_id", how="left")
        )

        loaded = {step: _load_ivg(history, date, seq) for step, seq in ladder["seqs"].items()}

        # Diagnostic print + ΔV_CNP accumulation.
        print(f"\n=== Alisson{chip}  {date} ===")
        for step in STEP_ORDER:
            d = loaded[step]
            seq = ladder["seqs"][step]
            cnp_f = d["cnp_forward"]
            cnp_b = d["cnp_backward"]
            hyst = (cnp_b - cnp_f) if (cnp_f is not None and cnp_b is not None) else None
            print(
                f"  seq {seq:>3}  step={d['step_time_s']:g} s  "
                f"CNP_fwd={cnp_f:+.3f} V  CNP_back={cnp_b:+.3f} V  "
                f"ΔV_CNP={hyst:+.3f} V  n={d['n']}"
            )
            rows.append({
                "chip": chip,
                "date": date,
                "seq": seq,
                "step_time_s": d["step_time_s"],
                "cnp_forward_V": cnp_f,
                "cnp_backward_V": cnp_b,
                "delta_vcnp_V": hyst,
            })

        # IVg figure for this chip.
        fig, ax = plt.subplots(figsize=(20, 20))
        for step in STEP_ORDER:
            d = loaded[step]
            _plot_curve(ax, d["vg"], d["i_uA"], COLORS[step], LABELS[step])
        _finalize_iv_axes(ax, f"Alisson{chip}  —  {date}")
        plt.tight_layout()
        out_path = OUTPUT_DIR / f"Alisson{chip}_step_time_ladder_{date}_I.pdf"
        plt.savefig(out_path, dpi=config.dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"  saved {out_path}")

    # ΔV_CNP tables.
    df = pl.DataFrame(rows)
    print("\n=== ΔV_CNP long form ===")
    with pl.Config(tbl_rows=20, tbl_cols=10):
        print(df)

    pivot = df.pivot(values="delta_vcnp_V", index="chip", on="step_time_s").sort("chip")
    pivot = pivot.rename({c: f"ΔV_CNP @ {c} s (V)" for c in pivot.columns if c != "chip"})
    print("\n=== ΔV_CNP pivot (rows = chip, cols = step_time) ===")
    with pl.Config(tbl_rows=20, tbl_cols=10, float_precision=3):
        print(pivot)

    df.write_csv(CSV_PATH)
    print(f"\nsaved {CSV_PATH}")


if __name__ == "__main__":
    main()
