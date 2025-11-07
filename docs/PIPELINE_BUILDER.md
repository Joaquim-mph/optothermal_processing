# Pipeline Builder System

**Last Updated:** November 7, 2025
**Status:** Beta (v3.1+)

## Overview

The formal **Pipeline Builder** system provides a declarative way to define, execute, and manage multi-step data processing pipelines with advanced features like:

- ✅ **Error handling** - Automatic retry with exponential backoff
- ✅ **Rollback** - Undo completed steps on failure
- ✅ **Checkpointing** - Resume from last successful step
- ✅ **YAML definitions** - Save and reuse pipeline configurations
- ✅ **State management** - Track execution history and status
- ✅ **Rich UI** - Beautiful progress display with timing

## Quick Start

### Using the Pipeline Builder in Code

```python
from src.core.pipeline import Pipeline
from src.cli.commands.stage import stage_all_command

# Create pipeline
pipeline = Pipeline(
    name="my-pipeline",
    description="Custom data processing workflow"
)

# Add steps with error handling
pipeline.add_step(
    name="stage-data",
    command=stage_all_command,
    raw_root=Path("data/01_raw"),
    workers=8,
    retry_count=2,  # Retry twice on failure
    rollback_fn=lambda: shutil.rmtree("data/02_stage"),
)

# Execute with rollback enabled
result = pipeline.execute(
    stop_on_error=True,
    enable_rollback=True,
)

if result.success:
    print(f"✓ Pipeline completed in {result.total_time:.1f}s")
```

### Using Pre-defined Pipelines (CLI)

```bash
# Run full pipeline with rollback
python process_and_analyze.py full-pipeline-v2 --rollback

# Resume from checkpoint after failure
python process_and_analyze.py full-pipeline-v2 --resume

# Quick staging only
python process_and_analyze.py quick-staging --workers 16

# Metrics extraction only
python process_and_analyze.py metrics-only --force
```

### Using YAML Pipeline Definitions

```bash
# Execute pipeline from YAML
python process_and_analyze.py run-pipeline-yaml config/pipelines/full-pipeline.yml

# With rollback and resume
python process_and_analyze.py run-pipeline-yaml config/pipelines/full-pipeline.yml --rollback --resume
```

## Architecture

### Core Components

```
src/core/pipeline.py
├── Pipeline           # Main pipeline orchestrator
├── PipelineStep       # Individual step definition
├── PipelineState      # Checkpoint and state management
├── PipelineResult     # Execution results
└── StepStatus         # Step status enum
```

### Pipeline Lifecycle

```
1. Define Pipeline
   ├── Add steps with commands
   ├── Configure retry/rollback
   └── Set error handling policy

2. Execute Pipeline
   ├── Load checkpoint (if resuming)
   ├── Execute steps sequentially
   │   ├── Retry on failure
   │   ├── Save checkpoints
   │   └── Handle errors
   └── Rollback on failure (optional)

3. Result Summary
   ├── Success/failure status
   ├── Step execution times
   └── Error details
```

## Features

### 1. Automatic Retry

Steps can automatically retry on transient failures:

```python
pipeline.add_step(
    "flaky-network-call",
    fetch_remote_data,
    retry_count=3,        # Retry up to 3 times
    retry_delay=2.0,      # Wait 2 seconds between retries
)
```

**Use cases:**
- Network requests
- Database connections
- External API calls
- File system operations with locks

### 2. Rollback on Failure

Automatically undo completed steps when pipeline fails:

```python
def rollback_staging(stage_dir):
    """Remove staged files on failure."""
    if stage_dir.exists():
        shutil.rmtree(stage_dir)

pipeline.add_step(
    "stage-data",
    stage_all_command,
    rollback_fn=rollback_staging,  # Called if later step fails
)

# Execute with rollback enabled
result = pipeline.execute(enable_rollback=True)
```

**Rollback order:** Reverse execution order (LIFO)

**Example scenario:**
```
Step 1: Stage data ✓
Step 2: Build histories ✓
Step 3: Extract metrics ✗ (fails)

→ Rollback Step 2 (remove histories)
→ Rollback Step 1 (remove staged data)
```

### 3. Checkpointing & Resume

Pipeline state is automatically saved after each successful step:

```bash
# First run (fails at step 3)
$ python process_and_analyze.py full-pipeline-v2
Step 1: stage-raw-data ✓
Step 2: build-histories ✓
Step 3: derive-metrics ✗ (failed)
Checkpoint saved: data/.pipeline_checkpoints/full-pipeline_20251107_143022.json

# Fix the issue, then resume
$ python process_and_analyze.py full-pipeline-v2 --resume
Resuming from checkpoint: 20251107_143022
Skipping completed steps: stage-raw-data, build-histories
Step 3: derive-metrics ✓
```

**Checkpoint location:** `data/.pipeline_checkpoints/`

**Checkpoint format:**
```json
{
  "pipeline_name": "full-pipeline",
  "execution_id": "20251107_143022",
  "timestamp": "2025-11-07T14:30:22",
  "steps": [
    {
      "name": "stage-raw-data",
      "status": "success",
      "elapsed_time": 45.2
    },
    {
      "name": "build-histories",
      "status": "success",
      "elapsed_time": 12.3
    },
    {
      "name": "derive-metrics",
      "status": "failed",
      "error": "ValueError: Missing CNP data"
    }
  ]
}
```

### 4. Skip on Error

Continue pipeline execution even if a step fails:

```python
pipeline.add_step(
    "optional-step",
    optional_command,
    skip_on_error=True,  # Don't stop pipeline if this fails
)
```

**Use cases:**
- Optional optimizations
- Non-critical metrics
- Experimental features
- Cleanup operations

### 5. YAML Pipeline Definitions

Define reusable pipelines in YAML:

**`config/pipelines/my-pipeline.yml`**
```yaml
name: my-custom-pipeline
description: Custom workflow for Alisson chips

steps:
  - name: stage-data
    command: stage_all_command
    kwargs:
      raw_root: data/01_raw
      stage_root: data/02_stage/raw_measurements
      workers: 16
      force: true
    retry_count: 1

  - name: build-histories
    command: build_all_histories_command
    kwargs:
      manifest_path: data/02_stage/raw_measurements/_manifest/manifest.parquet
      output_dir: data/02_stage/chip_histories
      chip_group: Alisson
      min_experiments: 5
    skip_on_error: false

  - name: extract-metrics
    command: derive_all_metrics_command
    kwargs:
      chip_group: Alisson
      workers: 8
    skip_on_error: true
    retry_count: 2
```

**Execute:**
```bash
python process_and_analyze.py run-pipeline-yaml config/pipelines/my-pipeline.yml
```

**Benefits:**
- Share pipelines across team
- Version control configurations
- No code changes needed
- Easy experimentation

## Pre-defined Pipelines

### Full Pipeline (v2)

Complete data processing with advanced error handling:

```bash
python process_and_analyze.py full-pipeline-v2 \
    --rollback \
    --workers 16 \
    --force
```

**Steps:**
1. Stage raw CSVs → Parquet
2. Build chip histories
3. Extract derived metrics

**Options:**
- `--rollback` - Enable automatic rollback
- `--resume` - Resume from checkpoint
- `--skip-metrics` - Skip metrics extraction
- `--save-yaml PATH` - Export definition to YAML

### Quick Staging

Fast staging without downstream processing:

```bash
python process_and_analyze.py quick-staging \
    --workers 16 \
    --force
```

**Use cases:**
- Validate raw data format
- Quick iteration during development
- Test schema changes

### Metrics Only

Extract metrics from already-staged data:

```bash
python process_and_analyze.py metrics-only \
    --force \
    --workers 12
```

**Use cases:**
- Re-extract metrics after bug fix
- Add new metric extractors
- Update calibration associations

## Creating Custom Pipelines

### Method 1: Python Code

Create a pipeline factory function:

```python
# src/cli/commands/my_pipeline.py
from src.core.pipeline import Pipeline

def create_analysis_pipeline(chip_number: int, output_dir: Path) -> Pipeline:
    """Create custom analysis pipeline for single chip."""
    pipeline = Pipeline(
        name=f"analyze-chip-{chip_number}",
        description=f"Complete analysis for chip {chip_number}",
    )

    # Step 1: Load data
    pipeline.add_step(
        "load-history",
        load_chip_history,
        chip_number=chip_number,
        retry_count=2,
    )

    # Step 2: Generate plots
    pipeline.add_step(
        "generate-plots",
        generate_all_plots,
        chip_number=chip_number,
        output_dir=output_dir,
    )

    # Step 3: Export data
    pipeline.add_step(
        "export-csv",
        export_to_csv,
        chip_number=chip_number,
        output_dir=output_dir,
        skip_on_error=True,  # Optional
    )

    return pipeline

@cli_command(name="analyze-chip", group="analysis")
def analyze_chip_command(
    chip_number: int = typer.Argument(...),
    output_dir: Path = typer.Option(Path("output")),
):
    """Run complete analysis for a chip."""
    pipeline = create_analysis_pipeline(chip_number, output_dir)
    result = pipeline.execute(stop_on_error=True, enable_rollback=False)

    if not result.success:
        raise typer.Exit(1)
```

### Method 2: YAML Definition

Create `config/pipelines/analyze-chip.yml`:

```yaml
name: analyze-chip
description: Complete chip analysis workflow

steps:
  - name: load-history
    command: load_chip_history
    kwargs:
      chip_number: ${CHIP_NUMBER}  # Parameter placeholder
    retry_count: 2

  - name: generate-plots
    command: generate_all_plots
    kwargs:
      chip_number: ${CHIP_NUMBER}
      output_dir: output

  - name: export-csv
    command: export_to_csv
    kwargs:
      chip_number: ${CHIP_NUMBER}
      output_dir: output
    skip_on_error: true
```

**Execute with parameters:**
```bash
CHIP_NUMBER=67 python process_and_analyze.py run-pipeline-yaml config/pipelines/analyze-chip.yml
```

## Best Practices

### 1. Idempotent Steps

Make steps safe to re-run:

```python
def idempotent_staging(output_dir: Path, force: bool):
    """Stage data with idempotency."""
    if output_dir.exists() and not force:
        print("Already staged, skipping")
        return

    # Perform staging...
```

### 2. Meaningful Rollback

Provide rollback functions that undo side effects:

```python
pipeline.add_step(
    "create-indexes",
    build_database_indexes,
    rollback_fn=lambda: drop_database_indexes(),  # Undo index creation
)
```

### 3. Granular Steps

Break complex operations into smaller steps:

❌ **Bad:** One monolithic step
```python
pipeline.add_step("process-everything", process_all_data)
```

✅ **Good:** Multiple granular steps
```python
pipeline.add_step("validate-input", validate_data)
pipeline.add_step("transform-data", transform_data)
pipeline.add_step("save-output", save_results)
```

**Benefits:**
- Better error localization
- Checkpoint between steps
- Easier debugging

### 4. Retry Transient Failures Only

Use retry for operations that may fail temporarily:

✅ **Good retry candidates:**
- Network requests
- Database connections
- File locks
- Race conditions

❌ **Bad retry candidates:**
- Data validation errors
- Missing files
- Schema mismatches
- Logic errors

### 5. Document Pipeline Purpose

```python
pipeline = Pipeline(
    name="production-etl",
    description=(
        "Production ETL pipeline:\n"
        "1. Extract from raw CSVs\n"
        "2. Transform with validation\n"
        "3. Load into data warehouse\n"
        "Owner: data-team@example.com"
    ),
)
```

## Comparison: Old vs New

### Old Approach (data_pipeline.py)

```python
# Manual error handling
try:
    stage_all_command(...)
except SystemExit as e:
    if e.code != 0:
        console.print("[red]Failed[/red]")
        raise typer.Exit(1)

# No rollback
# No retry
# No checkpointing
# Manual progress tracking
```

### New Approach (data_pipeline_v2.py)

```python
# Declarative with automatic error handling
pipeline = Pipeline("full-pipeline")

pipeline.add_step(
    "stage-data",
    stage_all_command,
    retry_count=2,           # Automatic retry
    rollback_fn=cleanup,     # Automatic rollback
    checkpoint=True,         # Automatic checkpointing
)

result = pipeline.execute(
    stop_on_error=True,
    enable_rollback=True,
    resume_from="latest",    # Resume support
)
```

## Limitations & Future Enhancements

### Current Limitations

1. **No parallel step execution** - Steps run sequentially
2. **No conditional branching** - Linear execution only
3. **No parameter interpolation** - YAML doesn't support `${VAR}` yet
4. **Resume logic is basic** - Doesn't skip completed steps automatically

### Planned Enhancements

1. **Parallel execution** - Run independent steps concurrently
   ```python
   pipeline.add_parallel_group([step1, step2, step3])
   ```

2. **Conditional steps** - Skip steps based on conditions
   ```python
   pipeline.add_step("optional", command, condition=lambda: check_flag())
   ```

3. **Step dependencies** - Explicit dependency graph
   ```python
   pipeline.add_step("step3", command, depends_on=["step1", "step2"])
   ```

4. **Progress callbacks** - Custom callbacks for monitoring
   ```python
   pipeline.on_step_complete(lambda step: send_notification(step))
   ```

5. **Pipeline composition** - Nest pipelines
   ```python
   main_pipeline.add_subpipeline(preprocessing_pipeline)
   ```

## Testing

Run pipeline tests:

```bash
# All pipeline tests
python -m pytest tests/test_pipeline.py -v

# Specific test
python -m pytest tests/test_pipeline.py::test_rollback_on_failure -v

# With coverage
python -m pytest tests/test_pipeline.py --cov=src.core.pipeline
```

## Troubleshooting

### Pipeline Fails Without Checkpoint

**Problem:** Checkpoint not saved after step completes

**Solution:** Ensure `checkpoint=True` in `add_step()`:
```python
pipeline.add_step("my-step", command, checkpoint=True)
```

### Rollback Function Not Called

**Problem:** Rollback doesn't execute on failure

**Solution:** Enable rollback in `execute()`:
```python
result = pipeline.execute(enable_rollback=True)
```

### Cannot Resume from Checkpoint

**Problem:** `--resume` flag ignored

**Solution:** Check checkpoint directory exists:
```bash
ls data/.pipeline_checkpoints/
```

### YAML Pipeline Import Fails

**Problem:** `Unknown command: my_command`

**Solution:** Add command to registry:
```python
command_registry = {
    "my_command": my_command_function,
}
pipeline = Pipeline.from_yaml(path, command_registry)
```

## Migration Guide

### Migrating from Old full-pipeline

**Before:**
```bash
python process_and_analyze.py full-pipeline --force --workers 16
```

**After:**
```bash
python process_and_analyze.py full-pipeline-v2 --force --workers 16 --rollback
```

**Benefits:**
- Automatic retry on transient failures
- Rollback on error (with `--rollback`)
- Resume from checkpoint (with `--resume`)
- Better progress display

## Examples

### Example 1: Development Pipeline with Rollback

```python
pipeline = Pipeline("dev-pipeline", description="Fast development iteration")

# Stage with rollback
pipeline.add_step(
    "stage",
    stage_all_command,
    workers=16,
    force=True,
    rollback_fn=lambda: shutil.rmtree("data/02_stage/raw_measurements"),
)

# Build histories
pipeline.add_step(
    "histories",
    build_all_histories_command,
    rollback_fn=lambda: shutil.rmtree("data/02_stage/chip_histories"),
)

# Execute with rollback
result = pipeline.execute(enable_rollback=True)
```

### Example 2: Production Pipeline with Checkpointing

```python
pipeline = Pipeline(
    "production-etl",
    checkpoint_dir=Path("/var/lib/optothermal/checkpoints"),
)

# All steps with checkpoints
pipeline.add_step("extract", extract_data, checkpoint=True, retry_count=3)
pipeline.add_step("transform", transform_data, checkpoint=True, retry_count=2)
pipeline.add_step("load", load_data, checkpoint=True, retry_count=5)

# Execute with resume
result = pipeline.execute(resume_from="latest")
```

### Example 3: Export Pipeline Definition

```python
pipeline = create_full_pipeline(...)

# Save to YAML for reuse
pipeline.to_yaml(Path("config/pipelines/production.yml"))

# Later, load and execute
pipeline = Pipeline.from_yaml(
    Path("config/pipelines/production.yml"),
    command_registry,
)
result = pipeline.execute()
```

## See Also

- **[CLI_PLUGIN_SYSTEM.md](CLI_PLUGIN_SYSTEM.md)** - Command plugin system
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration management
- **[DERIVED_METRICS_ARCHITECTURE.md](DERIVED_METRICS_ARCHITECTURE.md)** - Metrics pipeline

---

**Questions or feedback?** Open an issue or contribute improvements!
