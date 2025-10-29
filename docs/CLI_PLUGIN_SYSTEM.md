# CLI Plugin System Architecture

## Table of Contents

1. [Overview](#overview)
2. [Current System Limitations](#current-system-limitations)
3. [Plugin System Design](#plugin-system-design)
4. [Implementation](#implementation)
5. [Command Plugin Structure](#command-plugin-structure)
6. [Plugin Configuration](#plugin-configuration)
7. [Migration Guide](#migration-guide)
8. [Advanced Features](#advanced-features)
9. [Examples](#examples)

---

## Overview

The **Plugin System** enables automatic discovery and registration of CLI commands, eliminating the need to manually update `main.py` when adding new commands. It supports:

- **Auto-discovery**: Commands are automatically found and registered
- **Declarative metadata**: Commands declare their own names and groups
- **Dynamic loading**: Enable/disable command groups via configuration
- **Third-party extensions**: External packages can provide commands
- **Backward compatibility**: Existing commands work without changes

---

## Current System Limitations

### Manual Registration Required

**Current `main.py`:**
```python
# Must import every command
from src.cli.commands.data_pipeline import full_pipeline_command
from src.cli.commands.history import show_history_command, build_history_command
from src.cli.commands.plot_its import plot_its_command
# ... 15+ imports

# Must register every command
app.command(name="full-pipeline")(full_pipeline_command)
app.command(name="show-history")(show_history_command)
app.command(name="build-history")(build_history_command)
# ... 15+ registrations
```

**Problems:**
1. Adding a command requires modifying `main.py`
2. No way to disable command groups (e.g., disable plotting)
3. No support for third-party command extensions
4. High coupling between commands and main app
5. Harder to test individual command modules

---

## Plugin System Design

### Architecture Overview

```
src/cli/
├── main.py                    # Plugin discovery and app creation
├── plugin_system.py           # Plugin infrastructure (NEW)
├── commands/                  # Command plugins
│   ├── __init__.py
│   ├── data_pipeline.py       # Data pipeline plugin
│   ├── history.py             # History plugin
│   ├── stage.py               # Staging plugin
│   ├── plot_its.py            # ITS plotting plugin
│   ├── plot_ivg.py            # IVg plotting plugin
│   └── plot_transconductance.py
├── helpers.py
└── history_utils.py

config/
└── cli_plugins.yaml           # Plugin configuration (NEW)
```

### Core Concepts

#### 1. Command Decorator

Commands use a `@cli_command` decorator to declare metadata:

```python
from src.cli.plugin_system import cli_command

@cli_command(
    name="full-pipeline",
    group="pipeline",
    description="Run complete data processing pipeline"
)
def full_pipeline_command(...):
    """Full pipeline implementation"""
    pass
```

#### 2. Plugin Discovery

Main app discovers and registers all decorated commands:

```python
# main.py
from src.cli.plugin_system import discover_commands

app = typer.Typer(name="process_and_analyze", ...)

# Auto-discover and register commands
discover_commands(app, "src/cli/commands")
```

#### 3. Plugin Configuration

Enable/disable command groups via YAML:

```yaml
# config/cli_plugins.yaml
enabled_groups:
  - pipeline
  - history
  - staging
  - plotting

disabled_commands:
  - plot-its-sequential  # Temporarily disable specific command
```

---

## Implementation

### 1. Plugin System Infrastructure

Create `src/cli/plugin_system.py`:

```python
"""
CLI Plugin System - Auto-discovery and registration of commands.

Provides decorator-based command registration and automatic discovery
from the commands directory.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass, field
from functools import wraps

import typer
import yaml


@dataclass
class CommandMetadata:
    """Metadata for a CLI command plugin."""

    name: str
    """Command name (kebab-case, e.g., 'full-pipeline')"""

    function: Callable
    """The actual command function"""

    group: str = "general"
    """Command group for organization (e.g., 'pipeline', 'plotting')"""

    description: str = ""
    """Short description for the command"""

    aliases: List[str] = field(default_factory=list)
    """Alternative names for the command"""

    enabled: bool = True
    """Whether the command is enabled"""

    priority: int = 0
    """Registration priority (higher = earlier)"""


# Global registry of discovered commands
_COMMAND_REGISTRY: Dict[str, CommandMetadata] = {}


def cli_command(
    name: str,
    group: str = "general",
    description: str = "",
    aliases: Optional[List[str]] = None,
    priority: int = 0,
):
    """
    Decorator to register a function as a CLI command plugin.

    Parameters
    ----------
    name : str
        Command name (kebab-case, e.g., 'show-history')
    group : str
        Command group for organization (e.g., 'history', 'plotting')
    description : str
        Short description (overrides docstring first line)
    aliases : list[str], optional
        Alternative command names
    priority : int
        Registration priority (higher = registered earlier)

    Examples
    --------
    >>> @cli_command(name="show-history", group="history")
    ... def show_history_command(chip_number: int, ...):
    ...     '''Display chip experiment history'''
    ...     pass

    Notes
    -----
    The decorated function is registered in the global command registry
    and will be discovered by discover_commands().
    """
    def decorator(func: Callable) -> Callable:
        # Extract description from docstring if not provided
        if not description and func.__doc__:
            desc = func.__doc__.strip().split('\n')[0]
        else:
            desc = description

        # Create metadata
        metadata = CommandMetadata(
            name=name,
            function=func,
            group=group,
            description=desc,
            aliases=aliases or [],
            priority=priority,
        )

        # Register command
        _COMMAND_REGISTRY[name] = metadata

        # Return original function (decorator doesn't wrap)
        return func

    return decorator


def load_plugin_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load plugin configuration from YAML file.

    Parameters
    ----------
    config_path : Path, optional
        Path to plugin config YAML. Defaults to config/cli_plugins.yaml

    Returns
    -------
    dict
        Plugin configuration with keys:
        - enabled_groups: List of enabled command groups
        - disabled_commands: List of disabled command names
        - settings: Additional plugin settings
    """
    if config_path is None:
        config_path = Path("config/cli_plugins.yaml")

    # Default configuration
    default_config = {
        "enabled_groups": ["all"],  # "all" means enable everything
        "disabled_commands": [],
        "settings": {},
    }

    if not config_path.exists():
        return default_config

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Merge with defaults
        return {**default_config, **(config or {})}

    except Exception as e:
        # If config fails to load, use defaults
        import sys
        print(f"Warning: Failed to load plugin config: {e}", file=sys.stderr)
        return default_config


def discover_commands(
    app: typer.Typer,
    commands_dir: str | Path = "src/cli/commands",
    config_path: Optional[Path] = None,
    verbose: bool = False,
) -> None:
    """
    Auto-discover and register all command plugins.

    Scans the commands directory for Python modules, imports them to
    trigger @cli_command decorators, then registers discovered commands
    with the Typer app.

    Parameters
    ----------
    app : typer.Typer
        The Typer application to register commands with
    commands_dir : str | Path
        Directory containing command modules
    config_path : Path, optional
        Path to plugin configuration YAML
    verbose : bool
        Print discovered commands (for debugging)

    Examples
    --------
    >>> app = typer.Typer()
    >>> discover_commands(app, "src/cli/commands")
    >>> # All decorated commands are now registered

    Notes
    -----
    Commands are registered in priority order (highest first), then
    alphabetically by name.
    """
    commands_path = Path(commands_dir)

    if not commands_path.exists():
        raise FileNotFoundError(f"Commands directory not found: {commands_path}")

    # Load plugin configuration
    config = load_plugin_config(config_path)
    enabled_groups = config["enabled_groups"]
    disabled_commands = config["disabled_commands"]

    # Import all command modules (triggers @cli_command decorators)
    for module_path in commands_path.glob("*.py"):
        if module_path.stem == "__init__":
            continue

        # Convert path to module name: src/cli/commands/history.py -> src.cli.commands.history
        module_name = str(module_path.with_suffix("")).replace("/", ".")

        try:
            importlib.import_module(module_name)
            if verbose:
                print(f"Loaded plugin module: {module_name}")
        except Exception as e:
            import sys
            print(f"Warning: Failed to load plugin {module_name}: {e}", file=sys.stderr)

    # Register discovered commands
    # Sort by priority (descending) then name (ascending)
    sorted_commands = sorted(
        _COMMAND_REGISTRY.values(),
        key=lambda c: (-c.priority, c.name)
    )

    registered_count = 0
    for metadata in sorted_commands:
        # Check if command group is enabled
        if "all" not in enabled_groups and metadata.group not in enabled_groups:
            if verbose:
                print(f"Skipped (group disabled): {metadata.name} [{metadata.group}]")
            continue

        # Check if specific command is disabled
        if metadata.name in disabled_commands:
            if verbose:
                print(f"Skipped (explicitly disabled): {metadata.name}")
            continue

        # Register command with Typer
        app.command(name=metadata.name)(metadata.function)
        registered_count += 1

        if verbose:
            print(f"Registered: {metadata.name} [{metadata.group}]")

        # Register aliases
        for alias in metadata.aliases:
            app.command(name=alias)(metadata.function)
            if verbose:
                print(f"  Alias: {alias} -> {metadata.name}")

    if verbose:
        print(f"\nTotal commands registered: {registered_count}/{len(_COMMAND_REGISTRY)}")


def list_available_commands(group: Optional[str] = None) -> List[CommandMetadata]:
    """
    Get list of all available command plugins.

    Parameters
    ----------
    group : str, optional
        Filter by command group

    Returns
    -------
    list[CommandMetadata]
        List of command metadata objects
    """
    commands = list(_COMMAND_REGISTRY.values())

    if group:
        commands = [c for c in commands if c.group == group]

    return sorted(commands, key=lambda c: c.name)


def get_command_groups() -> List[str]:
    """Get list of all command groups."""
    return sorted(set(c.group for c in _COMMAND_REGISTRY.values()))


def clear_registry() -> None:
    """Clear the command registry (useful for testing)."""
    _COMMAND_REGISTRY.clear()
```

### 2. Updated main.py

Simplified with plugin discovery:

```python
#!/usr/bin/env python3
"""
Main CLI application entry point with plugin system.

Commands are auto-discovered from the commands/ directory using
the @cli_command decorator. No manual registration required.
"""

import typer
from pathlib import Path
from src.cli.plugin_system import discover_commands

# Create the main Typer app
app = typer.Typer(
    name="process_and_analyze",
    help="Complete data processing and analysis pipeline for semiconductor device characterization",
    add_completion=False
)

# Auto-discover and register all command plugins
discover_commands(
    app,
    commands_dir=Path("src/cli/commands"),
    config_path=Path("config/cli_plugins.yaml"),
    verbose=False  # Set to True for debugging
)


def main():
    """Main entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
```

**Before vs After:**
- **Before**: 40+ lines of imports and registrations
- **After**: 10 lines with auto-discovery
- **Adding command**: Just add `@cli_command` decorator, no main.py changes

### 3. Plugin Configuration File

Create `config/cli_plugins.yaml`:

```yaml
# CLI Plugin Configuration
# Controls which command groups and individual commands are enabled

# Command groups to enable
# Use "all" to enable everything, or list specific groups
enabled_groups:
  - all  # Enable all command groups

# Alternative: Enable only specific groups
# enabled_groups:
#   - pipeline
#   - history
#   - staging
#   - plotting

# Disable specific commands (even if their group is enabled)
disabled_commands: []
  # - plot-its-sequential  # Example: disable experimental command
  # - staging-stats        # Example: disable stats command

# Plugin settings (for advanced features)
settings:
  # Allow third-party plugins
  allow_third_party: false

  # Third-party plugin directories
  third_party_dirs: []
    # - ~/.optothermal/plugins
    # - /usr/local/share/optothermal/plugins

  # Command name prefix for third-party plugins
  third_party_prefix: "ext-"
```

---

## Command Plugin Structure

### Migrating Existing Commands

**Before (manual registration):**
```python
# src/cli/commands/history.py

def show_history_command(
    chip_number: int = typer.Argument(...),
    ...
):
    """Display chip experiment history"""
    pass
```

**After (plugin system):**
```python
# src/cli/commands/history.py
from src.cli.plugin_system import cli_command

@cli_command(
    name="show-history",
    group="history",
    description="Display chip experiment history"
)
def show_history_command(
    chip_number: int = typer.Argument(...),
    ...
):
    """Display chip experiment history"""
    pass


@cli_command(
    name="build-history",
    group="history"
)
def build_history_command(...):
    """Build chip history from staged data"""
    pass


@cli_command(
    name="build-all-histories",
    group="history"
)
def build_all_histories_command(...):
    """Build histories for all chips"""
    pass
```

### Plugin Module Template

**Pattern for new command modules:**

```python
"""
Command module: <name>

Description of what these commands do.
"""

import typer
from pathlib import Path
from rich.console import Console
from src.cli.plugin_system import cli_command

console = Console()


@cli_command(
    name="my-command",
    group="my-group",
    description="Brief description",
    aliases=["mc", "myc"],  # Optional aliases
    priority=0  # Optional priority
)
def my_command(
    arg: int = typer.Argument(..., help="Required argument"),
    opt: str = typer.Option("default", "--opt", "-o", help="Optional flag"),
):
    """
    Detailed command description.

    Examples:
        python process_and_analyze.py my-command 42 --opt value
    """
    console.print("[cyan]Running my command...[/cyan]")
    # Implementation here
    console.print("[green]✓ Success![/green]")
```

---

## Plugin Configuration

### Command Groups

Organize commands into logical groups:

```python
@cli_command(name="full-pipeline", group="pipeline")
@cli_command(name="show-history", group="history")
@cli_command(name="stage-all", group="staging")
@cli_command(name="plot-its", group="plotting")
```

**Suggested groups:**
- `pipeline` - Full pipeline orchestration
- `history` - History viewing and generation
- `staging` - Data staging and validation
- `plotting` - All plotting commands
- `utilities` - Helper commands
- `experimental` - Beta/experimental features

### Disabling Command Groups

**Disable all plotting commands:**

```yaml
# config/cli_plugins.yaml
enabled_groups:
  - pipeline
  - history
  - staging
  # plotting is NOT listed, so it's disabled

disabled_commands: []
```

**Disable specific commands:**

```yaml
enabled_groups:
  - all

disabled_commands:
  - plot-its-sequential  # Experimental, not ready
  - staging-stats        # Under development
```

### Priority Control

Use priority for command ordering (e.g., help text):

```python
@cli_command(
    name="full-pipeline",
    group="pipeline",
    priority=100  # Show first in help
)

@cli_command(
    name="plot-its",
    group="plotting",
    priority=50  # Show after pipeline commands
)

@cli_command(
    name="experimental-command",
    group="experimental",
    priority=-10  # Show last
)
```

---

## Migration Guide

### Step-by-Step Migration

#### 1. Create Plugin Infrastructure

```bash
# Create plugin system module
touch src/cli/plugin_system.py

# Create plugin configuration
mkdir -p config
touch config/cli_plugins.yaml
```

Copy the implementation from the [Implementation](#implementation) section above.

#### 2. Update Command Modules

For each command module in `src/cli/commands/`:

**Before:**
```python
# No decorator
def command_function(...):
    pass
```

**After:**
```python
from src.cli.plugin_system import cli_command

@cli_command(name="command-name", group="group-name")
def command_function(...):
    pass
```

**Example - src/cli/commands/history.py:**

```python
from src.cli.plugin_system import cli_command

# Add decorator to each command function
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

#### 3. Update main.py

Replace manual imports and registrations:

```python
# OLD: main.py (40+ lines)
from src.cli.commands.data_pipeline import full_pipeline_command
from src.cli.commands.history import show_history_command, ...
# ... many more imports

app.command(name="full-pipeline")(full_pipeline_command)
app.command(name="show-history")(show_history_command)
# ... many more registrations

# NEW: main.py (10 lines)
from src.cli.plugin_system import discover_commands

app = typer.Typer(...)
discover_commands(app, "src/cli/commands")
```

#### 4. Test Migration

```bash
# Verify all commands are discovered
python process_and_analyze.py --help

# Test individual commands
python process_and_analyze.py show-history 67
python process_and_analyze.py plot-its 67 --seq 52,57,58

# Debug mode (see what's being loaded)
# Temporarily set verbose=True in main.py
python process_and_analyze.py --help
```

#### 5. Create Plugin Configuration

```bash
# Copy default configuration
cat > config/cli_plugins.yaml <<EOF
enabled_groups:
  - all

disabled_commands: []

settings:
  allow_third_party: false
  third_party_dirs: []
  third_party_prefix: "ext-"
EOF
```

---

## Advanced Features

### 1. Third-Party Plugin Support

**Structure for external plugins:**

```
~/.optothermal/plugins/
└── my_custom_plugin/
    ├── __init__.py
    └── commands.py
```

**External plugin example:**

```python
# ~/.optothermal/plugins/my_custom_plugin/commands.py
from src.cli.plugin_system import cli_command
from rich.console import Console

console = Console()

@cli_command(
    name="custom-analysis",
    group="custom",
    description="My custom analysis command"
)
def custom_analysis_command(
    chip_number: int = typer.Argument(...),
):
    """Run custom analysis on chip data."""
    console.print(f"[cyan]Running custom analysis for chip {chip_number}...[/cyan]")
    # Custom implementation
```

**Enable third-party plugins:**

```yaml
# config/cli_plugins.yaml
settings:
  allow_third_party: true
  third_party_dirs:
    - ~/.optothermal/plugins
    - /usr/local/share/optothermal/plugins
  third_party_prefix: "ext-"  # Commands become: ext-custom-analysis
```

**Enhanced discovery in plugin_system.py:**

```python
def discover_commands(
    app: typer.Typer,
    commands_dir: str | Path = "src/cli/commands",
    config_path: Optional[Path] = None,
    verbose: bool = False,
):
    """Auto-discover commands from built-in and third-party plugins."""
    config = load_plugin_config(config_path)

    # Discover built-in commands
    _discover_from_directory(commands_dir, verbose)

    # Discover third-party plugins
    if config["settings"].get("allow_third_party", False):
        for plugin_dir in config["settings"].get("third_party_dirs", []):
            plugin_path = Path(plugin_dir).expanduser()
            if plugin_path.exists():
                _discover_third_party_plugins(plugin_path, verbose)

    # Register all discovered commands
    _register_commands(app, config, verbose)
```

### 2. Dynamic Command Loading

**Load commands on demand (lazy loading):**

```python
@dataclass
class CommandMetadata:
    name: str
    module_path: str  # NEW: Module path for lazy loading
    function_name: str  # NEW: Function name
    # ... other fields

    _loaded_function: Optional[Callable] = field(default=None, init=False)

    @property
    def function(self) -> Callable:
        """Lazy-load the command function."""
        if self._loaded_function is None:
            module = importlib.import_module(self.module_path)
            self._loaded_function = getattr(module, self.function_name)
        return self._loaded_function
```

**Benefits:**
- Faster startup time (only load commands when used)
- Lower memory footprint
- Useful for large plugin ecosystems

### 3. Plugin Metadata and Help

**Enhanced command discovery with metadata:**

```python
@cli_command(
    name="plot-its",
    group="plotting",
    description="Generate ITS overlay plots",
    metadata={
        "author": "Lab Team",
        "version": "2.0",
        "requires": ["polars", "matplotlib"],
        "experimental": False,
    }
)
def plot_its_command(...):
    pass
```

**List available plugins:**

```bash
# Add utility command
@cli_command(name="list-plugins", group="utilities")
def list_plugins_command(
    group: Optional[str] = typer.Option(None, "--group", "-g"),
):
    """List all available command plugins."""
    from src.cli.plugin_system import list_available_commands, get_command_groups
    from rich.table import Table

    console = Console()

    if group:
        commands = list_available_commands(group)
    else:
        commands = list_available_commands()

    table = Table(title="Available Command Plugins")
    table.add_column("Command", style="cyan")
    table.add_column("Group", style="yellow")
    table.add_column("Description", style="white")

    for cmd in commands:
        table.add_row(cmd.name, cmd.group, cmd.description)

    console.print(table)
    console.print(f"\nTotal: {len(commands)} commands")
    console.print(f"Groups: {', '.join(get_command_groups())}")
```

### 4. Plugin Hooks and Events

**Add lifecycle hooks:**

```python
from typing import Protocol

class CommandPlugin(Protocol):
    """Protocol for command plugins with lifecycle hooks."""

    def on_register(self) -> None:
        """Called when command is registered."""
        pass

    def on_before_execute(self, context: dict) -> None:
        """Called before command execution."""
        pass

    def on_after_execute(self, context: dict, result: Any) -> None:
        """Called after command execution."""
        pass

    def on_error(self, error: Exception) -> None:
        """Called when command raises an error."""
        pass
```

**Usage:**

```python
@cli_command(name="my-command", group="custom")
class MyCommandPlugin:
    """Command as a class with hooks."""

    def on_register(self):
        console.print("[dim]Registering my-command plugin[/dim]")

    def __call__(self, arg: int):
        """Main command implementation."""
        self.on_before_execute({"arg": arg})
        result = self._do_work(arg)
        self.on_after_execute({"arg": arg}, result)
        return result

    def _do_work(self, arg: int):
        return arg * 2
```

---

## Examples

### Example 1: Creating a New Plugin Command

**Goal**: Add a new `export-data` command without modifying `main.py`.

**1. Create command module:**

```python
# src/cli/commands/export.py
"""Data export commands."""

import typer
from pathlib import Path
from rich.console import Console
from src.cli.plugin_system import cli_command

console = Console()


@cli_command(
    name="export-csv",
    group="export",
    description="Export chip history to CSV",
    aliases=["export"],
)
def export_csv_command(
    chip_number: int = typer.Argument(..., help="Chip number"),
    output: Path = typer.Option(Path("export.csv"), "--output", "-o"),
    chip_group: str = typer.Option("Alisson", "--group", "-g"),
):
    """
    Export chip history to CSV format.

    Examples:
        python process_and_analyze.py export-csv 67
        python process_and_analyze.py export-csv 67 -o results/chip67.csv
    """
    console.print(f"[cyan]Exporting chip {chip_group}{chip_number}...[/cyan]")

    # Implementation
    # ...

    console.print(f"[green]✓ Exported to {output}[/green]")
```

**2. Test the new command:**

```bash
# No changes to main.py needed!
python process_and_analyze.py export-csv 67
python process_and_analyze.py export --help  # Alias works too
```

### Example 2: Disabling Experimental Features

**config/cli_plugins.yaml:**

```yaml
enabled_groups:
  - all

disabled_commands:
  - plot-its-sequential  # Not ready for production
  - experimental-analysis  # Beta feature
```

### Example 3: Development vs Production Configurations

**config/cli_plugins_dev.yaml:**

```yaml
# Development configuration
enabled_groups:
  - all

disabled_commands: []  # Everything enabled for testing

settings:
  allow_third_party: true
  third_party_dirs:
    - ./dev_plugins  # Local development plugins
```

**config/cli_plugins.yaml:**

```yaml
# Production configuration
enabled_groups:
  - pipeline
  - history
  - staging
  - plotting

disabled_commands:
  - experimental-analysis
  - dev-test-command

settings:
  allow_third_party: false
```

**Switch configurations:**

```bash
# Development
export PLUGIN_CONFIG=config/cli_plugins_dev.yaml
python process_and_analyze.py --help

# Production (default)
python process_and_analyze.py --help
```

### Example 4: Creating a Third-Party Plugin Package

**Structure:**

```
optothermal-custom-analysis/
├── setup.py
├── README.md
└── optothermal_custom_analysis/
    ├── __init__.py
    └── commands.py
```

**setup.py:**

```python
from setuptools import setup, find_packages

setup(
    name="optothermal-custom-analysis",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "optothermal-processing",  # Main package
    ],
    entry_points={
        "optothermal.plugins": [
            "custom_analysis = optothermal_custom_analysis.commands",
        ],
    },
)
```

**commands.py:**

```python
from src.cli.plugin_system import cli_command
from rich.console import Console

console = Console()

@cli_command(
    name="custom-fft-analysis",
    group="custom",
    description="FFT analysis of photoresponse"
)
def fft_analysis_command(chip_number: int, ...):
    """Perform FFT analysis on ITS data."""
    # Custom implementation
    pass
```

**Installation:**

```bash
pip install optothermal-custom-analysis

# Enable in config
echo "allow_third_party: true" >> config/cli_plugins.yaml

# Use the command
python process_and_analyze.py custom-fft-analysis 67
```

---

## Benefits Summary

### Developer Benefits

1. **No main.py changes**: Add commands without touching central registry
2. **Modular development**: Work on command modules independently
3. **Easy testing**: Test commands in isolation
4. **Clean separation**: Commands don't know about each other
5. **Extensibility**: Third-party plugins without forking

### User Benefits

1. **Customization**: Enable only needed command groups
2. **Performance**: Lazy loading reduces startup time
3. **Stability**: Disable buggy commands without reinstalling
4. **Extensions**: Install community plugins easily

### Deployment Benefits

1. **Configuration-driven**: Different configs for dev/staging/prod
2. **Feature flags**: Enable/disable features via config
3. **Versioning**: Track command versions independently
4. **Documentation**: Auto-generate command lists from metadata

---

## Migration Checklist

- [ ] Create `src/cli/plugin_system.py` with plugin infrastructure
- [ ] Create `config/cli_plugins.yaml` with default configuration
- [ ] Update `src/cli/main.py` to use `discover_commands()`
- [ ] Add `@cli_command` decorators to all command functions
- [ ] Remove manual imports from `main.py`
- [ ] Remove manual registrations from `main.py`
- [ ] Test all commands work with plugin system
- [ ] Add `list-plugins` utility command
- [ ] Update documentation with plugin development guide
- [ ] Create example third-party plugin
- [ ] Test configuration options (enable/disable groups)
- [ ] Add plugin system to project README

---

## Conclusion

The Plugin System transforms the CLI from a monolithic, manually-registered command set into a **flexible, modular, and extensible** architecture. Key improvements:

- **From 40+ lines** of manual registration to **10 lines** of auto-discovery
- **Zero main.py changes** when adding new commands
- **Configuration-driven** command availability
- **Third-party extension** support
- **Better organization** with command groups
- **Backward compatible** - existing commands work with minimal changes

This architecture scales better as the command set grows and enables a plugin ecosystem for custom analysis tools.
