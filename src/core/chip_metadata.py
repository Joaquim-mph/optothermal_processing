"""Chip-app metadata loader.

Chip identity is a (group, number, sample) triple. The mapping from a chip
group to its physical-architecture metadata file (geometry, dielectric stack)
is configured in ``config/chip_apps.yaml`` — different apps host different
chip families (biotite vs graphene-on-SiO2 legacy, etc.).

This module is read-only and side-effect free apart from filesystem reads
of the config files. It has no callers yet; callers will be wired in
subsequent migration steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHIP_APPS_FILE = PROJECT_ROOT / "config" / "chip_apps.yaml"


@dataclass(frozen=True)
class ChipId:
    group: str
    number: int
    sample: str | None = None

    def __str__(self) -> str:
        base = f"{self.group}{self.number}"
        return f"{base}_{self.sample}" if self.sample else base


class ChipMetadataError(Exception):
    """Base class for chip-metadata resolution errors."""


class AmbiguousSampleError(ChipMetadataError):
    def __init__(self, group: str, number: int, samples: list[str]):
        self.group = group
        self.number = number
        self.samples = samples
        example = samples[0] if samples else "<sample>"
        super().__init__(
            f"{group} {number} has samples {','.join(samples)}. "
            f"Specify one, e.g. '{group} {number} {example}'."
        )


class UnknownChipGroupError(ChipMetadataError):
    """Raised when a chip group is not registered with any app."""


@dataclass(frozen=True)
class AppConfig:
    name: str
    chip_groups: tuple[str, ...]
    metadata_file: Path
    schema: str  # "per_chip" | "per_sample"


@dataclass(frozen=True)
class ChipAppsConfig:
    default_chip_group: str
    apps: tuple[AppConfig, ...]

    def app_for_group(self, group: str) -> AppConfig:
        for app in self.apps:
            if group in app.chip_groups:
                return app
        raise UnknownChipGroupError(
            f"No app registered for chip group {group!r}. "
            f"Add it under apps.<name>.chip_groups in chip_apps.yaml."
        )


def load_chip_apps_config(path: Path = CHIP_APPS_FILE) -> ChipAppsConfig:
    data = yaml.safe_load(path.read_text()) or {}
    if "default_chip_group" not in data:
        raise ChipMetadataError(
            f"{path} missing required key 'default_chip_group'"
        )
    apps_data = data.get("apps") or {}
    apps = tuple(
        AppConfig(
            name=name,
            chip_groups=tuple(spec.get("chip_groups") or []),
            metadata_file=_resolve_path(spec["metadata_file"], path.parent),
            schema=spec["schema"],
        )
        for name, spec in apps_data.items()
    )
    return ChipAppsConfig(
        default_chip_group=data["default_chip_group"],
        apps=apps,
    )


def _resolve_path(p: str, base: Path) -> Path:
    raw = Path(p)
    if raw.is_absolute():
        return raw
    # `config/chip_metadata/foo.yaml` is interpreted relative to project root,
    # i.e. the directory above the chip_apps.yaml file.
    return (base.parent / raw).resolve()


def _read_metadata_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def _number_block(data: dict[str, Any], group: str, number: int) -> dict[str, Any]:
    return ((data.get("chips") or {}).get(group) or {}).get(number) or {}


def list_samples(
    group: str,
    number: int,
    *,
    config: ChipAppsConfig | None = None,
) -> list[str]:
    """Return registered sample names for a (group, number), sorted."""
    cfg = config or load_chip_apps_config()
    app = cfg.app_for_group(group)
    if app.schema == "per_chip":
        return []
    block = _number_block(_read_metadata_file(app.metadata_file), group, number)
    if "samples" in block:
        return sorted(block["samples"].keys())
    if "geometry_pairs" in block:
        out: list[str] = []
        for pair in block["geometry_pairs"]:
            out.extend(pair.get("samples") or [])
        return sorted(out)
    return []


def resolve_chip_id(
    args: list[str],
    *,
    config: ChipAppsConfig | None = None,
) -> ChipId:
    """Parse CLI positionals into a ChipId, inferring sample when unambiguous.

    Accepts:
      [number]                          -> (default_group, number, inferred)
      [group, number]                   -> (group, number, inferred)
      [group, number, sample]           -> fully qualified

    Raises ``AmbiguousSampleError`` when the app schema is per_sample and the
    chip has >1 registered sample but none was supplied.
    """
    cfg = config or load_chip_apps_config()
    if not args:
        raise ValueError("No chip identifier provided")

    sample: str | None = None
    if len(args) == 1:
        group = cfg.default_chip_group
        number = _parse_number(args[0])
    elif len(args) == 2:
        group = args[0]
        number = _parse_number(args[1])
    elif len(args) == 3:
        group = args[0]
        number = _parse_number(args[1])
        sample = args[2]
    else:
        raise ValueError(f"Too many chip arguments: {args!r}")

    if sample is None:
        try:
            app = cfg.app_for_group(group)
        except UnknownChipGroupError:
            return ChipId(group, number, None)
        if app.schema == "per_sample":
            samples = list_samples(group, number, config=cfg)
            if len(samples) == 1:
                sample = samples[0]
            elif len(samples) > 1:
                raise AmbiguousSampleError(group, number, samples)
    return ChipId(group, number, sample)


def _parse_number(arg: str) -> int:
    try:
        return int(arg)
    except ValueError as exc:
        raise ValueError(f"Expected chip number, got {arg!r}") from exc


def load_chip_metadata(
    chip: ChipId,
    *,
    config: ChipAppsConfig | None = None,
) -> dict[str, Any]:
    """Return merged metadata dict for a ChipId.

    For per_chip apps: returns the (group, number) block verbatim.
    For per_sample apps: returns chip-level fields merged with sample-level
    fields (sample-level wins), with ``samples`` / ``geometry_pairs``
    structural keys stripped.
    """
    cfg = config or load_chip_apps_config()
    app = cfg.app_for_group(chip.group)
    block = _number_block(_read_metadata_file(app.metadata_file), chip.group, chip.number)
    if app.schema == "per_chip":
        return dict(block)

    chip_level = {
        k: v for k, v in block.items() if k not in ("samples", "geometry_pairs")
    }
    if chip.sample is None:
        return chip_level

    sample_level: dict[str, Any] = {}
    if "samples" in block:
        sample_level = dict(block["samples"].get(chip.sample) or {})
    elif "geometry_pairs" in block:
        for pair in block["geometry_pairs"]:
            if chip.sample in (pair.get("samples") or []):
                sample_level = {
                    k: v for k, v in pair.items() if k != "samples"
                }
                break
    return {**chip_level, **sample_level}
