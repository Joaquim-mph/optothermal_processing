"""
Plotting module for measurement data visualization.

Organized as one module per measurement procedure, plus a `shared/`
subpackage for cross-cutting infrastructure.

Procedure modules:
- its.py: ITS (current vs time) plots
- ivg.py: IVg (current vs gate voltage) plots
- vvg.py: VVg (voltage vs gate voltage) plots
- vt.py: Vt (voltage vs time) plots
- transconductance.py: Transconductance (gm = dI/dVg) plots
- cnp_time.py: Charge-neutrality-point vs time plots
- photoresponse.py / its_photoresponse.py: Photoresponse plots
- laser_calibration.py: Laser power calibration plots
- ivg_by_sample.py: IVg comparison across samples
- its_relaxation_fit.py / its_relaxation_individual.py: ITS relaxation fits
- consecutive_sweep_diff.py: Differences between consecutive sweeps

Shared infrastructure (`shared/`):
- config.py: PlotConfig and output-path resolution
- styles.py: Matplotlib style/theme configuration
- formatters.py: Legend/label formatters
- plot_utils.py: Shared data-prep and helper functions
- transforms.py: Resistance/conductance conversions
- batch.py: Batch-plot orchestration from YAML configs
"""

from pathlib import Path

# --- Procedure plotting functions ---
from src.plotting.its import (
    plot_its_overlay,
    plot_its_dark,
    plot_its_sequential,
)
from src.plotting.ivg import plot_ivg_sequence
from src.plotting.vvg import plot_vvg_sequence
from src.plotting.vt import plot_vt_overlay, plot_vt_sequential
from src.plotting.transconductance import (
    plot_ivg_transconductance,
    plot_ivg_transconductance_savgol,
)
from src.plotting.cnp_time import plot_cnp_vs_time
from src.plotting.photoresponse import plot_photoresponse
from src.plotting.its_photoresponse import plot_its_photoresponse
from src.plotting.laser_calibration import (
    plot_laser_calibration,
    plot_laser_calibration_comparison,
)
from src.plotting.ivg_by_sample import plot_ivg_by_sample
from src.plotting.its_relaxation_fit import (
    plot_its_relaxation_fits,
    plot_single_its_relaxation_fit,
)
from src.plotting.its_relaxation_individual import generate_individual_relaxation_plots
from src.plotting.consecutive_sweep_diff import plot_consecutive_sweep_differences

# --- Shared infrastructure ---
from src.plotting.shared.plot_utils import (
    detect_light_on_window,
    interpolate_baseline,
    get_chip_label,
    calculate_transconductance,
    calculate_light_window,
    combine_metadata_by_seq,
    load_and_prepare_metadata,
    segment_voltage_sweep,
)
from src.plotting.shared.styles import set_plot_style

# Global configuration
BASE_DIR = Path(".")
FIG_DIR = Path("figs")
FIG_DIR.mkdir(exist_ok=True)

__all__ = [
    # ITS plotting
    "plot_its_overlay",
    "plot_its_dark",
    "plot_its_sequential",
    "plot_its_photoresponse",
    "plot_its_relaxation_fits",
    "plot_single_its_relaxation_fit",
    "generate_individual_relaxation_plots",
    "plot_consecutive_sweep_differences",
    # IVg plotting
    "plot_ivg_sequence",
    "plot_ivg_by_sample",
    "plot_ivg_transconductance",
    "plot_ivg_transconductance_savgol",
    # VVg / Vt plotting
    "plot_vvg_sequence",
    "plot_vt_overlay",
    "plot_vt_sequential",
    # Other procedures
    "plot_cnp_vs_time",
    "plot_photoresponse",
    "plot_laser_calibration",
    "plot_laser_calibration_comparison",
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
