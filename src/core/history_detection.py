"""
History Detection and Loading.

Automatically detects whether enriched chip histories (with derived metrics)
are available, and falls back to regular histories if not.

This module enables the TUI to seamlessly support both regular and enriched
chip histories, providing clear status messages and graceful fallback behavior.
"""

from __future__ import annotations
from pathlib import Path
from typing import Tuple, Optional
import polars as pl


def detect_history_availability(
    chip_number: int,
    chip_group: str,
    history_dir: Path,
    enriched_dir: Path,
) -> Tuple[bool, bool, Optional[Path], Optional[Path]]:
    """
    Detect availability of regular and enriched chip histories.

    Parameters
    ----------
    chip_number : int
        Chip number (e.g., 67)
    chip_group : str
        Chip group name (e.g., "Alisson")
    history_dir : Path
        Regular history directory (data/02_stage/chip_histories)
    enriched_dir : Path
        Enriched history directory (data/03_derived/chip_histories_enriched)

    Returns
    -------
    tuple
        (has_regular, has_enriched, regular_path, enriched_path)

    Examples
    --------
    >>> from pathlib import Path
    >>> has_reg, has_enr, reg_path, enr_path = detect_history_availability(
    ...     67, "Alisson",
    ...     Path("data/02_stage/chip_histories"),
    ...     Path("data/03_derived/chip_histories_enriched")
    ... )
    >>> print(f"Regular: {has_reg}, Enriched: {has_enr}")
    Regular: True, Enriched: True
    """
    chip_name = f"{chip_group}{chip_number}"

    regular_path = history_dir / f"{chip_name}_history.parquet"
    enriched_path = enriched_dir / f"{chip_name}_history_enriched.parquet"

    has_regular = regular_path.exists()
    has_enriched = enriched_path.exists()

    return (
        has_regular,
        has_enriched,
        regular_path if has_regular else None,
        enriched_path if has_enriched else None
    )


def load_chip_history(
    chip_number: int,
    chip_group: str,
    history_dir: Path,
    enriched_dir: Path,
    prefer_enriched: bool = True,
    require_enriched: bool = False,
) -> Tuple[pl.DataFrame, bool]:
    """
    Load chip history, preferring enriched if available.

    This function provides automatic fallback logic:
    1. Try enriched history if prefer_enriched=True
    2. Fall back to regular history if enriched not available
    3. Raise error if no history found

    Parameters
    ----------
    chip_number : int
        Chip number (e.g., 67)
    chip_group : str
        Chip group name (e.g., "Alisson")
    history_dir : Path
        Regular history directory
    enriched_dir : Path
        Enriched history directory
    prefer_enriched : bool, optional
        Prefer enriched history if available (default: True)
    require_enriched : bool, optional
        Raise error if enriched history not available (default: False)

    Returns
    -------
    tuple
        (history_df, is_enriched)
        - history_df: Polars DataFrame with chip history
        - is_enriched: True if loaded from enriched history, False otherwise

    Raises
    ------
    FileNotFoundError
        If no history file found, or if require_enriched=True and enriched not available
    ValueError
        If require_enriched=True and enriched history not available but regular exists

    Examples
    --------
    >>> # Load with automatic fallback
    >>> history, is_enriched = load_chip_history(67, "Alisson", hist_dir, enr_dir)
    >>> if is_enriched:
    ...     print("Using enriched history with derived metrics")
    ... else:
    ...     print("Using regular history (no derived metrics)")

    >>> # Require enriched history (for CNP/Photoresponse plots)
    >>> try:
    ...     history, _ = load_chip_history(
    ...         67, "Alisson", hist_dir, enr_dir, require_enriched=True
    ...     )
    ... except ValueError as e:
    ...     print(f"Error: {e}")
    ...     print("Run: python3 process_and_analyze.py enrich-history 67")
    """
    has_regular, has_enriched, regular_path, enriched_path = detect_history_availability(
        chip_number, chip_group, history_dir, enriched_dir
    )

    # Handle require_enriched mode (for CNP/Photoresponse plots)
    if require_enriched and not has_enriched:
        if has_regular:
            raise ValueError(
                f"Enriched history required but not available for {chip_group}{chip_number}. "
                f"Run: python3 process_and_analyze.py enrich-history {chip_number}"
            )
        else:
            raise FileNotFoundError(
                f"No history found for {chip_group}{chip_number}. "
                f"Run: python3 process_and_analyze.py full-pipeline"
            )

    # Load enriched if preferred and available
    if prefer_enriched and has_enriched:
        return pl.read_parquet(enriched_path), True

    # Fallback to regular history
    if has_regular:
        return pl.read_parquet(regular_path), False

    # No history available at all
    raise FileNotFoundError(
        f"No history found for {chip_group}{chip_number}. "
        f"Run: python3 process_and_analyze.py full-pipeline"
    )


def get_history_status_message(
    chip_number: int,
    chip_group: str,
    history_dir: Path,
    enriched_dir: Path,
) -> str:
    """
    Get human-readable status message about history availability.

    Useful for displaying in configuration screens to inform users
    whether enriched histories are available for advanced plots.

    Parameters
    ----------
    chip_number : int
        Chip number
    chip_group : str
        Chip group name
    history_dir : Path
        Regular history directory
    enriched_dir : Path
        Enriched history directory

    Returns
    -------
    str
        Status message with emoji indicator:
        - "✓ Enriched history available (with derived metrics)"
        - "⚠ Regular history only (no derived metrics - run enrich-history)"
        - "✗ No history found (run full-pipeline)"

    Examples
    --------
    >>> status = get_history_status_message(67, "Alisson", hist_dir, enr_dir)
    >>> print(f"History Status: {status}")
    History Status: ✓ Enriched history available (with derived metrics)
    """
    has_regular, has_enriched, _, _ = detect_history_availability(
        chip_number, chip_group, history_dir, enriched_dir
    )

    if has_enriched:
        return "✓ Enriched history available (with derived metrics)"
    elif has_regular:
        return "⚠ Regular history only (no derived metrics - run enrich-history)"
    else:
        return "✗ No history found (run full-pipeline)"


def get_history_status_details(
    chip_number: int,
    chip_group: str,
    history_dir: Path,
    enriched_dir: Path,
) -> dict:
    """
    Get detailed status information about history availability.

    Returns comprehensive information for debugging or advanced UI displays.

    Parameters
    ----------
    chip_number : int
        Chip number
    chip_group : str
        Chip group name
    history_dir : Path
        Regular history directory
    enriched_dir : Path
        Enriched history directory

    Returns
    -------
    dict
        Status details with keys:
        - has_regular: bool
        - has_enriched: bool
        - regular_path: Optional[Path]
        - enriched_path: Optional[Path]
        - chip_name: str
        - status_message: str
        - available_plot_types: list[str] (plot types supported)

    Examples
    --------
    >>> details = get_history_status_details(67, "Alisson", hist_dir, enr_dir)
    >>> print(f"Chip: {details['chip_name']}")
    >>> print(f"Enriched: {details['has_enriched']}")
    >>> print(f"Available plots: {', '.join(details['available_plot_types'])}")
    """
    has_regular, has_enriched, regular_path, enriched_path = detect_history_availability(
        chip_number, chip_group, history_dir, enriched_dir
    )

    chip_name = f"{chip_group}{chip_number}"
    status_message = get_history_status_message(chip_number, chip_group, history_dir, enriched_dir)

    # Determine which plot types are available
    available_plot_types = []
    if has_regular or has_enriched:
        # Measurement-based plots (work with any history)
        available_plot_types.extend(["ITS", "IVg", "Transconductance", "VVg", "Vt", "LaserCalibration"])
    if has_enriched:
        # Derived metric plots (require enriched history)
        available_plot_types.extend(["CNP", "Photoresponse"])

    return {
        "has_regular": has_regular,
        "has_enriched": has_enriched,
        "regular_path": regular_path,
        "enriched_path": enriched_path,
        "chip_name": chip_name,
        "status_message": status_message,
        "available_plot_types": available_plot_types,
    }
