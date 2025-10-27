"""
Plotting module for measurement data visualization.

This module is organized by measurement procedure type:
- its.py: ITS (current vs time) plots
- ivg.py: IVg (current vs gate voltage) plots
- transconductance.py: Transconductance (gm = dI/dVg) plots
- overlays.py: Multi-experiment overlays and animations
- plot_utils.py: Shared utilities and helper functions
- styles.py: Matplotlib style configurations
"""

from pathlib import Path

# Import all plotting functions
from src.plotting.its import (
    plot_its_overlay,
    plot_its_dark,
)

from src.plotting.ivg import (
    plot_ivg_sequence,
)

from src.plotting.transconductance import (
    plot_ivg_transconductance,
    plot_ivg_transconductance_savgol,
)

from src.plotting.overlays import (
    ivg_sequence_gif,
)

# Import utilities
from src.plotting.plot_utils import (
    detect_light_on_window,
    interpolate_baseline,
    get_chip_label,
    calculate_transconductance,
    calculate_light_window,
    combine_metadata_by_seq,
    load_and_prepare_metadata,
    segment_voltage_sweep,
)

from src.plotting.styles import (
    set_plot_style,
)

# Global configuration
BASE_DIR = Path(".")
FIG_DIR = Path("figs")
FIG_DIR.mkdir(exist_ok=True)

__all__ = [
    # ITS plotting
    "plot_its_overlay",
    "plot_its_dark",
    # IVg plotting
    "plot_ivg_sequence",
    # Transconductance plotting
    "plot_ivg_transconductance",
    "plot_ivg_transconductance_savgol",
    # Overlays and animations
    "ivg_sequence_gif",
    # Utilities
    "detect_light_on_window",
    "interpolate_baseline",
    "get_chip_label",
    "calculate_transconductance",
    "calculate_light_window",
    "combine_metadata_by_seq",
    "load_and_prepare_metadata",
    "segment_voltage_sweep",
    # Styles
    "set_plot_style",
    # Configuration
    "BASE_DIR",
    "FIG_DIR",
]
