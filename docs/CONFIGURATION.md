# Configuration Guide

Complete guide to configuring the optothermal processing pipeline CLI.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration Sources](#configuration-sources)
3. [Configuration Fields Reference](#configuration-fields-reference)
4. [Configuration Commands](#configuration-commands)
5. [Usage Examples](#usage-examples)
6. [Configuration Profiles](#configuration-profiles)
7. [Environment Variables](#environment-variables)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### View Current Configuration

```bash
# Display all settings with their sources
python process_and_analyze.py config-show
```

### Initialize Configuration File

```bash
# Create config in home directory (~/.optothermal_cli_config.json)
python process_and_analyze.py config-init

# Create config with a specific profile
python process_and_analyze.py config-init --profile production

# Create project-specific config
python process_and_analyze.py config-init --output ./.optothermal_cli_config.json
```

### Validate Configuration

```bash
# Check configuration for errors
python process_and_analyze.py config-validate

# Validate and auto-fix issues
python process_and_analyze.py config-validate --fix
```

---

## Configuration Sources

The CLI supports multiple configuration sources with a clear precedence order.

### Precedence (Highest to Lowest)

1. **Command-line overrides** - Explicit flags override everything
2. **Specified config file** - Via `--config` flag
3. **Project config** - `./.optothermal_cli_config.json` in current directory
4. **User config** - `~/.optothermal_cli_config.json` in home directory
5. **Environment variables** - `CLI_*` prefixed variables
6. **Defaults** - Built-in sensible defaults

### Example Priority Resolution

```bash
# 1. Default: output_dir = "figs"

# 2. Environment variable overrides default
export CLI_OUTPUT_DIR="/data/plots"
# Now: output_dir = "/data/plots"

# 3. User config overrides environment
echo '{"output_dir": "/home/user/plots"}' > ~/.optothermal_cli_config.json
# Now: output_dir = "/home/user/plots"

# 4. Command-line overrides everything
python process_and_analyze.py --output-dir /tmp/test plot-its 67 --auto
# Now: output_dir = "/tmp/test"
```

---

## Configuration Fields Reference

### Directory Paths

All paths support both absolute and relative paths. Relative paths are resolved to absolute paths automatically.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `raw_data_dir` | Path | `data/01_raw` | Directory containing raw CSV measurement files |
| `stage_dir` | Path | `data/02_stage` | Directory for staged Parquet files and manifest |
| `history_dir` | Path | `data/02_stage/chip_histories` | Directory for chip history Parquet files |
| `output_dir` | Path | `figs` | Directory for generated plots and outputs |

**Features:**
- Auto-creates missing directories during validation
- Resolves relative paths to absolute paths
- Validates write permissions for output directories

### Behavior Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `verbose` | bool | `false` | Enable detailed logging output |
| `dry_run` | bool | `false` | Preview mode - show what would happen without executing |

**Usage:**
```bash
# Enable verbose globally
python process_and_analyze.py --verbose plot-its 67 --auto

# Dry-run mode to preview pipeline
python process_and_analyze.py --dry-run full-pipeline
```

### Processing Settings

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `parallel_workers` | int | `4` | 1-16 | Number of parallel worker processes for staging |
| `cache_enabled` | bool | `true` | - | Enable caching for faster repeated operations |
| `cache_ttl` | int | `300` | ≥0 | Cache time-to-live in seconds |

**Recommendations:**
- **parallel_workers**: Set to number of CPU cores for best performance
- **cache_enabled**: Disable for testing to ensure fresh data
- **cache_ttl**: Increase for stable datasets, decrease for actively changing data

### Plot Settings

| Field | Type | Default | Choices/Range | Description |
|-------|------|---------|---------------|-------------|
| `default_plot_format` | str | `"png"` | png, pdf, svg, jpg | Default output format for plots |
| `plot_dpi` | int | `300` | 72-600 | DPI resolution for plot output |

**Usage:**
```json
{
  "default_plot_format": "pdf",
  "plot_dpi": 600
}
```

This creates high-quality PDF plots suitable for publications.

### Metadata

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `config_version` | str | `"1.0.0"` | Configuration schema version (managed automatically) |

---

## Configuration Commands

### config-show

Display the current configuration with sources and validation status.

**Usage:**
```bash
# Show all settings with sources
python process_and_analyze.py config-show

# Hide source information for cleaner output
python process_and_analyze.py config-show --no-sources
```

**Output:**
- **Value**: Current setting value
- **Type**: Data type (Path, bool, int, str, Literal)
- **Source**: Where the value came from (default, env, file, override)
- **Status**: For paths, shows if directory exists

### config-init

Create a new configuration file with defaults or a preset profile.

**Usage:**
```bash
# Create default config in home directory
python process_and_analyze.py config-init

# Create in specific location
python process_and_analyze.py config-init --output ./my_config.json

# Overwrite existing config
python process_and_analyze.py config-init --force

# Use a preset profile
python process_and_analyze.py config-init --profile development
python process_and_analyze.py config-init --profile production
python process_and_analyze.py config-init --profile testing
python process_and_analyze.py config-init --profile high_quality
```

**Profiles:**
- `development`: Verbose output, dry-run mode, fewer workers
- `production`: Optimized for batch processing, more workers
- `testing`: Temporary directories, verbose, single worker
- `high_quality`: PDF output at 600 DPI for publications

### config-validate

Validate the current configuration and check for issues.

**Usage:**
```bash
# Validate configuration
python process_and_analyze.py config-validate

# Validate and auto-fix issues (create missing directories, etc.)
python process_and_analyze.py config-validate --fix

# Validate specific config file
python process_and_analyze.py --config my_config.json config-validate
```

**Checks:**
- ✓ Path accessibility and write permissions
- ✓ Value ranges (workers, DPI, cache TTL)
- ✓ Format choices (plot format)
- ✓ Config file JSON validity
- ✓ Schema compliance

### config-reset

Reset configuration file to defaults with optional backup.

**Usage:**
```bash
# Reset with confirmation and backup
python process_and_analyze.py config-reset

# Skip confirmation
python process_and_analyze.py config-reset --yes

# Reset without creating backup
python process_and_analyze.py config-reset --yes --no-backup

# Reset specific config file
python process_and_analyze.py --config my_config.json config-reset
```

**Safety:**
- Creates `.json.backup` file by default
- Requires confirmation unless `--yes` is used
- Warns before overwriting

---

## Usage Examples

### Example 1: Personal Development Setup

Create a development-friendly configuration:

```bash
# Initialize development profile
python process_and_analyze.py config-init --profile development

# Edit config to customize
nano ~/.optothermal_cli_config.json
```

Edit to add custom paths:
```json
{
  "raw_data_dir": "/mnt/data/raw",
  "output_dir": "/home/user/plots",
  "verbose": true,
  "dry_run": false,
  "parallel_workers": 2
}
```

Now all commands use these settings automatically:
```bash
# Uses your config automatically
python process_and_analyze.py full-pipeline
python process_and_analyze.py plot-its 67 --auto
```

### Example 2: High-Performance Production

Configuration for batch processing:

```json
{
  "raw_data_dir": "/data/raw",
  "stage_dir": "/data/stage",
  "output_dir": "/data/plots",
  "verbose": false,
  "parallel_workers": 16,
  "cache_enabled": true,
  "cache_ttl": 3600,
  "default_plot_format": "png",
  "plot_dpi": 300
}
```

Run with production settings:
```bash
python process_and_analyze.py --config production.json full-pipeline
```

### Example 3: Publication-Quality Figures

Configuration for generating publication figures:

```bash
# Create high-quality profile
python process_and_analyze.py config-init --profile high_quality

# Edit to customize
nano ~/.optothermal_cli_config.json
```

```json
{
  "output_dir": "manuscript/figures",
  "default_plot_format": "pdf",
  "plot_dpi": 600,
  "verbose": true
}
```

Generate figures:
```bash
python process_and_analyze.py plot-its 67 --seq 52,57,58 --preset light_power_sweep
python process_and_analyze.py plot-ivg 67 --auto
```

### Example 4: Project-Specific Configuration

Different settings per project:

```bash
# Project A
cd /projects/experiment_A
python process_and_analyze.py config-init --output ./.optothermal_cli_config.json
# Edit with project A paths

# Project B
cd /projects/experiment_B
python process_and_analyze.py config-init --output ./.optothermal_cli_config.json
# Edit with project B paths

# Commands automatically use project-specific config
python process_and_analyze.py full-pipeline
```

### Example 5: Environment Variable Override

Use environment variables for CI/CD:

```bash
# In CI/CD script
export CLI_RAW_DATA_DIR=/ci/data/raw
export CLI_OUTPUT_DIR=/ci/artifacts
export CLI_PARALLEL_WORKERS=8
export CLI_VERBOSE=true

# Run pipeline (uses environment config)
python process_and_analyze.py full-pipeline
```

### Example 6: One-Off Override

Override config for a single command:

```bash
# Normal usage uses config defaults
python process_and_analyze.py plot-its 67 --auto

# One-time override for testing
python process_and_analyze.py --output-dir /tmp/test plot-its 67 --auto
```

---

## Configuration Profiles

### Development Profile

**Use Case:** Development, debugging, testing changes

```python
ConfigProfile.development()
```

**Settings:**
- `verbose`: `true` - See detailed output
- `dry_run`: `true` - Preview without execution
- `parallel_workers`: `2` - Easier to debug
- `cache_enabled`: `false` - Always use fresh data

**Usage:**
```bash
python process_and_analyze.py config-init --profile development
```

### Production Profile

**Use Case:** Batch processing, production data pipelines

```python
ConfigProfile.production()
```

**Settings:**
- `verbose`: `false` - Clean output
- `dry_run`: `false` - Actually execute
- `parallel_workers`: `8` - Maximum throughput
- `cache_enabled`: `true` - Faster reruns
- `cache_ttl`: `600` - 10-minute cache

**Usage:**
```bash
python process_and_analyze.py config-init --profile production
```

### Testing Profile

**Use Case:** Automated tests, temporary experiments

```python
ConfigProfile.testing()
```

**Settings:**
- Uses temporary directories (auto-cleaned)
- `verbose`: `true` - See test progress
- `parallel_workers`: `1` - Deterministic behavior
- `cache_enabled`: `false` - Isolated tests

**Usage:**
```python
# In test code
config = ConfigProfile.testing()
set_config(config)
```

### High Quality Profile

**Use Case:** Publication figures, presentations

```python
ConfigProfile.high_quality()
```

**Settings:**
- `default_plot_format`: `"pdf"` - Vector graphics
- `plot_dpi`: `600` - High resolution

**Usage:**
```bash
python process_and_analyze.py config-init --profile high_quality
```

---

## Environment Variables

All configuration fields can be set via environment variables with the `CLI_` prefix.

### Naming Convention

- Prefix: `CLI_`
- Field name: UPPERCASE with underscores
- Example: `raw_data_dir` → `CLI_RAW_DATA_DIR`

### Complete Reference

| Config Field | Environment Variable | Example Value |
|--------------|---------------------|---------------|
| `raw_data_dir` | `CLI_RAW_DATA_DIR` | `/data/raw` |
| `stage_dir` | `CLI_STAGE_DIR` | `/data/stage` |
| `history_dir` | `CLI_HISTORY_DIR` | `/data/histories` |
| `output_dir` | `CLI_OUTPUT_DIR` | `/data/plots` |
| `verbose` | `CLI_VERBOSE` | `true` or `false` |
| `dry_run` | `CLI_DRY_RUN` | `true` or `false` |
| `parallel_workers` | `CLI_PARALLEL_WORKERS` | `8` |
| `cache_enabled` | `CLI_CACHE_ENABLED` | `true` or `false` |
| `cache_ttl` | `CLI_CACHE_TTL` | `600` |
| `default_plot_format` | `CLI_DEFAULT_PLOT_FORMAT` | `pdf` |
| `plot_dpi` | `CLI_PLOT_DPI` | `300` |

### Boolean Values

Environment variables support multiple boolean representations:

**True values:** `true`, `1`, `yes`, `on`
**False values:** `false`, `0`, `no`, `off`, (empty string)

```bash
# All of these set verbose to True
export CLI_VERBOSE=true
export CLI_VERBOSE=1
export CLI_VERBOSE=yes
export CLI_VERBOSE=on
```

### Example: Docker Environment

```dockerfile
FROM python:3.11

# Set configuration via environment
ENV CLI_RAW_DATA_DIR=/data/raw
ENV CLI_STAGE_DIR=/data/stage
ENV CLI_OUTPUT_DIR=/data/plots
ENV CLI_PARALLEL_WORKERS=16
ENV CLI_VERBOSE=false

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

CMD ["python", "process_and_analyze.py", "full-pipeline"]
```

### Example: CI/CD Pipeline

```yaml
# .github/workflows/process.yml
jobs:
  process:
    runs-on: ubuntu-latest
    env:
      CLI_RAW_DATA_DIR: ${{ github.workspace }}/data/raw
      CLI_OUTPUT_DIR: ${{ github.workspace }}/output
      CLI_PARALLEL_WORKERS: 4
      CLI_VERBOSE: true
    steps:
      - uses: actions/checkout@v2
      - run: python process_and_analyze.py full-pipeline
```

---

## Troubleshooting

### Issue: Config file not being used

**Symptoms:** Changes to config file don't take effect

**Solutions:**

1. **Check file location**
   ```bash
   # User config should be here
   ls -la ~/.optothermal_cli_config.json

   # Project config should be here
   ls -la ./.optothermal_cli_config.json
   ```

2. **Verify config is valid JSON**
   ```bash
   python process_and_analyze.py config-validate
   ```

3. **Check for overrides**
   ```bash
   # Environment variables might be overriding
   env | grep CLI_

   # Check precedence with sources
   python process_and_analyze.py config-show
   ```

### Issue: Paths not found

**Symptoms:** "Directory not found" or "Permission denied" errors

**Solutions:**

1. **Check path exists**
   ```bash
   python process_and_analyze.py config-validate
   ```

2. **Auto-fix missing directories**
   ```bash
   python process_and_analyze.py config-validate --fix
   ```

3. **Check permissions**
   ```bash
   # Verify write access
   touch ~/.optothermal_cli_config.json
   ```

### Issue: Invalid configuration values

**Symptoms:** Validation errors when running commands

**Solutions:**

1. **Run validation**
   ```bash
   python process_and_analyze.py config-validate --details
   ```

2. **Check value ranges**
   - `parallel_workers`: Must be 1-16
   - `plot_dpi`: Must be 72-600
   - `default_plot_format`: Must be png, pdf, svg, or jpg
   - `cache_ttl`: Must be ≥ 0

3. **Reset to defaults**
   ```bash
   python process_and_analyze.py config-reset --yes
   ```

### Issue: Performance problems

**Symptoms:** Pipeline runs slower than expected

**Solutions:**

1. **Increase parallel workers**
   ```json
   {
     "parallel_workers": 16
   }
   ```

2. **Enable caching**
   ```json
   {
     "cache_enabled": true,
     "cache_ttl": 3600
   }
   ```

3. **Use production profile**
   ```bash
   python process_and_analyze.py config-init --profile production --force
   ```

### Issue: Environment variable not working

**Symptoms:** Environment variable seems to be ignored

**Solutions:**

1. **Check variable name format**
   ```bash
   # Correct
   export CLI_VERBOSE=true

   # Incorrect (no CLI_ prefix)
   export VERBOSE=true
   ```

2. **Verify export**
   ```bash
   echo $CLI_VERBOSE
   env | grep CLI_
   ```

3. **Check precedence**
   ```bash
   # Environment vars are overridden by config files
   # Use --config flag or remove config file
   python process_and_analyze.py config-show
   ```

### Issue: Want to temporarily ignore config

**Solution:** Use a minimal config file

```bash
# Create empty config (uses all defaults)
echo '{}' > /tmp/empty.json
python process_and_analyze.py --config /tmp/empty.json full-pipeline
```

### Getting Help

1. **View current effective configuration**
   ```bash
   python process_and_analyze.py config-show
   ```

2. **Validate configuration**
   ```bash
   python process_and_analyze.py config-validate --details
   ```

3. **Check command-specific help**
   ```bash
   python process_and_analyze.py <command> --help
   ```

4. **Reset to known-good state**
   ```bash
   python process_and_analyze.py config-reset --yes
   ```

---

## Best Practices

### 1. Use Config Files for Persistent Settings

Store common settings in config files rather than passing flags repeatedly:

```bash
# Instead of this
python process_and_analyze.py --output-dir /data/plots plot-its 67 --auto
python process_and_analyze.py --output-dir /data/plots plot-ivg 67 --auto

# Do this
echo '{"output_dir": "/data/plots"}' > ~/.optothermal_cli_config.json
python process_and_analyze.py plot-its 67 --auto
python process_and_analyze.py plot-ivg 67 --auto
```

### 2. Use Environment Variables in CI/CD

Environment variables are ideal for automated environments:

```bash
# CI/CD script
export CLI_OUTPUT_DIR=/ci/artifacts
export CLI_PARALLEL_WORKERS=8
python process_and_analyze.py full-pipeline
```

### 3. Use Project Configs for Multi-Project Workflows

Keep project-specific settings in project directories:

```bash
cd project_A
python process_and_analyze.py config-init --output ./.optothermal_cli_config.json
# Commands automatically use project_A config

cd ../project_B
python process_and_analyze.py config-init --output ./.optothermal_cli_config.json
# Commands automatically use project_B config
```

### 4. Version Control Config Templates

Commit config templates (not user configs):

```bash
# .gitignore
.optothermal_cli_config.json

# config.template.json (committed)
{
  "raw_data_dir": "data/01_raw",
  "stage_dir": "data/02_stage",
  "output_dir": "figs",
  "parallel_workers": 8
}
```

### 5. Validate Before Long-Running Operations

Always validate config before expensive operations:

```bash
python process_and_analyze.py config-validate
python process_and_analyze.py full-pipeline
```

### 6. Use Profiles as Starting Points

Start with a profile and customize:

```bash
python process_and_analyze.py config-init --profile production
nano ~/.optothermal_cli_config.json  # Customize as needed
```

---

## Additional Resources

- **CLI Architecture**: See `docs/CLI_MODULE_ARCHITECTURE.md` for implementation details
- **Command Reference**: Run `python process_and_analyze.py --help` for all commands
- **Source Code**: Configuration implementation in `src/cli/config.py`
- **Tests**: Comprehensive tests in `tests/test_config.py`
