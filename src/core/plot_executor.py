"""
Plot Executor -- standalone plot generation logic.

Extracted from src/tui/screens/processing/plot_generation.py so that both
the Textual TUI and the PyQt6 GUI (and any future frontend) can generate
plots without duplicating the dispatch logic.

The key function is `execute_plot()`, which takes a callback interface
for progress updates and returns a `PlotResult` on success.
"""

from __future__ import annotations
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Protocol

import polars as pl

from src.plotting.config import PlotConfig

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════

class ProgressCallback(Protocol):
    """Callback interface for reporting progress from the executor."""

    def __call__(self, percent: float, status: str) -> None: ...


@dataclass
class PlotResult:
    """Result of a successful plot generation."""
    output_path: Path
    file_size_mb: float
    elapsed_seconds: float
    num_experiments: int


@dataclass
class PlotRequest:
    """All inputs needed to generate a plot."""
    chip_number: int
    chip_group: str
    plot_type: str
    seq_numbers: List[int]
    config: dict
    stage_dir: Path = Path("data/02_stage/raw_measurements")
    history_dir: Path = Path("data/02_stage/chip_histories")
    output_dir: Path = Path("figs")


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _noop_progress(percent: float, status: str) -> None:
    pass


def _load_and_prepare_metadata(
    request: PlotRequest,
    progress: ProgressCallback,
) -> tuple[pl.DataFrame, Path, PlotConfig, str]:
    """
    Load chip history, filter to selected experiments, prepare paths.

    Returns (meta, stage_dir, plot_config, plot_tag).
    """
    progress(10, "Loading experiment history...")

    history_dir = request.history_dir
    stage_dir = request.stage_dir

    chip_name = f"{request.chip_group}{request.chip_number}"
    history_file = history_dir / f"{chip_name}_history.parquet"

    if not history_file.exists():
        raise FileNotFoundError(f"History file not found: {history_file}")

    history = pl.read_parquet(history_file)
    logger.info(f"Loaded history with {history.height} total experiments")

    meta = history.filter(pl.col("seq").is_in(request.seq_numbers))
    if meta.height == 0:
        raise ValueError(f"No experiments found for seq numbers: {request.seq_numbers}")

    # Validate all seq numbers found
    found_seqs = set(meta["seq"].to_list())
    missing = set(request.seq_numbers) - found_seqs
    if missing:
        raise ValueError(f"Seq numbers not found in history: {sorted(missing)}")

    # Rename parquet_path -> source_file for plotting compatibility
    if "parquet_path" in meta.columns:
        if "source_file" in meta.columns:
            meta = meta.rename({"source_file": "raw_source_file"})
        meta = meta.rename({"parquet_path": "source_file"})
    elif "source_file" not in meta.columns:
        raise ValueError("History file missing both parquet_path and source_file columns")

    # Make source_file paths relative to stage_dir
    stage_dir_str = str(stage_dir)

    def make_relative(path_str: str) -> str:
        if path_str.startswith(stage_dir_str + "/"):
            return path_str[len(stage_dir_str) + 1:]
        elif path_str.startswith(stage_dir_str):
            return path_str[len(stage_dir_str):]
        return path_str

    meta = meta.with_columns(
        pl.col("source_file").map_elements(make_relative, return_dtype=pl.Utf8).alias("source_file")
    )

    progress(30, f"Loaded {meta.height} experiment(s)...")

    # Output directory
    base_output_dir = request.output_dir
    chip_subdir_name = chip_name
    base_str = str(base_output_dir)
    if base_str.endswith(f"/{chip_subdir_name}") or base_str.endswith(f"/{chip_subdir_name}/"):
        output_dir = base_output_dir
    elif base_str.endswith(chip_subdir_name):
        output_dir = base_output_dir
    else:
        output_dir = base_output_dir / chip_subdir_name

    output_dir.mkdir(parents=True, exist_ok=True)

    plot_config = PlotConfig(
        output_dir=output_dir,
        use_proc_subdirs=False,
        chip_subdir_enabled=False,
        auto_subcategories=False,
    )

    # Plot tag from seq numbers
    seq_str = "_".join(map(str, request.seq_numbers[:10]))
    if len(request.seq_numbers) > 10:
        seq_str += f"_plus{len(request.seq_numbers) - 10}more"

    return meta, stage_dir, plot_config, seq_str


def _detect_all_dark(meta: pl.DataFrame) -> bool:
    """Check if all ITS experiments are dark (no laser)."""
    its_df = meta.filter(pl.col("proc") == "It")
    if its_df.height == 0:
        return False

    if "has_light" in its_df.columns:
        try:
            vals = its_df["has_light"].to_list()
            return all(not v for v in vals if v is not None)
        except Exception:
            pass

    if "laser_voltage_v" in its_df.columns:
        try:
            voltages = its_df["laser_voltage_v"].to_list()
            return all(v < 0.1 for v in voltages if v is not None)
        except Exception:
            pass

    return False


def _determine_output_filename(request: PlotRequest, meta: pl.DataFrame, plot_tag: str, config: dict) -> str:
    """Determine the expected output filename for the plot."""
    chip_prefix = (
        f"{request.chip_group}{request.chip_number}"
        if request.chip_group
        else f"encap{request.chip_number}"
    )

    if request.plot_type == "ITS":
        all_dark = _detect_all_dark(meta)
        baseline_mode = config.get("baseline_mode", "fixed")
        raw_suffix = "_raw" if baseline_mode == "none" else ""
        if all_dark:
            return f"{chip_prefix}_It_dark_{plot_tag}{raw_suffix}.png"
        return f"{chip_prefix}_It_{plot_tag}{raw_suffix}.png"

    elif request.plot_type == "IVg":
        return f"{chip_prefix}_IVg_{plot_tag}.png"

    elif request.plot_type == "Transconductance":
        method = config.get("method", "gradient")
        if method == "savgol":
            return f"{chip_prefix}_gm_savgol_{plot_tag}.png"
        return f"{chip_prefix}_gm_{plot_tag}.png"

    elif request.plot_type == "VVg":
        return f"{chip_prefix}_VVg_{plot_tag}.png"

    elif request.plot_type == "Vt":
        return f"{chip_prefix}_Vt_{plot_tag}.png"

    elif request.plot_type == "CNP":
        metric = config.get("cnp_metric", "cnp_voltage")
        return f"{chip_prefix}_CNP_{metric}_time.png"

    elif request.plot_type == "Photoresponse":
        mode = config.get("photoresponse_mode", "power")
        return f"{chip_prefix}_photoresponse_{mode}.png"

    return f"{chip_prefix}_{request.plot_type}_{plot_tag}.png"


# ═══════════════════════════════════════════════════════════════════
# Plot dispatch
# ═══════════════════════════════════════════════════════════════════

def _generate_its(meta, stage_dir, plot_tag, plot_config, config, progress):
    """Generate ITS plot."""
    from src.plotting import its

    output_dir = plot_config.output_dir
    its.FIG_DIR = output_dir

    legend_by = config.get("legend_by", "vg")
    baseline_t = config.get("baseline", 60.0)
    padding = config.get("padding", 0.05)
    baseline_mode = config.get("baseline_mode", "fixed")
    baseline_auto_divisor = config.get("baseline_auto_divisor", 2.0)
    plot_start_time = config.get("plot_start_time", 20.0)
    check_duration = config.get("check_duration_mismatch", False)
    duration_tol = config.get("duration_tolerance", 0.10)
    conductance = config.get("conductance", False)
    absolute = config.get("absolute", False)

    all_dark = _detect_all_dark(meta)

    import sys, io
    stdout_capture = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = stdout_capture
        if all_dark:
            its.plot_its_dark(
                meta, stage_dir, plot_tag,
                baseline_t=baseline_t, baseline_mode=baseline_mode,
                baseline_auto_divisor=baseline_auto_divisor,
                plot_start_time=plot_start_time,
                legend_by="vg", padding=padding,
                check_duration_mismatch=check_duration,
                duration_tolerance=duration_tol,
                conductance=conductance, absolute=absolute,
                config=plot_config,
            )
        else:
            its.plot_its_overlay(
                meta, stage_dir, plot_tag,
                baseline_t=baseline_t, baseline_mode=baseline_mode,
                baseline_auto_divisor=baseline_auto_divisor,
                plot_start_time=plot_start_time,
                legend_by=legend_by, padding=padding,
                check_duration_mismatch=check_duration,
                duration_tolerance=duration_tol,
                conductance=conductance, absolute=absolute,
                config=plot_config,
            )
    finally:
        sys.stdout = old_stdout
        output = stdout_capture.getvalue()
        if output:
            logger.info(f"Plotting output:\n{output}")


def _generate_ivg(meta, stage_dir, plot_tag, plot_config, config, progress):
    """Generate IVg plot."""
    from src.plotting import ivg
    ivg.FIG_DIR = plot_config.output_dir
    conductance = config.get("conductance", False)
    absolute = config.get("absolute", False)
    ivg.plot_ivg_sequence(
        meta, stage_dir, plot_tag,
        conductance=conductance, absolute=absolute,
        config=plot_config,
    )


def _generate_transconductance(meta, stage_dir, plot_tag, plot_config, config, progress):
    """Generate transconductance plot."""
    from src.plotting import transconductance
    transconductance.FIG_DIR = plot_config.output_dir
    method = config.get("method", "gradient")
    if method == "savgol":
        transconductance.plot_ivg_transconductance_savgol(
            meta, stage_dir, plot_tag,
            window_length=config.get("window_length", 9),
            polyorder=config.get("polyorder", 3),
            config=plot_config,
        )
    else:
        transconductance.plot_ivg_transconductance(
            meta, stage_dir, plot_tag, config=plot_config,
        )


def _generate_vvg(meta, stage_dir, plot_tag, plot_config, config, progress):
    """Generate VVg plot."""
    from src.plotting import vvg
    vvg.FIG_DIR = plot_config.output_dir
    vvg.plot_vvg_sequence(
        meta, stage_dir, plot_tag,
        resistance=config.get("resistance", False),
        absolute=config.get("absolute", False),
        config=plot_config,
    )


def _generate_vt(meta, stage_dir, plot_tag, plot_config, config, progress):
    """Generate Vt plot."""
    from src.plotting import vt
    vt.FIG_DIR = plot_config.output_dir
    vt.plot_vt_overlay(
        meta, stage_dir, plot_tag,
        baseline_t=config.get("baseline", 60.0),
        baseline_mode=config.get("baseline_mode", "fixed"),
        baseline_auto_divisor=config.get("baseline_auto_divisor", 2.0),
        plot_start_time=config.get("plot_start_time", 20.0),
        legend_by=config.get("legend_by", "wavelength"),
        padding=config.get("padding", 0.05),
        resistance=config.get("resistance", False),
        absolute=config.get("absolute", False),
        config=plot_config,
    )


def _generate_cnp(request, progress):
    """Generate CNP time evolution plot (requires enriched history)."""
    from src.plotting import cnp_time
    from src.tui.history_detection import load_chip_history

    progress(20, "Loading enriched history...")
    enriched_dir = Path("data/03_derived/chip_histories_enriched")
    history, is_enriched = load_chip_history(
        request.chip_number, request.chip_group,
        request.history_dir, enriched_dir,
        prefer_enriched=True, require_enriched=True,
    )
    logger.info(f"Loaded enriched history with {history.height} experiments")

    progress(40, "Generating CNP plot...")
    output_dir = request.output_dir / f"{request.chip_group}{request.chip_number}"
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_config = PlotConfig(
        output_dir=output_dir,
        use_proc_subdirs=False,
        chip_subdir_enabled=False,
        auto_subcategories=False,
    )
    cnp_time.FIG_DIR = output_dir

    show_illumination = request.config.get("cnp_show_illumination", True)
    chip_name = f"{request.chip_group}{request.chip_number}"

    output_file = cnp_time.plot_cnp_vs_time(
        history, chip_name,
        show_light=show_illumination,
        config=plot_config,
    )
    if not output_file:
        raise ValueError("CNP plot returned no output file")
    return Path(output_file)


def _generate_photoresponse(request, progress):
    """Generate photoresponse analysis plot (requires enriched history)."""
    from src.plotting import photoresponse
    from src.tui.history_detection import load_chip_history

    progress(20, "Loading enriched history...")
    enriched_dir = Path("data/03_derived/chip_histories_enriched")
    history, is_enriched = load_chip_history(
        request.chip_number, request.chip_group,
        request.history_dir, enriched_dir,
        prefer_enriched=True, require_enriched=True,
    )
    logger.info(f"Loaded enriched history with {history.height} experiments")

    progress(40, "Generating photoresponse plot...")
    output_dir = request.output_dir / f"{request.chip_group}{request.chip_number}"
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_config = PlotConfig(
        output_dir=output_dir,
        use_proc_subdirs=False,
        chip_subdir_enabled=False,
        auto_subcategories=False,
    )
    photoresponse.FIG_DIR = output_dir

    chip_name = f"{request.chip_group}{request.chip_number}"
    mode = request.config.get("photoresponse_mode", "power")
    filter_vg = request.config.get("photoresponse_filter_vg")
    filter_wl = request.config.get("photoresponse_filter_wl")

    output_file = photoresponse.plot_photoresponse(
        history, chip_name, mode,
        filter_vg=filter_vg,
        filter_wavelength=filter_wl,
        config=plot_config,
    )
    if not output_file:
        raise ValueError("Photoresponse plot returned no output file")
    return Path(output_file)


def _generate_laser_calibration(request, progress):
    """Generate laser calibration plot (global measurements from manifest)."""
    from src.plotting import laser_calibration

    progress(20, "Loading manifest...")
    manifest_path = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
    if not manifest_path.exists():
        raise FileNotFoundError("Manifest not found. Run 'biotite stage-all' first.")

    manifest = pl.read_parquet(manifest_path)
    calibrations = manifest.filter(pl.col("proc") == "LaserCalibration")

    time_col = "start_time_utc" if "start_time_utc" in calibrations.columns else "start_dt"
    calibrations = calibrations.sort(time_col)
    calibrations = calibrations.with_row_index(name="seq", offset=1)

    if "path" in calibrations.columns and "parquet_path" not in calibrations.columns:
        calibrations = calibrations.rename({"path": "parquet_path"})

    # Filter to selected seq numbers
    if request.seq_numbers:
        calibrations = calibrations.filter(pl.col("seq").is_in(request.seq_numbers))

    if calibrations.height == 0:
        raise ValueError("No calibrations match the selection")

    progress(40, "Generating calibration plot...")
    output_dir = request.output_dir / "laser_calibrations"
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_config = PlotConfig(
        output_dir=output_dir,
        use_proc_subdirs=False,
        chip_subdir_enabled=False,
        auto_subcategories=False,
    )
    laser_calibration.FIG_DIR = output_dir

    power_unit = request.config.get("power_unit", "uW")
    group_by_wavelength = request.config.get("group_by_wavelength", True)
    show_markers = request.config.get("show_markers", False)
    comparison = request.config.get("comparison", False)

    if comparison:
        output_file = laser_calibration.plot_laser_calibration_comparison(
            calibrations, Path("."), "calibrations",
            group_by="wavelength", config=plot_config,
        )
    else:
        output_file = laser_calibration.plot_laser_calibration(
            calibrations, Path("."), "calibrations",
            group_by_wavelength=group_by_wavelength,
            show_markers=show_markers,
            power_unit=power_unit,
            config=plot_config,
        )

    if not output_file:
        raise ValueError("Laser calibration plot returned no output file")
    return Path(output_file)


def _generate_its_relaxation(request, progress):
    """Generate ITS relaxation fits plot (requires derived metrics)."""
    from src.plotting.its_relaxation_fit import plot_its_relaxation_fits

    progress(20, "Loading chip history...")
    chip_name = f"{request.chip_group}{request.chip_number}"
    history_path = request.history_dir / f"{chip_name}_history.parquet"
    if not history_path.exists():
        raise FileNotFoundError(f"History not found: {history_path}")

    history = pl.read_parquet(history_path)
    selected = history.filter(pl.col("seq").is_in(request.seq_numbers))

    progress(40, "Loading relaxation metrics...")
    metrics_path = Path("data/03_derived/_metrics/metrics.parquet")
    if not metrics_path.exists():
        raise FileNotFoundError("Metrics not found. Run 'biotite derive-all-metrics' first.")

    all_metrics = pl.read_parquet(metrics_path)
    selected_metrics = all_metrics.filter(
        (pl.col("metric_name") == "relaxation_time") &
        (pl.col("run_id").is_in(selected["run_id"]))
    )

    progress(60, "Generating relaxation plot...")
    output_dir = request.output_dir / chip_name
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_config = PlotConfig(
        output_dir=output_dir,
        use_proc_subdirs=False,
        chip_subdir_enabled=False,
        auto_subcategories=False,
    )

    plot_tag = f"{chip_name}_It_relaxation"
    output_file = plot_its_relaxation_fits(
        df=selected,
        metrics_df=selected_metrics,
        base_dir=Path("."),
        tag=plot_tag,
        config=plot_config,
    )

    if not output_file:
        raise ValueError("ITS relaxation plot returned no output file")
    return Path(output_file)


# ═══════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════

def execute_plot(
    request: PlotRequest,
    progress: Optional[ProgressCallback] = None,
) -> PlotResult:
    """
    Execute a plot generation request.

    Parameters
    ----------
    request : PlotRequest
        All inputs needed to generate the plot.
    progress : ProgressCallback, optional
        Callback for reporting progress (percent, status_msg).

    Returns
    -------
    PlotResult
        Result with output path, file size, elapsed time, experiment count.

    Raises
    ------
    FileNotFoundError
        If history file or data not found.
    ValueError
        If no matching experiments or invalid configuration.
    """
    if progress is None:
        progress = _noop_progress

    start_time = time.time()

    # Force non-interactive matplotlib backend
    import matplotlib
    matplotlib.use("Agg")

    logger.info("=" * 80)
    logger.info(f"Starting plot generation: {request.chip_group}{request.chip_number} / {request.plot_type}")
    logger.info(f"Seq numbers: {request.seq_numbers}")

    # ── Special plot types that load their own data ──
    special_dispatch = {
        "CNP": _generate_cnp,
        "Photoresponse": _generate_photoresponse,
        "LaserCalibration": _generate_laser_calibration,
        "ITSRelaxation": _generate_its_relaxation,
    }

    special_handler = special_dispatch.get(request.plot_type)
    if special_handler is not None:
        output_path = special_handler(request, progress)

        progress(90, "Finalizing...")
        file_size = 0.0
        if output_path.exists():
            file_size = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Output file: {output_path} ({file_size:.2f} MB)")

        elapsed = time.time() - start_time
        progress(100, "Complete!")
        logger.info(f"Plot generation completed in {elapsed:.2f}s")
        logger.info("=" * 80)

        return PlotResult(
            output_path=output_path,
            file_size_mb=file_size,
            elapsed_seconds=elapsed,
            num_experiments=max(len(request.seq_numbers), 1),
        )

    # ── Standard plot types: load history + metadata ──
    meta, stage_dir, plot_config, plot_tag = _load_and_prepare_metadata(request, progress)

    progress(50, "Generating plot...")

    # ── Dispatch to plot type handler ──
    dispatch = {
        "ITS": _generate_its,
        "IVg": _generate_ivg,
        "Transconductance": _generate_transconductance,
        "VVg": _generate_vvg,
        "Vt": _generate_vt,
    }

    handler = dispatch.get(request.plot_type)
    if handler is None:
        raise ValueError(f"Unknown plot type: {request.plot_type}")

    handler(meta, stage_dir, plot_tag, plot_config, request.config, progress)

    progress(90, "Saving file...")

    # ── Determine output path ──
    filename = _determine_output_filename(request, meta, plot_tag, request.config)
    output_path = plot_config.output_dir / filename

    file_size = 0.0
    if output_path.exists():
        file_size = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Output file: {output_path} ({file_size:.2f} MB)")
    else:
        logger.warning(f"Expected output not found: {output_path}")
        # Try to find any recently created file in the output directory
        output_dir = plot_config.output_dir
        if output_dir.exists():
            pngs = sorted(output_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
            if pngs:
                output_path = pngs[0]
                file_size = output_path.stat().st_size / (1024 * 1024)
                logger.info(f"Found output file: {output_path} ({file_size:.2f} MB)")

    elapsed = time.time() - start_time
    progress(100, "Complete!")
    logger.info(f"Plot generation completed in {elapsed:.2f}s")
    logger.info("=" * 80)

    return PlotResult(
        output_path=output_path,
        file_size_mb=file_size,
        elapsed_seconds=elapsed,
        num_experiments=len(request.seq_numbers),
    )
