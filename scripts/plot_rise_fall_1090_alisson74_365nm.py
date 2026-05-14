"""
10%-90% rise/fall time visualization for Alisson74 It measurements at 365 nm.

For each 365 nm It measurement (seq 28 on 2026-04-16; seq 43 and 53 on
2026-04-21), runs ITSRiseFallExtractor in both rise and fall mode and overlays
the extraction on the raw I(t) trace: the 10% / 90% threshold levels, the
first-crossing points, the shaded 10-90 interval, and the resulting rise/fall
time. One panel per seq.

The 10-90 rule here is model-free: rise is measured over the illuminated
(LED-ON) phase, fall over the post-dark relaxation phase, both referenced to
the illuminated-phase maximum current I_max. When the photocurrent sustains a
sign reversal within a phase, the phase is split in two and each section gets
its own response time.

Run from repo root:
    python scripts/plot_rise_fall_1090_alisson74_365nm.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.extractors.its_rise_fall_extractor import ITSRiseFallExtractor
from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style

CHIP = 74
WAVELENGTH_NM = 365.0
SEQS = [28, 43, 53]
HISTORY_PATH = Path("data/02_stage/chip_histories/Alisson74_history.parquet")
OUTPUT_DIR = Path("figs/compare")

RISE_COLOR = "#377eb8"
FALL_COLOR = "#e41a1c"

rise_extractor = ITSRiseFallExtractor(mode="rise")
fall_extractor = ITSRiseFallExtractor(mode="fall")


def _metadata(row: dict) -> dict:
    return {
        "run_id": row["run_id"],
        "chip_number": row["chip_number"],
        "chip_group": row["chip_group"],
        "proc": row["proc"],
        "seq_num": row["seq"],
        "extraction_version": "rise_fall_viz",
    }


def _draw_metric(ax, t, i, metric, color, name):
    """Overlay 10/90 levels, first-crossing markers and the response interval."""
    if metric is None:
        ax.plot([], [], " ", label=f"{name}: n/a")
        return
    details = json.loads(metric.value_json)
    for sec in details["sections"]:
        l10 = sec["level_10"] * 1e6
        l90 = sec["level_90"] * 1e6
        idx10, idx90 = sec["idx_10"], sec["idx_90"]
        t10, t90 = sec["t_10"], sec["t_90"]
        rt = sec["response_time"]

        # 10% / 90% threshold levels (of this section's reference extremum)
        ax.axhline(l10, color=color, linewidth=0.7, linestyle=":", alpha=0.7)
        ax.axhline(l90, color=color, linewidth=0.7, linestyle=":", alpha=0.7)
        # shaded 10-90 time interval
        ax.axvspan(min(t10, t90), max(t10, t90), color=color, alpha=0.12)
        # first-crossing points, on the trace
        ax.plot(
            [t10, t90],
            [i[idx10] * 1e6, i[idx90] * 1e6],
            "o", color=color, markersize=6, zorder=5,
        )

    secs = details["sections"]
    times = " + ".join(f"{s['response_time']:.1f}" for s in secs)
    suffix = "  (sign switch)" if details["sign_switch"] else ""
    ax.plot([], [], "o", color=color, label=f"{name} = {times} s{suffix}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)
    # The project theme sizes fonts for its 35-inch publication figures;
    # rescale for this compact 3-panel diagnostic.
    plt.rcParams.update({
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 10,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "lines.linewidth": 1.0,
    })

    history = pl.read_parquet(HISTORY_PATH)
    rows = (
        history.filter(
            (pl.col("proc") == "It")
            & (pl.col("wavelength_nm") == WAVELENGTH_NM)
            & (pl.col("seq").is_in(SEQS))
        )
        .sort("seq")
    )
    if rows.height != len(SEQS):
        raise ValueError(
            f"expected {len(SEQS)} It rows at {WAVELENGTH_NM:.0f} nm, "
            f"got {rows.height}: {rows['seq'].to_list()}"
        )

    print("Selected It measurements (Alisson74, 365 nm):")
    print(rows.select(["seq", "date", "has_light", "wavelength_nm",
                       "vg_fixed_v", "vds_v", "laser_period_s", "rows"]))

    fig, axes = plt.subplots(
        len(SEQS), 1, figsize=(11, 3.0 * len(SEQS)), constrained_layout=True
    )

    for ax, row in zip(axes, rows.to_dicts()):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy().astype(np.float64)
        i = meas["I (A)"].to_numpy().astype(np.float64)
        vl = meas["VL (V)"].to_numpy().astype(np.float64)
        finite = np.isfinite(t) & np.isfinite(i) & np.isfinite(vl)
        t, i, vl = t[finite], i[finite], vl[finite]

        meta = _metadata(row)
        rise = rise_extractor.extract(meas, meta)
        fall = fall_extractor.extract(meas, meta)

        # raw trace
        ax.plot(t, i * 1e6, color="0.25", linewidth=1.0, label="I(t)")

        # illuminated window
        on_idx = np.where(vl > 0.1)[0]
        if on_idx.size:
            ax.axvspan(
                float(t[on_idx[0]]), float(t[on_idx[-1]]),
                color="0.85", alpha=config.light_window_alpha, zorder=0,
            )

        _draw_metric(ax, t, i, rise, RISE_COLOR, "rise")
        _draw_metric(ax, t, i, fall, FALL_COLOR, "fall")

        print(f"\nseq {row['seq']} ({row['date']}):")
        for nm, metric in (("rise", rise), ("fall", fall)):
            if metric is None:
                print(f"  {nm}: None (precondition/incomplete)")
            else:
                d = json.loads(metric.value_json)
                ts = [f"{s['response_time']:.2f}" for s in d["sections"]]
                print(f"  {nm}: value_float={metric.value_float:.2f} s  "
                      f"sections={ts}  flags={metric.flags}")

        ax.set_title(
            f"seq {row['seq']}  ({row['date']}, "
            rf"$V_g={row['vg_fixed_v']:+g}$ V, $V_{{ds}}={row['vds_v']:g}$ V)",
            fontsize=9,
        )
        ax.set_ylabel(r"$I\ (\mu\mathrm{A})$")
        ax.legend(loc="upper right", framealpha=0.9, ncol=1)
        T_total = float(t[-1])
        if np.isfinite(T_total) and T_total > 0:
            ax.set_xlim(float(t[0]), T_total)

    axes[-1].set_xlabel(r"$t\ (\mathrm{s})$")
    fig.suptitle(
        rf"Alisson{CHIP} It @ {WAVELENGTH_NM:.0f} nm — 10–90% rise/fall extraction",
        fontsize=11,
    )

    out = config.get_output_path(
        f"Alisson{CHIP}_It_365nm_rise_fall_1090",
        chip_number=CHIP,
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
