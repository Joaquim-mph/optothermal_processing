# Plugin System Migration Guide

Quick reference for migrating from manual command registration to the plugin system.

## Before & After Comparison

### main.py

**BEFORE (Current System - 66 lines):**
```python
#!/usr/bin/env python3
"""
Main CLI application entry point.
"""

import typer

# Import command functions from command modules
from src.cli.commands.data_pipeline import (
    full_pipeline_command,
)
from src.cli.commands.history import (
    show_history_command,
    build_history_command,
    build_all_histories_command,
)
from src.cli.commands.plot_its import (
    plot_its_command,
    list_presets_command,
    plot_its_sequential_command
)
from src.cli.commands.plot_ivg import plot_ivg_command
from src.cli.commands.plot_transconductance import plot_transconductance_command
from src.cli.commands.stage import (
    stage_all_command,
    validate_manifest_command,
    inspect_manifest_command,
    staging_stats_command,
)

# Create the main Typer app
app = typer.Typer(
    name="process_and_analyze",
    help="Complete data processing and analysis pipeline",
    add_completion=False
)

# Register data pipeline commands
app.command(name="full-pipeline")(full_pipeline_command)

# Register history commands
app.command(name="show-history")(show_history_command)
app.command(name="build-history")(build_history_command)
app.command(name="build-all-histories")(build_all_histories_command)

# Register plotting commands
app.command(name="plot-its")(plot_its_command)
app.command(name="plot-its-sequential")(plot_its_sequential_command)
app.command(name="plot-its-presets")(list_presets_command)
app.command(name="plot-ivg")(plot_ivg_command)
app.command(name="plot-transconductance")(plot_transconductance_command)

# Register staging commands
app.command(name="stage-all")(stage_all_command)
app.command(name="validate-manifest")(validate_manifest_command)
app.command(name="inspect-manifest")(inspect_manifest_command)
app.command(name="staging-stats")(staging_stats_command)


def main():
    """Main entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
```

**AFTER (Plugin System - 22 lines):**
```python
#!/usr/bin/env python3
"""
Main CLI application entry point with plugin system.
"""

import typer
from pathlib import Path
from src.cli.plugin_system import discover_commands

# Create the main Typer app
app = typer.Typer(
    name="process_and_analyze",
    help="Complete data processing and analysis pipeline",
    add_completion=False
)

# Auto-discover and register all command plugins
discover_commands(app, Path("src/cli/commands"))


def main():
    """Main entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
```

**Improvement:** 66 lines → 22 lines (67% reduction)

---

### Command Module Changes

**BEFORE (Current System):**
```python
# src/cli/commands/history.py

def show_history_command(
    chip_number: int = typer.Argument(...),
    chip_group: str = typer.Option("Alisson", "--group", "-g"),
    # ... more parameters
):
    """Display the complete experiment history for a specific chip."""
    # Implementation
    pass


def build_history_command(...):
    """Build chip history from staged data."""
    pass


def build_all_histories_command(...):
    """Build histories for all chips."""
    pass
```

**AFTER (Plugin System):**
```python
# src/cli/commands/history.py
from src.cli.plugin_system import cli_command


@cli_command(name="show-history", group="history")
def show_history_command(
    chip_number: int = typer.Argument(...),
    chip_group: str = typer.Option("Alisson", "--group", "-g"),
    # ... more parameters
):
    """Display the complete experiment history for a specific chip."""
    # Implementation
    pass


@cli_command(name="build-history", group="history")
def build_history_command(...):
    """Build chip history from staged data."""
    pass


@cli_command(name="build-all-histories", group="history")
def build_all_histories_command(...):
    """Build histories for all chips."""
    pass
```

**Change:** Just add `@cli_command()` decorator to each function. Implementation stays the same.

---

## Migration Steps

### Step 1: Create Infrastructure (5 minutes)

```bash
# Create plugin system module
touch src/cli/plugin_system.py

# Create default configuration
cat > config/cli_plugins.yaml <<EOF
enabled_groups:
  - all

disabled_commands: []

settings:
  allow_third_party: false
EOF
```

Copy implementation from `docs/CLI_PLUGIN_SYSTEM.md` into `src/cli/plugin_system.py`.

### Step 2: Add Decorators to Commands (10 minutes)

Add `@cli_command()` decorator to each command function:

```python
# Add import at top of each command module
from src.cli.plugin_system import cli_command

# Add decorator to each command
@cli_command(name="command-name", group="group-name")
def command_function(...):
    pass
```

**Command → Group mapping:**
- `full-pipeline` → `pipeline`
- `show-history`, `build-history`, `build-all-histories` → `history`
- `stage-all`, `validate-manifest`, `inspect-manifest`, `staging-stats` → `staging`
- `plot-its`, `plot-its-sequential`, `plot-its-presets` → `plotting`
- `plot-ivg` → `plotting`
- `plot-transconductance` → `plotting`

### Step 3: Update main.py (2 minutes)

Replace contents with plugin discovery version (see above).

### Step 4: Test (5 minutes)

```bash
# Test command discovery
python process_and_analyze.py --help

# Test each command still works
python process_and_analyze.py show-history --help
python process_and_analyze.py plot-its --help
python process_and_analyze.py stage-all --help

# Test a real command
python process_and_analyze.py show-history 67
```

### Step 5: Optional - Add Configuration (5 minutes)

```bash
# Try disabling a command group
cat > config/cli_plugins.yaml <<EOF
enabled_groups:
  - pipeline
  - history
  - staging
  # plotting disabled

disabled_commands: []

settings:
  allow_third_party: false
EOF

# Verify plotting commands are gone
python process_and_analyze.py --help
```

**Total time:** ~30 minutes

---

## Detailed Command Migration

### data_pipeline.py

```python
from src.cli.plugin_system import cli_command

@cli_command(
    name="full-pipeline",
    group="pipeline",
    description="Run complete data processing pipeline"
)
def full_pipeline_command(...):
    pass
```

### history.py

```python
from src.cli.plugin_system import cli_command

@cli_command(name="show-history", group="history")
def show_history_command(...):
    pass

@cli_command(name="build-history", group="history")
def build_history_command(...):
    pass

@cli_command(name="build-all-histories", group="history")
def build_all_histories_command(...):
    pass
```

### stage.py

```python
from src.cli.plugin_system import cli_command

@cli_command(name="stage-all", group="staging")
def stage_all_command(...):
    pass

@cli_command(name="validate-manifest", group="staging")
def validate_manifest_command(...):
    pass

@cli_command(name="inspect-manifest", group="staging")
def inspect_manifest_command(...):
    pass

@cli_command(name="staging-stats", group="staging")
def staging_stats_command(...):
    pass
```

### plot_its.py

```python
from src.cli.plugin_system import cli_command

@cli_command(name="plot-its", group="plotting")
def plot_its_command(...):
    pass

@cli_command(name="plot-its-sequential", group="plotting")
def plot_its_sequential_command(...):
    pass

@cli_command(
    name="plot-its-presets",
    group="plotting",
    aliases=["list-its-presets"]
)
def list_presets_command(...):
    pass
```

### plot_ivg.py

```python
from src.cli.plugin_system import cli_command

@cli_command(name="plot-ivg", group="plotting")
def plot_ivg_command(...):
    pass
```

### plot_transconductance.py

```python
from src.cli.plugin_system import cli_command

@cli_command(name="plot-transconductance", group="plotting")
def plot_transconductance_command(...):
    pass
```

---

## Adding New Commands (Post-Migration)

**Before Plugin System:**
1. Create command function in command module
2. Open `main.py`
3. Add import for new command
4. Add `app.command()` registration
5. Test

**After Plugin System:**
1. Create command function in command module
2. Add `@cli_command()` decorator
3. Test

**Example:**

```python
# NEW FILE: src/cli/commands/export.py
from src.cli.plugin_system import cli_command

@cli_command(
    name="export-csv",
    group="export",
    description="Export chip history to CSV"
)
def export_csv_command(
    chip_number: int = typer.Argument(...),
    output: Path = typer.Option(Path("export.csv"), "--output", "-o"),
):
    """Export chip history to CSV format."""
    # Implementation
    pass
```

**That's it!** No `main.py` changes needed.

---

## Rollback Plan

If issues occur, rollback is simple:

1. **Backup current main.py:**
   ```bash
   cp src/cli/main.py src/cli/main.py.plugin_backup
   ```

2. **Keep old main.py as fallback:**
   ```bash
   cp src/cli/main.py src/cli/main_manual.py
   ```

3. **To rollback:**
   ```bash
   cp src/cli/main_manual.py src/cli/main.py
   ```

The `@cli_command()` decorators don't affect functionality - they just register metadata. Commands work the same with or without the plugin system.

---

## Testing Checklist

After migration, verify:

- [ ] All commands appear in `--help` output
- [ ] Each command's `--help` still works
- [ ] Can run each command successfully
- [ ] No import errors on startup
- [ ] Configuration loading works
- [ ] Disabling command groups works
- [ ] Disabling specific commands works

**Test script:**

```bash
#!/bin/bash
set -e

echo "Testing command discovery..."
python process_and_analyze.py --help | grep -q "full-pipeline"
python process_and_analyze.py --help | grep -q "show-history"
python process_and_analyze.py --help | grep -q "plot-its"

echo "Testing individual commands..."
python process_and_analyze.py show-history --help > /dev/null
python process_and_analyze.py plot-its --help > /dev/null
python process_and_analyze.py stage-all --help > /dev/null

echo "Testing configuration..."
# Disable plotting
cat > config/cli_plugins.yaml <<EOF
enabled_groups:
  - pipeline
  - history
  - staging
disabled_commands: []
settings:
  allow_third_party: false
EOF

# Verify plotting is disabled
if python process_and_analyze.py --help | grep -q "plot-its"; then
    echo "ERROR: plot-its should be disabled!"
    exit 1
fi

echo "All tests passed!"
```

---

## Common Issues

### Issue 1: Commands not discovered

**Symptom:** `--help` shows empty or missing commands

**Causes:**
- `@cli_command()` decorator missing
- Import error in command module
- Wrong `commands_dir` path in `discover_commands()`

**Fix:**
```bash
# Debug mode - see what's being discovered
# Edit main.py temporarily:
discover_commands(app, Path("src/cli/commands"), verbose=True)

# Run to see debug output
python process_and_analyze.py --help
```

### Issue 2: Duplicate command registration

**Symptom:** Warning about duplicate commands

**Cause:** Command registered both manually and via plugin system

**Fix:** Remove manual registration from `main.py` - let plugin system handle it.

### Issue 3: Configuration not loaded

**Symptom:** All commands enabled despite config

**Cause:** Config file path wrong or YAML syntax error

**Fix:**
```bash
# Check config syntax
python -c "import yaml; yaml.safe_load(open('config/cli_plugins.yaml'))"

# Check file exists
ls -la config/cli_plugins.yaml
```

---

## Benefits Realized

After migration, you get:

✅ **No main.py changes** when adding commands
✅ **Configuration-driven** command availability
✅ **Third-party plugin** support
✅ **Better organization** with command groups
✅ **Easy testing** of individual commands
✅ **Cleaner codebase** (67% reduction in main.py)
✅ **Extensibility** for future features
✅ **Backward compatible** - existing commands work unchanged

---

## Next Steps

After successful migration:

1. **Add utility command** to list plugins:
   ```python
   @cli_command(name="list-plugins", group="utilities")
   def list_plugins_command(...):
       # Show all available commands and groups
       pass
   ```

2. **Create development config** for testing:
   ```yaml
   # config/cli_plugins_dev.yaml
   enabled_groups:
     - all
   disabled_commands: []
   settings:
     allow_third_party: true
     third_party_dirs: [./dev_plugins]
   ```

3. **Document plugin development** for external contributors

4. **Add plugin examples** to repository

5. **Consider lazy loading** for faster startup:
   ```python
   settings:
     lazy_loading: true  # Only load commands when used
   ```

---

## Summary

The plugin system migration is **low-risk, high-reward**:

- **Low risk**: Minimal code changes, easy rollback, backward compatible
- **High reward**: Cleaner code, better extensibility, configuration control

**Recommended approach:**
1. Migrate in development environment first
2. Test thoroughly (30 minutes)
3. Deploy to production when comfortable

The entire migration takes ~30 minutes and makes future development significantly easier.
