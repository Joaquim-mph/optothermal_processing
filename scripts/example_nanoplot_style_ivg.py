"""Example: plot dark IVg sweeps on Encap67 using the bundled nanoplot style.

Loads the `.mplstyle` shipped under `nanoplot-main/src/nanoplot/styles/`
directly via `plt.style.use(path)` — no pip-install of nanoplot needed.
SciencePlots' `science` + `nature` are layered underneath if available,
mirroring `nanoplot.apply()` behavior.

Run from repo root:

    python scripts/example_nanoplot_style_ivg.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl
import scienceplots  # noqa: F401  registers 'science' / 'nature' with matplotlib

from src.core.utils import read_measurement_parquet

REPO_ROOT = Path(__file__).resolve().parents[1]
NANOPLOT_STYLE = (
    REPO_ROOT / "nanoplot-main/src/nanoplot/styles/default.mplstyle"
)

CHIP = 67
SEQS = [1, 3, 5, 15]
OUT = REPO_ROOT / "figs/_examples/nanoplot_style_ivg_encap67.png"


def apply_nanoplot_style() -> None:
    """Layer science + nature + nanoplot default — mirrors `nplt.apply()`."""
    chain: list[str] = []
    for base in ("science", "nature"):
        if base in plt.style.available:
            chain.append(base)
    chain.append(str(NANOPLOT_STYLE))
    plt.style.use(chain)


def main() -> None:
    apply_nanoplot_style()

    history = pl.read_parquet(
        REPO_ROOT
        / f"data/03_derived/chip_histories_enriched/Alisson{CHIP}_history.parquet"
    )
    rows = (
        history.filter(
            (pl.col("proc") == "IVg")
            & (pl.col("has_light") == False)  # noqa: E712
            & (pl.col("seq").is_in(SEQS))
        )
        .unique(subset=["seq"], keep="first")
        .sort("seq")
        .to_dicts()
    )

    fig, ax = plt.subplots()
    for row in rows:
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        vg = meas["Vg (V)"].to_numpy()
        i_ua = meas["I (A)"].to_numpy() * 1e6
        ax.plot(vg, i_ua, label=f"seq {row['seq']}")

    ax.set_xlabel(r"$V_G$ (V)")
    ax.set_ylabel(r"$I_{DS}$ ($\mu$A)")
    ax.set_title(f"Encap{CHIP} dark IVg — nanoplot style")
    ax.legend()
    fig.tight_layout()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
