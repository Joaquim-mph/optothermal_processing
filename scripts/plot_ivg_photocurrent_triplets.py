"""
Unified IVg photocurrent / triplet plots for chips with OFF -> ON -> OFF
wavelength sweeps.

For each configured chip+date, two figures are produced:

1. Photocurrent overlay: (I_on - I_off) vs Vg, one trace per wavelength.
2. 2x2 grid: one subplot per wavelength showing OFF -> ON -> OFF triplet.

Currently configured: Alisson74 (2026-04-21), Alisson72 (2026-04-28),
Alisson80 (2026-05-04). For Alisson80 the first 405/455 nm triplets were
trash (source disconnected) and the redo seqs are used instead.

Run from the repo root:
    python scripts/plot_ivg_photocurrent_triplets.py             # all chips
    python scripts/plot_ivg_photocurrent_triplets.py 80          # one chip
    python scripts/plot_ivg_photocurrent_triplets.py 72 74       # subset
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.signal import savgol_filter

from src.core.utils import read_measurement_parquet
from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style
from src.plotting.transconductance import auto_select_savgol_params


@dataclass(frozen=True)
class Dataset:
    chip_number: int
    date: str
    triplets: list[tuple[int, int, int]]  # (off_before, on, off_after)


DATASETS: list[Dataset] = [
    Dataset(
        chip_number=74,
        date="2026-04-21",
        triplets=[(56, 57, 58), (59, 60, 61), (62, 63, 64), (65, 66, 67)],
    ),
    Dataset(
        chip_number=72,
        date="2026-04-28",
        triplets=[(88, 89, 90), (91, 92, 93), (94, 95, 96), (97, 98, 99)],
    ),
    Dataset(
        chip_number=80,
        date="2026-05-04",
        # 405 and 455 first attempts (128-130, 131-133) were trash — source
        # disconnected. Use the redo triplets (136-138, 139-141).
        triplets=[(122, 123, 124), (125, 126, 127), (136, 137, 138), (139, 140, 141)],
    ),
]


def _history_path(chip_number: int) -> Path:
    return Path(f"data/02_stage/chip_histories/Alisson{chip_number}_history.parquet")


def _load_seq(hist: pl.DataFrame, seq: int):
    row = hist.filter(pl.col("seq") == seq).row(0, named=True)
    return read_measurement_parquet(row["parquet_path"]), row


def load_pair(hist: pl.DataFrame, off_seq: int, on_seq: int):
    off, _ = _load_seq(hist, off_seq)
    on, on_row = _load_seq(hist, on_seq)
    return off, on, float(on_row["wavelength_nm"])


def _first_half_sweep(vg: np.ndarray) -> slice:
    """Return slice covering 0 -> Vgmin -> 0 -> Vgmax -> 0 (first half of the
    full IVg sweep 0 -> Vgmin -> 0 -> Vgmax -> 0 -> Vgmin -> 0)."""
    i_max = int(np.argmax(vg))
    tail = vg[i_max:]
    below = np.where(tail <= 0.0)[0]
    end = i_max + int(below[0]) if below.size else len(vg) - 1
    return slice(0, end + 1)


def plot_photocurrent_overlay(ds: Dataset, hist: pl.DataFrame, config: PlotConfig) -> None:
    plt.figure(figsize=config.figsize_voltage_sweep)

    for off_seq, on_seq, _ in ds.triplets:
        off, on, wl = load_pair(hist, off_seq, on_seq)
        vg_off = off["Vg (V)"].to_numpy()
        i_off = off["I (A)"].to_numpy()
        vg_on = on["Vg (V)"].to_numpy()
        i_on = on["I (A)"].to_numpy()

        n = min(len(vg_off), len(vg_on))
        if not np.allclose(vg_off[:n], vg_on[:n], atol=1e-6):
            print(
                f"[warn] Vg arrays not aligned for wl={wl:.0f} nm; "
                f"subtracting by sample index anyway"
            )

        vg = vg_on[:n]
        i_photo = (i_on[:n] - i_off[:n]) * 1e6  # µA

        (line_full,) = plt.plot(vg, i_photo, linewidth=0.6, alpha=0.3)
        color = line_full.get_color()

        s = _first_half_sweep(vg)
        vg_half = vg[s]
        iph_half = i_photo[s]
        window, polyorder = auto_select_savgol_params(vg_half, iph_half, "auto")
        iph_smooth = savgol_filter(iph_half, window_length=window, polyorder=polyorder)
        plt.plot(vg_half, iph_smooth, color=color, label=f"{int(wl)} nm", linewidth=1.8)

    plt.axhline(0.0, color="k", linewidth=0.5, alpha=0.5)
    plt.xlabel("$\\rm{V_g\\ (V)}$")
    plt.ylabel("$\\rm{I_{ph} = I_{on} - I_{off}\\ (\\mu A)}$")
    plt.legend(title="Wavelength")
    plt.tight_layout()

    filename = f"Alisson{ds.chip_number}_IVg_photocurrent_{ds.date}"
    out = config.get_output_path(
        filename,
        chip_number=ds.chip_number,
        procedure="IVg",
        metadata={"has_light": True},
        special_type="photocurrent",
        create_dirs=True,
    )
    plt.savefig(out, dpi=config.dpi)
    plt.close()
    print(f"saved {out}")


def plot_triplet_grid(ds: Dataset, hist: pl.DataFrame, config: PlotConfig) -> None:
    """2x2 grid: one subplot per wavelength with OFF -> ON -> OFF traces."""
    fig, axes = plt.subplots(2, 2, figsize=(24, 20), sharex=True, sharey=True)

    for ax, (off1_seq, on_seq, off2_seq) in zip(axes.flat, ds.triplets):
        off1, _ = _load_seq(hist, off1_seq)
        on, on_row = _load_seq(hist, on_seq)
        off2, _ = _load_seq(hist, off2_seq)
        wl = float(on_row["wavelength_nm"])

        ax.plot(
            off1["Vg (V)"],
            off1["I (A)"] * 1e6,
            label="OFF (before)",
            linewidth=1.7,
            linestyle="--",
        )
        ax.plot(on["Vg (V)"], on["I (A)"] * 1e6, label="ON", linewidth=1.3)
        ax.plot(
            off2["Vg (V)"],
            off2["I (A)"] * 1e6,
            label="OFF (after)",
            linewidth=1.7,
            linestyle=":",
        )

        ax.set_title(f"{int(wl)} nm")

    for ax in axes[-1, :]:
        ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    for ax in axes[:, 0]:
        ax.set_ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=3,
        bbox_to_anchor=(0.5, 1.0),
        frameon=False,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    filename = f"Alisson{ds.chip_number}_IVg_triplets_grid_{ds.date}"
    out = config.get_output_path(
        filename,
        chip_number=ds.chip_number,
        procedure="IVg",
        special_type="triplets",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi)
    plt.close(fig)
    print(f"saved {out}")


def run(ds: Dataset, config: PlotConfig) -> None:
    print(f"\n=== Alisson{ds.chip_number} ({ds.date}) ===")
    hist = pl.read_parquet(_history_path(ds.chip_number))
    hist = hist.filter((pl.col("proc") == "IVg") & (pl.col("date") == ds.date))
    plot_photocurrent_overlay(ds, hist, config)
    plot_triplet_grid(ds, hist, config)


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    if len(sys.argv) > 1:
        wanted = {int(x) for x in sys.argv[1:]}
        selected = [d for d in DATASETS if d.chip_number in wanted]
        missing = wanted - {d.chip_number for d in selected}
        if missing:
            raise SystemExit(f"No dataset configured for chip(s): {sorted(missing)}")
    else:
        selected = list(DATASETS)

    for ds in selected:
        run(ds, config)


if __name__ == "__main__":
    main()
