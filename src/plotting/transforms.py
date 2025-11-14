"""Data transformations for plotting (conductance, resistance, etc.).

This module provides functions to transform raw measurement data (current, voltage)
into derived quantities like conductance (G = I/V), resistance (R = V/I),
and their inverses (1/G, 1/R).

Features:
- Automatic unit selection based on data magnitude
- Zero-division handling (warn and skip)
- Support for absolute value transformations
- Inverse transforms for extracting complementary parameters
- Compatible with NumPy arrays and Polars Series

Functions:
- calculate_resistance(V, I): R = V/I with resistance units (Ω, kΩ, MΩ)
- calculate_conductance(I, V): G = I/V with conductance units (pS, nS, µS, mS, S)
- calculate_inverse_conductance(I, V): 1/G = V/I with resistance units
- calculate_inverse_resistance(V, I): 1/R = I/V with conductance units
"""

from __future__ import annotations
from typing import Optional, Tuple
import numpy as np
import polars as pl


def calculate_resistance(
    voltage: np.ndarray | pl.Series,
    current: float,
    absolute: bool = False,
) -> Tuple[Optional[np.ndarray], Optional[str], Optional[str]]:
    """
    Calculate resistance R = V/I with automatic unit selection.

    Parameters
    ----------
    voltage : np.ndarray | pl.Series
        Voltage array (V) - measured drain-source voltage
    current : float
        Fixed current value (A) - drain-source current setpoint
    absolute : bool, optional
        If True, return |R| (absolute resistance). Default: False

    Returns
    -------
    tuple[np.ndarray | None, str | None, str | None]
        (resistance_array, ylabel, units) or (None, None, None) if current=0
        - resistance_array: Scaled resistance values in selected units
        - ylabel: LaTeX-formatted label (e.g., "R" or "|R|")
        - units: Unit string (e.g., "kΩ", "MΩ")

    Examples
    --------
    >>> V = np.array([0.1, 0.2, 0.3])  # Volts
    >>> I = 1e-6  # 1 µA
    >>> R, label, units = calculate_resistance(V, I)
    >>> print(f"{label} = {R[0]:.2f} {units}")
    R = 100.00 kΩ

    Notes
    -----
    - Zero or non-finite current values return (None, None, None)
    - Automatic unit selection: Ω (< 1 kΩ), kΩ (< 1 MΩ), MΩ (≥ 1 MΩ)
    - Preserves sign of resistance unless absolute=True
    """
    # Convert Polars Series to NumPy if needed
    if isinstance(voltage, pl.Series):
        voltage = voltage.to_numpy()

    # Check for zero or invalid current
    if current == 0 or not np.isfinite(current):
        print(
            f"[warn] Cannot calculate resistance: IDS={current}A "
            "(would divide by zero - skipping curve)"
        )
        return None, None, None

    # Calculate R = V/I
    R = voltage / current  # NumPy broadcasts division

    # Apply absolute value if requested
    if absolute:
        R = np.abs(R)

    # Auto-select units based on magnitude
    scale_factor, units = _auto_select_resistance_units(R)
    R_scaled = R / scale_factor

    # Format label for plotting
    ylabel = "|R|" if absolute else "R"

    return R_scaled, ylabel, units


def calculate_conductance(
    current: np.ndarray | pl.Series,
    voltage: float,
    absolute: bool = False,
) -> Tuple[Optional[np.ndarray], Optional[str], Optional[str]]:
    """
    Calculate conductance G = I/V with automatic unit selection.

    Parameters
    ----------
    current : np.ndarray | pl.Series
        Current array (A) - measured drain-source current
    voltage : float
        Fixed voltage value (V) - drain-source voltage setpoint
    absolute : bool, optional
        If True, return |G| (absolute conductance). Default: False

    Returns
    -------
    tuple[np.ndarray | None, str | None, str | None]
        (conductance_array, ylabel, units) or (None, None, None) if voltage=0
        - conductance_array: Scaled conductance values in selected units
        - ylabel: LaTeX-formatted label (e.g., "G" or "|G|")
        - units: Unit string (e.g., "µS", "mS", "S")

    Examples
    --------
    >>> I = np.array([1e-6, 2e-6, 3e-6])  # µA
    >>> V = 3.3  # Volts
    >>> G, label, units = calculate_conductance(I, V)
    >>> print(f"{label} = {G[0]:.2f} {units}")
    G = 0.30 µS

    Notes
    -----
    - Zero or non-finite voltage values return (None, None, None)
    - Automatic unit selection: nS (< 1 µS), µS (< 1 mS), mS (< 1 S), S (≥ 1 S)
    - Preserves sign of conductance unless absolute=True
    """
    # Convert Polars Series to NumPy if needed
    if isinstance(current, pl.Series):
        current = current.to_numpy()

    # Check for zero or invalid voltage
    if voltage == 0 or not np.isfinite(voltage):
        print(
            f"[warn] Cannot calculate conductance: VDS={voltage}V "
            "(would divide by zero - skipping curve)"
        )
        return None, None, None

    # Calculate G = I/V
    G = current / voltage  # NumPy broadcasts division

    # Apply absolute value if requested
    if absolute:
        G = np.abs(G)

    # Auto-select units based on magnitude
    scale_factor, units = _auto_select_conductance_units(G)
    G_scaled = G / scale_factor

    # Format label for plotting
    ylabel = "|G|" if absolute else "G"

    return G_scaled, ylabel, units


def calculate_inverse_conductance(
    current: np.ndarray | pl.Series,
    voltage: float,
    absolute: bool = False,
) -> Tuple[Optional[np.ndarray], Optional[str], Optional[str]]:
    """
    Calculate inverse conductance 1/G = V/I (equivalent to resistance).

    First calculates G = I/V, then takes reciprocal to get 1/G = V/I = R.
    Useful for extracting resistance characteristics from IVg measurements.

    Parameters
    ----------
    current : np.ndarray | pl.Series
        Current array (A) - measured drain-source current
    voltage : float
        Fixed voltage value (V) - drain-source voltage setpoint
    absolute : bool, optional
        If True, return |1/G| (absolute inverse conductance). Default: False

    Returns
    -------
    tuple[np.ndarray | None, str | None, str | None]
        (inverse_conductance_array, ylabel, units) or (None, None, None) if error
        - inverse_conductance_array: Scaled 1/G values in resistance units (Ω, kΩ, MΩ)
        - ylabel: LaTeX-formatted label (e.g., "1/G" or "|1/G|")
        - units: Unit string (e.g., "kΩ", "MΩ")

    Examples
    --------
    >>> I = np.array([1e-6, 2e-6, 3e-6])  # µA
    >>> V = 3.3  # Volts
    >>> inv_G, label, units = calculate_inverse_conductance(I, V)
    >>> print(f"{label} = {inv_G[0]:.2f} {units}")
    1/G = 3300.00 kΩ

    Notes
    -----
    - Zero or non-finite voltage values return (None, None, None)
    - Near-zero current values may cause very large 1/G (warns if necessary)
    - Automatic unit selection uses resistance units: Ω (< 1 kΩ), kΩ (< 1 MΩ), MΩ (≥ 1 MΩ)
    - Preserves sign unless absolute=True
    - Mathematically equivalent to calculate_resistance(V, I)
    """
    # Convert Polars Series to NumPy if needed
    if isinstance(current, pl.Series):
        current = current.to_numpy()

    # Check for zero or invalid voltage
    if voltage == 0 or not np.isfinite(voltage):
        print(
            f"[warn] Cannot calculate inverse conductance: VDS={voltage}V "
            "(would divide by zero - skipping curve)"
        )
        return None, None, None

    # Check for zero or near-zero current values (would cause infinite 1/G)
    if np.any(np.abs(current) < 1e-15):
        print(
            f"[warn] Cannot calculate inverse conductance: current contains near-zero values "
            "(would cause infinite 1/G - skipping curve)"
        )
        return None, None, None

    # Calculate 1/G = V/I (equivalent to resistance R = V/I)
    inv_G = voltage / current  # NumPy broadcasts division

    # Apply absolute value if requested
    if absolute:
        inv_G = np.abs(inv_G)

    # Auto-select resistance units (since 1/G has units of Ω)
    scale_factor, units = _auto_select_resistance_units(inv_G)
    inv_G_scaled = inv_G / scale_factor

    # Format label for plotting
    ylabel = "|1/G|" if absolute else "1/G"

    return inv_G_scaled, ylabel, units


def calculate_inverse_resistance(
    voltage: np.ndarray | pl.Series,
    current: float,
    absolute: bool = False,
) -> Tuple[Optional[np.ndarray], Optional[str], Optional[str]]:
    """
    Calculate inverse resistance 1/R = I/V (equivalent to conductance).

    First calculates R = V/I, then takes reciprocal to get 1/R = I/V = G.
    Useful for extracting conductance characteristics from VVg measurements.

    Parameters
    ----------
    voltage : np.ndarray | pl.Series
        Voltage array (V) - measured drain-source voltage
    current : float
        Fixed current value (A) - drain-source current setpoint
    absolute : bool, optional
        If True, return |1/R| (absolute inverse resistance). Default: False

    Returns
    -------
    tuple[np.ndarray | None, str | None, str | None]
        (inverse_resistance_array, ylabel, units) or (None, None, None) if error
        - inverse_resistance_array: Scaled 1/R values in conductance units (pS, nS, µS, mS, S)
        - ylabel: LaTeX-formatted label (e.g., "1/R" or "|1/R|")
        - units: Unit string (e.g., "µS", "mS", "S")

    Examples
    --------
    >>> V = np.array([0.1, 0.2, 0.3])  # Volts
    >>> I = 1e-6  # 1 µA
    >>> inv_R, label, units = calculate_inverse_resistance(V, I)
    >>> print(f"{label} = {inv_R[0]:.2f} {units}")
    1/R = 10.00 µS

    Notes
    -----
    - Zero or non-finite current values return (None, None, None)
    - Near-zero voltage values may cause very large 1/R (warns if necessary)
    - Automatic unit selection uses conductance units: pS, nS, µS, mS, S
    - Preserves sign unless absolute=True
    - Mathematically equivalent to calculate_conductance(I, V)
    """
    # Convert Polars Series to NumPy if needed
    if isinstance(voltage, pl.Series):
        voltage = voltage.to_numpy()

    # Check for zero or invalid current
    if current == 0 or not np.isfinite(current):
        print(
            f"[warn] Cannot calculate inverse resistance: IDS={current}A "
            "(would divide by zero - skipping curve)"
        )
        return None, None, None

    # Check for zero or near-zero voltage values (would cause infinite 1/R)
    if np.any(np.abs(voltage) < 1e-15):
        print(
            f"[warn] Cannot calculate inverse resistance: voltage contains near-zero values "
            "(would cause infinite 1/R - skipping curve)"
        )
        return None, None, None

    # Calculate 1/R = I/V (equivalent to conductance G = I/V)
    inv_R = current / voltage  # NumPy broadcasts division

    # Apply absolute value if requested
    if absolute:
        inv_R = np.abs(inv_R)

    # Auto-select conductance units (since 1/R has units of S)
    scale_factor, units = _auto_select_conductance_units(inv_R)
    inv_R_scaled = inv_R / scale_factor

    # Format label for plotting
    ylabel = "|1/R|" if absolute else "1/R"

    return inv_R_scaled, ylabel, units


def _auto_select_resistance_units(R_values: np.ndarray) -> Tuple[float, str]:
    """
    Select appropriate resistance units based on data range.

    Parameters
    ----------
    R_values : np.ndarray
        Resistance values in Ohms (Ω)

    Returns
    -------
    tuple[float, str]
        (scale_factor, unit_string)
        - scale_factor: Division factor to convert to selected units
        - unit_string: LaTeX-compatible unit string

    Examples
    --------
    >>> R = np.array([100, 200, 300])  # Ohms
    >>> scale, unit = _auto_select_resistance_units(R)
    >>> print(f"{scale}, {unit}")
    1.0, Ω

    >>> R = np.array([1e5, 2e5, 3e5])  # 100 kΩ range
    >>> scale, unit = _auto_select_resistance_units(R)
    >>> print(f"{scale}, {unit}")
    1000.0, kΩ
    """
    max_R = np.max(np.abs(R_values))

    if max_R < 1e3:
        return 1.0, "Ω"
    elif max_R < 1e6:
        return 1e3, "kΩ"
    else:
        return 1e6, "MΩ"


def _auto_select_conductance_units(G_values: np.ndarray) -> Tuple[float, str]:
    """
    Select appropriate conductance units based on data range.

    Parameters
    ----------
    G_values : np.ndarray
        Conductance values in Siemens (S)

    Returns
    -------
    tuple[float, str]
        (scale_factor, unit_string)
        - scale_factor: Division factor to convert to selected units
        - unit_string: LaTeX-compatible unit string

    Examples
    --------
    >>> G = np.array([1e-6, 2e-6, 3e-6])  # µS range
    >>> scale, unit = _auto_select_conductance_units(G)
    >>> print(f"{scale}, {unit}")
    1e-06, µS

    >>> G = np.array([1e-3, 2e-3, 3e-3])  # mS range
    >>> scale, unit = _auto_select_conductance_units(G)
    >>> print(f"{scale}, {unit}")
    0.001, mS
    """
    max_G = np.max(np.abs(G_values))

    if max_G < 1e-9:
        return 1e-12, "pS"  # picosiemens (very small)
    elif max_G < 1e-6:
        return 1e-9, "nS"  # nanosiemens
    elif max_G < 1e-3:
        return 1e-6, "µS"  # microsiemens
    elif max_G < 1:
        return 1e-3, "mS"  # millisiemens
    else:
        return 1.0, "S"  # siemens
