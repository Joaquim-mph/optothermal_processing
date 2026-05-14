"""Variadic chip-identifier CLI helpers.

Provides a single way for plot/analysis commands to accept chip identity:

    graphene plot-its 75              # default group
    graphene plot-its Alisson 75      # explicit group
    graphene plot-its Miguel 1 a      # fully qualified (group, number, sample)
    graphene plot-its Miguel 1 --list-samples

Use ``CHIP_ARG`` for the Typer positional and ``LIST_SAMPLES_OPTION`` for the
discovery flag, then call ``resolve_chip_cli_args`` inside the command.
"""

from __future__ import annotations

import typer

from src.core.chip_metadata import (
    AmbiguousSampleError,
    ChipId,
    UnknownChipGroupError,
    list_samples,
    resolve_chip_id,
)

CHIP_ARG_HELP = (
    "Chip identifier. One of:\n"
    "  NUMBER                  -> uses default group\n"
    "  GROUP NUMBER            -> explicit group\n"
    "  GROUP NUMBER SAMPLE     -> fully qualified"
)


CHIP_ARG = typer.Argument(
    ...,
    help=CHIP_ARG_HELP,
    metavar="CHIP...",
)


LIST_SAMPLES_OPTION = typer.Option(
    False,
    "--list-samples",
    help="Print registered samples for the given (group, number) and exit.",
)


def resolve_chip_cli_args(
    chip: list[str],
    list_samples_flag: bool = False,
) -> ChipId:
    """Resolve variadic chip CLI args.

    If ``list_samples_flag`` is set, prints the samples and exits 0.
    Otherwise returns a ChipId (sample inferred or fully qualified).
    Surfaces ambiguity errors as typer.BadParameter for clean CLI exit.
    """
    if not chip:
        raise typer.BadParameter("chip identifier required (see --help)")

    if list_samples_flag:
        chip = list(chip)
        group: str
        number: int
        if len(chip) == 1:
            from src.core.chip_metadata import load_chip_apps_config
            group = load_chip_apps_config().default_chip_group
            number = _parse_int(chip[0])
        elif len(chip) >= 2:
            group = chip[0]
            number = _parse_int(chip[1])
        try:
            samples = list_samples(group, number)
        except UnknownChipGroupError as exc:
            raise typer.BadParameter(str(exc))
        if not samples:
            typer.echo(f"{group} {number}: no samples registered")
        else:
            typer.echo(f"{group} {number} samples: {','.join(samples)}")
        raise typer.Exit(code=0)

    try:
        return resolve_chip_id(list(chip))
    except AmbiguousSampleError as exc:
        raise typer.BadParameter(str(exc))
    except ValueError as exc:
        raise typer.BadParameter(str(exc))


def _parse_int(arg: str) -> int:
    try:
        return int(arg)
    except ValueError as exc:
        raise typer.BadParameter(f"Expected chip number, got {arg!r}") from exc
