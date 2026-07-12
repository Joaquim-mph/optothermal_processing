"""Chip-80 CNP evolution *within* the two responsivity sessions (Apr vs Jul).

During each session several dark transfer curves (IVg) were taken interleaved
with the It (photoresponse) measurements. This plots the CNP of those
interleaved transfer curves against a per-session 0-based index (i.e. the
transfer-curve count within the session), so the two relaxation trajectories
overlay for a direct Old (Apr 28) vs New (Jul 1) comparison.

The two datasets are the sessions anchored by the sweeps used in
`plot_chip80_transfer_shift_apr_jul.py` (April run_id d1e762d30df2b0e4,
July run_id fd6cd72def7d9c5d); here we take *all* dark IVg on each of those
dates, not just the single representative sweep.

Run from repo root:
    .venv/bin/python "scripts/spectral plots/plot_chip80_cnp_within_session_apr_jul.py"
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

CHIP = 80
HISTORY_PATH = Path(
    "data/03_derived/chip_histories_enriched/Alisson80_history.parquet"
)
OUTPUT_DIR = Path("figs/chip80_within_session_cnp")

# The two sessions. Colours/labels match plot_chip80_transfer_shift_apr_jul.py:
# April = "Old" (C3), July = "New" (C2).
# `skip` drops that many leading transfer curves from the series (their CNP is
# flat/redundant and adds nothing to the narrative). The within-session index is
# kept truthful, so a skipped series simply starts at index = skip.
SESSIONS = [
    {"date": "2026-04-28", "label": "Old", "color": "C3", "marker": "o", "skip": 2},
    {"date": "2026-07-01", "label": "New", "color": "C2", "marker": "s", "skip": 0},
]

LEGEND_FONTSIZE_BUMP = 2.0


def _legend_fontsize(relative: str = "small") -> float:
    from matplotlib.font_manager import font_scalings
    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


def session_cnp(
    df: pl.DataFrame, date: str, skip: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """0-based transfer-curve index and CNP for the dark IVg of one session,
    in acquisition-time order. The first `skip` curves are dropped and the
    index is re-based so the first plotted point is 0."""
    sub = (
        df.filter(
            (pl.col("proc") == "IVg")
            & (pl.col("date") == date)
            & (~pl.col("has_light"))
            & pl.col("cnp_voltage").is_not_null()
        )
        .sort("start_dt")
    )
    cnp = sub["cnp_voltage"].to_numpy()[skip:]
    return np.arange(len(cnp)), cnp


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pl.read_parquet(HISTORY_PATH)

    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(figsize=(side, side))

    for s in SESSIONS:
        idx, cnp = session_cnp(df, s["date"], s.get("skip", 0))
        print(f"{s['label']}: {len(cnp)} dark transfer curves")
        ax.plot(
            idx, cnp,
            marker=s["marker"], ms=10, lw=1.5,
            color=s["color"], label=s["label"],
        )

    ax.set_xlabel("Transfer-curve index within session")
    ax.set_ylabel(r"$V_{CNP}$ (V)")
    ax.set_box_aspect(1.0)
    ax.legend(loc="best", fontsize=_legend_fontsize())

    fig.tight_layout()
    out = OUTPUT_DIR / "chip80_cnp_within_session_apr_jul.pdf"
    fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
