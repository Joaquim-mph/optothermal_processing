#!/usr/bin/env python3
"""
Centralized Label and Legend Formatters

This module provides consistent formatting for all plot labels and legends
across the plotting module. It eliminates duplication and ensures uniform
appearance of wavelengths, voltages, power values, and other metadata.

Usage
-----
>>> from src.plotting.formatters import format_wavelength, format_voltage
>>> wl_label = format_wavelength(365.0)  # "365 nm"
>>> vg_label = format_voltage(3.0)        # "3 V"
>>> vg_label = format_voltage(0.25)       # "0.25 V"

Integration with PlotConfig
----------------------------
Formatters respect PlotConfig settings when provided:

>>> from src.plotting.config import PlotConfig
>>> config = PlotConfig(wavelength_format="{:.1f} nm")
>>> wl_label = format_wavelength(365.0, config)  # "365.0 nm"
"""

from typing import Optional, Callable, Dict, Any
import numpy as np


def format_wavelength(wl_nm: float, config: Optional['PlotConfig'] = None) -> str:
    """
    Format wavelength consistently.

    Parameters
    ----------
    wl_nm : float
        Wavelength in nanometers
    config : PlotConfig, optional
        Configuration with wavelength_format setting

    Returns
    -------
    str
        Formatted wavelength string (e.g., "365 nm")

    Examples
    --------
    >>> format_wavelength(365.0)
    '365 nm'
    >>> format_wavelength(532.5)
    '532 nm'
    >>> format_wavelength(1064.0)
    '1064 nm'

    >>> from src.plotting.config import PlotConfig
    >>> config = PlotConfig(wavelength_format="{:.1f} nm")
    >>> format_wavelength(365.0, config)
    '365.0 nm'
    """
    if not np.isfinite(wl_nm):
        return "N/A"

    fmt = config.wavelength_format if config else "{:.0f} nm"
    return fmt.format(wl_nm)


def format_voltage(voltage: float, config: Optional['PlotConfig'] = None) -> str:
    """
    Format voltage consistently.

    Uses :g formatter to avoid trailing zeros:
    - 3.0 V → "3 V"
    - 0.25 V → "0.25 V"
    - -0.4 V → "-0.4 V"

    Parameters
    ----------
    voltage : float
        Voltage in volts
    config : PlotConfig, optional
        Configuration with voltage_format setting

    Returns
    -------
    str
        Formatted voltage string (e.g., "3 V", "0.25 V")

    Examples
    --------
    >>> format_voltage(3.0)
    '3 V'
    >>> format_voltage(0.25)
    '0.25 V'
    >>> format_voltage(-0.4)
    '-0.4 V'
    >>> format_voltage(0.0)
    '0 V'
    """
    if not np.isfinite(voltage):
        return "N/A"

    fmt = config.voltage_format if config else "{:g} V"
    return fmt.format(voltage)


def format_power(
    power_w: float,
    config: Optional['PlotConfig'] = None,
    return_value: bool = False
) -> tuple[Optional[float], str] | str:
    """
    Format power with auto-selected unit (W, mW, µW, nW).

    Automatically selects the most appropriate unit based on magnitude:
    - ≥ 1 W: watts (W)
    - ≥ 1 mW: milliwatts (mW)
    - ≥ 1 µW: microwatts (µW)
    - ≥ 1 nW: nanowatts (nW)
    - < 1 nW: scientific notation (W)

    Parameters
    ----------
    power_w : float
        Power in watts
    config : PlotConfig, optional
        Configuration with power_decimal_places setting
    return_value : bool
        If True, return (scaled_value, formatted_string) tuple
        If False, return only formatted_string (default)

    Returns
    -------
    tuple[float, str] or str
        If return_value=True: (scaled_value, formatted_string)
        If return_value=False: formatted_string only

        Example tuples:
        - (5.98, "5.98 µW") when power_w = 5.98e-6
        - (2.5, "2.50 mW") when power_w = 2.5e-3

    Examples
    --------
    >>> format_power(5.98e-6)
    '5.98 µW'
    >>> format_power(2.5e-3)
    '2.50 mW'
    >>> format_power(1.2)
    '1.20 W'
    >>> format_power(500e-9)
    '500.00 nW'

    >>> # With return_value=True
    >>> value, string = format_power(5.98e-6, return_value=True)
    >>> print(value, string)
    5.98e-06 5.98 µW

    >>> # Custom decimal places
    >>> from src.plotting.config import PlotConfig
    >>> config = PlotConfig(power_decimal_places=4)
    >>> format_power(5.98e-6, config)
    '5.9800 µW'
    """
    if not np.isfinite(power_w) or power_w < 0:
        if return_value:
            return None, "N/A"
        return "N/A"

    # Get decimal places from config
    decimals = config.power_decimal_places if config else 2

    # Auto-select unit based on magnitude
    if power_w >= 1.0:
        scaled_value = power_w
        unit = "W"
    elif power_w >= 1e-3:
        scaled_value = power_w * 1e3
        unit = "mW"
    elif power_w >= 1e-6:
        scaled_value = power_w * 1e6
        unit = "µW"
    elif power_w >= 1e-9:
        scaled_value = power_w * 1e9
        unit = "nW"
    else:
        # Very small values: use scientific notation
        if return_value:
            return power_w, f"{power_w:.2e} W"
        return f"{power_w:.2e} W"

    formatted_string = f"{scaled_value:.{decimals}f} {unit}"

    if return_value:
        return power_w, formatted_string
    return formatted_string


def format_datetime(dt_str: str, config: Optional['PlotConfig'] = None) -> str:
    """
    Format datetime consistently (trim seconds by default).

    Converts "2025-10-14 15:03:53" → "2025-10-14 15:03"

    Parameters
    ----------
    dt_str : str
        Datetime string (usually from datetime_local column)
    config : PlotConfig, optional
        Configuration with datetime_format setting

    Returns
    -------
    str
        Formatted datetime string

    Examples
    --------
    >>> format_datetime("2025-10-14 15:03:53")
    '2025-10-14 15:03'
    >>> format_datetime("2025-10-14 15:03")
    '2025-10-14 15:03'
    >>> format_datetime("2025-10-14")
    '2025-10-14'

    >>> # With custom format
    >>> from src.plotting.config import PlotConfig
    >>> config = PlotConfig(datetime_format="%Y-%m-%d")
    >>> # Note: This uses simple string slicing, not strftime
    >>> format_datetime("2025-10-14 15:03:53")
    '2025-10-14 15:03'
    """
    if not dt_str:
        return "N/A"

    # Simple implementation: trim to first 16 characters (removes seconds)
    # Format: "YYYY-MM-DD HH:MM"
    return dt_str[:16] if len(dt_str) >= 16 else dt_str


def format_current(current_a: float, auto_unit: bool = True) -> str:
    """
    Format current with auto-selected unit (A, mA, µA, nA, pA).

    Parameters
    ----------
    current_a : float
        Current in amperes
    auto_unit : bool
        Auto-select unit based on magnitude (default: True)

    Returns
    -------
    str
        Formatted current string

    Examples
    --------
    >>> format_current(1.5e-6)
    '1.50 µA'
    >>> format_current(500e-9)
    '500.00 nA'
    >>> format_current(2.5e-3)
    '2.50 mA'
    """
    if not np.isfinite(current_a):
        return "N/A"

    if not auto_unit:
        return f"{current_a:.2e} A"

    # Auto-select unit
    abs_current = abs(current_a)
    if abs_current >= 1.0:
        return f"{current_a:.2f} A"
    elif abs_current >= 1e-3:
        return f"{current_a * 1e3:.2f} mA"
    elif abs_current >= 1e-6:
        return f"{current_a * 1e6:.2f} µA"
    elif abs_current >= 1e-9:
        return f"{current_a * 1e9:.2f} nA"
    elif abs_current >= 1e-12:
        return f"{current_a * 1e12:.2f} pA"
    else:
        return f"{current_a:.2e} A"


# ============================================================================
# Legend-by Formatters
# ============================================================================

def _format_for_wavelength(row: dict, config: Optional['PlotConfig'] = None) -> tuple[str, str]:
    """
    Extract and format wavelength for legend.

    Parameters
    ----------
    row : dict
        Metadata row (from iter_rows(named=True))
    config : PlotConfig, optional
        Configuration

    Returns
    -------
    tuple[str, str]
        (label, legend_title)
    """
    from src.plotting.plot_utils import get_wavelength_nm

    wl = get_wavelength_nm(row)
    if wl is not None:
        return format_wavelength(wl, config), "Wavelength"
    else:
        # Fallback to seq or file_idx
        seq = row.get("seq", row.get("file_idx", 0))
        return f"#{int(seq)}", "Trace"


def _format_for_vg(row: dict, config: Optional['PlotConfig'] = None, data=None) -> tuple[str, str]:
    """
    Extract and format gate voltage for legend.

    Parameters
    ----------
    row : dict
        Metadata row (from iter_rows(named=True))
    config : PlotConfig, optional
        Configuration
    data : pl.DataFrame, optional
        Measurement data (for extracting constant VG from trace)

    Returns
    -------
    tuple[str, str]
        (label, legend_title)
    """
    from src.plotting.plot_utils import get_gate_voltage

    vg = get_gate_voltage(row, data)
    if vg is not None:
        return format_voltage(vg, config), "Vg"
    else:
        seq = row.get("seq", row.get("file_idx", 0))
        return f"#{int(seq)}", "Trace"


def _format_for_led_voltage(row: dict, config: Optional['PlotConfig'] = None) -> tuple[str, str]:
    """
    Extract and format LED/laser voltage for legend.

    Parameters
    ----------
    row : dict
        Metadata row (from iter_rows(named=True))
    config : PlotConfig, optional
        Configuration

    Returns
    -------
    tuple[str, str]
        (label, legend_title)
    """
    from src.plotting.plot_utils import get_led_voltage

    led_v = get_led_voltage(row)
    if led_v is not None:
        return format_voltage(led_v, config), "LED Voltage"
    else:
        seq = row.get("seq", row.get("file_idx", 0))
        return f"#{int(seq)}", "Trace"


def _format_for_power(row: dict, config: Optional['PlotConfig'] = None) -> tuple[str, str]:
    """
    Extract and format irradiated power for legend.

    Parameters
    ----------
    row : dict
        Metadata row (from iter_rows(named=True))
    config : PlotConfig, optional
        Configuration

    Returns
    -------
    tuple[str, str]
        (label, legend_title)
    """
    from src.plotting.plot_utils import get_irradiated_power

    power_w, power_str = get_irradiated_power(row, format_display=True)
    if power_str is not None:
        return power_str, "LED Power"
    else:
        seq = row.get("seq", row.get("file_idx", 0))
        return f"#{int(seq)}", "Trace"


def _format_for_datetime(row: dict, config: Optional['PlotConfig'] = None) -> tuple[str, str]:
    """
    Extract and format datetime for legend.

    Parameters
    ----------
    row : dict
        Metadata row (from iter_rows(named=True))
    config : PlotConfig, optional
        Configuration

    Returns
    -------
    tuple[str, str]
        (label, legend_title)
    """
    datetime_str = row.get("datetime_local")
    if datetime_str:
        return format_datetime(datetime_str, config), "Date & Time"
    else:
        seq = row.get("seq", row.get("file_idx", 0))
        return f"#{int(seq)}", "Experiment"


# ============================================================================
# Legend Formatters Registry
# ============================================================================

LEGEND_FORMATTERS: Dict[str, Callable[[dict, Optional['PlotConfig']], tuple[str, str]]] = {
    "wavelength": _format_for_wavelength,
    "vg": _format_for_vg,
    "led_voltage": _format_for_led_voltage,
    "power": _format_for_power,
    "datetime": _format_for_datetime,
}

# Aliases for convenience
LEGEND_FORMATTERS["wl"] = _format_for_wavelength
LEGEND_FORMATTERS["lambda"] = _format_for_wavelength
LEGEND_FORMATTERS["gate"] = _format_for_vg
LEGEND_FORMATTERS["vgs"] = _format_for_vg
LEGEND_FORMATTERS["led"] = _format_for_led_voltage
LEGEND_FORMATTERS["laser"] = _format_for_led_voltage
LEGEND_FORMATTERS["laser_voltage"] = _format_for_led_voltage
LEGEND_FORMATTERS["pow"] = _format_for_power
LEGEND_FORMATTERS["irradiated_power"] = _format_for_power
LEGEND_FORMATTERS["led_power"] = _format_for_power
LEGEND_FORMATTERS["date"] = _format_for_datetime
LEGEND_FORMATTERS["time"] = _format_for_datetime
LEGEND_FORMATTERS["dt"] = _format_for_datetime


def get_legend_formatter(
    legend_by: str
) -> Callable[[dict, Optional['PlotConfig']], tuple[str, str]]:
    """
    Get the appropriate formatter function for a legend_by value.

    Parameters
    ----------
    legend_by : str
        Legend grouping key (e.g., "wavelength", "vg", "power")

    Returns
    -------
    Callable
        Formatter function that takes (row, config) and returns (label, legend_title)

    Examples
    --------
    >>> formatter = get_legend_formatter("wavelength")
    >>> row = {"Laser wavelength": 365.0}
    >>> label, title = formatter(row, None)
    >>> print(label, title)
    365 nm Wavelength

    >>> # With alias
    >>> formatter = get_legend_formatter("wl")
    >>> label, title = formatter(row, None)
    >>> print(label, title)
    365 nm Wavelength
    """
    # Normalize legend_by to canonical value
    lb = legend_by.strip().lower()

    # Try direct lookup
    if lb in LEGEND_FORMATTERS:
        return LEGEND_FORMATTERS[lb]

    # Fallback: return seq number formatter
    def _fallback_formatter(row: dict, config: Optional['PlotConfig'] = None) -> tuple[str, str]:
        seq = row.get("seq", row.get("file_idx", 0))
        return f"#{int(seq)}", "Trace"

    return _fallback_formatter


# ============================================================================
# Utility Functions
# ============================================================================

def normalize_legend_by(legend_by: str) -> str:
    """
    Normalize legend_by string to canonical form.

    Parameters
    ----------
    legend_by : str
        Legend grouping key (may include aliases)

    Returns
    -------
    str
        Canonical legend_by value

    Examples
    --------
    >>> normalize_legend_by("wl")
    'wavelength'
    >>> normalize_legend_by("WAVELENGTH")
    'wavelength'
    >>> normalize_legend_by("led")
    'led_voltage'
    >>> normalize_legend_by("pow")
    'power'
    """
    lb = legend_by.strip().lower()

    # Map to canonical values
    canonical_map = {
        "wavelength": "wavelength",
        "wl": "wavelength",
        "lambda": "wavelength",
        "vg": "vg",
        "gate": "vg",
        "vgs": "vg",
        "led_voltage": "led_voltage",
        "led": "led_voltage",
        "laser": "led_voltage",
        "laser_voltage": "led_voltage",
        "power": "power",
        "pow": "power",
        "irradiated_power": "power",
        "led_power": "power",
        "datetime": "datetime",
        "date": "datetime",
        "time": "datetime",
        "dt": "datetime",
    }

    return canonical_map.get(lb, "seq")  # Default to "seq" if unknown
