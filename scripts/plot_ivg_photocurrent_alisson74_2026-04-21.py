"""
IVg analysis plots for Alisson74 on 2026-04-21.

Two figures are produced:

1. Photocurrent overlay: (I_on - I_off) vs Vg, one trace per wavelength,
   obtained by subtracting each IVg OFF from its subsequent IVg ON.

2. 2x2 grid with one subplot per wavelength, each showing the OFF -> ON -> OFF
   triplet (raw IVg current vs Vg).

Triplets (OFF, ON, OFF, wavelength):
    (56, 57, 58, 365 nm)
    (59, 60, 61, 385 nm)
    (62, 63, 64, 405 nm)
    (65, 66, 67, 455 nm)

Run from the repo root:
    python scripts/plot_ivg_photocurrent_alisson74_2026-04-21.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.signal import savgol_filter

from src.core.utils import read_measurement_parquet
from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style
from src.plotting.transconductance import auto_select_savgol_params

CHIP_NUMBER = 74
DATE = "2026-04-21"
HISTORY_PATH = Path(
    f"data/02_stage/chip_histories/Alisson{CHIP_NUMBER}_history.parquet"
)

TRIPLETS: list[tuple[int, int, int]] = [
    (56, 57, 58),
    (59, 60, 61),
    (62, 63, 64),
    (65, 66, 67),
]


def _load_seq(hist: pl.DataFrame, seq: int):
    row = hist.filter(pl.col("seq") == seq).row(0, named=True)
    return read_measurement_parquet(row["parquet_path"]), row


def load_pair(hist: pl.DataFrame, off_seq: int, on_seq: int):
    off, _ = _load_seq(hist, off_seq)
    on, on_row = _load_seq(hist, on_seq)
    return off, on, float(on_row["wavelength_nm"])


def _single_forward_sweep(vg: np.ndarray) -> slice:
    """Return indices of a single monotonic forward sweep (min Vg -> max Vg)."""
    i_min = int(np.argmin(vg))
    # First occurrence of the max after i_min
    tail = vg[i_min:]
    i_max = i_min + int(np.argmax(tail))
    return slice(i_min, i_max + 1)


def plot_photocurrent_overlay(hist: pl.DataFrame, config: PlotConfig) -> None:
    plt.figure(figsize=config.figsize_voltage_sweep)

    for off_seq, on_seq, _ in TRIPLETS:
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

        # Thin, faded full raw trace (hysteresis visible but de-emphasized)
        (line_full,) = plt.plot(vg, i_photo, linewidth=0.6, alpha=0.3)
        color = line_full.get_color()

        # Solid bold single forward sweep (-5 V -> +5 V), Sav-Gol smoothed
        s = _single_forward_sweep(vg)
        vg_fwd = vg[s]
        iph_fwd = i_photo[s]
        window, polyorder = auto_select_savgol_params(vg_fwd, iph_fwd, "auto")
        iph_smooth = savgol_filter(iph_fwd, window_length=window, polyorder=polyorder)
        plt.plot(vg_fwd, iph_smooth, color=color, label=f"{int(wl)} nm", linewidth=1.8)

    plt.axhline(0.0, color="k", linewidth=0.5, alpha=0.5)
    plt.xlabel("$\\rm{V_g\\ (V)}$")
    plt.ylabel("$\\rm{I_{ph} = I_{on} - I_{off}\\ (\\mu A)}$")
    # plt.title(f"Alisson{CHIP_NUMBER} — IVg photocurrent ({DATE})")
    plt.legend(title="Wavelength")
    plt.tight_layout()

    filename = f"Alisson{CHIP_NUMBER}_IVg_photocurrent_{DATE}"
    out = config.get_output_path(
        filename,
        chip_number=CHIP_NUMBER,
        procedure="IVg",
        metadata={"has_light": True},
        special_type="photocurrent",
        create_dirs=True,
    )
    plt.savefig(out, dpi=config.dpi)
    plt.close()
    print(f"saved {out}")


def plot_triplet_grid(hist: pl.DataFrame, config: PlotConfig) -> None:
    """2x2 grid: one subplot per wavelength with OFF -> ON -> OFF traces."""
    fig, axes = plt.subplots(2, 2, figsize=(24, 20), sharex=True, sharey=True)

    for ax, (off1_seq, on_seq, off2_seq) in zip(axes.flat, TRIPLETS):
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

    filename = f"Alisson{CHIP_NUMBER}_IVg_triplets_grid_{DATE}"
    out = config.get_output_path(
        filename,
        chip_number=CHIP_NUMBER,
        procedure="IVg",
        special_type="triplets",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi)
    plt.close(fig)
    print(f"saved {out}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    hist = pl.read_parquet(HISTORY_PATH)
    hist = hist.filter((pl.col("proc") == "IVg") & (pl.col("date") == DATE))

    plot_photocurrent_overlay(hist, config)
    plot_triplet_grid(hist, config)


if __name__ == "__main__":
    main()
