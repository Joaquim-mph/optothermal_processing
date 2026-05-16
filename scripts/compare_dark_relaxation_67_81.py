"""
Dark relaxation comparison: Encap81 (seq 81→82) vs Encap67 (seq 85→86).

Two figures, both with the y axis normalized to percent of each pair's
photocurrent magnitude — the photo-induced current change on the paired light It,
defined as |I_end_of_illumination − I_pre_illumination_baseline|.

1. `..._dark_relaxation_compare..._pct`: dark It only (the ~40500 s relaxation
   tail). First sample dropped, curve anchored so the new first point is 0%.

2. `..._light_dark_concat..._pct`: the paired light It prepended before the dark
   It on a continuous real-time axis (gap from `start_dt` preserved). Everything
   anchored to the light It pre-illumination baseline (0%), so the illumination
   step reaches ~−100% (photocurrent "at scale") and the dark relaxation then
   recovers upward from there.

Run from repo root:

    python scripts/compare_dark_relaxation_67_81.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

# Each pair: light seq (for photocurrent) + dark seq (relaxation trace).
TRACES = [
    {
        "chip": 81,
        "light_seq": 81,
        "dark_seq": 82,
        "color": "#e41a1c",
        "label": "Encap81",
    },
    {
        "chip": 67,
        "light_seq": 85,
        "dark_seq": 86,
        "color": "#377eb8",
        "label": "Encap67",
    },
]

PRE_BASELINE_S = 20.0  # window before light-on used for the dark baseline
END_LIGHT_S = 5.0  # window at end of illumination used for I_on


def history_path(chip: int) -> Path:
    return Path(
        f"data/03_derived/chip_histories_enriched/Alisson{chip}_history.parquet"
    )


def get_row(history: pl.DataFrame, seq: int, chip: int) -> dict:
    rows = history.filter((pl.col("proc") == "It") & (pl.col("seq") == seq))
    if rows.height == 0:
        raise ValueError(f"no It row for Alisson{chip} seq {seq}")
    return rows.to_dicts()[0]


def load_trace(row: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return finite (t, I[µA], VL[V]) arrays for an It measurement."""
    meas = read_measurement_parquet(Path(row["parquet_path"]))
    t = meas["t (s)"].to_numpy().astype(np.float64)
    i = meas["I (A)"].to_numpy().astype(np.float64) * 1e6  # µA
    vl = (
        meas["VL (V)"].to_numpy().astype(np.float64)
        if "VL (V)" in meas.columns
        else np.zeros_like(t)
    )
    finite = np.isfinite(t) & np.isfinite(i)
    return t[finite], i[finite], vl[finite]


def light_baseline_and_photocurrent(row: dict) -> tuple[float, float]:
    """Return (pre-illumination baseline µA, photocurrent magnitude µA)."""
    t, i, vl = load_trace(row)
    on = np.where(vl > 0.1)[0]
    if on.size == 0:
        raise ValueError(f"no illumination window in seq {row['seq']}")
    t_on0, t_on1 = t[on[0]], t[on[-1]]
    pre = (t < t_on0) & (t >= t_on0 - PRE_BASELINE_S)
    end = (t <= t_on1) & (t >= t_on1 - END_LIGHT_S)
    baseline = float(np.nanmean(i[pre]))
    i_on = float(np.nanmean(i[end]))
    return baseline, abs(i_on - baseline)


def plot_dark_only(config: PlotConfig) -> None:
    fig, ax = plt.subplots(figsize=config.figsize_timeseries)
    for spec in TRACES:
        history = pl.read_parquet(history_path(spec["chip"]))
        light_row = get_row(history, spec["light_seq"], spec["chip"])
        dark_row = get_row(history, spec["dark_seq"], spec["chip"])
        _, pc = light_baseline_and_photocurrent(light_row)

        t, i, _ = load_trace(dark_row)
        t, i = t[1:], i[1:]  # drop first sample
        rel_pct = (i - i[0]) / pc * 100.0  # anchored at new first point

        ax.plot(
            t,
            rel_pct,
            color=spec["color"],
            linewidth=1.0,
            label=f"{spec['label']} seq {spec['dark_seq']}",
        )
        print(
            f"[dark-only] Encap{spec['chip']} seq {spec['dark_seq']} "
            f"(pc={pc:.4f} µA): recovery(end)={rel_pct[-1]:+.1f}%"
        )

    ax.axhline(0, color="k", linewidth=0.5, alpha=0.5)
    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"Dark relaxation (\% of photocurrent)")
    ax.set_title("Dark relaxation comparison, normalized to photocurrent")
    ax.legend()
    fig.tight_layout()

    out = config.get_output_path(
        "Encap67_81_dark_relaxation_compare_seq86_seq82_pct",
        chip_number=67,
        procedure="It",
        metadata={"has_light": False},
        special_type="light_dark_concat",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def plot_light_dark_concat(config: PlotConfig) -> None:
    fig, ax = plt.subplots(figsize=config.figsize_timeseries)
    for spec in TRACES:
        history = pl.read_parquet(history_path(spec["chip"]))
        light_row = get_row(history, spec["light_seq"], spec["chip"])
        dark_row = get_row(history, spec["dark_seq"], spec["chip"])
        baseline, pc = light_baseline_and_photocurrent(light_row)

        # Light It: anchored to its own pre-illumination baseline.
        t_l, i_l, vl_l = load_trace(light_row)
        y_l = (i_l - baseline) / pc * 100.0

        # Dark It: same baseline + pc reference, placed at the real wall-clock gap.
        t_d, i_d, _ = load_trace(dark_row)
        t_d, i_d = t_d[1:], i_d[1:]  # drop first sample
        offset = (dark_row["start_dt"] - light_row["start_dt"]).total_seconds()
        y_d = (i_d - baseline) / pc * 100.0

        # Light segment "before" the relaxation: faded, thin.
        ax.plot(t_l, y_l, color=spec["color"], linewidth=1.0, alpha=0.45)
        ax.plot(
            t_d + offset,
            y_d,
            color=spec["color"],
            linewidth=1.0,
            label=f"{spec['label']} seq {spec['light_seq']}→{spec['dark_seq']}",
        )

        on = np.where(vl_l > 0.1)[0]
        if on.size:
            ax.axvspan(
                float(t_l[on[0]]),
                float(t_l[on[-1]]),
                color="gold",
                alpha=config.light_window_alpha,
            )
        print(
            f"[concat]    Encap{spec['chip']} seq {spec['light_seq']}→{spec['dark_seq']} "
            f"(pc={pc:.4f} µA): light min={y_l.min():+.1f}%  "
            f"dark start={y_d[0]:+.1f}%  dark end={y_d[-1]:+.1f}%"
        )

    ax.axhline(0, color="k", linewidth=0.5, alpha=0.5)
    ax.axhline(-100, color="k", linewidth=0.5, linestyle=":", alpha=0.5)
    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I(t)$ relative to dark baseline (\% of photocurrent)")
    ax.set_title("Light It + dark relaxation, normalized to photocurrent")
    ax.legend()
    fig.tight_layout()

    out = config.get_output_path(
        "Encap67_81_light_dark_concat_seq85_86_seq81_82_pct",
        chip_number=67,
        procedure="It",
        metadata={"has_light": True},
        special_type="light_dark_concat",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def main() -> None:
    config = PlotConfig(chip_subdir_enabled=True, chip_folder_prefix="Encap")
    set_plot_style(config.theme)
    plot_dark_only(config)
    plot_light_dark_concat(config)


if __name__ == "__main__":
    main()
