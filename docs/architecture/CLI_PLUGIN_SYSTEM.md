# CLI Plugin System Documentation

**Last Updated:** October 31, 2025
**Version:** 3.0+

Complete guide to the CLI plugin system for automatic command discovery and registration.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Creating Commands](#creating-commands)
5. [Plugin Configuration](#plugin-configuration)
6. [Command Groups](#command-groups)
7. [Advanced Features](#advanced-features)
8. [API Reference](#api-reference)
9. [Migration Guide](#migration-guide)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The CLI plugin system provides **automatic command discovery and registration** using a decorator-based pattern. Commands are defined with the `@cli_command` decorator and automatically registered when the CLI starts.

### Key Benefits

✅ **Zero Boilerplate** - No manual registration in `main.py`
✅ **Automatic Discovery** - Commands are found and registered automatically
✅ **Configuration-Driven** - Enable/disable commands via YAML config
✅ **Group Organization** - Organize commands into logical groups
✅ **Extensible** - Easy to add new commands without touching core code
✅ **Priority Control** - Control command registration order
✅ **Alias Support** - Multiple names for the same command

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Application                         │
│                      (src/cli/main.py)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
                  ┌────────────────────┐
                  │ Plugin Discovery   │
                  │ discover_commands()│
                  └────────┬───────────┘
                           │
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
    ┌─────────┐      ┌─────────┐     ┌─────────┐
    │ Import  │      │ Import  │     │ Import  │
    │ Module 1│      │ Module 2│     │ Module 3│
    └────┬────┘      └────┬────┘     └────┬────┘
         │                │                │
         ↓                ↓                ↓
    @cli_command    @cli_command     @cli_command
         │                │                │
         └────────────────┴────────────────┘
                          │
                          ↓
                ┌──────────────────┐
                │ Command Registry │
                │  (_COMMAND_      │
                │   REGISTRY)      │
                └─────────┬────────┘
                          │
                          ↓
                ┌──────────────────┐
                │ Filter by Config │
                │ (cli_plugins.yml)│
                └─────────┬────────┘
                          │
                          ↓
                ┌──────────────────┐
                │ Register with    │
                │ Typer App        │
                └──────────────────┘
```

---

## Quick Start

### Creating Your First Command

**1. Create a command file** in `src/cli/commands/`:

```python
# src/cli/commands/my_feature.py
from src.cli.plugin_system import cli_command
import typer
from rich.console import Console

console = Console()


@cli_command(
    name="my-command",
    group="utilities",
    description="Brief description of what this command does"
)
def my_command_function(
    chip_number: int = typer.Argument(..., help="Chip number"),
    option: str = typer.Option("default", "--option", "-o", help="Optional parameter")
):
    """
    Detailed description of your command.

    This will be shown in --help output.
    """
    console.print(f"Running my command for chip {chip_number}")
    console.print(f"Option value: {option}")
    # Your implementation here
```

**2. Test it immediately** - No registration needed!

```bash
# Command is auto-discovered and available
python process_and_analyze.py my-command 67 --option test

# Check help
python process_and_analyze.py my-command --help
```

That's it! The command is automatically discovered and registered.

---

## Architecture

### Plugin System Components

#### 1. Decorator: `@cli_command`

The `@cli_command` decorator marks functions as CLI commands and stores their metadata in a global registry.

**Source:** `src/cli/plugin_system.py`

```python
@cli_command(
    name="command-name",      # Required: kebab-case command name
    group="group-name",       # Required: command group for organization
    description="...",        # Optional: short description (or uses docstring)
    aliases=["alias1"],       # Optional: alternative names
    priority=0                # Optional: registration priority (higher = earlier)
)
def my_command_function(...):
    pass
```

#### 2. Discovery: `discover_commands()`

Scans the commands directory, imports modules, and registers decorated commands with the Typer app.

**Process:**

1. **Scan** `src/cli/commands/` for Python files
2. **Import** each module (triggers `@cli_command` decorators)
3. **Load** plugin configuration from `config/cli_plugins.yaml`
4. **Filter** commands based on enabled groups and disabled list
5. **Register** commands with Typer app in priority order

#### 3. Registry: `_COMMAND_REGISTRY`

Global dictionary storing all discovered command metadata.

```python
_COMMAND_REGISTRY = {
    "show-history": CommandMetadata(
        name="show-history",
        function=show_history_command,
        group="history",
        description="Display chip experiment timeline",
        aliases=[],
        enabled=True,
        priority=0
    ),
    # ... more commands
}
```

#### 4. Configuration: `cli_plugins.yaml`

YAML file controlling which commands are available.

**Location:** `config/cli_plugins.yaml`

```yaml
enabled_groups:
  - all  # or list specific groups

disabled_commands:
  - command-to-disable
```

---

## Creating Commands

### Basic Command Structure

```python
from src.cli.plugin_system import cli_command
from src.cli.main import get_config
import typer
from rich.console import Console
from pathlib import Path

console = Console()


@cli_command(
    name="example-command",
    group="plotting",  # or: pipeline, history, staging, utilities
    description="Short description for list-plugins output"
)
def example_command(
    # Required arguments (positional)
    chip_number: int = typer.Argument(
        ...,
        help="Chip number to process"
    ),

    # Optional arguments (flags)
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: from config)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output"
    ),
):
    """
    Detailed command description shown in --help.

    This can be multiple paragraphs and include examples.

    Examples:
        python process_and_analyze.py example-command 67
        python process_and_analyze.py example-command 67 --verbose
    """
    # Load configuration
    config = get_config()

    # Determine output directory
    if output_dir is None:
        output_dir = config.output_dir

    # Implementation
    console.print(f"Processing chip {chip_number}")
    console.print(f"Output: {output_dir}")

    # Your logic here
```

### Command Patterns by Type

#### Data Processing Command

```python
@cli_command(name="process-data", group="pipeline")
def process_data_command(
    input_dir: Path = typer.Argument(...),
    workers: int = typer.Option(6, "--workers", "-w")
):
    """Process raw data files."""
    from src.core import stage_raw_measurements

    stage_raw_measurements.stage_all(
        input_dir=input_dir,
        workers=workers
    )
```

#### Plotting Command

```python
@cli_command(name="plot-analysis", group="plotting")
def plot_analysis_command(
    chip_number: int = typer.Argument(...),
    seq: Optional[str] = typer.Option(None, "--seq")
):
    """Generate analysis plots."""
    from src.plotting import my_analysis
    from src.cli.helpers import parse_sequence_str

    config = get_config()

    # Load history
    history_file = config.history_dir / f"Alisson{chip_number}_history.parquet"
    history = pl.read_parquet(history_file)

    # Filter by sequence
    if seq:
        seq_nums = parse_sequence_str(seq)
        history = history.filter(pl.col("seq").is_in(seq_nums))

    # Generate plot
    output_file = my_analysis.plot(
        history,
        output_dir=config.output_dir,
        chip_name=f"Alisson{chip_number}"
    )

    console.print(f"[green]✓[/green] Saved: {output_file}")
```

#### Validation Command

```python
@cli_command(name="validate-data", group="staging")
def validate_data_command(
    strict: bool = typer.Option(False, "--strict")
):
    """Validate staged data quality."""
    from src.core.schema_validator import validate_all

    issues = validate_all(strict=strict)

    if issues:
        console.print(f"[red]Found {len(issues)} issues[/red]")
        for issue in issues:
            console.print(f"  • {issue}")
        raise typer.Exit(1)
    else:
        console.print("[green]✓ All data valid[/green]")
```

### Command with Aliases

```python
@cli_command(
    name="list-presets",
    group="utilities",
    aliases=["presets", "show-presets"]  # Multiple names
)
def list_presets_command():
    """List available presets."""
    # All three names work:
    # - python process_and_analyze.py list-presets
    # - python process_and_analyze.py presets
    # - python process_and_analyze.py show-presets
    pass
```

### Command with Priority

```python
# High priority = registered early (useful for --help ordering)
@cli_command(
    name="full-pipeline",
    group="pipeline",
    priority=100  # Higher priority = registered first
)
def full_pipeline_command():
    """Run complete pipeline (appears first in help)."""
    pass


@cli_command(
    name="advanced-feature",
    group="pipeline",
    priority=-10  # Lower priority = registered last
)
def advanced_feature_command():
    """Advanced feature (appears last in help)."""
    pass
```

---

## Plugin Configuration

### Configuration File: `config/cli_plugins.yaml`

Controls which commands are enabled/disabled at runtime.

#### Enable All Commands (Default)

```yaml
enabled_groups:
  - all

disabled_commands: []
```

#### Enable Specific Groups

```yaml
enabled_groups:
  - pipeline
  - history
  - staging
  # plotting not listed = disabled

disabled_commands: []
```

**Result:** Only pipeline, history, and staging commands are available. All plotting commands are hidden.

#### Disable Specific Commands

```yaml
enabled_groups:
  - all

disabled_commands:
  - experimental-feature
  - beta-command
```

**Result:** All commands except `experimental-feature` and `beta-command` are available.

#### Lab User Configuration (Minimal Commands)

```yaml
enabled_groups:
  - plotting  # Only plotting commands

disabled_commands:
  - plot-transconductance  # Hide advanced plots
```

**Result:** Only plotting commands (except transconductance) are available. Staging and pipeline commands are hidden.

### Loading Order

1. **Try to load** `config/cli_plugins.yaml`
2. **If missing or invalid**, use defaults (all enabled)
3. **Apply filters** during command discovery
4. **Register** only enabled commands with Typer

### Third-Party Plugins (Planned)

```yaml
settings:
  allow_third_party: true
  third_party_dirs:
    - ~/.optothermal/plugins
    - /usr/local/share/optothermal/plugins
  third_party_prefix: "ext-"
```

**Note:** Third-party plugin loading is not yet implemented but the configuration structure is reserved.

---

## Command Groups

Commands are organized into logical groups for better organization and selective enabling/disabling.

### Standard Groups

| Group | Purpose | Example Commands |
|-------|---------|------------------|
| **pipeline** | Full pipeline orchestration | `full-pipeline`, `derive-all-metrics` |
| **history** | History viewing and generation | `show-history`, `build-all-histories` |
| **staging** | Data staging and validation | `stage-all`, `validate-manifest` |
| **plotting** | All plotting commands | `plot-its`, `plot-ivg`, `plot-cnp-time` |
| **utilities** | Helper and utility commands | `list-plugins`, `config-show` |

### Group Guidelines

**Choose the right group:**

- **pipeline** - Commands that run multiple steps or orchestrate workflows
- **history** - Commands that work with chip histories
- **staging** - Commands that process raw data or validate staged data
- **plotting** - Commands that generate figures
- **utilities** - Commands for configuration, inspection, or debugging

**Naming conventions:**

- Use lowercase for group names
- Use plural if the group contains multiple command types
- Keep names short (1-2 words)

### Listing Commands by Group

```bash
# List all available groups
python process_and_analyze.py list-plugins --groups

# List commands in a specific group
python process_and_analyze.py list-plugins --group plotting

# List all commands with metadata
python process_and_analyze.py list-plugins
```

---

## Advanced Features

### Custom Command Discovery

You can programmatically control command discovery:

```python
from src.cli.plugin_system import (
    discover_commands,
    list_available_commands,
    get_command_groups
)

# Discover with custom settings
app = typer.Typer()
discover_commands(
    app,
    commands_dir="src/cli/commands",
    config_path=Path("config/cli_plugins.yaml"),
    verbose=True  # Print discovery progress
)

# Query registered commands
all_commands = list_available_commands()
plotting_commands = list_available_commands(group="plotting")
groups = get_command_groups()
```

### Testing Commands

```python
from src.cli.plugin_system import clear_registry, _COMMAND_REGISTRY

# Clear registry for testing
clear_registry()

# Manually register test command
@cli_command(name="test-cmd", group="test")
def test_command():
    pass

# Verify registration
assert "test-cmd" in _COMMAND_REGISTRY
```

### Dynamic Command Registration

```python
from src.cli.plugin_system import cli_command

# Dynamically create commands
for metric in ["cnp", "mobility", "resistance"]:
    @cli_command(
        name=f"extract-{metric}",
        group="metrics"
    )
    def extract_metric(chip: int, metric_name=metric):
        print(f"Extracting {metric_name} for chip {chip}")
```

### Configuration Integration

All commands should support the persistent configuration system:

```python
@cli_command(name="my-command", group="plotting")
def my_command(
    chip_number: int = typer.Argument(...),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o")
):
    """Command with config integration."""
    # Load config
    config = get_config()

    # Use CLI override if provided, otherwise use config
    if output_dir is None:
        output_dir = config.output_dir

    # Access other config fields
    if config.verbose:
        console.print("[dim]Verbose mode enabled[/dim]")

    # Check dry run
    if config.dry_run:
        console.print("[yellow]DRY RUN[/yellow] - Would process chip {chip_number}")
        return
```

---

## API Reference

### Decorator: `@cli_command`

```python
def cli_command(
    name: str,
    group: str = "general",
    description: str = "",
    aliases: Optional[List[str]] = None,
    priority: int = 0,
) -> Callable
```

**Parameters:**

- `name` (str): Command name in kebab-case (e.g., "show-history")
- `group` (str): Command group for organization (default: "general")
- `description` (str): Short description (default: extracted from docstring)
- `aliases` (List[str]): Alternative command names (default: [])
- `priority` (int): Registration priority, higher = earlier (default: 0)

**Returns:** Decorator function that registers the command

**Example:**
```python
@cli_command(name="my-cmd", group="utilities", priority=10)
def my_cmd():
    pass
```

### Function: `discover_commands`

```python
def discover_commands(
    app: typer.Typer,
    commands_dir: str | Path = "src/cli/commands",
    config_path: Optional[Path] = None,
    verbose: bool = False,
) -> None
```

**Parameters:**

- `app` (typer.Typer): Typer app to register commands with
- `commands_dir` (str | Path): Directory containing command modules
- `config_path` (Path | None): Path to plugin config YAML
- `verbose` (bool): Print discovery progress

**Side Effects:** Imports all modules in commands_dir and registers discovered commands

**Example:**
```python
app = typer.Typer()
discover_commands(app, verbose=True)
```

### Function: `load_plugin_config`

```python
def load_plugin_config(
    config_path: Optional[Path] = None
) -> Dict[str, Any]
```

**Parameters:**

- `config_path` (Path | None): Path to YAML config (default: config/cli_plugins.yaml)

**Returns:** Dict with keys: `enabled_groups`, `disabled_commands`, `settings`

**Example:**
```python
config = load_plugin_config()
print(config["enabled_groups"])  # ['all'] or ['pipeline', 'history']
```

### Function: `list_available_commands`

```python
def list_available_commands(
    group: Optional[str] = None
) -> List[CommandMetadata]
```

**Parameters:**

- `group` (str | None): Filter by group name

**Returns:** List of CommandMetadata objects

**Example:**
```python
all_cmds = list_available_commands()
plotting_cmds = list_available_commands(group="plotting")
```

### Function: `get_command_groups`

```python
def get_command_groups() -> List[str]
```

**Returns:** Sorted list of all command group names

**Example:**
```python
groups = get_command_groups()  # ['history', 'pipeline', 'plotting', ...]
```

### Class: `CommandMetadata`

```python
@dataclass
class CommandMetadata:
    name: str                  # Command name (kebab-case)
    function: Callable         # Command function
    group: str                 # Command group
    description: str           # Short description
    aliases: List[str]         # Alternative names
    enabled: bool              # Whether enabled
    priority: int              # Registration priority
```

---

## Migration Guide

### From Manual Registration to Plugin System

**Before (Manual Registration):**

```python
# main.py
from src.cli.commands.history import show_history_command

app = typer.Typer()
app.command(name="show-history")(show_history_command)
```

**After (Plugin System):**

```python
# src/cli/commands/history.py
@cli_command(name="show-history", group="history")
def show_history_command(...):
    pass

# main.py
app = typer.Typer()
discover_commands(app)  # Automatic!
```

### Migration Checklist

- [ ] Add `@cli_command` decorator to each command function
- [ ] Specify `name` and `group` parameters
- [ ] Remove manual `app.command()` calls from `main.py`
- [ ] Add `discover_commands(app)` in `main.py`
- [ ] Test all commands still work: `python process_and_analyze.py --help`
- [ ] Create `config/cli_plugins.yaml` if needed

### Common Migration Issues

**Issue:** Command not appearing

**Solution:** Check decorator syntax and ensure module is in `src/cli/commands/`

```python
# Wrong - function not decorated
def my_command():
    pass

# Right - function decorated
@cli_command(name="my-command", group="utilities")
def my_command():
    pass
```

**Issue:** Command appears but doesn't work

**Solution:** Ensure function signature is correct for Typer

```python
# Wrong - missing type hints
@cli_command(name="cmd", group="util")
def cmd(chip):  # No type hint
    pass

# Right - includes type hints
@cli_command(name="cmd", group="util")
def cmd(chip: int = typer.Argument(...)):
    pass
```

---

## Troubleshooting

### Debugging Discovery

Enable verbose mode to see discovery process:

```python
# main.py
discover_commands(
    app,
    commands_dir=Path("src/cli/commands"),
    verbose=True  # Prints loaded modules and registered commands
)
```

**Output:**
```
Loaded plugin module: src.cli.commands.history
Loaded plugin module: src.cli.commands.stage
Registered: show-history [history]
Registered: stage-all [staging]
Skipped (group disabled): plot-its [plotting]
Total commands registered: 8/13
```

### Common Issues

#### Command Not Discovered

**Symptoms:** Command doesn't appear in `--help`

**Causes:**
1. File not in `src/cli/commands/` directory
2. File name starts with underscore (ignored)
3. Import error in module
4. Missing `@cli_command` decorator

**Solutions:**
- Check file location
- Run discovery with `verbose=True`
- Check for import errors: `python -c "import src.cli.commands.my_module"`

#### Command Disabled by Configuration

**Symptoms:** Command worked before but now missing

**Causes:**
1. Group disabled in `cli_plugins.yaml`
2. Command explicitly disabled in `cli_plugins.yaml`

**Solutions:**
```bash
# Check configuration
cat config/cli_plugins.yaml

# Temporarily enable all
# Edit config/cli_plugins.yaml:
enabled_groups:
  - all
disabled_commands: []
```

#### Import Errors

**Symptoms:** Discovery prints warnings about failed imports

**Solutions:**
- Fix import errors in command module
- Check dependencies are installed
- Verify circular import issues

```python
# Check imports
python -c "from src.cli.commands.my_module import my_command"
```

#### Priority Not Working

**Symptoms:** Commands appear in wrong order in help

**Cause:** Typer may reorder commands alphabetically regardless of registration order

**Solution:** Priority controls registration order, but Typer's help display order is implementation-dependent. Use command names to control alphabetical ordering if needed.

### Validation Commands

```bash
# List all discovered commands
python process_and_analyze.py list-plugins

# List commands by group
python process_and_analyze.py list-plugins --group plotting

# Check if specific command is registered
python process_and_analyze.py my-command --help
```

### Reset Registry (For Testing)

```python
from src.cli.plugin_system import clear_registry

# Clear all registered commands
clear_registry()

# Re-import to re-register
import importlib
import src.cli.commands.history
importlib.reload(src.cli.commands.history)
```

---

## Best Practices

### ✅ DO

- Use kebab-case for command names (`show-history`, not `show_history`)
- Assign commands to appropriate groups
- Write clear docstrings (shown in `--help`)
- Support configuration system via `get_config()`
- Handle missing optional parameters gracefully
- Provide helpful error messages
- Use Rich for beautiful terminal output

### ❌ DON'T

- Don't manually register commands in `main.py`
- Don't use spaces in command names
- Don't create commands in subdirectories of `commands/`
- Don't forget type hints on parameters
- Don't hard-code paths (use config)
- Don't ignore import errors

### Example: Well-Structured Command

```python
from src.cli.plugin_system import cli_command
from src.cli.main import get_config
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel

console = Console()


@cli_command(
    name="process-chip",
    group="pipeline",
    description="Process all measurements for a chip"
)
def process_chip_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number to process"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: from config)"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force reprocessing"
    ),
):
    """
    Process all measurements for a specific chip.

    This command stages raw measurements, builds history,
    and extracts derived metrics.

    Examples:
        # Process chip 67
        python process_and_analyze.py process-chip 67

        # Process with custom output
        python process_and_analyze.py process-chip 67 --output /tmp/results

        # Force reprocessing
        python process_and_analyze.py process-chip 67 --force
    """
    # Load configuration
    config = get_config()

    # Use config defaults if not overridden
    if output_dir is None:
        output_dir = config.output_dir

    # Display header
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Processing Chip {chip_number}[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    # Validate inputs
    if chip_number < 1:
        console.print("[red]Error:[/red] Chip number must be positive")
        raise typer.Exit(1)

    # Dry run check
    if config.dry_run:
        console.print("[yellow]DRY RUN:[/yellow] Would process chip {chip_number}")
        return

    try:
        # Implementation
        console.print(f"[cyan]Output directory:[/cyan] {output_dir}")
        console.print(f"[cyan]Force reprocessing:[/cyan] {force}")

        # Your processing logic here

        console.print()
        console.print("[green]✓ Processing complete[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if config.verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)
```

---

## See Also

- [CLI Module Architecture](CLI_MODULE_ARCHITECTURE.md) - Overall CLI design
- [Configuration Guide](CONFIGURATION.md) - Configuration system
- [Adding Procedures](ADDING_PROCEDURES.md) - Data processing procedures
- [Plotting Implementation Guide](PLOTTING_IMPLEMENTATION_GUIDE.md) - Creating plotting commands

---

**Questions or issues?** Check the [Troubleshooting](#troubleshooting) section or open an issue on GitHub.
