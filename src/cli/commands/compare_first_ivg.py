"""compare-first-ivg: overlay the first IVg sweep across multiple chips."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import typer
from rich.console import Console

from src.cli.plugin_system import cli_command
from src.core.chip_metadata import ChipId, UnknownChipGroupError, load_chip_metadata
from src.core.utils import read_measurement_parquet
from src.plotting.config import PlotConfig
from src.plotting.plot_utils import ensure_standard_columns
from src.plotting.styles import set_plot_style

ENRICHED_HISTORY_DIR = Path("data/03_derived/chip_histories_enriched")
STAGE_HISTORY_DIR = Path("data/02_stage/chip_histories")
DEFAULT_OUTPUT_DIR = Path("figs/compare/first-ivg")

console = Console()


def _lookup_chip_metadata(chip_group: str, chip_number: int) -> dict:
    """Return chip metadata or an empty dict if the chip / group is unknown."""
    try:
        return load_chip_metadata(ChipId(chip_group, chip_number))
    except UnknownChipGroupError:
        return {}


def _resolve_history_path(chip_group: str, chip_number: int) -> Path:
    enriched = ENRICHED_HISTORY_DIR / f"{chip_group}{chip_number}_history.parquet"
    if enriched.exists():
        return enriched
    staged = STAGE_HISTORY_DIR / f"{chip_group}{chip_number}_history.parquet"
    if staged.exists():
        return staged
    raise FileNotFoundError(
        f"No history found for {chip_group}{chip_number}. Looked in:\n"
        f"  {enriched}\n  {staged}\n"
        f"Run: biotite build-all-histories"
    )


def _load_first_ivg(chip_group: str, chip_number: int) -> tuple[np.ndarray, np.ndarray, int]:
    history = pl.read_parquet(_resolve_history_path(chip_group, chip_number))
    ivg = history.filter(pl.col("proc") == "IVg").sort("seq")
    if ivg.height == 0:
        raise ValueError(f"{chip_group}{chip_number}: no IVg measurements in history.")

    first = ivg.row(0, named=True)
    candidate = first.get("parquet_path") or first.get("source_file")
    if not candidate:
        raise ValueError(
            f"{chip_group}{chip_number} seq={first['seq']}: history row has no "
            f"parquet_path or source_file column."
        )
    parquet_path = Path(candidate)
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"{chip_group}{chip_number} seq={first['seq']}: measurement file missing: "
            f"{parquet_path}"
        )

    measurement = ensure_standard_columns(read_measurement_parquet(parquet_path))
    missing = {"VG", "I"} - set(measurement.columns)
    if missing:
        raise ValueError(
            f"{chip_group}{chip_number} seq={first['seq']}: missing columns {missing}. "
            f"Got: {measurement.columns}"
        )

    vg = measurement["VG"].to_numpy()
    i_uA = measurement["I"].to_numpy() * 1e6
    return vg, i_uA, int(first["seq"])


def _parse_chip_list(chips: str) -> list[int]:
    out: list[int] = []
    for tok in chips.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(int(tok))
        except ValueError as e:
            raise typer.BadParameter(f"Invalid chip number: {tok!r}") from e
    if not out:
        raise typer.BadParameter("No chip numbers provided.")
    return out


@cli_command(
    name="compare-first-ivg",
    group="plotting",
    description="Overlay the first IVg sweep of multiple chips on a single figure",
)
def compare_first_ivg(
    chips: str = typer.Argument(
        ...,
        help="Comma-separated chip numbers, e.g. '80,81,72'.",
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name (default: Alisson).",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output PNG path (default: figs/compare/<group_lower>_<n1>_<n2>_..._IVg_first.png).",
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Custom filename tag (replaces the chip-list portion).",
    ),
    theme: Optional[str] = typer.Option(
        None,
        "--theme",
        help="Matplotlib theme override (default: from PlotConfig).",
    ),
):
    """
    Overlay the first IVg sweep of multiple chips.

    Material tags (biotite/hBN/etc.) are read via the chip-metadata loader
    (config/chip_apps.yaml → config/chip_metadata/biotite.yaml).
    Chips not listed are plotted with the chip number only and a warning is printed.

    Examples:
        biotite compare-first-ivg 80,81,72
        biotite compare-first-ivg 67,72,74,75 --group Alisson --tag baseline
    """
    chip_numbers = _parse_chip_list(chips)

    plot_config = PlotConfig()
    set_plot_style(theme or plot_config.theme)

    curves: list[tuple[str, np.ndarray, np.ndarray]] = []
    for n in chip_numbers:
        try:
            vg, i_uA, seq = _load_first_ivg(chip_group, n)
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]error:[/red] {e}")
            raise typer.Exit(1)

        info = _lookup_chip_metadata(chip_group, n)
        material = info.get("material")
        if material:
            label = f"{n} ({material})"
        else:
            reason = "not listed" if not info else "material missing"
            console.print(
                f"[yellow]warning:[/yellow] chip {n} {reason} in chip-metadata "
                f"for group {chip_group!r} — plotting without material tag."
            )
            label = str(n)

        console.print(
            f"[green]✓[/green] {chip_group}{n} seq={seq} n={len(vg)} "
            f"Vg=[{vg.min():.2f}, {vg.max():.2f}] V "
            f"I=[{i_uA.min():.3g}, {i_uA.max():.3g}] µA"
        )
        curves.append((label, vg, i_uA))

    fig, ax = plt.subplots()
    for label, vg, i_uA in curves:
        ax.plot(vg, i_uA, label=label)
    ax.set_xlabel("Gate Voltage $V_g$ (V)")
    ax.set_ylabel("Drain Current $I_d$ (µA)")
    ax.legend(loc="best", framealpha=0.9)
    plt.tight_layout()

    if output is None:
        chip_part = tag or "_".join(str(n) for n in chip_numbers)
        output = DEFAULT_OUTPUT_DIR / f"{chip_group.lower()}_{chip_part}_IVg_first.png"
    output.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(output, dpi=plot_config.dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]saved[/bold green] {output}")
