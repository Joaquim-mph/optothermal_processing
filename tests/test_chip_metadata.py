"""Tests for src.core.chip_metadata loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.core.chip_metadata import (
    AmbiguousSampleError,
    AppConfig,
    ChipAppsConfig,
    ChipId,
    UnknownChipGroupError,
    list_samples,
    load_chip_apps_config,
    load_chip_metadata,
    resolve_chip_id,
)


@pytest.fixture
def biotite_md_file(tmp_path: Path) -> Path:
    p = tmp_path / "biotite.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "schema": "per_chip",
                "chips": {
                    "Alisson": {
                        75: {"top_hBN_nm": 30, "bottom_dielectric_nm": 285},
                    }
                },
            }
        )
    )
    return p


@pytest.fixture
def sio2_md_file(tmp_path: Path) -> Path:
    p = tmp_path / "sio2_legacy.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "schema": "per_sample",
                "chips": {
                    "Miguel": {
                        1: {
                            "sio2_thickness_nm": 285,
                            "al2o3_thickness_nm": 30,
                            "geometry_pairs": [
                                {"samples": ["a", "b"], "width_um": 10, "length_um": 5},
                                {"samples": ["c", "d"], "width_um": 20, "length_um": 5},
                            ],
                        },
                        2: {
                            "sio2_thickness_nm": 100,
                            "samples": {
                                "x": {"width_um": 5, "length_um": 5},
                            },
                        },
                    }
                },
            }
        )
    )
    return p


@pytest.fixture
def config(biotite_md_file: Path, sio2_md_file: Path) -> ChipAppsConfig:
    return ChipAppsConfig(
        default_chip_group="Alisson",
        apps=(
            AppConfig(
                name="biotite",
                chip_groups=("Alisson",),
                metadata_file=biotite_md_file,
                schema="per_chip",
            ),
            AppConfig(
                name="sio2_legacy",
                chip_groups=("Miguel",),
                metadata_file=sio2_md_file,
                schema="per_sample",
            ),
        ),
    )


def test_resolve_single_arg_uses_default_group(config):
    chip = resolve_chip_id(["75"], config=config)
    assert chip == ChipId("Alisson", 75, None)


def test_resolve_two_args_explicit_group(config):
    chip = resolve_chip_id(["Alisson", "75"], config=config)
    assert chip == ChipId("Alisson", 75, None)


def test_resolve_three_args_fully_qualified(config):
    chip = resolve_chip_id(["Miguel", "1", "a"], config=config)
    assert chip == ChipId("Miguel", 1, "a")


def test_resolve_infers_single_sample(config):
    chip = resolve_chip_id(["Miguel", "2"], config=config)
    assert chip == ChipId("Miguel", 2, "x")


def test_resolve_ambiguous_sample_raises_with_listing(config):
    with pytest.raises(AmbiguousSampleError) as exc_info:
        resolve_chip_id(["Miguel", "1"], config=config)
    err = exc_info.value
    assert err.group == "Miguel"
    assert err.number == 1
    assert err.samples == ["a", "b", "c", "d"]
    assert "Miguel 1" in str(err)
    assert "a" in str(err)


def test_resolve_unknown_group_returns_chip_without_sample(config):
    chip = resolve_chip_id(["Wat", "9"], config=config)
    assert chip == ChipId("Wat", 9, None)


def test_resolve_rejects_non_numeric(config):
    with pytest.raises(ValueError, match="chip number"):
        resolve_chip_id(["Alisson", "abc"], config=config)


def test_resolve_rejects_empty(config):
    with pytest.raises(ValueError, match="No chip identifier"):
        resolve_chip_id([], config=config)


def test_resolve_rejects_too_many_args(config):
    with pytest.raises(ValueError, match="Too many"):
        resolve_chip_id(["a", "1", "b", "c"], config=config)


def test_list_samples_per_chip_returns_empty(config):
    assert list_samples("Alisson", 75, config=config) == []


def test_list_samples_geometry_pairs(config):
    assert list_samples("Miguel", 1, config=config) == ["a", "b", "c", "d"]


def test_list_samples_explicit_samples_block(config):
    assert list_samples("Miguel", 2, config=config) == ["x"]


def test_list_samples_unknown_chip_returns_empty(config):
    assert list_samples("Miguel", 99, config=config) == []


def test_list_samples_unknown_group_raises(config):
    with pytest.raises(UnknownChipGroupError):
        list_samples("Wat", 1, config=config)


def test_load_metadata_per_chip(config):
    md = load_chip_metadata(ChipId("Alisson", 75), config=config)
    assert md == {"top_hBN_nm": 30, "bottom_dielectric_nm": 285}


def test_load_metadata_per_sample_geometry_pairs(config):
    md = load_chip_metadata(ChipId("Miguel", 1, "a"), config=config)
    assert md["sio2_thickness_nm"] == 285
    assert md["al2o3_thickness_nm"] == 30
    assert md["width_um"] == 10
    assert md["length_um"] == 5
    # paired sample 'b' shares the same geometry as 'a'
    assert load_chip_metadata(ChipId("Miguel", 1, "b"), config=config) == md
    # 'c' is a different pair
    md_c = load_chip_metadata(ChipId("Miguel", 1, "c"), config=config)
    assert md_c["width_um"] == 20


def test_load_metadata_per_sample_explicit_block(config):
    md = load_chip_metadata(ChipId("Miguel", 2, "x"), config=config)
    assert md == {"sio2_thickness_nm": 100, "width_um": 5, "length_um": 5}


def test_load_metadata_per_sample_no_sample_returns_chip_level(config):
    md = load_chip_metadata(ChipId("Miguel", 1, None), config=config)
    assert md == {"sio2_thickness_nm": 285, "al2o3_thickness_nm": 30}


def test_load_metadata_unknown_sample_returns_chip_level_only(config):
    md = load_chip_metadata(ChipId("Miguel", 1, "zzz"), config=config)
    assert md == {"sio2_thickness_nm": 285, "al2o3_thickness_nm": 30}


def test_chip_id_str():
    assert str(ChipId("Alisson", 75)) == "Alisson75"
    assert str(ChipId("Miguel", 1, "a")) == "Miguel1_a"


def test_load_chip_apps_config_reads_real_file():
    cfg = load_chip_apps_config()
    assert cfg.default_chip_group == "Alisson"
    app_names = {a.name for a in cfg.apps}
    assert "biotite" in app_names
    assert "sio2_legacy" in app_names
    biotite = next(a for a in cfg.apps if a.name == "biotite")
    assert "Alisson" in biotite.chip_groups
    assert biotite.schema == "per_chip"


def test_app_for_group_raises_for_unknown(config):
    with pytest.raises(UnknownChipGroupError):
        config.app_for_group("Nope")
