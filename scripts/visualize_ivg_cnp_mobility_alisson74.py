"""Encap 74 IVg visualizer — CNPs + per-direction mobility on the gm plot.

Produces a two-panel figure per IVg sweep:

  Top:    I vs Vg with the three CNPs (forward/backward/average) marked
          and the two parabolic fits drawn (same as visualize_ivg_cnp_alisson74.py).
  Bottom: signed transconductance gm = dI/dVg vs Vg, split into forward
          (blue) and backward (red) legs, with the four peak-gm points
          marked — holes forward, holes backward, electrons forward,
          electrons backward — and their µ_FE values annotated in the
          legend.

Signed gm (not |gm|) is plotted: hole-branch peaks sit at negative gm,
electron-branch peaks at positive gm.

Run from repo root:

    python scripts/visualize_ivg_cnp_mobility_alisson74.py
    python scripts/visualize_ivg_cnp_mobility_alisson74.py --seq 14
    python scripts/visualize_ivg_cnp_mobility_alisson74.py --all
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.cnp_parabola import split_full_range_legs
from src.derived.algorithms.mobility import peak_gm_on_leg
from src.derived.extractors.cnp_extractor import CNPExtractor
from src.derived.extractors.mobility_extractor import MobilityExtractor

CHIP = 74
HISTORY = Path(
    f"data/03_derived/chip_histories_enriched/Alisson{CHIP}_history.parquet"
)
OUTDIR = Path(f"figs/Encap{CHIP}/IVg/CNP_mobility_overlay")

DIR_COLORS = {"forward": "#1f77b4", "backward": "#d62728"}
CNP_COLORS = {"forward": "#1f77b4", "backward": "#d62728", "average": "#2ca02c"}


def _parabola_curve(coeffs: dict, vg_leg: np.ndarray):
    a, b, c = coeffs["a"], coeffs["b"], coeffs["c"]
    v_cnp = -b / (2.0 * a)
    span = 0.05 * (vg_leg.max() - vg_leg.min())
    xs = np.linspace(v_cnp - span, v_cnp + span, 200)
    return xs, a * xs * xs + b * xs + c


def _run_cnp(df, metadata):
    return {
        d: CNPExtractor(direction=d).extract(df, metadata)
        for d in ("forward", "backward", "average")
    }


def _run_mobility(df, metadata):
    out = {}
    for branch in ("holes", "electrons"):
        for direction in ("forward", "backward", "average"):
            out[(branch, direction)] = MobilityExtractor(
                branch=branch, direction=direction,
            ).extract(df, metadata)
    return out


def _plot_one(row: dict, out_path: Path) -> None:
    parquet_path = Path(row["parquet_path"])
    df = read_measurement_parquet(parquet_path)
    if "Vg (V)" not in df.columns or "I (A)" not in df.columns:
        print(f"  skipped seq {row['seq']}: missing Vg/I columns")
        return

    metadata = {
        "run_id": row["run_id"],
        "chip_number": row["chip_number"],
        "chip_group": row["chip_group"],
        "proc": "IVg",
        "seq_num": int(row["seq"]),
        "vds_v": float(row["vds_v"]) if row["vds_v"] is not None else None,
        "extraction_version": "visualizer",
    }

    vg = df["Vg (V)"].to_numpy()
    i = df["I (A)"].to_numpy()

    cnp_metrics = _run_cnp(df, metadata)
    mob_metrics = _run_mobility(df, metadata)

    # Per-leg gm traces for the bottom panel.
    legs = split_full_range_legs(vg, i)
    leg_data = {}
    for vg_leg, i_leg, direction in legs:
        gm_h, gm_e, vg_h, vg_e, vg_seg, i_seg, gm_seg, cnp = peak_gm_on_leg(vg_leg, i_leg)
        leg_data[direction] = {
            "vg_seg": vg_seg, "gm_seg": gm_seg,
            "gm_h": gm_h, "gm_e": gm_e,
            "vg_h": vg_h, "vg_e": vg_e,
            "cnp": cnp,
        }

    fig, (ax_iv, ax_gm) = plt.subplots(
        2, 1, figsize=(8.0, 7.4), constrained_layout=True, sharex=True,
    )

    # ────────────────── Top panel: I vs Vg + CNPs ──────────────────
    ax_iv.plot(vg, i * 1e6, lw=1.0, color="black", alpha=0.85, label="IVg")

    carrier = next((m for m in cnp_metrics.values() if m is not None), None)
    if carrier is not None:
        details = json.loads(carrier.value_json)
        if details.get("parabola_fwd") is not None:
            xs, ys = _parabola_curve(details["parabola_fwd"], vg)
            ax_iv.plot(xs, ys * 1e6, color=DIR_COLORS["forward"], lw=2.2,
                       label=f"forward fit (vCNP={details['v_fwd']:.3f} V)")
        if details.get("parabola_back") is not None:
            xs, ys = _parabola_curve(details["parabola_back"], vg)
            ax_iv.plot(xs, ys * 1e6, color=DIR_COLORS["backward"], lw=2.2,
                       label=f"backward fit (vCNP={details['v_back']:.3f} V)")
        hyst = details.get("hysteresis_v")
        if hyst is not None:
            ax_iv.text(
                0.02, 0.97,
                f"Hysteresis (V_back − V_fwd): {hyst:+.3f} V",
                transform=ax_iv.transAxes, ha="left", va="top",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.7", alpha=0.85),
            )

    for direction, metric in cnp_metrics.items():
        if metric is None:
            continue
        ax_iv.axvline(
            metric.value_float, color=CNP_COLORS[direction],
            ls="--", lw=1.4, alpha=0.9,
            label=f"CNP {direction}: {metric.value_float:.3f} V",
        )
    ax_iv.set_ylabel("I (µA)")
    ax_iv.legend(loc="best", fontsize=8, framealpha=0.85)

    # ────────────────── Bottom panel: gm vs Vg + mobility peaks ──────────────────
    for direction, d in leg_data.items():
        ax_gm.plot(
            d["vg_seg"], d["gm_seg"] * 1e6,
            color=DIR_COLORS[direction], lw=1.4, alpha=0.9,
            label=f"gm {direction}",
        )

    # Mobility-peak markers (signed gm), with µ_FE pulled from MobilityExtractor.
    marker_specs = [
        ("holes", "forward",  "o"),
        ("holes", "backward", "o"),
        ("electrons", "forward",  "s"),
        ("electrons", "backward", "s"),
    ]
    for branch, direction, marker in marker_specs:
        d = leg_data.get(direction)
        if d is None:
            continue
        gm_signed = d["gm_h"] if branch == "holes" else d["gm_e"]
        vg_at = d["vg_h"] if branch == "holes" else d["vg_e"]
        if not (np.isfinite(gm_signed) and np.isfinite(vg_at)):
            continue
        mob = mob_metrics.get((branch, direction))
        mu_str = f"µ={mob.value_float:.0f}" if mob is not None else "µ=—"
        ax_gm.scatter(
            [vg_at], [gm_signed * 1e6],
            color=DIR_COLORS[direction],
            edgecolor="black", linewidth=1.0,
            marker=marker, s=80, zorder=5,
            label=f"{branch[:-1]} peak, {direction}: gm={gm_signed*1e6:+.2f} µS, {mu_str} cm²/V·s",
        )

    ax_gm.axhline(0.0, color="0.6", lw=0.8)
    ax_gm.set_xlabel("V$_g$ (V)")
    ax_gm.set_ylabel("gm = dI/dV$_g$ (µS)")
    ax_gm.legend(loc="best", fontsize=7, framealpha=0.85)

    title = (
        f"Encap{CHIP} IVg — seq {row['seq']} ({row['date']}), "
        f"V$_{{ds}}$ = {row['vds_v']} V"
    )
    if row.get("has_light"):
        title += " — light"
    fig.suptitle(title, fontsize=10)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", type=int, default=None,
                    help="IVg seq to plot. Defaults to the first available.")
    ap.add_argument("--all", action="store_true",
                    help="Plot every IVg in the chip history.")
    args = ap.parse_args()

    if not HISTORY.exists():
        raise FileNotFoundError(f"History not found: {HISTORY}")

    hist = pl.read_parquet(HISTORY).filter(pl.col("proc") == "IVg")
    if hist.height == 0:
        raise RuntimeError(f"No IVg sweeps in {HISTORY}")

    if args.all:
        rows = hist.to_dicts()
    elif args.seq is not None:
        rows = hist.filter(pl.col("seq") == args.seq).to_dicts()
        if not rows:
            raise ValueError(f"seq {args.seq} not found among IVg rows")
    else:
        rows = [hist.row(0, named=True)]

    print(f"Plotting {len(rows)} IVg sweep(s) for Encap{CHIP}")
    for row in rows:
        out_path = OUTDIR / f"Encap{CHIP}_IVg_seq{int(row['seq']):03d}_CNP_mobility.png"
        _plot_one(row, out_path)


if __name__ == "__main__":
    main()
