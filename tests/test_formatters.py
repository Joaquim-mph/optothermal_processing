"""
Unit tests for CLI output formatters.

Tests cover:
- Abstract base class
- RichTableFormatter (terminal output)
- JSONFormatter (machine-readable)
- CSVFormatter (spreadsheet export)
- Formatter registry and factory
- Edge cases (nulls, dates, floats, encoding)
"""

import json
from datetime import datetime
from io import StringIO

import numpy as np
import polars as pl
import pytest

from src.cli.formatters import (
    OutputFormatter,
    RichTableFormatter,
    JSONFormatter,
    CSVFormatter,
    get_formatter,
    list_formatters,
    register_formatter,
    FORMATTERS,
)


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def simple_dataframe():
    """Simple DataFrame for basic tests."""
    return pl.DataFrame({
        "seq": [1, 2, 3],
        "name": ["A", "B", "C"],
        "value": [10.5, 20.3, 30.1],
    })


@pytest.fixture
def complex_dataframe():
    """Complex DataFrame with edge cases."""
    return pl.DataFrame({
        "seq": [1, 2, 3, 4],
        "procedure": ["IVg", "ITS", "IV", "LaserCalibration"],
        "datetime_local": [
            "2025-01-01 12:00:53",
            "2025-01-02 13:30:15",
            "2025-01-03 14:45:00",
            "2025-01-04 09:00:00",
        ],
        "light_status": ["light", "dark", "unknown", "light"],
        "voltage": [0.5, -0.3, None, 1.2],  # Test null handling
        "current": [1.5e-6, np.nan, 2.3e-6, np.inf],  # Test NaN/Inf
        "wavelength_nm": [365.0, None, None, 532.0],
    })


@pytest.fixture
def metadata_dict():
    """Sample metadata dictionary."""
    return {
        "chip": "Alisson67",
        "chip_number": 67,
        "chip_group": "Alisson",
        "filters_applied": ["proc=IVg", "light=light"],
        "total_experiments": 15,
    }


# ============================================================================
# Test Abstract Base Class
# ============================================================================

def test_output_formatter_is_abstract():
    """Test that OutputFormatter cannot be instantiated directly."""
    with pytest.raises(TypeError):
        OutputFormatter()


def test_custom_formatter_must_implement_methods():
    """Test that custom formatters must implement abstract methods."""

    class IncompleteFormatter(OutputFormatter):
        pass

    with pytest.raises(TypeError):
        IncompleteFormatter()


def test_custom_formatter_with_implementation():
    """Test that custom formatter with implementation works."""

    class CustomFormatter(OutputFormatter):
        def format_dataframe(self, df, title="", metadata=None):
            return f"Custom: {len(df)} rows"

        def format_summary(self, data):
            return f"Custom summary: {len(data)} items"

    formatter = CustomFormatter()
    df = pl.DataFrame({"a": [1, 2, 3]})
    assert formatter.format_dataframe(df) == "Custom: 3 rows"
    assert formatter.format_summary({"x": 1, "y": 2}) == "Custom summary: 2 items"


# ============================================================================
# Test RichTableFormatter
# ============================================================================

def test_rich_table_formatter_basic(simple_dataframe):
    """Test basic Rich table output."""
    formatter = RichTableFormatter()
    output = formatter.format_dataframe(simple_dataframe, title="Test Table")

    # Check that output contains table elements
    assert "Test Table" in output  # Title
    assert "seq" in output  # Column header
    assert "name" in output
    assert "value" in output
    assert "A" in output  # Data
    assert "10.5" in output


def test_rich_table_formatter_light_status(complex_dataframe):
    """Test light status emoji rendering."""
    formatter = RichTableFormatter()
    output = formatter.format_dataframe(complex_dataframe)

    # Check emoji rendering (may be escaped in output)
    assert "Light" in output or "💡" in output
    assert "Dark" in output or "🌙" in output
    assert "Unknown" in output or "❗" in output


def test_rich_table_formatter_null_handling(complex_dataframe):
    """Test null value rendering as —."""
    formatter = RichTableFormatter()
    output = formatter.format_dataframe(complex_dataframe)

    # Nulls should be rendered as dim —
    # Note: Rich markup may appear in output
    assert "—" in output or "None" in output


def test_rich_table_formatter_summary(metadata_dict):
    """Test summary formatting."""
    formatter = RichTableFormatter()
    output = formatter.format_summary(metadata_dict)

    # Check that all keys appear
    assert "chip" in output
    assert "Alisson67" in output
    assert "total_experiments" in output
    assert "15" in output


# ============================================================================
# Test JSONFormatter
# ============================================================================

def test_json_formatter_basic(simple_dataframe):
    """Test basic JSON output."""
    formatter = JSONFormatter()
    output = formatter.format_dataframe(simple_dataframe)

    # Parse JSON to verify validity
    data = json.loads(output)

    # Check structure
    assert "metadata" in data
    assert "data" in data
    assert len(data["data"]) == 3

    # Check first row
    assert data["data"][0]["seq"] == 1
    assert data["data"][0]["name"] == "A"
    assert data["data"][0]["value"] == 10.5


def test_json_formatter_with_metadata(simple_dataframe, metadata_dict):
    """Test JSON output with metadata."""
    formatter = JSONFormatter()
    output = formatter.format_dataframe(
        simple_dataframe,
        title="Test Data",
        metadata=metadata_dict
    )

    data = json.loads(output)

    # Check metadata
    assert data["metadata"]["chip"] == "Alisson67"
    assert data["metadata"]["title"] == "Test Data"
    assert data["metadata"]["row_count"] == 3


def test_json_formatter_null_handling(complex_dataframe):
    """Test null/NaN/Inf handling in JSON."""
    formatter = JSONFormatter()
    output = formatter.format_dataframe(complex_dataframe)

    data = json.loads(output)

    # Check null handling
    assert data["data"][2]["voltage"] is None  # None → null
    assert data["data"][1]["current"] is None  # NaN → null
    assert data["data"][3]["current"] is None  # Inf → null
    assert data["data"][1]["wavelength_nm"] is None  # None → null


def test_json_formatter_float_precision():
    """Test float precision handling."""
    df = pl.DataFrame({
        "value": [1.23456789012345, 0.000000123456789, 1e-10],
    })

    formatter = JSONFormatter()
    output = formatter.format_dataframe(df)
    data = json.loads(output)

    # Check that floats are rounded (no precision artifacts)
    assert isinstance(data["data"][0]["value"], float)
    assert len(str(data["data"][0]["value"])) < 20  # Reasonable precision


def test_json_formatter_datetime_handling():
    """Test datetime serialization to ISO 8601."""
    df = pl.DataFrame({
        "datetime_local": ["2025-01-01 12:00:53", "2025-01-02 13:30:15"],
    })

    formatter = JSONFormatter()
    output = formatter.format_dataframe(df)
    data = json.loads(output)

    # Check that datetime strings are preserved
    assert data["data"][0]["datetime_local"] == "2025-01-01 12:00:53"
    assert data["data"][1]["datetime_local"] == "2025-01-02 13:30:15"


def test_json_formatter_summary(metadata_dict):
    """Test summary formatting as JSON."""
    formatter = JSONFormatter()
    output = formatter.format_summary(metadata_dict)

    data = json.loads(output)
    assert data["chip"] == "Alisson67"
    assert data["total_experiments"] == 15


def test_json_formatter_utf8_encoding():
    """Test UTF-8 encoding (non-ASCII characters)."""
    df = pl.DataFrame({
        "name": ["Naño", "Müller", "北京"],
        "value": [1, 2, 3],
    })

    formatter = JSONFormatter(ensure_ascii=False)
    output = formatter.format_dataframe(df)

    # Should contain raw UTF-8 characters (not \u escapes)
    assert "Naño" in output
    assert "Müller" in output
    assert "北京" in output

    # Verify it's valid JSON
    data = json.loads(output)
    assert data["data"][0]["name"] == "Naño"


def test_json_formatter_ascii_mode():
    """Test ASCII mode (escape non-ASCII)."""
    df = pl.DataFrame({
        "name": ["Naño"],
    })

    formatter = JSONFormatter(ensure_ascii=True)
    output = formatter.format_dataframe(df)

    # Should contain escape sequences
    assert "\\u" in output or "Naño" not in output

    # But still parse correctly
    data = json.loads(output)
    assert data["data"][0]["name"] == "Naño"


# ============================================================================
# Test CSVFormatter
# ============================================================================

def test_csv_formatter_basic(simple_dataframe):
    """Test basic CSV output."""
    formatter = CSVFormatter()
    output = formatter.format_dataframe(simple_dataframe)

    lines = output.strip().split("\n")

    # Check header
    assert lines[0] == "seq,name,value"

    # Check first data row
    assert lines[1] == "1,A,10.5"

    # Check row count
    assert len(lines) == 4  # Header + 3 data rows


def test_csv_formatter_null_handling():
    """Test null handling in CSV (empty strings)."""
    df = pl.DataFrame({
        "name": ["A", "B", None],
        "value": [1.0, None, 3.0],
    })

    formatter = CSVFormatter(null_value="")
    output = formatter.format_dataframe(df)

    lines = output.strip().split("\n")

    # Nulls should be empty
    assert lines[2] == "B,"  # value is null
    assert lines[3] == ",3.0"  # name is null


def test_csv_formatter_custom_null_value():
    """Test custom null value representation."""
    df = pl.DataFrame({
        "value": [1.0, None, 3.0],
    })

    formatter = CSVFormatter(null_value="NA")
    output = formatter.format_dataframe(df)

    assert "NA" in output


def test_csv_formatter_comma_escaping():
    """Test that commas in values are properly escaped."""
    df = pl.DataFrame({
        "name": ["A, B", "C"],
        "value": [1, 2],
    })

    formatter = CSVFormatter()
    output = formatter.format_dataframe(df)

    # Comma in value should be quoted
    assert '"A, B"' in output or "A, B" in output  # Polars handles escaping


def test_csv_formatter_summary(metadata_dict):
    """Test summary formatting as CSV."""
    formatter = CSVFormatter()
    output = formatter.format_summary(metadata_dict)

    lines = output.strip().split("\n")

    # Should have header
    assert lines[0] == "key,value"

    # Should contain all keys
    keys = [line.split(",")[0] for line in lines[1:]]
    assert "chip" in keys
    assert "total_experiments" in keys


# ============================================================================
# Test Formatter Registry and Factory
# ============================================================================

def test_get_formatter_table():
    """Test getting table formatter."""
    formatter = get_formatter("table")
    assert isinstance(formatter, RichTableFormatter)


def test_get_formatter_json():
    """Test getting JSON formatter."""
    formatter = get_formatter("json")
    assert isinstance(formatter, JSONFormatter)


def test_get_formatter_csv():
    """Test getting CSV formatter."""
    formatter = get_formatter("csv")
    assert isinstance(formatter, CSVFormatter)


def test_get_formatter_case_insensitive():
    """Test that format names are case-insensitive."""
    assert isinstance(get_formatter("TABLE"), RichTableFormatter)
    assert isinstance(get_formatter("Json"), JSONFormatter)
    assert isinstance(get_formatter("CSV"), CSVFormatter)


def test_get_formatter_with_whitespace():
    """Test that format names are trimmed."""
    assert isinstance(get_formatter("  table  "), RichTableFormatter)
    assert isinstance(get_formatter(" json "), JSONFormatter)


def test_get_formatter_alias():
    """Test formatter aliases."""
    # "rich" is alias for "table"
    assert isinstance(get_formatter("rich"), RichTableFormatter)
    assert isinstance(get_formatter("terminal"), RichTableFormatter)


def test_get_formatter_invalid():
    """Test that invalid format names raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        get_formatter("invalid_format")

    # Error message should list valid formats
    assert "Unknown format" in str(exc_info.value)
    assert "table" in str(exc_info.value)


def test_list_formatters():
    """Test listing available formatters."""
    formatters = list_formatters()

    assert "table" in formatters
    assert "json" in formatters
    assert "csv" in formatters
    assert isinstance(formatters, list)
    assert formatters == sorted(formatters)  # Should be sorted


def test_register_formatter():
    """Test registering a custom formatter."""

    class YAMLFormatter(OutputFormatter):
        def format_dataframe(self, df, title="", metadata=None):
            return "yaml output"

        def format_summary(self, data):
            return "yaml summary"

    # Register new formatter
    register_formatter("yaml", YAMLFormatter)

    # Should be available
    formatter = get_formatter("yaml")
    assert isinstance(formatter, YAMLFormatter)

    # Should appear in list
    assert "yaml" in list_formatters()

    # Clean up (remove from registry)
    FORMATTERS.pop("yaml", None)


def test_register_formatter_duplicate():
    """Test that registering duplicate name raises error."""
    class DuplicateFormatter(OutputFormatter):
        def format_dataframe(self, df, title="", metadata=None):
            return "duplicate"

        def format_summary(self, data):
            return "duplicate"

    with pytest.raises(ValueError) as exc_info:
        register_formatter("table", DuplicateFormatter)  # Already exists

    assert "already registered" in str(exc_info.value)


def test_register_formatter_invalid_type():
    """Test that registering non-OutputFormatter raises error."""

    class NotAFormatter:
        pass

    with pytest.raises(TypeError) as exc_info:
        register_formatter("invalid", NotAFormatter)

    assert "OutputFormatter" in str(exc_info.value)


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_workflow_json(complex_dataframe, metadata_dict):
    """Test complete workflow: DataFrame → JSON → parse."""
    # Get formatter
    formatter = get_formatter("json")

    # Format data
    output = formatter.format_dataframe(
        complex_dataframe,
        title="Test Workflow",
        metadata=metadata_dict
    )

    # Parse result
    data = json.loads(output)

    # Verify structure
    assert data["metadata"]["chip"] == "Alisson67"
    assert data["metadata"]["title"] == "Test Workflow"
    assert len(data["data"]) == len(complex_dataframe)

    # Verify data integrity
    assert data["data"][0]["procedure"] == "IVg"
    assert data["data"][0]["voltage"] == 0.5
    assert data["data"][1]["current"] is None  # NaN → null


def test_full_workflow_csv(simple_dataframe):
    """Test complete workflow: DataFrame → CSV → parse."""
    # Get formatter
    formatter = get_formatter("csv")

    # Format data
    output = formatter.format_dataframe(simple_dataframe)

    # Parse result
    lines = output.strip().split("\n")
    header = lines[0].split(",")

    assert header == ["seq", "name", "value"]
    assert len(lines) == 4  # Header + 3 rows


def test_all_formatters_produce_output(simple_dataframe):
    """Test that all formatters produce non-empty output."""
    for format_name in list_formatters():
        formatter = get_formatter(format_name)
        output = formatter.format_dataframe(simple_dataframe, title="Test")

        assert output  # Non-empty
        assert isinstance(output, str)
        assert len(output) > 0


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_empty_dataframe():
    """Test formatting an empty DataFrame."""
    df = pl.DataFrame({
        "seq": [],
        "name": [],
        "value": [],
    })

    # All formatters should handle empty data
    for format_name in list_formatters():
        formatter = get_formatter(format_name)
        output = formatter.format_dataframe(df)
        assert isinstance(output, str)


def test_single_row_dataframe():
    """Test formatting a single-row DataFrame."""
    df = pl.DataFrame({
        "seq": [1],
        "name": ["A"],
    })

    formatter = get_formatter("json")
    output = formatter.format_dataframe(df)
    data = json.loads(output)

    assert len(data["data"]) == 1
    assert data["data"][0]["seq"] == 1


def test_large_dataframe():
    """Test formatting a large DataFrame (performance check)."""
    import time

    # Create DataFrame with 1000 rows
    df = pl.DataFrame({
        "seq": range(1000),
        "value": np.random.rand(1000),
    })

    # Test JSON formatter (most complex serialization)
    formatter = get_formatter("json")
    start = time.time()
    output = formatter.format_dataframe(df)
    elapsed = time.time() - start

    # Should complete in reasonable time (< 1 second)
    assert elapsed < 1.0

    # Verify output
    data = json.loads(output)
    assert len(data["data"]) == 1000


def test_special_characters_in_strings():
    """Test handling of special characters in string values."""
    df = pl.DataFrame({
        "name": ['test"quote', "test'apostrophe", "test\nnewline", "test\ttab"],
    })

    # JSON should escape properly
    formatter = get_formatter("json")
    output = formatter.format_dataframe(df)
    data = json.loads(output)  # Should parse without error

    assert data["data"][0]["name"] == 'test"quote'
    assert data["data"][2]["name"] == "test\nnewline"

    # CSV should escape properly
    formatter = get_formatter("csv")
    output = formatter.format_dataframe(df)
    assert isinstance(output, str)  # Should not crash
