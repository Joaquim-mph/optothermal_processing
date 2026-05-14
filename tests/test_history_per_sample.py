"""Per-sample chip-history filename behavior.

Covers the additive change in Step 5 of the general-branch migration: when a
chip has multiple registered Samples (graphene-on-SiO2 historic chips), each
sample gets its own history Parquet; biotite chips (sample is null everywhere)
keep the legacy `<group><number>_history.parquet` naming.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from src.core.history_builder import (
    generate_all_chip_histories,
    generate_chip_name,
)
from src.core.history_detection import (
    chip_history_basename,
    detect_history_availability,
    load_chip_history,
)


def test_basename_without_sample():
    assert chip_history_basename("Alisson", 75) == "Alisson75_history"


def test_basename_with_sample():
    assert chip_history_basename("Miguel", 1, "a") == "Miguel1_a_history"


def test_basename_empty_sample_is_legacy():
    assert chip_history_basename("Alisson", 75, "") == "Alisson75_history"
    assert chip_history_basename("Alisson", 75, None) == "Alisson75_history"


def test_generate_chip_name_includes_sample():
    assert generate_chip_name(1, "Miguel", None, sample="a") == "Miguel1_a"
    assert generate_chip_name(1, "Miguel", None, sample=None) == "Miguel1"


def test_detect_routes_to_per_sample_path(tmp_path: Path):
    history_dir = tmp_path / "hist"
    enriched_dir = tmp_path / "enr"
    history_dir.mkdir()
    enriched_dir.mkdir()
    (history_dir / "Miguel1_a_history.parquet").write_bytes(b"")
    has_reg, has_enr, reg_path, enr_path = detect_history_availability(
        1, "Miguel", history_dir, enriched_dir, sample="a"
    )
    assert has_reg is True
    assert has_enr is False
    assert reg_path == history_dir / "Miguel1_a_history.parquet"
    assert enr_path is None


def test_detect_legacy_naming_without_sample(tmp_path: Path):
    history_dir = tmp_path / "hist"
    enriched_dir = tmp_path / "enr"
    history_dir.mkdir()
    enriched_dir.mkdir()
    (history_dir / "Alisson75_history.parquet").write_bytes(b"")
    has_reg, has_enr, reg_path, _ = detect_history_availability(
        75, "Alisson", history_dir, enriched_dir
    )
    assert has_reg is True
    assert reg_path == history_dir / "Alisson75_history.parquet"


def _write_synthetic_manifest(path: Path) -> None:
    """Manifest with two samples (a, b) on Miguel 1 — 5 IVg rows each."""
    rows = []
    base = datetime(2024, 1, 1, 10, 0, 0)
    for sample in ("a", "b"):
        for i in range(5):
            rows.append(
                {
                    "status": "ok",
                    "chip_number": 1,
                    "chip_group": "Miguel",
                    "sample": sample,
                    "proc": "IVg",
                    "start_time_utc": base.replace(
                        minute=i * 5 + (0 if sample == "a" else 30)
                    ).strftime("%Y-%m-%d %H:%M:%S.000000+0000"),
                    "source_file": f"x/y/{sample}_{i}.csv",
                    "information": None,
                    "has_light": False,
                    "summary": f"IVg #{i}",
                }
            )
    pl.DataFrame(rows).write_parquet(path)


def test_per_sample_history_files_are_written(tmp_path: Path):
    manifest = tmp_path / "manifest.parquet"
    _write_synthetic_manifest(manifest)
    out = tmp_path / "histories"

    result = generate_all_chip_histories(
        manifest_path=manifest,
        output_dir=out,
        min_experiments=3,
    )

    assert (out / "Miguel1_a_history.parquet").exists()
    assert (out / "Miguel1_b_history.parquet").exists()
    assert not (out / "Miguel1_history.parquet").exists()
    assert set(result.keys()) == {"Miguel1_a", "Miguel1_b"}


def test_legacy_history_filename_when_sample_all_null(tmp_path: Path):
    """Biotite path: sample column exists but all rows have null sample → legacy naming."""
    manifest = tmp_path / "manifest.parquet"
    rows = []
    base = datetime(2024, 1, 1, 10, 0, 0)
    for i in range(6):
        rows.append(
            {
                "status": "ok",
                "chip_number": 75,
                "chip_group": "Alisson",
                "sample": None,
                "proc": "IVg",
                "start_time_utc": base.replace(minute=i * 5).strftime(
                    "%Y-%m-%d %H:%M:%S.000000+0000"
                ),
                "source_file": f"a/b/{i}.csv",
                "information": None,
                "has_light": False,
                "summary": f"IVg #{i}",
            }
        )
    pl.DataFrame(rows).write_parquet(manifest)
    out = tmp_path / "histories"

    result = generate_all_chip_histories(
        manifest_path=manifest,
        output_dir=out,
        min_experiments=3,
    )

    # Sample is null → no `_<sample>` suffix.
    assert (out / "Alisson75_history.parquet").exists()
    assert result == {"Alisson75": out / "Alisson75_history.parquet"}


def test_load_per_sample_history_round_trips(tmp_path: Path):
    manifest = tmp_path / "manifest.parquet"
    _write_synthetic_manifest(manifest)
    out = tmp_path / "histories"
    generate_all_chip_histories(
        manifest_path=manifest,
        output_dir=out,
        min_experiments=3,
    )
    df, is_enriched = load_chip_history(
        1, "Miguel", out, tmp_path / "missing_enriched", sample="a"
    )
    assert is_enriched is False
    assert df.height == 5
