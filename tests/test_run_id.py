#!/usr/bin/env python3
"""
Tests for the intrinsic `run_id` computation.

`run_id` identifies a measurement by its own contents (procedure, chip,
start time, data-block bytes) rather than by the source file's path. These
tests pin down the properties that matter:
- determinism (same inputs -> same id)
- path-independence (id does not depend on where the file lives)
- content-sensitivity (id changes when the data changes)
- timestamp-sensitivity (id changes when the start time changes)
- null-chip tolerance (LaserCalibration has no chip)
"""

import datetime as dt

import polars as pl

from src.core.stage_utils import compute_run_id, content_hash, normalize_timestamp


def _df(values=(1.0, 2.0, 3.0)):
    return pl.DataFrame({"Vg (V)": [0.0, 1.0, 2.0], "I (A)": list(values)})


START = dt.datetime(2026, 5, 4, 21, 4, 1, tzinfo=dt.timezone.utc)


def test_deterministic():
    a = compute_run_id("IVg", "Alisson", 80, START, _df())
    b = compute_run_id("IVg", "Alisson", 80, START, _df())
    assert a == b
    assert len(a) == 16


def test_path_independent():
    # The source path is not an input at all -- identical measurement
    # contents must yield an identical id regardless of file location.
    a = compute_run_id("IVg", "Alisson", 80, START, _df())
    b = compute_run_id("IVg", "Alisson", 80, START, _df())
    assert a == b


def test_content_sensitive():
    base = compute_run_id("IVg", "Alisson", 80, START, _df())
    perturbed = compute_run_id("IVg", "Alisson", 80, START, _df((1.0, 2.0, 3.5)))
    assert base != perturbed


def test_timestamp_sensitive():
    later = START + dt.timedelta(seconds=1)
    assert compute_run_id("IVg", "Alisson", 80, START, _df()) != compute_run_id(
        "IVg", "Alisson", 80, later, _df()
    )


def test_chip_sensitive():
    assert compute_run_id("IVg", "Alisson", 80, START, _df()) != compute_run_id(
        "IVg", "Alisson", 81, START, _df()
    )


def test_null_chip_ok():
    rid = compute_run_id("LaserCalibration", None, None, START, _df())
    assert isinstance(rid, str) and len(rid) == 16


def test_normalize_timestamp_is_utc_and_stable():
    # A non-UTC datetime must normalize to the same string as its UTC form.
    naive_other_tz = START.astimezone(dt.timezone(dt.timedelta(hours=-4)))
    assert normalize_timestamp(naive_other_tz) == normalize_timestamp(START)
    assert normalize_timestamp(START) == "2026-05-04T21:04:01.000000"


def test_content_hash_deterministic():
    assert content_hash(_df()) == content_hash(_df())
    assert content_hash(_df()) != content_hash(_df((9.0, 9.0, 9.0)))
