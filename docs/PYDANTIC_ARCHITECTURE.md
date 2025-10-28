# Pydantic Architecture Documentation

**Author:** System Documentation
**Date:** 2025-10-28
**Version:** 1.0

## Table of Contents

1. [Overview](#overview)
2. [Core Philosophy](#core-philosophy)
3. [Module-by-Module Analysis](#module-by-module-analysis)
4. [Data Flow & Validation Points](#data-flow--validation-points)
5. [Benefits & Trade-offs](#benefits--trade-offs)
6. [Best Practices](#best-practices)

---

## Overview

Pydantic is used throughout the optothermal processing pipeline as the **data validation and type safety backbone**. It provides schema-driven validation at every critical data transformation point, from raw CSV ingestion to GUI state management.

### Key Pydantic Models

| Model | Location | Purpose | Validation Level |
|-------|----------|---------|------------------|
| `ManifestRow` | `src/models/manifest.py` | Schema for manifest.parquet rows | **Strict** - 50+ fields |
| `StagingConfig` | `src/models/config.py` | Staging pipeline configuration | **Strict** - path validation |
| `StagingParameters` | `src/models/parameters.py` | Legacy staging params (deprecated) | **Moderate** |
| `PlotSession` | `src/tui/session.py` | TUI wizard state management | **Moderate** - enum validation |
| `IntermediateParameters` | `src/models/parameters.py` | Intermediate preprocessing config | **Moderate** |
| `IVAnalysisParameters` | `src/models/parameters.py` | IV curve analysis config | **Strict** - polynomial validation |
| `PlottingParameters` | `src/models/parameters.py` | Visualization config | **Moderate** |
| `PipelineParameters` | `src/models/parameters.py` | End-to-end pipeline orchestration | **Strict** - cross-validation |

---

## Core Philosophy

### 1. **Schema-Driven Data Engineering**

Pydantic models serve as **executable schema definitions** that:
- Document expected data structure (self-documenting code)
- Validate data at runtime (fail-fast on malformed inputs)
- Enable type-safe refactoring (IDE autocomplete, type checkers)
- Provide serialization/deserialization (JSON ↔ Python ↔ Parquet)

### 2. **Defense in Depth**

Validation occurs at **multiple layers**:

```
Raw CSV → Pydantic Validation → Parquet
          ↓
          ManifestRow (50+ field constraints)
          ↓
          - run_id lowercase normalization
          - chip_group title casing
          - datetime timezone awareness
          - path existence checks
          - numeric range constraints (ge, gt, le)
```

### 3. **Configuration as Code**

All pipeline parameters are defined as Pydantic models with:
- **Default values** (single source of truth)
- **Field validation** (ranges, patterns, constraints)
- **Cross-field validation** (model_validator for consistency checks)
- **Auto-computed fields** (derived paths, git version detection)

---

## Module-by-Module Analysis

### `src/models/manifest.py`

**Purpose:** Authoritative schema for `manifest.parquet` - the central metadata table representing all measurement runs.

#### Key Features

**1. Strict Field Definitions (50+ fields)**

```python
class ManifestRow(BaseModel):
    # Identity (Required)
    run_id: str = Field(..., min_length=16, max_length=64)
    source_file: Path = Field(...)
    proc: Proc = Field(...)  # Literal["IVg", "IV", "IVgT", "It", ...]

    # Chip Identification (Optional)
    chip_group: Optional[str] = Field(default=None)
    chip_number: Optional[int] = Field(default=None, ge=0)

    # Voltage Parameters (Procedure-Specific)
    vg_fixed_v: Optional[float] = Field(default=None)
    vg_start_v: Optional[float] = Field(default=None)
    vds_v: Optional[float] = Field(default=None)

    # ... 40+ more fields with constraints
```

**2. Custom Validators**

| Validator | Purpose | Impact |
|-----------|---------|--------|
| `_lowercase_runid` | Normalize run_id to lowercase | Prevents duplicate runs due to case mismatch |
| `_titlecase_group` | Normalize chip_group to TitleCase | Consistent chip grouping (Alisson vs alisson) |
| `_ensure_utc` | Require timezone-aware datetimes | Prevents naive datetime bugs |
| `_coerce_source_file` | Convert str → Path | Accept both types seamlessly |

**3. ConfigDict Settings**

```python
model_config = ConfigDict(
    extra="forbid",              # Reject unknown fields (prevent schema drift)
    validate_assignment=True,    # Validate on field updates (not just __init__)
    arbitrary_types_allowed=True # Allow Path objects
)
```

**Why This Matters:**
- **`extra="forbid"`**: Catches typos, prevents accidental column bloat
- **`validate_assignment=True`**: Protects against bugs from mutation after creation
- **`arbitrary_types_allowed=True`**: Allows Pathlib objects instead of just strings

**4. Helper Functions**

```python
def proc_display_name(proc: Proc) -> str:
    """Get human-readable name: 'It' → 'Current vs Time'"""

def proc_short_name(proc: Proc) -> str:
    """Get abbreviation: 'It' → 'ITS'"""
```

#### Usage in Pipeline

**Creation (Staging Pipeline):**
```python
# In src/core/stage_raw_measurements.py (conceptually - actual usage is via dict construction)
row_dict = {
    "run_id": compute_run_id(path, timestamp),
    "source_file": path.relative_to(raw_root),
    "proc": detected_procedure,
    "chip_number": extract_chip_number(filename),
    # ... 40+ more fields
}

# Validation happens during manifest write/read via Polars schema
# Pydantic TypeAdapter used for validation in validate-manifest command
```

**Validation (CLI Command):**
```python
# In src/cli/commands/stage.py
from pydantic import TypeAdapter
from src.models.manifest import ManifestRow

ta = TypeAdapter(list[ManifestRow])
rows = manifest_df.to_dicts()
ta.validate_python(rows)  # Raises ValidationError on schema mismatch
```

---

### `src/models/config.py`

**Purpose:** Staging pipeline configuration with auto-path resolution and git version detection.

#### Key Features

**1. Required vs Optional Paths**

```python
class StagingConfig(BaseModel):
    # Required (must exist)
    raw_root: Path = Field(..., description="Raw CSV root (must exist)")
    procedures_yaml: Path = Field(..., description="YAML schema (must exist)")

    # Auto-filled from stage_root
    rejects_dir: Optional[Path] = Field(default=None)  # → {stage_root}/../_rejects
    events_dir: Optional[Path] = Field(default=None)   # → {stage_root}/_manifest/events
    manifest_path: Optional[Path] = Field(default=None) # → {stage_root}/_manifest/manifest.parquet
```

**2. Path Existence Validation**

```python
@field_validator("raw_root", "procedures_yaml")
@classmethod
def _path_must_exist(cls, v: Path, info) -> Path:
    """Validate that required input paths exist."""
    if not v.exists():
        raise ValueError(f"{info.field_name} does not exist: {v}")
    return v.resolve()  # Return absolute path
```

**Why:** Fail-fast before starting expensive staging operations.

**3. Model Validators (Cross-Field Logic)**

```python
@model_validator(mode="after")
def _set_default_paths(self) -> StagingConfig:
    """Auto-fill paths based on stage_root if not provided."""
    if self.rejects_dir is None:
        self.rejects_dir = self.stage_root.parent / "_rejects"
    if self.events_dir is None:
        self.events_dir = self.stage_root / "_manifest" / "events"
    if self.manifest_path is None:
        self.manifest_path = self.stage_root / "_manifest" / "manifest.parquet"
    return self
```

**Why:** Convention over configuration - sensible defaults reduce boilerplate.

**4. Git Version Auto-Detection**

```python
@model_validator(mode="after")
def _auto_detect_version(self) -> StagingConfig:
    """Auto-detect extraction version from git if not provided."""
    if self.extraction_version is None:
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--always", "--dirty"],
                capture_output=True, text=True, check=True, timeout=2.0
            )
            self.extraction_version = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            self.extraction_version = "unknown"
    return self
```

**Why:** Automatic version tracking for data provenance without manual intervention.

**5. Helper Methods**

```python
def create_directories(self) -> None:
    """Create all output directories."""
    self.stage_root.mkdir(parents=True, exist_ok=True)
    # ... create rejects_dir, events_dir, manifest parent

def get_partition_path(self, proc: str, date: str, run_id: str) -> Path:
    """Get Hive-style partition path."""
    return self.stage_root / f"proc={proc}" / f"date={date}" / f"run_id={run_id}"

def validate_timezone(self) -> bool:
    """Validate IANA timezone name using zoneinfo."""
    ZoneInfo(self.local_tz)  # Raises ZoneInfoNotFoundError if invalid
```

#### Usage in Pipeline

**CLI Command:**
```python
# In src/cli/commands/stage.py
from src.models.config import StagingConfig

config = StagingConfig(
    raw_root=Path("data/01_raw"),
    stage_root=Path("data/02_stage/raw_measurements"),
    procedures_yaml=Path("config/procedures.yml"),
    workers=8,
    force=True
)

# Auto-fills:
# - config.manifest_path = Path("data/02_stage/_manifest/manifest.parquet")
# - config.extraction_version = "v0.4.2+g1a2b3c" (from git)
# - config.rejects_dir = Path("data/02_stage/_rejects")
```

---

### `src/models/parameters.py`

**Purpose:** Comprehensive parameter models for all pipeline stages (staging, intermediate, analysis, plotting, orchestration).

This module contains **5 major Pydantic models**:

---

#### 1. `StagingParameters` (Deprecated in favor of StagingConfig)

**Status:** Legacy model, superseded by `StagingConfig` in `src/models/config.py`.
**Difference:** Less comprehensive validation, fewer helper methods.

---

#### 2. `IntermediateParameters`

**Purpose:** Configuration for 4-layer architecture's intermediate preprocessing step (segment detection for IV curves).

```python
class IntermediateParameters(BaseModel):
    stage_root: Path  # Input: staged Parquet data
    output_root: Path  # Output: intermediate processed data

    procedure: str = Field(default="IV", pattern=r"^(IV|IVg|IVgT)$")
    voltage_col: str = Field(default="Vsd (V)")

    # Segment detection parameters
    dv_threshold: float = Field(default=0.001, ge=0.0, le=1.0)
    min_segment_points: int = Field(default=5, ge=2, le=1000)

    workers: int = Field(default=6, ge=1, le=32)
```

**Key Validations:**
- `procedure`: Regex pattern matching (only IV/IVg/IVgT allowed)
- `dv_threshold`: Range constraint (0.0 ≤ x ≤ 1.0)
- `min_segment_points`: Bounds checking (2 ≤ x ≤ 1000)

**Helper Method:**
```python
def get_output_dir(self) -> Path:
    """Map procedure to subdirectory: 'IV' → 'iv_segments'"""
    proc_subdir = {
        "IV": "iv_segments",
        "IVg": "ivg_segments",
        "IVgT": "ivgt_segments",
    }.get(self.procedure, f"{self.procedure.lower()}_segments")
    return self.output_root / proc_subdir
```

---

#### 3. `IVAnalysisParameters`

**Purpose:** IV curve analysis pipeline configuration (polynomial fitting, hysteresis calculation).

```python
class IVAnalysisParameters(BaseModel):
    stage_root: Path
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD validation
    output_base_dir: Path

    # Polynomial fitting
    poly_orders: List[int] = Field(default=[1, 3, 5, 7])
    fit_backward: bool = Field(default=True)

    # Hysteresis computation
    compute_hysteresis: bool = Field(default=True)
    voltage_rounding_decimals: int = Field(default=2, ge=0, le=6)
```

**Critical Validator:**
```python
@field_validator("poly_orders")
@classmethod
def validate_poly_orders(cls, v: List[int]) -> List[int]:
    """Validate polynomial orders are positive, reasonable, and odd."""
    if not v:
        raise ValueError("Must specify at least one polynomial order")
    for order in v:
        if order < 1:
            raise ValueError(f"Polynomial order must be >= 1, got {order}")
        if order > 15:
            raise ValueError(f"Polynomial order {order} too high (max 15)")
        if order % 2 == 0:
            raise ValueError(f"Polynomial order {order} should be odd for symmetric fitting")
    return sorted(set(v))  # Remove duplicates and sort
```

**Why Odd Polynomials Only?**
Even-order polynomials lack symmetry, making them unsuitable for symmetric I-V curves around V=0.

---

#### 4. `PlottingParameters`

**Purpose:** Visualization configuration for publication-quality plots.

```python
class PlottingParameters(BaseModel):
    output_dir: Path

    # Quality
    dpi: int = Field(default=300, ge=72, le=1200)
    format: str = Field(default="png", pattern=r"^(png|pdf|svg|jpg)$")

    # Dimensions
    figure_width: float = Field(default=12.0, ge=4.0, le=30.0)
    figure_height: float = Field(default=8.0, ge=3.0, le=20.0)

    # Style
    style: str = Field(default="publication", pattern=r"^(publication|presentation|notebook)$")
    font_size: int = Field(default=10, ge=6, le=24)
    line_width: float = Field(default=1.5, ge=0.5, le=5.0)

    # Advanced
    show_error_bars: bool = Field(default=True)
    grid_alpha: float = Field(default=0.3, ge=0.0, le=1.0)
```

**Helper Methods:**
```python
def get_figsize(self) -> tuple[float, float]:
    """Get matplotlib figsize tuple."""
    return (self.figure_width, self.figure_height)

def get_style_params(self) -> dict:
    """Get matplotlib rcParams based on style preset."""
    if self.style == "publication":
        return {
            "font.size": self.font_size,
            "font.family": "sans-serif",
            "lines.linewidth": self.line_width,
            # ... more style-specific settings
        }
```

---

#### 5. `PipelineParameters`

**Purpose:** Orchestrate end-to-end pipeline runs with cross-layer validation.

```python
class PipelineParameters(BaseModel):
    staging: StagingParameters
    intermediate: Optional[IntermediateParameters] = None  # 4-layer architecture only
    analysis: IVAnalysisParameters
    plotting: PlottingParameters

    # Pipeline control flags
    run_staging: bool = Field(default=True)
    run_intermediate: bool = Field(default=False)  # Enable 4-layer mode
    run_analysis: bool = Field(default=True)
    run_plotting: bool = Field(default=True)
```

**Critical Cross-Validation:**
```python
@model_validator(mode="after")
def validate_consistency(self) -> PipelineParameters:
    """Validate cross-parameter consistency."""

    # Ensure analysis stage_root matches staging output
    if self.analysis.stage_root != self.staging.stage_root:
        raise ValueError(
            f"Analysis stage_root ({self.analysis.stage_root}) must match "
            f"staging stage_root ({self.staging.stage_root})"
        )

    # If using 4-layer architecture, validate intermediate layer
    if self.run_intermediate:
        if self.intermediate is None:
            raise ValueError("run_intermediate=True but no intermediate parameters provided")

        if not self.analysis.use_segments:
            raise ValueError("run_intermediate=True but analysis.use_segments=False")

        # Auto-set intermediate_root in analysis
        if self.analysis.intermediate_root is None:
            self.analysis.intermediate_root = self.intermediate.get_output_dir()

    # Ensure analysis runs before plotting
    if self.run_plotting and not self.run_analysis:
        stats_dir = self.analysis.get_stats_dir()
        if not stats_dir.exists():
            raise ValueError("Cannot run plotting without analysis outputs")

    return self
```

**Why This Matters:**
Prevents misconfiguration of multi-stage pipelines. For example, forgetting to set `use_segments=True` when enabling intermediate layer would cause analysis to read wrong data.

**JSON Serialization:**
```python
@classmethod
def from_json(cls, path: Path) -> PipelineParameters:
    """Load parameters from JSON config file."""
    with path.open("r") as f:
        data = json.load(f)
    return cls(**data)

def to_json(self, path: Path, indent: int = 2) -> None:
    """Save parameters to JSON config file."""
    with path.open("w") as f:
        json.dump(self.model_dump(mode="json"), f, indent=indent, default=str)
```

---

### `src/core/stage_raw_measurements.py`

**Purpose:** CSV → Parquet staging pipeline execution.

#### Pydantic Usage

**1. Import and Validation**
```python
from src.models.parameters import StagingParameters
from pydantic import ValidationError

def run_staging_pipeline(params: StagingParameters) -> None:
    """
    Execute staging pipeline with validated parameters.

    Args:
        params: Validated StagingParameters instance
    """
    # params is already validated by Pydantic
    # Safe to access params.raw_root, params.workers, etc.
```

**2. CLI Argument Parsing**
```python
# In main() function
try:
    if args.config:
        # Load from JSON with automatic validation
        params = StagingParameters.model_validate_json(args.config.read_text())
    else:
        # Construct from CLI args with validation
        params = StagingParameters(
            raw_root=args.raw_root,
            stage_root=args.stage_root,
            procedures_yaml=args.procedures_yaml,
            workers=args.workers,
            force=args.force,
            # ... more args
        )
except ValidationError as e:
    print(f"Configuration error: {e}", file=sys.stderr)
    sys.exit(1)
```

**Why:** Fail-fast on invalid configuration before starting expensive operations.

---

### `src/cli/commands/stage.py`

**Purpose:** Typer CLI commands for staging operations.

#### Pydantic Usage

**1. Staging Command**
```python
def stage_all_command(
    raw_root: Path = typer.Option(Path("data/01_raw"), ...),
    workers: int = typer.Option(8, ...),
    # ... more CLI options
):
    from src.models.parameters import StagingParameters

    # Create validated parameters
    params = StagingParameters(
        raw_root=raw_root,
        stage_root=stage_root,
        procedures_yaml=procedures_yaml,
        workers=workers,
        force=force,
        # ... more args
    )
    # If validation fails, Pydantic raises ValidationError with clear message

    run_staging_pipeline(params)
```

**2. Validation Command**
```python
def validate_manifest_command(manifest: Path, show_details: bool):
    from pydantic import TypeAdapter
    from src.models.manifest import ManifestRow

    # Load manifest
    df = pl.read_parquet(manifest)

    # Validate each row against ManifestRow schema
    ta = TypeAdapter(list[ManifestRow])
    rows = df.to_dicts()

    try:
        ta.validate_python(rows)
        console.print("[green]✓ Schema validation passed[/green]")
    except ValidationError as e:
        console.print(f"[red]✗ Schema validation failed: {e}[/red]")
```

**Why TypeAdapter?**
`TypeAdapter` allows validating against generic types like `list[ManifestRow]` without creating a wrapper model.

---

### `src/tui/session.py`

**Purpose:** Type-safe TUI wizard session state management.

#### Why Pydantic for GUI State?

**Before (dict-based):**
```python
# Untyped, error-prone
plot_config = {
    "chip_number": 67,
    "baseline": "60.0",  # ❌ Should be float, not str
    "legend_by": "Vg",   # ❌ Lowercase "vg" expected
    "seq_numebrs": [],   # ❌ Typo, silent failure
}

# Runtime errors when plotting
baseline = float(plot_config["baseline"])  # Manual coercion everywhere
```

**After (Pydantic-based):**
```python
class PlotSession(BaseModel):
    chip_number: Optional[int] = Field(default=None)
    baseline: Optional[float] = Field(default=60.0)
    legend_by: str = Field(default="vg")
    seq_numbers: List[int] = Field(default_factory=list)  # Correct spelling enforced

    @field_validator("legend_by")
    @classmethod
    def validate_legend_by(cls, v: str) -> str:
        if v not in ["vg", "led_voltage", "wavelength"]:
            raise ValueError(f"Invalid legend_by: {v}")
        return v

# Type-safe, auto-validated
session = PlotSession()
session.chip_number = 67
session.baseline = 60.0  # Auto-validated as float
session.legend_by = "Vg"  # ❌ ValidationError: invalid value (catches bug immediately)
```

#### Key Features

**1. Required vs Optional Fields**

```python
class PlotSession(BaseModel):
    # Required (set at app initialization)
    stage_dir: Path = Field(..., description="Staged Parquet data directory")
    history_dir: Path = Field(..., description="Chip history directory")
    output_dir: Path = Field(..., description="Output directory for plots")
    chip_group: str = Field(..., description="Default chip group")

    # Optional (filled during wizard flow)
    chip_number: Optional[int] = Field(default=None)
    plot_type: Optional[str] = Field(default=None)  # ITS, IVg, Transconductance
```

**2. Enum-Style Validation**

```python
@field_validator("plot_type")
@classmethod
def validate_plot_type(cls, v: Optional[str]) -> Optional[str]:
    if v is not None and v not in ["ITS", "IVg", "Transconductance"]:
        raise ValueError(f"Invalid plot_type: {v}")
    return v

@field_validator("legend_by")
@classmethod
def validate_legend_by(cls, v: str) -> str:
    if v not in ["vg", "led_voltage", "wavelength"]:
        raise ValueError(f"Invalid legend_by: {v}")
    return v
```

**Why Not Use Literal or Enum?**
GUI state is dynamic and may need to accept None initially. Validators provide more flexibility for optional fields.

**3. Helper Methods**

```python
def reset_wizard_state(self) -> None:
    """Reset wizard state to start fresh, keeping application paths."""
    self.chip_number = None
    self.plot_type = None
    self.seq_numbers = []

def chip_name(self) -> str:
    """Get formatted chip name (e.g., 'Alisson67')."""
    if self.chip_number is None:
        raise ValueError("chip_number is not set")
    return f"{self.chip_group}{self.chip_number}"

def to_config_dict(self) -> dict:
    """Convert to dict for backward compatibility with plotting functions."""
    return self.model_dump()
```

#### Usage in TUI

```python
# In src/tui/app.py
from src.tui.session import PlotSession

class PlotterApp(App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize session with validated parameters
        self.session = PlotSession(
            stage_dir=Path("data/02_stage/raw_measurements"),
            history_dir=Path("data/03_history"),
            output_dir=Path("figs"),
            chip_group="Alisson"
        )

    def on_chip_selected(self, chip_number: int):
        self.session.chip_number = chip_number  # Type-checked, validated
        self.router.go_to_plot_type_selector()

    def on_plot_type_selected(self, plot_type: str):
        self.session.plot_type = plot_type  # Validated against allowed types
        self.router.go_to_config_mode_selector()
```

---

## Data Flow & Validation Points

### Pipeline Overview

```
┌─────────────┐
│  Raw CSVs   │
│ data/01_raw │
└──────┬──────┘
       │
       │ Pydantic ValidationError if:
       │ - procedures_yaml missing
       │ - raw_root doesn't exist
       │
       ▼
┌──────────────────┐
│ Staging Pipeline │  ← StagingConfig (src/models/config.py)
│   stage_all      │  ← StagingParameters (src/models/parameters.py)
└────────┬─────────┘
         │
         │ Pydantic ValidationError if:
         │ - Invalid timezone (ZoneInfo check)
         │ - Workers out of range (1-32)
         │ - Path conflicts
         │
         ▼
┌──────────────────────┐
│  Staged Parquet      │
│  data/02_stage/      │
│  ├── proc=IVg/       │
│  ├── proc=It/        │
│  └── _manifest/      │
│      └── manifest    │  ← ManifestRow schema (src/models/manifest.py)
│         .parquet     │
└──────────┬───────────┘
           │
           │ Pydantic ValidationError if:
           │ - Missing required fields (run_id, proc, source_file)
           │ - Invalid Proc type (not in Literal["IVg", "IV", ...])
           │ - Datetime not timezone-aware
           │ - Negative values in ge=0 fields
           │
           ▼
┌──────────────────────┐
│ History Generation   │
│  build-all-histories │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Chip Histories      │
│  data/03_history/    │
│  ├── Alisson67_      │
│  │   history.parquet │
│  └── ...             │
└──────────┬───────────┘
           │
           │ GUI: PlotSession validation
           │ - chip_number set
           │ - plot_type in ["ITS", "IVg", "Transconductance"]
           │ - legend_by in ["vg", "led_voltage", "wavelength"]
           │
           ▼
┌──────────────────────┐
│  TUI Wizard          │  ← PlotSession (src/tui/session.py)
│  1. Chip Selector    │
│  2. Plot Type        │
│  3. Configuration    │
│  4. Preview          │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Generated Plots     │
│  figs/               │  ← PlottingParameters (src/models/parameters.py)
│  ├── Alisson67_ITS_  │
│  │   4_9_10.png      │
│  └── ...             │
└──────────────────────┘
```

### Validation Timing

| Stage | Model | Validation Occurs | Failure Mode |
|-------|-------|-------------------|--------------|
| **CLI Parsing** | `StagingConfig` | `__init__` call | ValidationError → Exit 1 |
| **Staging** | `ManifestRow` | TypeAdapter during `validate-manifest` | ValidationError → Warning/Error report |
| **TUI Input** | `PlotSession` | Field assignment | ValidationError → Red error notification |
| **Pipeline Orchestration** | `PipelineParameters` | `__init__` + `model_validator` | ValidationError → Detailed error message |

---

## Benefits & Trade-offs

### Benefits

#### 1. **Self-Documenting Code**

Pydantic models serve as **executable documentation**:

```python
# Instead of reading 200 lines of docstring:
def stage_raw_measurements(
    raw_root: str,
    stage_root: str,
    workers: int,
    force: bool,
    only_yaml_data: bool,
    local_tz: str,
    # ... 10 more params
):
    """
    Stage raw CSV files to Parquet format.

    Args:
        raw_root: Root directory with raw CSV files (must exist)
        stage_root: Output directory for staged Parquet files
        workers: Number of parallel workers (1-32)
        force: Overwrite existing files if True
        only_yaml_data: Drop non-YAML columns if True
        local_tz: IANA timezone name (e.g., 'America/Santiago')
        ... (200 more lines of docs)
    """

# Read the Pydantic model (50 lines, type-checked):
class StagingConfig(BaseModel):
    raw_root: Path = Field(..., description="Root directory (must exist)")
    stage_root: Path = Field(..., description="Output directory")
    workers: int = Field(default=6, ge=1, le=32, description="Parallel workers")
    force: bool = Field(default=False, description="Overwrite existing")
    only_yaml_data: bool = Field(default=False, description="Drop non-YAML columns")
    local_tz: str = Field(default="America/Santiago", description="IANA timezone")
```

#### 2. **IDE Autocomplete & Type Checking**

```python
# Type checkers (mypy, pyright) catch bugs at edit-time
config = StagingConfig(
    raw_root=Path("data/01_raw"),
    workers="8",  # ❌ Type error: Expected int, got str
)

# IDE autocomplete shows available fields + descriptions
config.  # ← Autocomplete shows: raw_root, stage_root, workers, force, ...
```

#### 3. **Fail-Fast Validation**

```python
# Invalid configuration caught immediately
try:
    config = StagingConfig(
        raw_root=Path("nonexistent_dir"),  # ❌ Path doesn't exist
        workers=100,  # ❌ Out of range (max 32)
    )
except ValidationError as e:
    print(e)
    # 2 validation errors for StagingConfig
    # raw_root
    #   Path does not exist: nonexistent_dir (type=value_error)
    # workers
    #   ensure this value is less than or equal to 32 (type=value_error.number.not_le)
```

#### 4. **JSON Serialization**

```python
# Save configuration
config = StagingConfig(...)
config_dict = config.model_dump()
with open("config.json", "w") as f:
    json.dump(config_dict, f, indent=2, default=str)

# Load configuration
with open("config.json") as f:
    data = json.load(f)
config = StagingConfig(**data)  # Auto-validated
```

#### 5. **Backward Compatibility**

```python
# Convert Pydantic model to dict for legacy code
session = PlotSession(...)
plot_config_dict = session.to_config_dict()

# Legacy plotting function still works
generate_its_plot(
    chip_name=session.chip_name(),
    **plot_config_dict
)
```

### Trade-offs

#### 1. **Performance Overhead**

**Validation Cost:** ~0.1-1ms per model creation
**Impact:** Negligible for configuration (runs once), noticeable for hot loops

**Solution:**
```python
# ❌ Don't validate in tight loops
for row in df.iter_rows(named=True):  # 100,000 rows
    manifest_row = ManifestRow(**row)  # 100,000 validations = ~10s overhead

# ✅ Validate batch once after DataFrame creation
df = pl.read_parquet(manifest_path)
ta = TypeAdapter(list[ManifestRow])
ta.validate_python(df.to_dicts())  # Single validation = ~100ms
```

#### 2. **Learning Curve**

**Complexity:** Requires understanding:
- Field types (Optional, Literal, List)
- Validators (field_validator, model_validator)
- ConfigDict settings (extra, validate_assignment)

**Mitigation:** Comprehensive docstrings + examples in models.

#### 3. **Dependency Management**

**Pydantic v2 Breaking Changes:**
- `Config` → `ConfigDict`
- `@validator` → `@field_validator`
- `.dict()` → `.model_dump()`

**Solution:** Pin Pydantic version in `requirements.txt`:
```
pydantic>=2.0,<3.0
```

---

## Best Practices

### 1. **Field Naming Conventions**

```python
# ✅ Use descriptive, snake_case names
class ManifestRow(BaseModel):
    chip_number: Optional[int]  # Clear, unambiguous
    vg_start_v: Optional[float]  # Units in name
    laser_wavelength_nm: Optional[float]

# ❌ Avoid abbreviations or unclear names
class ManifestRow(BaseModel):
    cn: Optional[int]  # What is 'cn'?
    vstart: Optional[float]  # Voltage? Volume?
    wl: Optional[float]  # Wavelength? Width-length?
```

### 2. **Use Optional for Non-Required Fields**

```python
# ✅ Explicit optionality
class ManifestRow(BaseModel):
    run_id: str  # Required
    chip_number: Optional[int] = Field(default=None)  # Optional

# ❌ Implicit None defaults (confusing)
class ManifestRow(BaseModel):
    run_id: str
    chip_number: int = None  # Type checker warning: int | None mismatch
```

### 3. **Leverage Field Constraints**

```python
# ✅ Use constraints for data quality
class StagingConfig(BaseModel):
    workers: int = Field(ge=1, le=32, description="Parallel workers")
    poly_orders: List[int] = Field(default=[1, 3, 5, 7])

    @field_validator("poly_orders")
    @classmethod
    def validate_poly_orders(cls, v: List[int]) -> List[int]:
        if any(order % 2 == 0 for order in v):
            raise ValueError("Polynomial orders must be odd")
        return v

# ❌ No validation (bugs discovered in production)
class StagingConfig(BaseModel):
    workers: int  # Could be -1, 1000000
    poly_orders: List[int]  # Could be [0, 2, 4] (even orders)
```

### 4. **Use model_validator for Cross-Field Logic**

```python
# ✅ Cross-field validation
class PipelineParameters(BaseModel):
    staging: StagingParameters
    analysis: IVAnalysisParameters

    @model_validator(mode="after")
    def validate_consistency(self) -> PipelineParameters:
        if self.analysis.stage_root != self.staging.stage_root:
            raise ValueError("Analysis must read from staging output")
        return self

# ❌ Manual checks scattered throughout code
def run_pipeline(params: PipelineParameters):
    if params.analysis.stage_root != params.staging.stage_root:
        raise ValueError("...")
    # Repeated in 5 different functions
```

### 5. **Provide Helper Methods**

```python
# ✅ Encapsulate common operations
class StagingConfig(BaseModel):
    stage_root: Path
    manifest_path: Optional[Path] = None

    def create_directories(self) -> None:
        """Create all output directories."""
        self.stage_root.mkdir(parents=True, exist_ok=True)
        if self.manifest_path:
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

# ❌ Scattered directory creation logic
config = StagingConfig(...)
config.stage_root.mkdir(parents=True, exist_ok=True)
if config.manifest_path:
    config.manifest_path.parent.mkdir(parents=True, exist_ok=True)
# Repeated in 10 different places
```

### 6. **Use ConfigDict Wisely**

```python
# ✅ Strict validation for production schemas
class ManifestRow(BaseModel):
    model_config = ConfigDict(
        extra="forbid",  # Reject unknown fields
        validate_assignment=True,  # Validate on mutation
        arbitrary_types_allowed=True  # Allow Path objects
    )

# ✅ Lenient validation for user input
class PlotSession(BaseModel):
    model_config = ConfigDict(
        extra="ignore",  # Silently drop unknown fields from old configs
        validate_assignment=True
    )
```

### 7. **Document with Field Descriptions**

```python
# ✅ Clear, concise descriptions
class StagingConfig(BaseModel):
    workers: int = Field(
        default=6,
        ge=1,
        le=32,
        description="Number of parallel worker processes"
    )

# ❌ No description (users guess)
class StagingConfig(BaseModel):
    workers: int = Field(default=6, ge=1, le=32)
```

### 8. **Test Validators**

```python
# test_models.py
import pytest
from src.models.parameters import IVAnalysisParameters
from pydantic import ValidationError

def test_poly_orders_must_be_odd():
    with pytest.raises(ValidationError, match="should be odd"):
        IVAnalysisParameters(
            stage_root=Path("data/02_stage"),
            date="2025-10-18",
            output_base_dir=Path("data/04_analysis"),
            poly_orders=[1, 2, 3]  # ❌ 2 is even
        )

def test_poly_orders_remove_duplicates():
    params = IVAnalysisParameters(
        stage_root=Path("data/02_stage"),
        date="2025-10-18",
        output_base_dir=Path("data/04_analysis"),
        poly_orders=[1, 3, 1, 5, 3]  # Duplicates
    )
    assert params.poly_orders == [1, 3, 5]  # Sorted, deduplicated
```

---

## Summary

Pydantic serves as the **data integrity backbone** of the optothermal processing pipeline, providing:

1. **Schema-driven validation** at every critical transformation point
2. **Type-safe configuration** for CLI, GUI, and pipeline orchestration
3. **Self-documenting models** that replace hundreds of lines of docstrings
4. **Fail-fast error handling** that catches bugs before expensive operations
5. **JSON serialization** for configuration management and persistence

**Key Takeaway:**
Pydantic transforms Python from a dynamically-typed language into a **gradually-typed language with runtime validation**, catching entire classes of bugs (type errors, invalid values, configuration mismatches) at edit-time or initialization-time instead of production-time.

---

**Next Steps:**
- Review `src/models/` for all available schemas
- Add new validators when introducing new fields
- Use `TypeAdapter` for batch validation of DataFrames
- Leverage Pydantic's JSON schema generation for API documentation

**References:**
- Pydantic v2 Docs: https://docs.pydantic.dev/latest/
- Field Types: https://docs.pydantic.dev/latest/concepts/fields/
- Validators: https://docs.pydantic.dev/latest/concepts/validators/
