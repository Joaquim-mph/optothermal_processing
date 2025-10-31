"""
Laser calibration matching for light experiments.

Associates each light experiment with its appropriate laser calibration
based on temporal proximity and wavelength matching. Enables proper
power normalization and calibration tracking.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Literal, Tuple
import polars as pl
import numpy as np


@dataclass
class CalibrationMatch:
    """
    Result of calibration matching for a single experiment.

    Attributes
    ----------
    calibration_path : str or None
        Path to matched calibration Parquet file, or None if no match
    calibration_seq : int or None
        Seq number of matched calibration (for reference)
    time_delta_hours : float or None
        Hours between experiment and calibration (negative if cal is after)
    warning : str or None
        Warning message if issues with match, or None if perfect match
    status : str
        Match quality: "perfect", "acceptable", "stale", "future", "missing"
    """
    calibration_path: Optional[str]
    calibration_seq: Optional[int]
    time_delta_hours: Optional[float]
    warning: Optional[str]
    status: Literal["perfect", "acceptable", "stale", "future", "missing"]


@dataclass
class EnrichmentReport:
    """
    Report for single chip history enrichment.

    Attributes
    ----------
    chip_name : str
        Chip identifier (e.g., "Alisson67")
    total_light_exps : int
        Total number of light experiments processed
    matched_perfect : int
        Experiments matched with recent prior calibration
    matched_future : int
        Experiments matched with future calibration (suboptimal)
    matched_stale : int
        Experiments matched with old calibration (>24h)
    missing : int
        Experiments with no calibration match
    warnings : list[str]
        List of warning messages
    errors : list[str]
        List of error messages
    """
    chip_name: str
    total_light_exps: int
    matched_perfect: int
    matched_future: int
    matched_stale: int
    missing: int
    warnings: List[str]
    errors: List[str]


class CalibrationMatcher:
    """
    Matches light experiments to laser calibrations.

    Loads all available laser calibrations from the manifest and provides
    methods to find appropriate calibrations for light experiments based
    on wavelength and temporal proximity.

    Parameters
    ----------
    manifest_path : Path
        Path to manifest.parquet containing all staged measurements

    Attributes
    ----------
    calibrations : pl.DataFrame
        DataFrame of all LaserCalibration experiments with columns:
        - wavelength_nm: float
        - start_dt: datetime
        - parquet_path: str
        - seq: int (if from chip history)
        - date_local: str
    """

    def __init__(self, manifest_path: Path):
        """
        Initialize calibration matcher by loading calibrations from manifest.

        Parameters
        ----------
        manifest_path : Path
            Path to manifest.parquet file

        Raises
        ------
        FileNotFoundError
            If manifest file doesn't exist
        ValueError
            If no LaserCalibration experiments found in manifest
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        # Load manifest
        manifest = pl.read_parquet(manifest_path)

        # Filter to LaserCalibration experiments
        self.calibrations = manifest.filter(pl.col("proc") == "LaserCalibration")

        if self.calibrations.height == 0:
            raise ValueError(
                f"No LaserCalibration experiments found in manifest.\n"
                f"Please stage calibration data first with: stage-all"
            )

        # Normalize column names for compatibility
        # Manifest uses: start_time_utc (String), path
        # We need: start_dt (Datetime), parquet_path
        if "start_time_utc" in self.calibrations.columns and "start_dt" not in self.calibrations.columns:
            # Cast string to datetime if needed
            if self.calibrations["start_time_utc"].dtype == pl.String:
                self.calibrations = self.calibrations.with_columns(
                    pl.col("start_time_utc").str.to_datetime(time_zone="UTC").alias("start_time_utc")
                )
            self.calibrations = self.calibrations.rename({"start_time_utc": "start_dt"})

        if "path" in self.calibrations.columns and "parquet_path" not in self.calibrations.columns:
            self.calibrations = self.calibrations.rename({"path": "parquet_path"})

        # Ensure required columns exist
        required_cols = {"wavelength_nm", "start_dt", "parquet_path"}
        missing = required_cols - set(self.calibrations.columns)
        if missing:
            raise ValueError(f"Manifest missing required columns: {missing}")

        # Sort by time for efficient searching
        self.calibrations = self.calibrations.sort("start_dt")

        # Get available wavelengths for reporting
        self.available_wavelengths = sorted(
            self.calibrations["wavelength_nm"].drop_nulls().unique().to_list()
        )

    def get_power_from_calibration(
        self,
        calibration_path: str,
        laser_voltage: float,
    ) -> Optional[float]:
        """
        Interpolate irradiated power from calibration curve.

        Reads the calibration Parquet file and interpolates the power
        at the given laser voltage using the calibration curve.

        Parameters
        ----------
        calibration_path : str
            Path to calibration Parquet file
        laser_voltage : float
            Laser voltage (V) to interpolate at

        Returns
        -------
        float or None
            Interpolated power (W), or None if calibration cannot be read
            or voltage is invalid

        Notes
        -----
        - Uses linear interpolation between calibration points
        - Extrapolates if voltage is outside calibration range (with warning)
        - Returns None if calibration file cannot be read or has invalid data
        """
        try:
            # Read calibration data
            cal_data = pl.read_parquet(calibration_path)

            # Find voltage and power columns (handle variations)
            vl_col = None
            power_col = None

            for col in cal_data.columns:
                col_lower = col.lower().strip()
                if col_lower in ["vl (v)", "laser voltage (v)", "vl"]:
                    vl_col = col
                elif col_lower in ["power (w)", "power", "p (w)"]:
                    power_col = col

            if vl_col is None or power_col is None:
                return None

            # Extract voltage and power arrays
            voltages = cal_data[vl_col].to_numpy()
            powers = cal_data[power_col].to_numpy()

            # Remove any NaN values
            valid_mask = ~(np.isnan(voltages) | np.isnan(powers))
            voltages = voltages[valid_mask]
            powers = powers[valid_mask]

            if len(voltages) < 2:
                # Need at least 2 points for interpolation
                return None

            # Sort by voltage (in case not sorted)
            sort_idx = np.argsort(voltages)
            voltages = voltages[sort_idx]
            powers = powers[sort_idx]

            # Interpolate (extrapolate if outside range)
            interpolated_power = np.interp(laser_voltage, voltages, powers)

            return float(interpolated_power)

        except Exception:
            # If anything goes wrong, return None
            return None

    def find_calibration(
        self,
        experiment_time: datetime,
        experiment_wavelength: float,
        stale_threshold_hours: float = 24.0,
    ) -> CalibrationMatch:
        """
        Find appropriate calibration for a light experiment.

        Searches for laser calibration matching the experiment wavelength
        (strict equality) and closest in time. Prefers calibrations taken
        BEFORE the experiment, but will use future calibrations if necessary.

        Parameters
        ----------
        experiment_time : datetime
            Timestamp of the light experiment
        experiment_wavelength : float
            Wavelength of the experiment (nm) - must match exactly
        stale_threshold_hours : float, optional
            Hours beyond which a calibration is considered stale (default: 24)

        Returns
        -------
        CalibrationMatch
            Match result with calibration path, status, and any warnings

        Examples
        --------
        >>> matcher = CalibrationMatcher(Path("manifest.parquet"))
        >>> match = matcher.find_calibration(
        ...     datetime(2025, 10, 15, 12, 0),
        ...     450.0
        ... )
        >>> print(match.status)
        'perfect'
        """
        # Step 1: Filter by wavelength (strict equality)
        matching_wl = self.calibrations.filter(
            pl.col("wavelength_nm") == experiment_wavelength
        )

        if matching_wl.height == 0:
            # No calibrations for this wavelength at all
            available_str = ", ".join([f"{w:.0f}nm" for w in self.available_wavelengths])
            return CalibrationMatch(
                calibration_path=None,
                calibration_seq=None,
                time_delta_hours=None,
                warning=f"No calibration found for {experiment_wavelength:.0f}nm. Available: [{available_str}]",
                status="missing"
            )

        # Step 2: Find most recent calibration BEFORE experiment (PREFERRED)
        before = matching_wl.filter(
            pl.col("start_dt") < experiment_time
        ).sort("start_dt", descending=True)

        if before.height > 0:
            # Found calibration before experiment (IDEAL)
            cal_row = before.row(0, named=True)
            cal_path = cal_row["parquet_path"]
            cal_time = cal_row["start_dt"]
            time_delta_hours = (experiment_time - cal_time).total_seconds() / 3600

            # Determine status based on freshness
            if time_delta_hours <= stale_threshold_hours:
                # Fresh calibration (within threshold)
                return CalibrationMatch(
                    calibration_path=cal_path,
                    calibration_seq=cal_row.get("seq"),
                    time_delta_hours=time_delta_hours,
                    warning=None,
                    status="perfect"
                )
            else:
                # Stale calibration (old but usable)
                return CalibrationMatch(
                    calibration_path=cal_path,
                    calibration_seq=cal_row.get("seq"),
                    time_delta_hours=time_delta_hours,
                    warning=f"Calibration is {time_delta_hours:.1f}h old (>{stale_threshold_hours:.0f}h threshold)",
                    status="stale"
                )

        # Step 3: No calibration before, try AFTER experiment (SUBOPTIMAL)
        after = matching_wl.filter(
            pl.col("start_dt") > experiment_time
        ).sort("start_dt")

        if after.height > 0:
            # Found calibration after experiment (NOT IDEAL)
            cal_row = after.row(0, named=True)
            cal_path = cal_row["parquet_path"]
            cal_time = cal_row["start_dt"]
            time_delta_hours = -(cal_time - experiment_time).total_seconds() / 3600  # Negative

            return CalibrationMatch(
                calibration_path=cal_path,
                calibration_seq=cal_row.get("seq"),
                time_delta_hours=time_delta_hours,
                warning=f"Using calibration from {abs(time_delta_hours):.1f}h AFTER experiment",
                status="future"
            )

        # Step 4: Should never reach here (matching_wl has rows but no before/after)
        # This could happen if experiment_time equals calibration time exactly
        return CalibrationMatch(
            calibration_path=None,
            calibration_seq=None,
            time_delta_hours=None,
            warning=f"Unexpected: calibration exists for {experiment_wavelength:.0f}nm but no time match",
            status="missing"
        )

    def enrich_chip_history(
        self,
        history_path: Path,
        output_dir: Optional[Path] = None,
        force: bool = False,
        stale_threshold_hours: float = 24.0,
    ) -> EnrichmentReport:
        """
        Add calibration associations to a chip history file.

        Reads a chip history Parquet file from Stage 2, finds calibrations for
        all light experiments, and writes an enriched version to Stage 3 with
        new columns:
        - calibration_parquet_path: Path to calibration file
        - calibration_time_delta_hours: Time between exp and cal
        - irradiated_power_w: Interpolated power (W) at experiment voltage

        Parameters
        ----------
        history_path : Path
            Path to chip history Parquet file (Stage 2: data/02_stage/chip_histories/)
        output_dir : Path, optional
            Output directory for enriched history. If None, defaults to
            data/03_derived/chip_histories_enriched/ (Stage 3)
        force : bool, optional
            If True, overwrite existing enriched history file (default: False)
        stale_threshold_hours : float, optional
            Hours beyond which calibration is considered stale (default: 24)

        Returns
        -------
        EnrichmentReport
            Report summarizing matching results and any issues

        Raises
        ------
        FileNotFoundError
            If history file doesn't exist

        Notes
        -----
        - Only enriches experiments with with_light=True
        - Skips LaserCalibration experiments themselves
        - Reads from Stage 2 (raw metadata), writes to Stage 3 (derived analytics)
        - Does NOT modify Stage 2 files (they remain immutable)
        """
        if not history_path.exists():
            raise FileNotFoundError(f"History file not found: {history_path}")

        chip_name = history_path.stem.replace("_history", "")

        # Determine output directory (Stage 3)
        if output_dir is None:
            # Default: data/03_derived/chip_histories_enriched/
            # Navigate from Stage 2 history dir: data/02_stage/chip_histories/ -> data/03_derived/chip_histories_enriched/
            # Go up two levels from chip_histories to get to data/, then down to 03_derived
            data_dir = history_path.parent.parent  # chip_histories -> 02_stage -> data
            output_dir = data_dir / "03_derived" / "chip_histories_enriched"

        output_dir.mkdir(parents=True, exist_ok=True)
        enriched_path = output_dir / history_path.name

        # Check if already enriched (unless force=True)
        if enriched_path.exists() and not force:
            return EnrichmentReport(
                chip_name=chip_name,
                total_light_exps=0,
                matched_perfect=0,
                matched_future=0,
                matched_stale=0,
                missing=0,
                warnings=[f"Already enriched at {enriched_path} (use --force to overwrite)"],
                errors=[]
            )

        # Load history from Stage 2
        history = pl.read_parquet(history_path)

        # Normalize column names for compatibility
        # History files may use: start_time_utc (instead of start_dt)
        if "start_time_utc" in history.columns and "start_dt" not in history.columns:
            history = history.rename({"start_time_utc": "start_dt"})

        # Normalize column name: history uses "has_light", manifest uses "with_light"
        light_col = "has_light" if "has_light" in history.columns else "with_light"

        # Filter to light experiments (excluding LaserCalibration itself)
        light_experiments = history.filter(
            (pl.col(light_col) == True) &
            (pl.col("proc") != "LaserCalibration")
        )

        total_light_exps = light_experiments.height

        if total_light_exps == 0:
            return EnrichmentReport(
                chip_name=chip_name,
                total_light_exps=0,
                matched_perfect=0,
                matched_future=0,
                matched_stale=0,
                missing=0,
                warnings=["No light experiments found in history"],
                errors=[]
            )

        # Prepare lists for new columns
        cal_paths = []
        cal_time_deltas = []
        irradiated_powers = []
        warnings_list = []

        # Counters for report
        matched_perfect = 0
        matched_future = 0
        matched_stale = 0
        missing = 0

        # Process each light experiment
        for row in light_experiments.iter_rows(named=True):
            exp_time = row["start_dt"]
            exp_wavelength = row.get("wavelength_nm")
            exp_voltage = row.get("laser_voltage_v")
            seq = row["seq"]

            if exp_wavelength is None or not isinstance(exp_wavelength, (int, float)):
                # No wavelength data
                match = CalibrationMatch(
                    calibration_path=None,
                    calibration_seq=None,
                    time_delta_hours=None,
                    warning=f"seq {seq}: No wavelength data in experiment",
                    status="missing"
                )
            else:
                # Find calibration
                match = self.find_calibration(
                    exp_time,
                    exp_wavelength,
                    stale_threshold_hours
                )

            # Collect results
            cal_paths.append(match.calibration_path)
            cal_time_deltas.append(match.time_delta_hours)

            # Calculate irradiated power from calibration
            irradiated_power = None
            if match.calibration_path is not None and exp_voltage is not None:
                irradiated_power = self.get_power_from_calibration(
                    match.calibration_path,
                    exp_voltage
                )
            irradiated_powers.append(irradiated_power)

            # Count by status
            if match.status == "perfect":
                matched_perfect += 1
            elif match.status == "future":
                matched_future += 1
            elif match.status == "stale":
                matched_stale += 1
            elif match.status == "missing":
                missing += 1

            # Collect warnings
            if match.warning:
                warnings_list.append(f"seq {seq}: {match.warning}")

        # Create a DataFrame with seq -> calibration mapping
        calibration_mapping = pl.DataFrame({
            "seq": light_experiments["seq"].to_list(),
            "calibration_parquet_path": cal_paths,
            "calibration_time_delta_hours": cal_time_deltas,
            "irradiated_power_w": irradiated_powers,
        })

        # Join calibration data back to history
        history = history.join(
            calibration_mapping,
            on="seq",
            how="left"
        )

        # Write enriched history to Stage 3 (derived data)
        # Note: Stage 2 files remain unchanged (immutable)
        history.write_parquet(enriched_path)

        # Create report
        report = EnrichmentReport(
            chip_name=chip_name,
            total_light_exps=total_light_exps,
            matched_perfect=matched_perfect,
            matched_future=matched_future,
            matched_stale=matched_stale,
            missing=missing,
            warnings=warnings_list,
            errors=[]
        )

        return report

    def enrich_all_histories(
        self,
        history_dir: Path,
        output_dir: Optional[Path] = None,
        force: bool = False,
        stale_threshold_hours: float = 24.0,
    ) -> List[EnrichmentReport]:
        """
        Process all chip histories in directory.

        Finds all *_history.parquet files in Stage 2 directory and enriches
        them with calibration associations, writing to Stage 3.

        Parameters
        ----------
        history_dir : Path
            Directory containing chip history Parquet files (Stage 2)
        output_dir : Path, optional
            Output directory for enriched histories. If None, defaults to
            data/03_derived/chip_histories_enriched/ (Stage 3)
        force : bool, optional
            If True, overwrite existing enriched files (default: False)
        stale_threshold_hours : float, optional
            Hours beyond which calibration is considered stale (default: 24)

        Returns
        -------
        list[EnrichmentReport]
            List of reports, one per chip history file

        Raises
        ------
        FileNotFoundError
            If history directory doesn't exist
        ValueError
            If no history files found in directory
        """
        if not history_dir.exists():
            raise FileNotFoundError(f"History directory not found: {history_dir}")

        # Find all history files
        history_files = sorted(history_dir.glob("*_history.parquet"))

        if len(history_files) == 0:
            raise ValueError(
                f"No chip history files found in {history_dir}\n"
                f"Run 'build-all-histories' first to generate history files."
            )

        # Process each file
        reports = []
        for history_path in history_files:
            try:
                report = self.enrich_chip_history(
                    history_path,
                    output_dir=output_dir,
                    force=force,
                    stale_threshold_hours=stale_threshold_hours
                )
                reports.append(report)
            except Exception as e:
                # Create error report
                chip_name = history_path.stem.replace("_history", "")
                error_report = EnrichmentReport(
                    chip_name=chip_name,
                    total_light_exps=0,
                    matched_perfect=0,
                    matched_future=0,
                    matched_stale=0,
                    missing=0,
                    warnings=[],
                    errors=[f"Failed to process: {str(e)}"]
                )
                reports.append(error_report)

        return reports


def print_enrichment_report(report: EnrichmentReport, verbose: bool = False) -> None:
    """
    Print a formatted enrichment report to console.

    Parameters
    ----------
    report : EnrichmentReport
        Report to display
    verbose : bool, optional
        If True, show all warnings (default: False shows only first 10)
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    # Summary table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Chip", report.chip_name)
    table.add_row("Light experiments", str(report.total_light_exps))
    table.add_row("", "")

    if report.total_light_exps > 0:
        table.add_row("✓ Perfect matches", f"{report.matched_perfect} ({report.matched_perfect/report.total_light_exps*100:.0f}%)")
        table.add_row("⚠ Future calibrations", f"{report.matched_future}")
        table.add_row("⏰ Stale calibrations", f"{report.matched_stale}")
        table.add_row("✗ No match", f"{report.missing}")

    # Display in panel
    console.print()
    console.print(Panel(
        table,
        title=f"[bold]Calibration Enrichment - {report.chip_name}[/bold]",
        border_style="cyan"
    ))

    # Show warnings
    if report.warnings:
        console.print()
        if verbose or len(report.warnings) <= 10:
            for warning in report.warnings:
                console.print(f"  [yellow]⚠[/yellow] {warning}")
        else:
            for warning in report.warnings[:10]:
                console.print(f"  [yellow]⚠[/yellow] {warning}")
            console.print(f"  [dim]... and {len(report.warnings) - 10} more warnings (use --verbose to see all)[/dim]")

    # Show errors
    if report.errors:
        console.print()
        for error in report.errors:
            console.print(f"  [red]✗[/red] {error}")

    console.print()
