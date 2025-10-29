"""
TUI Session State Management.

Provides type-safe wizard session state using Pydantic models.
Replaces the untyped plot_config dict with validated, typed properties.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class PlotSession(BaseModel):
    """
    Type-safe wizard session state.

    Manages the state of the plot generation wizard flow, including:
    - Application paths (stage_dir, history_dir, output_dir)
    - Wizard progress (chip selection, plot type, config mode)
    - Plot parameters (baseline, legend, padding, etc.)
    - Experiment selection (seq_numbers)

    Benefits over dict-based config:
    - Type safety with IDE autocomplete
    - Validation on assignment
    - Clear defaults in one place
    - Easy serialization with .model_dump()

    Example
    -------
    >>> from pathlib import Path
    >>> session = PlotSession(
    ...     stage_dir=Path("data/02_stage/raw_measurements"),
    ...     history_dir=Path("data/02_stage/chip_histories"),
    ...     output_dir=Path("figs"),
    ...     chip_group="Alisson"
    ... )
    >>> session.chip_number = 67
    >>> session.plot_type = "ITS"
    >>> session.legend_by = "wavelength"
    """

    # ═══════════════════════════════════════════════════════════════════
    # Application Paths (Required, set at app initialization)
    # ═══════════════════════════════════════════════════════════════════

    stage_dir: Path = Field(
        ...,
        description="Staged Parquet data directory path"
    )

    history_dir: Path = Field(
        ...,
        description="Chip history directory path (Parquet files)"
    )

    output_dir: Path = Field(
        ...,
        description="Output directory for generated plots"
    )

    chip_group: str = Field(
        ...,
        description="Default chip group name (e.g., 'Alisson')"
    )

    # ═══════════════════════════════════════════════════════════════════
    # Wizard State (Filled during flow)
    # ═══════════════════════════════════════════════════════════════════

    chip_number: Optional[int] = Field(
        default=None,
        description="Selected chip number (Step 1)"
    )

    plot_type: Optional[str] = Field(
        default=None,
        description="Selected plot type: 'ITS', 'IVg', or 'Transconductance' (Step 2)"
    )

    # ═══════════════════════════════════════════════════════════════════
    # Configuration Mode
    # ═══════════════════════════════════════════════════════════════════

    config_mode: Optional[str] = Field(
        default=None,
        description="Configuration mode: 'quick', 'custom', 'preset', or 'recent'"
    )

    preset: Optional[str] = Field(
        default=None,
        description="ITS preset name (if using preset mode)"
    )

    selection_mode: str = Field(
        default="interactive",
        description="Experiment selection mode: 'interactive', 'all', or 'filtered'"
    )

    # ═══════════════════════════════════════════════════════════════════
    # ITS Plot Parameters (with defaults)
    # ═══════════════════════════════════════════════════════════════════

    legend_by: str = Field(
        default="vg",
        description="Legend grouping: 'vg', 'led_voltage', or 'wavelength'"
    )

    baseline: Optional[float] = Field(
        default=60.0,
        description="Baseline time in seconds for ITS baseline correction (None = auto)"
    )

    baseline_mode: str = Field(
        default="fixed",
        description="Baseline correction mode: 'none', 'auto', or 'fixed'"
    )

    baseline_auto_divisor: float = Field(
        default=2.0,
        description="Divisor for auto baseline calculation (total_duration / divisor)"
    )

    plot_start_time: float = Field(
        default=20.0,
        description="Start time for plotting in seconds (crop initial data)"
    )

    check_duration_mismatch: bool = Field(
        default=False,
        description="Check for duration mismatches between experiments"
    )

    duration_tolerance: float = Field(
        default=0.10,
        description="Duration mismatch tolerance (fraction, e.g., 0.10 = 10%)"
    )

    padding: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Y-axis padding fraction (0.05 = 5% padding)"
    )

    # ═══════════════════════════════════════════════════════════════════
    # Experiment Selection
    # ═══════════════════════════════════════════════════════════════════

    seq_numbers: List[int] = Field(
        default_factory=list,
        description="Selected experiment sequence numbers"
    )

    # ═══════════════════════════════════════════════════════════════════
    # Transconductance-Specific Parameters
    # ═══════════════════════════════════════════════════════════════════

    method: str = Field(
        default="gradient",
        description="Transconductance calculation method: 'gradient' or 'savgol'"
    )

    window_length: int = Field(
        default=9,
        ge=3,
        description="Savitzky-Golay filter window length (odd number >= 3)"
    )

    polyorder: int = Field(
        default=3,
        ge=1,
        description="Savitzky-Golay filter polynomial order"
    )

    # ═══════════════════════════════════════════════════════════════════
    # Validators
    # ═══════════════════════════════════════════════════════════════════

    @field_validator("plot_type")
    @classmethod
    def validate_plot_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate plot type is one of the supported types."""
        if v is not None and v not in ["ITS", "IVg", "Transconductance"]:
            raise ValueError(f"Invalid plot_type: {v}. Must be 'ITS', 'IVg', or 'Transconductance'")
        return v

    @field_validator("config_mode")
    @classmethod
    def validate_config_mode(cls, v: Optional[str]) -> Optional[str]:
        """Validate config mode is one of the supported modes."""
        if v is not None and v not in ["quick", "custom", "preset", "recent"]:
            raise ValueError(f"Invalid config_mode: {v}. Must be 'quick', 'custom', 'preset', or 'recent'")
        return v

    @field_validator("legend_by")
    @classmethod
    def validate_legend_by(cls, v: str) -> str:
        """Validate legend_by is one of the supported options."""
        if v not in ["vg", "led_voltage", "wavelength"]:
            raise ValueError(f"Invalid legend_by: {v}. Must be 'vg', 'led_voltage', or 'wavelength'")
        return v

    @field_validator("baseline_mode")
    @classmethod
    def validate_baseline_mode(cls, v: str) -> str:
        """Validate baseline_mode is one of the supported modes."""
        if v not in ["none", "auto", "fixed"]:
            raise ValueError(f"Invalid baseline_mode: {v}. Must be 'none', 'auto', or 'fixed'")
        return v

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        """Validate transconductance method is one of the supported methods."""
        if v not in ["gradient", "savgol"]:
            raise ValueError(f"Invalid method: {v}. Must be 'gradient' or 'savgol'")
        return v

    @field_validator("window_length")
    @classmethod
    def validate_window_length(cls, v: int) -> int:
        """Validate window_length is odd for Savitzky-Golay filter."""
        if v % 2 == 0:
            raise ValueError(f"window_length must be odd, got {v}")
        return v

    # ═══════════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════════

    def reset_wizard_state(self) -> None:
        """
        Reset wizard state to start fresh, keeping only application paths.

        Clears:
        - chip_number, plot_type
        - config_mode, preset
        - seq_numbers

        Preserves:
        - stage_dir, history_dir, output_dir, chip_group
        """
        self.chip_number = None
        self.plot_type = None
        self.config_mode = None
        self.preset = None
        self.seq_numbers = []

    def to_config_dict(self) -> dict:
        """
        Convert session to dict for backward compatibility with plotting functions.

        Returns
        -------
        dict
            Configuration dictionary compatible with legacy plot_config format
        """
        return self.model_dump()

    def chip_name(self) -> str:
        """
        Get formatted chip name (e.g., 'Alisson67').

        Returns
        -------
        str
            Chip name in format '{chip_group}{chip_number}'

        Raises
        ------
        ValueError
            If chip_number is not set
        """
        if self.chip_number is None:
            raise ValueError("chip_number is not set")
        return f"{self.chip_group}{self.chip_number}"
