"""Per-chip analysis: is backward mobility usually slower than forward?

Computes mu_FE on the forward and backward full-range legs of every IVg
in every Alisson chip history, then reports — per chip, per branch — the
median ratio mu_back / mu_fwd and the fraction of sweeps with back < fwd.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.extractors.mobility_extractor import MobilityExtractor

HISTORY_DIR = Path("data/03_derived/chip_histories_enriched")

# Pre-build six instances (init reloads encap config — do it once).
EXTRACTORS = {
    (b, d): MobilityExtractor(branch=b, direction=d)
    for b in ("holes", "electrons")
    for d in ("forward", "backward")
}


def per_ivg_pairs(row: dict, branch: str):
    df = read_measurement_parquet(Path(row["parquet_path"]))
    meta = {
        "run_id": row["run_id"],
        "chip_number": row["chip_number"],
        "chip_group": row["chip_group"],
        "proc": "IVg",
        "seq_num": int(row["seq"]),
        "vds_v": float(row["vds_v"]) if row["vds_v"] is not None else None,
        "has_light": bool(row.get("has_light", False)),
        "extraction_version": "analysis",
    }
    fwd = EXTRACTORS[(branch, "forward")].extract(df, meta)
    back = EXTRACTORS[(branch, "backward")].extract(df, meta)
    if fwd is None or back is None:
        return None
    if not (np.isfinite(fwd.value_float) and np.isfinite(back.value_float)):
        return None
    if fwd.value_float <= 0 or back.value_float <= 0:
        return None
    return fwd.value_float, back.value_float


def analyze_chip(path: Path, branch: str) -> dict | None:
    hist = pl.read_parquet(path).filter(pl.col("proc") == "IVg")
    if hist.height == 0:
        return None
    fwds, backs = [], []
    for row in hist.to_dicts():
        pair = per_ivg_pairs(row, branch)
        if pair is None:
            continue
        fwds.append(pair[0])
        backs.append(pair[1])
    if not fwds:
        return None
    fwds = np.array(fwds)
    backs = np.array(backs)
    ratio = backs / fwds
    return {
        "chip": int(re.search(r"(\d+)", path.stem).group(1)),
        "n": len(fwds),
        "median_fwd": float(np.median(fwds)),
        "median_back": float(np.median(backs)),
        "median_ratio_back_over_fwd": float(np.median(ratio)),
        "frac_back_slower": float(np.mean(backs < fwds)),
        "mean_log10_ratio": float(np.mean(np.log10(ratio))),
    }


def main() -> None:
    histories = sorted(HISTORY_DIR.glob("*_history.parquet"))
    for branch in ("holes", "electrons"):
        print(f"\n=== branch = {branch} ===")
        print(f"{'chip':>5} {'n':>4} {'med_fwd':>10} {'med_back':>10} "
              f"{'med_b/f':>9} {'frac_b<f':>9} {'mean_log10_ratio':>17}")
        rows = []
        for path in histories:
            try:
                r = analyze_chip(path, branch)
            except Exception as e:  # noqa: BLE001
                print(f"  {path.stem}: error {e}")
                continue
            if r is None:
                continue
            rows.append(r)
            print(f"{r['chip']:>5} {r['n']:>4} "
                  f"{r['median_fwd']:>10.1f} {r['median_back']:>10.1f} "
                  f"{r['median_ratio_back_over_fwd']:>9.3f} "
                  f"{r['frac_back_slower']:>9.2%} "
                  f"{r['mean_log10_ratio']:>17.4f}")

        if rows:
            all_ratio = np.array([r["median_ratio_back_over_fwd"] for r in rows])
            all_frac = np.array([r["frac_back_slower"] for r in rows])
            n_total = sum(r["n"] for r in rows)
            print(f"  ── pooled across {len(rows)} chips, "
                  f"{n_total} sweeps: "
                  f"median(med_b/f)={np.median(all_ratio):.3f}  "
                  f"mean(frac_b<f)={np.mean(all_frac):.2%}")


if __name__ == "__main__":
    main()
