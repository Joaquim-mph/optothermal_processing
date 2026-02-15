# Adding `plot-its-suite` and `plot-vts-suite` CLI Commands

## Summary

Added two new standalone CLI commands that expose the batch-only suite plotting functionality as direct CLI commands. Previously, these could only be triggered via YAML batch configs (`biotite batch-plot config.yaml`).

## Files Created

### `src/cli/commands/plot_its_suite.py`

New `plot-its-suite` command that generates up to 3 plots in one call:

1. **ITS overlay** (`its.plot_its_overlay`) - current vs time, multiple experiments overlaid
2. **ITS sequential** (`its.plot_its_sequential`) - experiments concatenated on continuous time axis
3. **ITS photoresponse** (`its_photoresponse.plot_its_photoresponse`) - delta current vs power/wavelength (only if light experiments exist; skipped gracefully otherwise)

### `src/cli/commands/plot_vts_suite.py`

New `plot-vts-suite` command that generates up to 3 plots in one call:

1. **Vt overlay** (`vt.plot_vt_overlay`) - voltage vs time, multiple experiments overlaid
2. **Vt sequential** (`vt.plot_vt_sequential`) - experiments concatenated on continuous time axis
3. **Vt photoresponse** (`photoresponse.plot_photoresponse` with `y_metric="delta_voltage"`) - delta voltage vs power/wavelength (wrapped in try/except; skipped if metrics unavailable)

## No Other Files Modified

Both commands are auto-discovered by the plugin system (`@cli_command` decorator) -- no changes to `main.py`, `__init__.py`, or any other file were needed.

## Design Decisions

- **Data loading pattern** copied from existing `plot_its.py` and `plot_vt.py` commands (context, validation, history loading, `parquet_path` -> `source_file` rename)
- **Plotting calls** match the batch engine logic in `src/plotting/batch.py` (lines 468-600) exactly
- **Photoresponse is non-fatal** -- if photoresponse plotting fails (e.g., no light experiments, metrics not extracted), the suite continues and reports a warning instead of aborting
- **Suite-specific options** added on top of common options:
  - `--photoresponse-x` (default: `power`) -- x-axis for photoresponse plot
  - `--axtype` -- axis scaling for photoresponse (ITS suite only)
  - `--filter-wavelength`, `--filter-vg` -- photoresponse-specific filters
  - `--filter-power-range` -- power range filter (Vt suite only)

## Usage Examples

```bash
# ITS suite
biotite plot-its-suite 67 --seq 4-7
biotite plot-its-suite 67 --seq 4-7 --legend irradiated_power
biotite plot-its-suite 67 --seq 4-7 --photoresponse-x wavelength
biotite plot-its-suite 67 --auto --conductance

# Vt suite
biotite plot-vts-suite 81 --seq 239-240
biotite plot-vts-suite 81 --seq 239-240 --legend vg
biotite plot-vts-suite 81 --auto --resistance

# Preview mode (no files generated)
biotite plot-its-suite 67 --seq 4-7 --preview
```

## Verification

```bash
# Confirm commands appear in help
biotite --help  # Shows plot-its-suite and plot-vts-suite under Plotting Commands

# Test imports
python3 -c "from src.cli.commands.plot_its_suite import plot_its_suite_command; print('OK')"
python3 -c "from src.cli.commands.plot_vts_suite import plot_vts_suite_command; print('OK')"
```
