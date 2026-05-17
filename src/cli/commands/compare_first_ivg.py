"""compare-first-ivg: overlay the first IVg sweep across multiple chips."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Optional

import typer

from src.cli.plugin_system import cli_command

# Palette / linestyle names. Actual color values are resolved from
# src.plotting.shared.styles inside the command body to keep import-time
# cost (matplotlib chain) out of `discover_commands`.
PALETTE_NAMES = ("prism_rain", "deep_rain", "prism_rain_vivid", "minimal", "scientific")
LINESTYLE_SET_NAMES = ("mixed",)

LINESTYLE_SETS = {
    "mixed": ["-", "--", "-.", ":"],
}

ENRICHED_HISTORY_DIR = Path("data/03_derived/chip_histories_enriched")
STAGE_HISTORY_DIR = Path("data/02_stage/chip_histories")
ENCAP_YAML = Path("config/encap_characteristics.yaml")
DEFAULT_OUTPUT_DIR = Path("figs/compare/first-ivg")


def _load_encap_characteristics() -> dict[int, dict]:
    import yaml

    if not ENCAP_YAML.exists():
        return {}
    with ENCAP_YAML.open("r") as f:
        data = yaml.safe_load(f) or {}
    return {int(k): (v or {}) for k, v in data.items() if isinstance(k, int)}


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


def _trim_to_full_sweeps(
    vg: "np.ndarray", i_uA: "np.ndarray", range_fraction: float = 0.9
) -> "tuple[np.ndarray, np.ndarray]":
    """Drop leading/trailing half-sweeps, keep only extremum-to-extremum segments.

    Adjacent full sweeps share their turn-point sample; the duplicate is removed
    so the concatenated trace is a clean hysteresis loop.
    """
    import numpy as np

    from src.plotting.shared.plot_utils import segment_voltage_sweep

    segments = segment_voltage_sweep(vg, i_uA)
    if not segments:
        return vg, i_uA

    total_range = float(vg.max() - vg.min())
    if total_range <= 0:
        return vg, i_uA

    threshold = range_fraction * total_range
    kept = [(v, c) for v, c, _ in segments if (v.max() - v.min()) >= threshold]
    if not kept:
        return vg, i_uA

    vg_parts: list[np.ndarray] = [kept[0][0]]
    i_parts: list[np.ndarray] = [kept[0][1]]
    for v, c in kept[1:]:
        vg_parts.append(v[1:])
        i_parts.append(c[1:])
    return np.concatenate(vg_parts), np.concatenate(i_parts)


def _load_first_ivg(
    chip_group: str, chip_number: int
) -> "tuple[np.ndarray, np.ndarray, int, int]":
    import polars as pl

    from src.core.utils import read_measurement_parquet
    from src.plotting.shared.plot_utils import ensure_standard_columns

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
    n_raw = len(vg)
    vg, i_uA = _trim_to_full_sweeps(vg, i_uA)
    return vg, i_uA, int(first["seq"]), n_raw


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
    palette: Optional[str] = typer.Option(
        None,
        "--palette",
        help=f"Color palette override (one of: {', '.join(PALETTE_NAMES)}). Keeps the theme's format.",
    ),
    linestyle: Optional[str] = typer.Option(
        None,
        "--linestyle",
        help=f"Linestyle cycle preset (one of: {', '.join(LINESTYLE_SET_NAMES)}). Each curve gets the next style.",
    ),
    fmt: Optional[str] = typer.Option(
        None,
        "--format",
        "-f",
        help="Output format: png, pdf, svg, jpg (default: from PlotConfig — png).",
    ),
):
    """
    Overlay the first IVg sweep of multiple chips.

    Material tags (biotite/hBN/etc.) are read from config/encap_characteristics.yaml.
    Chips not listed are plotted with the chip number only and a warning is printed.

    Examples:
        biotite compare-first-ivg 80,81,72
        biotite compare-first-ivg 67,72,74,75 --group Alisson --tag baseline
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from rich.console import Console

    from src.plotting.shared import styles as _styles
    from src.plotting.shared.config import PlotConfig
    from src.plotting.shared.styles import set_plot_style

    console = Console()

    PALETTES = {
        "prism_rain": _styles.PRISM_RAIN_PALETTE,
        "deep_rain": _styles.DEEP_RAIN_PALETTE,
        "prism_rain_vivid": _styles.PRISM_RAIN_PALETTE_VIVID,
        "minimal": _styles.MINIMAL_PALETTE,
        "scientific": _styles.SCIENTIFIC_PALETTE,
    }

    chip_numbers = _parse_chip_list(chips)
    encap = _load_encap_characteristics()

    plot_config = PlotConfig()
    set_plot_style(theme or plot_config.theme)

    if palette is not None:
        key = palette.lower()
        if key not in PALETTES:
            raise typer.BadParameter(
                f"Unknown palette {palette!r}. Choose from: {', '.join(PALETTES)}"
            )
        plt.rcParams["axes.prop_cycle"] = plt.cycler(color=PALETTES[key])

    style_iter = None
    if linestyle is not None:
        ls_key = linestyle.lower()
        if ls_key not in LINESTYLE_SETS:
            raise typer.BadParameter(
                f"Unknown linestyle preset {linestyle!r}. Choose from: {', '.join(LINESTYLE_SETS)}"
            )
        style_iter = itertools.cycle(LINESTYLE_SETS[ls_key])

    allowed_formats = {"png", "pdf", "svg", "jpg"}
    resolved_fmt = (fmt or plot_config.format).lower()
    if resolved_fmt not in allowed_formats:
        raise typer.BadParameter(
            f"Unknown format {fmt!r}. Choose from: {', '.join(sorted(allowed_formats))}"
        )

    curves: list[tuple[str, np.ndarray, np.ndarray]] = []
    for n in chip_numbers:
        try:
            vg, i_uA, seq, n_raw = _load_first_ivg(chip_group, n)
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]error:[/red] {e}")
            raise typer.Exit(1)

        info = encap.get(n)
        material = (info or {}).get("material")
        if material:
            label = f"{n} ({material})"
        else:
            reason = "not listed" if info is None else "material missing"
            console.print(
                f"[yellow]warning:[/yellow] chip {n} {reason} in {ENCAP_YAML} "
                f"— plotting without material tag."
            )
            label = str(n)

        console.print(
            f"[green]✓[/green] {chip_group}{n} seq={seq} n={len(vg)}/{n_raw} "
            f"Vg=[{vg.min():.2f}, {vg.max():.2f}] V "
            f"I=[{i_uA.min():.3g}, {i_uA.max():.3g}] µA"
        )
        curves.append((label, vg, i_uA))

    fig, ax = plt.subplots()
    for label, vg, i_uA in curves:
        kwargs = {"linestyle": next(style_iter)} if style_iter is not None else {}
        ax.plot(vg, i_uA, label=label, **kwargs)
    ax.set_xlabel("$V_g$ (V)")
    ax.set_ylabel(r"$I_{ds}$ (µA)")
    ax.legend(loc="best", framealpha=0.9)
    plt.tight_layout()

    if output is None:
        chip_part = tag or "_".join(str(n) for n in chip_numbers)
        output = (
            DEFAULT_OUTPUT_DIR
            / f"{chip_group.lower()}_{chip_part}_IVg_first.{resolved_fmt}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(output, dpi=plot_config.dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]saved[/bold green] {output}")
