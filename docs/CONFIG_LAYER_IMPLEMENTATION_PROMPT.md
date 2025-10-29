# Implementation Prompt: Configuration Management Layer for CLI Module

## Objective
Implement a centralized Configuration Management Layer for the optothermal processing pipeline CLI to replace scattered hardcoded paths and settings with a flexible, validated, environment-aware configuration system.

## Context
The CLI module (located in `src/cli/`) currently has hardcoded paths and settings scattered across multiple command files. This implementation will create a centralized configuration system using Pydantic for validation and support for environment variables and config files.

## Files to Create

### 1. `src/cli/config.py`
Create a new configuration module with the following specifications:

**Requirements:**
- Use Pydantic BaseModel for validation and type safety
- Support three configuration sources (in priority order):
  1. Command-line overrides
  2. Config file (`~/.optothermal_cli_config.json` or project-specific)
  3. Environment variables (with `CLI_` prefix)
  4. Hardcoded defaults

**Configuration Fields:**
```python
# Directory paths
- raw_data_dir: Path = "data/01_raw"
- stage_dir: Path = "data/02_stage"  
- history_dir: Path = "data/02_stage/chip_histories"
- output_dir: Path = "figs"

# Behavior settings
- verbose: bool = False
- dry_run: bool = False

# Processing settings
- parallel_workers: int = 4 (range: 1-16)
- cache_enabled: bool = True
- cache_ttl: int = 300  # seconds

# Plot defaults
- default_plot_format: str = "png" (choices: png, pdf, svg, jpg)
- plot_dpi: int = 300 (range: 72-600)
```

**Required Methods:**
- `from_env()`: Load from environment variables
- `from_file(config_file: Path)`: Load from JSON config file
- `save(config_file: Path)`: Save current config to JSON file
- Validators for:
  - Path fields (auto-create if missing)
  - plot_format (validate against allowed formats)
  - integer ranges (parallel_workers, plot_dpi)

**Implementation Details:**
- Use Pydantic's `Field()` for field metadata
- Use `@validator` decorators for validation
- Support both absolute and relative paths
- Auto-resolve relative paths to absolute
- Create directories if they don't exist during validation

### 2. `src/cli/commands/config.py`
Create configuration management commands:

**Commands to Implement:**

**a) `show-config` Command**
- Display current configuration in a Rich table
- Show source of each setting (default/env/file/override)
- Color-code: green for set values, dim for defaults
- Include path validation status (exists/will be created)

**b) `init-config` Command**
- Generate a config file with current defaults
- Options:
  - `--output / -o`: Config file location (default: `~/.optothermal_cli_config.json`)
  - `--force / -f`: Overwrite if exists
- Pretty-print JSON with comments explaining each field
- Display success message with edit instructions

**c) `validate-config` Command**
- Validate current configuration
- Check all paths are accessible
- Verify integer ranges
- Test write permissions for output directories
- Display validation report with checkmarks/warnings

**d) `reset-config` Command**
- Reset to default configuration
- Options:
  - `--confirm`: Skip confirmation prompt
- Backup existing config before reset

### 3. Update `src/cli/main.py`

**Add Global Config Management:**
```python
# Singleton config instance
_config: Optional[CLIConfig] = None

def get_config() -> CLIConfig:
    """Get or create global config instance"""
    # Priority: 1. Project config, 2. User config, 3. Env vars, 4. Defaults
    # Cache and return
    
def set_config(config: CLIConfig):
    """Set global config instance (for testing/overrides)"""
```

**Add Global Options to app.callback():**
```python
@app.callback()
def global_options(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """Global options applied to all commands"""
```

**Register new config commands:**
```python
from src.cli.commands.config import (
    show_config_command,
    init_config_command,
    validate_config_command,
    reset_config_command
)

app.command(name="config-show")(show_config_command)
app.command(name="config-init")(init_config_command)
app.command(name="config-validate")(validate_config_command)
app.command(name="config-reset")(reset_config_command)
```

## Files to Modify

### 4. Update Command Files to Use Config

**Files to modify:**
- `src/cli/commands/data_pipeline.py`
- `src/cli/commands/history.py`
- `src/cli/commands/stage.py`
- `src/cli/commands/plot_its.py`
- `src/cli/commands/plot_ivg.py`
- `src/cli/commands/plot_transconductance.py`
- `src/cli/helpers.py`

**Pattern for Updates:**

**Before:**
```python
def some_command(...):
    history_dir = Path("data/02_stage/chip_histories")  # Hardcoded
    output_dir = Path("figs")  # Hardcoded
```

**After:**
```python
from src.cli.main import get_config

def some_command(...):
    config = get_config()
    history_dir = config.history_dir
    output_dir = config.output_dir
    
    if config.verbose:
        console.print(f"[dim]Using history dir: {history_dir}[/dim]")
```

**Specific changes needed:**

1. **Replace all hardcoded paths** with `config.<field_name>`
2. **Add verbose logging** when `config.verbose` is True:
   - Show file paths being used
   - Show configuration values
   - Show validation steps
3. **Support dry-run mode** when `config.dry_run` is True:
   - Show what would happen
   - Skip actual file operations
   - Display preview of outputs

### 5. Update `src/cli/helpers.py`

**Functions to update:**

**a) `setup_output_dir()`**
```python
def setup_output_dir(chip: int, chip_group: str) -> Path:
    """Create chip-specific output subdirectories using config"""
    config = get_config()
    output_dir = config.output_dir / f"{chip_group}{chip}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
```

**b) `auto_select_experiments()`**
```python
def auto_select_experiments(chip, proc, chip_group, filters=None):
    """Auto-select experiments using config for history_dir"""
    config = get_config()
    history_file = config.history_dir / f"{chip_group}{chip}_history.parquet"
    # ... rest of logic
```

**c) Add new helper:**
```python
def get_verbose_console() -> Console:
    """Get console with verbosity from config"""
    config = get_config()
    return Console(quiet=not config.verbose)
```

## Testing Requirements

### 6. Create `tests/test_config.py`

**Test Cases to Implement:**

**a) Configuration Creation:**
- Test default configuration creation
- Test loading from environment variables
- Test loading from file
- Test validation of all fields

**b) Path Validation:**
- Test absolute path handling
- Test relative path resolution
- Test auto-creation of missing directories
- Test invalid path handling

**c) Field Validation:**
- Test plot_format validation (valid/invalid)
- Test integer range validation (parallel_workers, plot_dpi)
- Test boolean fields

**d) Configuration Precedence:**
- Test file overrides defaults
- Test environment overrides file
- Test command-line overrides environment

**e) Serialization:**
- Test save/load round-trip
- Test JSON format
- Test handling of Path objects

**f) Integration:**
- Test `get_config()` singleton behavior
- Test config usage in commands

## Additional Features (Optional but Recommended)

### 7. Configuration Profiles

Add support for named configuration profiles:

```python
# src/cli/config.py
class ConfigProfile:
    """Predefined configuration profiles"""
    
    @staticmethod
    def development() -> CLIConfig:
        """Development profile with verbose output"""
        return CLIConfig(verbose=True, dry_run=True, ...)
    
    @staticmethod
    def production() -> CLIConfig:
        """Production profile optimized for batch processing"""
        return CLIConfig(parallel_workers=8, cache_enabled=True, ...)
    
    @staticmethod
    def testing() -> CLIConfig:
        """Testing profile with temporary directories"""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        return CLIConfig(output_dir=tmp, stage_dir=tmp, ...)
```

Command:
```bash
python process_and_analyze.py --profile development plot-its 67
```

### 8. Configuration Migration

Add migration support for upgrading config files:

```python
def migrate_config(old_config: dict, version: str) -> CLIConfig:
    """Migrate old config format to new format"""
    # Handle renamed fields
    # Handle removed fields
    # Add new fields with defaults
```

### 9. Environment Detection

Auto-detect environment and apply appropriate defaults:

```python
def detect_environment() -> str:
    """Detect if running in CI/CD, Docker, etc."""
    if os.getenv("CI"):
        return "ci"
    if os.path.exists("/.dockerenv"):
        return "docker"
    return "local"
```

## Documentation Requirements

### 10. Update `CLI_MODULE_ARCHITECTURE.md`

Add a new section **"Configuration Management"** with:

1. **Overview**: What the config system provides
2. **Configuration Sources**: Priority order and examples
3. **Available Settings**: Table of all config fields
4. **Usage Examples**:
   - Using defaults
   - Environment variables
   - Config files
   - Command-line overrides
   - Per-project configs
5. **Command Reference**: All config-* commands
6. **Migration Guide**: How to migrate existing scripts

### 11. Create `docs/CONFIGURATION.md`

Comprehensive configuration guide including:
- Quick start
- Full field reference
- Environment variable reference
- Example config files for different scenarios
- Troubleshooting guide

## Implementation Steps (Suggested Order)

1. ✅ Create `src/cli/config.py` with all validation
2. ✅ Create `tests/test_config.py` and verify config works standalone
3. ✅ Create `src/cli/commands/config.py` with all commands
4. ✅ Update `src/cli/main.py` with global config and callback
5. ✅ Test config commands work (`config-show`, `config-init`, etc.)
6. ✅ Update `src/cli/helpers.py` to use config
7. ✅ Update one command file as reference (e.g., `plot_its.py`)
8. ✅ Test the updated command thoroughly
9. ✅ Update remaining command files following the pattern
10. ✅ Run full integration tests
11. ✅ Update documentation
12. ✅ Create migration guide for existing users

## Success Criteria

The implementation is complete when:

1. ✅ All commands use `get_config()` instead of hardcoded paths
2. ✅ Configuration can be loaded from all three sources (file/env/defaults)
3. ✅ All config commands work (`show`, `init`, `validate`, `reset`)
4. ✅ Path validation auto-creates missing directories
5. ✅ Global `--verbose` and `--dry-run` flags work across all commands
6. ✅ Tests pass with 90%+ coverage of config module
7. ✅ Documentation is updated with examples
8. ✅ Existing CLI functionality is preserved (no breaking changes to command signatures)

## Example Usage After Implementation

```bash
# View current config
python process_and_analyze.py config-show

# Initialize config file
python process_and_analyze.py config-init

# Edit config file at ~/.optothermal_cli_config.json
# Then all commands use it automatically

# Override for single command
python process_and_analyze.py --output-dir /tmp/test plot-its 67 --auto

# Use project-specific config
cd my_project
python process_and_analyze.py --config my_config.json full-pipeline 67

# Use environment variables
export CLI_VERBOSE=true
export CLI_OUTPUT_DIR=/data/plots
python process_and_analyze.py plot-its 67 --auto

# Validate configuration
python process_and_analyze.py config-validate
```

## Notes and Considerations

1. **Backward Compatibility**: Ensure existing scripts that don't use config still work
2. **Performance**: Config should be loaded once and cached (singleton pattern)
3. **Error Messages**: Provide helpful messages when config is invalid
4. **Type Safety**: Use Pydantic for runtime validation and IDE support
5. **Testing**: Use temporary directories for tests to avoid affecting user config
6. **Documentation**: Include examples for common use cases

## Dependencies

Ensure these are in `requirements.txt`:
- `pydantic>=2.0.0` (for config validation)
- `typer` (already present)
- `rich` (already present)

## Questions to Consider During Implementation

1. Should config file support YAML in addition to JSON?
2. Should there be per-chip configuration overrides?
3. Should config include logging configuration?
4. Should config validation warn vs error for missing directories?
5. Should there be a `--no-config` flag to ignore all config files?

---

## Implementation Checklist

Use this checklist to track progress:

- [ ] Create `src/cli/config.py` with CLIConfig class
- [ ] Add all validators (paths, formats, ranges)
- [ ] Implement `from_env()`, `from_file()`, `save()` methods
- [ ] Create `tests/test_config.py` with comprehensive tests
- [ ] Create `src/cli/commands/config.py` with all commands
- [ ] Update `src/cli/main.py` with global config management
- [ ] Add global options callback (`--verbose`, `--config`, etc.)
- [ ] Register config commands in main.py
- [ ] Update `src/cli/helpers.py` to use config
- [ ] Update `src/cli/commands/plot_its.py` (reference implementation)
- [ ] Update `src/cli/commands/plot_ivg.py`
- [ ] Update `src/cli/commands/plot_transconductance.py`
- [ ] Update `src/cli/commands/data_pipeline.py`
- [ ] Update `src/cli/commands/history.py`
- [ ] Update `src/cli/commands/stage.py`
- [ ] Run integration tests on all commands
- [ ] Add "Configuration Management" section to `CLI_MODULE_ARCHITECTURE.md`
- [ ] Create `docs/CONFIGURATION.md` guide
- [ ] Create example config files for common scenarios
- [ ] Test with environment variables
- [ ] Test with config file
- [ ] Test with command-line overrides
- [ ] Test configuration precedence
- [ ] Verify no breaking changes to existing command usage
- [ ] Update README with configuration quick start

---

**Start with creating the config.py file and its tests, then progressively update the rest of the codebase. This ensures a solid foundation before integration.**
