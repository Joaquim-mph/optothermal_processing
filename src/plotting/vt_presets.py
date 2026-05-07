"""
Vt Preset Configuration System

Defines preset configurations for common Vt plotting scenarios:
- Dark experiments (no illumination)
- Power sweep (same wavelength, different LED powers)
- Spectral response (same power, different wavelengths)
- Custom (fully configurable)

Mirrors the structure of `its_presets` so the two preset systems share the
same field set and helper API.
"""

from dataclasses import dataclass
from typing import Optional, Literal


@dataclass
class VtPreset:
    """Vt plotting preset configuration.

    Attributes
    ----------
    name : str
        Display name of the preset
    description : str
        User-friendly description
    baseline_mode : {"auto", "fixed", "none"}
        Baseline correction mode:
        - "auto": Calculate from LED ON+OFF period / baseline_auto_divisor
        - "fixed": Use baseline_value
        - "none": No baseline correction (for dark experiments)
    baseline_value : float, optional
        Fixed baseline time in seconds (used if baseline_mode="fixed")
    baseline_auto_divisor : float
        Divisor for auto baseline calculation (period / divisor)
        Default: 2.0 (baseline at half the period)
    plot_start_time : float
        Start time for x-axis in seconds (default: 20.0)
    legend_by : str
        Legend grouping field: "wavelength", "led_voltage", "vg", "power", "datetime"
    padding : float
        Y-axis padding as fraction (0.02 = 2%)
    check_duration_mismatch : bool
        Enable duration mismatch warning (passed through to plot_vt_overlay
        when supported; ignored otherwise — kept for parity with ITSPreset)
    duration_tolerance : float
        Maximum allowed variation in durations (0.10 = 10%)
    """

    name: str
    description: str

    # Baseline configuration
    baseline_mode: Literal["auto", "fixed", "none"]
    baseline_value: Optional[float] = None
    baseline_auto_divisor: float = 2.0

    # Plot configuration
    plot_start_time: float = 20.0
    legend_by: str = "wavelength"
    padding: float = 0.02

    # Validation
    check_duration_mismatch: bool = True
    duration_tolerance: float = 0.10


# Built-in preset configurations
PRESETS = {
    "dark": VtPreset(
        name="Dark Experiments",
        description="No illumination - voltage drift/stability",
        baseline_mode="none",
        plot_start_time=1.0,  # Start at 1s instead of 20s for dark experiments
        legend_by="vg",
        padding=0.02,
        check_duration_mismatch=True,
        duration_tolerance=0.10,
    ),

    "light_power_sweep": VtPreset(
        name="Power Sweep (Same λ)",
        description="Different LED powers, same wavelength",
        baseline_mode="auto",
        baseline_auto_divisor=2.0,  # baseline = period / 2
        plot_start_time=20.0,
        legend_by="led_voltage",
        padding=0.02,
        check_duration_mismatch=True,
        duration_tolerance=0.10,
    ),

    "light_spectral": VtPreset(
        name="Spectral Response (Same Power)",
        description="Different wavelengths, same LED power",
        baseline_mode="auto",
        baseline_auto_divisor=2.0,  # baseline = period / 2
        plot_start_time=20.0,
        legend_by="wavelength",
        padding=0.02,
        check_duration_mismatch=True,
        duration_tolerance=0.10,
    ),

    "custom": VtPreset(
        name="Custom",
        description="Fully configurable parameters",
        baseline_mode="fixed",
        baseline_value=60.0,
        plot_start_time=20.0,
        legend_by="wavelength",
        padding=0.02,
        check_duration_mismatch=False,
        duration_tolerance=0.10,
    ),
}


def get_preset(name: str) -> Optional[VtPreset]:
    """
    Get a preset configuration by name.

    Parameters
    ----------
    name : str
        Preset name (e.g., "dark", "light_power_sweep")

    Returns
    -------
    VtPreset or None
        Preset configuration, or None if not found
    """
    return PRESETS.get(name)


def list_presets() -> dict[str, VtPreset]:
    """
    Get all available presets.

    Returns
    -------
    dict[str, VtPreset]
        Dictionary of preset name -> preset configuration
    """
    return PRESETS.copy()


def preset_summary(preset: VtPreset) -> str:
    """
    Generate a human-readable summary of a preset.

    Parameters
    ----------
    preset : VtPreset
        Preset configuration

    Returns
    -------
    str
        Multi-line summary string
    """
    lines = [
        f"Preset: {preset.name}",
        f"  {preset.description}",
        "",
        "Configuration:",
    ]

    # Baseline mode
    if preset.baseline_mode == "none":
        lines.append("  • Baseline: None (no correction)")
    elif preset.baseline_mode == "auto":
        lines.append(f"  • Baseline: Auto (LED period / {preset.baseline_auto_divisor})")
    else:
        lines.append(f"  • Baseline: Fixed at {preset.baseline_value}s")

    # Other settings
    lines.append(f"  • Plot start: {preset.plot_start_time}s")
    lines.append(f"  • Legend by: {preset.legend_by}")
    lines.append(f"  • Y-axis padding: {preset.padding*100:.0f}%")

    # Duration check
    if preset.check_duration_mismatch:
        lines.append(f"  • Duration check: Enabled (±{preset.duration_tolerance*100:.0f}% tolerance)")
    else:
        lines.append("  • Duration check: Disabled")

    return "\n".join(lines)
