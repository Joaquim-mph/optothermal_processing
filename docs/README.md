# Documentation Index

**Last Updated:** October 31, 2025
**Project Version:** 3.0+

Welcome to the optothermal processing pipeline documentation. This index organizes all documentation by topic for easy navigation.

---

## 🚀 Getting Started

Start here if you're new to the project:

- **[../CLAUDE.md](../CLAUDE.md)** - Complete project overview, commands, and architecture (for AI assistants and developers)
- **[../README.md](../README.md)** - Quick start guide, features, and basic usage
- **[DERIVED_METRICS_QUICKSTART.md](DERIVED_METRICS_QUICKSTART.md)** - Quick start for the derived metrics pipeline (v3.0)

---

## 📚 Core Documentation

### CLI & Architecture

Understand the command-line interface and overall system design:

- **[CLI_MODULE_ARCHITECTURE.md](CLI_MODULE_ARCHITECTURE.md)** (40KB) - Complete CLI architecture, module organization, and design patterns
- **[CLI_PLUGIN_SYSTEM.md](CLI_PLUGIN_SYSTEM.md)** (NEW) - Plugin system guide: auto-discovery, decorators, and configuration
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration management: files, environment variables, and precedence

### Data Models & Validation

Core data structures and validation:

- **[PYDANTIC_ARCHITECTURE.md](PYDANTIC_ARCHITECTURE.md)** (36KB) - Data models, validation schemas, and Pydantic usage
- **[SCHEMA_VALIDATION_GUIDE.md](SCHEMA_VALIDATION_GUIDE.md)** - CSV validation, schema evolution, and error handling
- **[YAML_DRIVEN_MANIFEST.md](YAML_DRIVEN_MANIFEST.md)** - Dynamic manifest generation from YAML schemas

---

## 🔬 Data Processing

### Staging & Pipeline

Processing raw data into the pipeline:

- **[STAGING_GUIDE.md](STAGING_GUIDE.md)** - Staging raw CSVs to Parquet, validation, and parallel processing
- **[ADDING_PROCEDURES.md](ADDING_PROCEDURES.md)** - Adding new measurement procedure types to the pipeline
- **[PROCEDURES.md](PROCEDURES.md)** - Upstream PyMeasure measurement procedures (from lab equipment)

**Note:** PROCEDURES.md documents the upstream measurement system (PyMeasure). For data processing procedure schemas, see `config/procedures.yml` and SCHEMA_VALIDATION_GUIDE.md.

### Datetime Handling

- **[DATETIME_LOCAL_USAGE.md](DATETIME_LOCAL_USAGE.md)** - Timezone handling, UTC storage, and local time display

---

## 📊 Derived Metrics (v3.0)

**New in version 3.0:** Automated extraction of analytical metrics

### Quick Start & Overview

- **[DERIVED_METRICS_QUICKSTART.md](DERIVED_METRICS_QUICKSTART.md)** ⭐ - **START HERE** for derived metrics
- **[DERIVED_METRICS_ARCHITECTURE.md](DERIVED_METRICS_ARCHITECTURE.md)** (24KB) - Complete architecture, data flow, and design patterns

### Implementation Guides

- **[ADDING_NEW_METRICS_GUIDE.md](ADDING_NEW_METRICS_GUIDE.md)** (16KB) - Step-by-step guide to creating custom metric extractors
- **[CNP_EXTRACTOR_GUIDE.md](CNP_EXTRACTOR_GUIDE.md)** - CNP (Charge Neutrality Point) extractor implementation details

### Available Metrics

The pipeline currently extracts:

- **CNP (Charge Neutrality Point)** - Dirac point voltage and resistance from IVg/VVg
- **Photoresponse** - Light-induced current/voltage changes (ΔI, ΔV) from It/Vt/ITt
- **Laser Power** - Irradiated power from calibration curve interpolation

---

## 📈 Plotting & Visualization

Creating publication-quality plots:

- **[PLOTTING_IMPLEMENTATION_GUIDE.md](PLOTTING_IMPLEMENTATION_GUIDE.md)** (37KB) - **Comprehensive guide** with templates for all procedure types
  - ITS (current vs time)
  - IVg (current vs gate voltage)
  - VVg (voltage vs gate voltage)
  - Vt (voltage vs time)
  - Transconductance (dI/dVg)
  - CNP evolution
  - Photoresponse analysis
  - Laser calibration curves

---

## 🖥️ Terminal UI

User-friendly terminal interface for lab users:

- **[TUI_OVERVIEW.md](TUI_OVERVIEW.md)** - Terminal UI overview, screens, and configuration manager

---

## 🔧 Upstream Systems

External system documentation:

- **[UPSTREAM_MEASUREMENT_SYSTEM.md](UPSTREAM_MEASUREMENT_SYSTEM.md)** - PyMeasure-based measurement system that generates raw CSV files

---

## 📖 Documentation by Topic

### For New Developers

**Read these in order:**

1. [../README.md](../README.md) - Project overview
2. [CONFIGURATION.md](CONFIGURATION.md) - Set up your environment
3. [CLI_PLUGIN_SYSTEM.md](CLI_PLUGIN_SYSTEM.md) - Understand command structure
4. [PLOTTING_IMPLEMENTATION_GUIDE.md](PLOTTING_IMPLEMENTATION_GUIDE.md) - Create your first command

### For Data Scientists

**Focus on these:**

1. [DERIVED_METRICS_QUICKSTART.md](DERIVED_METRICS_QUICKSTART.md) - Extract analytical metrics
2. [ADDING_NEW_METRICS_GUIDE.md](ADDING_NEW_METRICS_GUIDE.md) - Create custom extractors
3. [PLOTTING_IMPLEMENTATION_GUIDE.md](PLOTTING_IMPLEMENTATION_GUIDE.md) - Visualize results

### For Lab Users

**Use these:**

1. [../README.md](../README.md) - Basic usage
2. [TUI_OVERVIEW.md](TUI_OVERVIEW.md) - Terminal UI guide
3. [CONFIGURATION.md](CONFIGURATION.md) - Customize paths and settings

### For System Architects

**Deep dives:**

1. [CLI_MODULE_ARCHITECTURE.md](CLI_MODULE_ARCHITECTURE.md) - CLI design
2. [PYDANTIC_ARCHITECTURE.md](PYDANTIC_ARCHITECTURE.md) - Data models
3. [DERIVED_METRICS_ARCHITECTURE.md](DERIVED_METRICS_ARCHITECTURE.md) - Metrics pipeline
4. [SCHEMA_VALIDATION_GUIDE.md](SCHEMA_VALIDATION_GUIDE.md) - Validation system

---

## 📝 Quick Reference

### Adding New Features

| Feature Type | Documentation |
|--------------|---------------|
| **CLI Command** | [CLI_PLUGIN_SYSTEM.md](CLI_PLUGIN_SYSTEM.md) |
| **Plotting Function** | [PLOTTING_IMPLEMENTATION_GUIDE.md](PLOTTING_IMPLEMENTATION_GUIDE.md) |
| **Metric Extractor** | [ADDING_NEW_METRICS_GUIDE.md](ADDING_NEW_METRICS_GUIDE.md) |
| **Procedure Type** | [ADDING_PROCEDURES.md](ADDING_PROCEDURES.md) |
| **Data Model** | [PYDANTIC_ARCHITECTURE.md](PYDANTIC_ARCHITECTURE.md) |

### Common Tasks

| Task | Command | Documentation |
|------|---------|---------------|
| Stage raw data | `python process_and_analyze.py full-pipeline` | [STAGING_GUIDE.md](STAGING_GUIDE.md) |
| Extract metrics | `python process_and_analyze.py derive-all-metrics` | [DERIVED_METRICS_QUICKSTART.md](DERIVED_METRICS_QUICKSTART.md) |
| Generate plots | `python process_and_analyze.py plot-its 67 --auto` | [PLOTTING_IMPLEMENTATION_GUIDE.md](PLOTTING_IMPLEMENTATION_GUIDE.md) |
| Configure CLI | `python process_and_analyze.py config-init` | [CONFIGURATION.md](CONFIGURATION.md) |
| List commands | `python process_and_analyze.py list-plugins` | [CLI_PLUGIN_SYSTEM.md](CLI_PLUGIN_SYSTEM.md) |

---

## 🆕 What's New in v3.0

### Major Features

✅ **Derived Metrics Pipeline**
- Automated CNP, photoresponse, and laser power extraction
- Plugin-based extractor architecture
- Enriched chip histories with metrics as columns

✅ **Plugin System**
- Auto-discovery of CLI commands
- Configuration-driven command enabling/disabling
- No `main.py` changes needed to add commands

✅ **New Plotting Commands**
- `plot-cnp-time` - CNP evolution over time
- `plot-photoresponse` - Photoresponse vs power/wavelength/gate/time
- `plot-vvg` - Drain-source voltage vs gate voltage
- `plot-vt` - Voltage vs time

✅ **Enhanced Configuration**
- Persistent CLI configuration
- Environment variable support
- Profile-based initialization

### New Documentation

- **CLI_PLUGIN_SYSTEM.md** - Complete plugin system guide
- **DERIVED_METRICS_ARCHITECTURE.md** - Metrics pipeline architecture
- **DERIVED_METRICS_QUICKSTART.md** - Quick start for metrics
- **ADDING_NEW_METRICS_GUIDE.md** - Step-by-step extractor guide
- **CNP_EXTRACTOR_GUIDE.md** - CNP implementation details

---

## 📊 Documentation Statistics

| Category | Files | Total Size |
|----------|-------|------------|
| Core Architecture | 3 | ~95KB |
| Data Processing | 5 | ~56KB |
| Derived Metrics | 4 | ~56KB |
| Plotting | 1 | 37KB |
| Other | 4 | ~25KB |
| **Total** | **17** | **~269KB** |

---

## 🔗 External Resources

- **GitHub Repository:** [github.com/your-org/optothermal-processing](https://github.com/your-org/optothermal-processing)
- **Issue Tracker:** Report bugs and request features
- **Main README:** [../README.md](../README.md)
- **Project Instructions for AI:** [../CLAUDE.md](../CLAUDE.md)

---

## 💡 Tips for Using Documentation

### Search Tips

```bash
# Find all references to a topic
grep -r "plugin system" docs/

# List all documentation files
ls -lh docs/*.md

# Find documentation by size
ls -lhS docs/*.md | head -5
```

### Documentation Conventions

- **Code blocks** are syntax-highlighted and ready to copy-paste
- **File sizes** indicate depth of coverage
- **⭐ markers** indicate recommended starting points
- **"NEW" labels** indicate v3.0 additions
- **Cross-references** use relative links for easy navigation

### Contributing to Documentation

When adding new documentation:

1. Add entry to this README.md index
2. Include "Last Updated" date at the top
3. Use clear section headers with anchors
4. Provide code examples where applicable
5. Cross-reference related documentation

---

**Questions or suggestions?** Open an issue or contribute improvements via pull request!
