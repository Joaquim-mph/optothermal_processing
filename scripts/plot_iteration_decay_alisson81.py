"""
Iteration-decay of photoresponse on Alisson81 at fixed (λ, P, Vg).

Repeated It measurements at the same wavelength, power, and gate
voltage do *not* give exchangeable replicates — |ΔI| decays
monotonically with iteration index as the chip's trap state evolves. This
script visualizes that decay for the cleanest tight-time clusters.

Plots It Δi_corrected vs iteration for several Vg clusters at λ = 455 nm,
P = 6 µW, period = 120 s.

Run from repo root:
    python scripts/plot_iteration_decay_alisson81.py

Prereq: biotite enrich-history 81.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style

CHIP_NUMBER = 81
HISTORY_PATH = Path(
    f"data/03_derived/chip_histories_enriched/Alisson{CHIP_NUMBER}_history.parquet"
)

IT_CLUSTERS: list[dict] = [
    {
        "label": r"$V_g = -1.7$ V",
        "color": "#1f77b4",
        "seqs": [132, 133, 134, 135, 136, 137, 138, 139],
    },
    {
        "label": r"$V_g = -1.5$ V",
        "color": "#ff7f0e",
        "seqs": [146, 147, 148, 149, 150, 151, 152, 153],
    },
    {
        "label": r"$V_g = -1.15$ V",
        "color": "#2ca02c",
        "seqs": [95, 97, 99, 101, 103],
    },
    {
        "label": r"$V_g = -1.15$ V",
        "color": "#2ca02c",
        "linestyle": "--",
        "seqs": [117, 120, 121, 122, 123, 126],
    },
    {
        "label": r"$V_g = 0$ V",
        "color": "#d62728",
        "seqs": [193, 194, 195, 196, 197, 198, 199, 200],
    },
]


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    hist = pl.read_parquet(HISTORY_PATH)

    # Adjusted to a single plot using the default derived figsize
    fig, ax1 = plt.subplots(figsize=(20, 20))

    for cluster in IT_CLUSTERS:
        rows = (
            hist.filter(pl.col("seq").is_in(cluster["seqs"]))
            .filter(pl.col("proc") == "It")
            .sort("seq")
        )
        di_uA = rows["delta_i_corrected"].to_numpy() * 1e6
        idx = np.arange(1, len(di_uA) + 1)
        ax1.plot(
            idx,
            di_uA,
            marker="o",
            linestyle=cluster.get("linestyle", "-"),
            color=cluster["color"],
            label=cluster["label"],
        )
        print(
            f"It {cluster['label']:<45}  n={len(di_uA)}  "
            f"first={di_uA[0]:+.3f} µA  last={di_uA[-1]:+.3f} µA  "
            f"ratio={di_uA[0] / di_uA[-1] if di_uA[-1] != 0 else float('inf'):.1f}×"
        )

    # ax1.axhline(0.0, color="k", linewidth=0.5, alpha=0.5)
    ax1.set_xlabel("Iteration index within cluster")
    ax1.set_ylabel(r"$\Delta I_{\mathrm{corr}}$ ($\mu$A)")
    # ax1.set_title(
    #    r"Alisson81 — It iteration decay at $\lambda = 455$ nm, $P \approx 6\ \mu$W"
    # )
    # ax1.legend(fontsize="small")

    plt.tight_layout()

    # Updated filename to reflect that Vt is no longer included
    filename = f"Alisson{CHIP_NUMBER}_iteration_decay_It"
    out = config.get_output_path(
        filename,
        chip_number=CHIP_NUMBER,
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
