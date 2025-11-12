# Pipeline Architecture Diagram - Implementation Summary

**Date:** November 8, 2025
**Status:** ✅ Complete
**Version:** 3.1

---

## Overview

Created comprehensive visual diagram of the entire optothermal processing pipeline using Graphviz, showing data flow, processing stages, and the integration of the new output formatters feature.

## Deliverables

### 1. Diagram Files (4 formats)

**Location:** `docs/`

- **`pipeline_architecture.png`** (657 KB) - Raster image for viewing
- **`pipeline_architecture.svg`** (66 KB) - Scalable vector for web/presentations
- **`pipeline_architecture.pdf`** (124 KB) - Print-ready document
- **`pipeline_architecture.dot`** (20 KB) - Graphviz source (editable)

### 2. Documentation Updates

**Updated Files:**

1. **`CLAUDE.md`** (+3 lines)
   - Added visual overview reference in Architecture section
   - Points to `docs/pipeline_architecture.png`

2. **`docs/OUTPUT_FORMATTERS_COMPLETE.md`** (+2 lines)
   - Added diagram reference in Technical Achievements section

3. **`docs/README.md`** (+60 lines)
   - Added new "Pipeline Architecture Diagram" section at top
   - Added "Output Formatters (v3.1)" section with examples
   - Updated "What's New in v3.1" section
   - Updated Documentation Statistics
   - Added to "Adding New Features" table
   - Added "Export data" to Common Tasks table
   - Updated version to 3.1

---

## Diagram Structure

### Visual Elements

**Color Scheme:**
- 🔵 **Blue** - Raw data (Stage 1)
- 🟢 **Green** - Staged data (Stage 2)
- 🟠 **Orange** - Derived metrics (Stage 3)
- 🟣 **Purple** - Processing steps
- 🔴 **Red** - Output formats and plots
- 🟡 **Yellow** - Configuration files
- 🟢 **Light Green** - External tools integration

**Shape Legend:**
- **Folders** - Data artifacts (Parquet files, histories)
- **Cylinders** - Key data files (manifest.parquet, metrics.parquet)
- **Rounded boxes** - CLI commands
- **Components** - Processing modules
- **Notes** - Output formats and configuration
- **Double octagon** - Unified pipeline command

### Diagram Sections

1. **Stage 1: Raw Data** (`data/01_raw/`)
   - CSV files from lab equipment
   - Structured headers with Parameters/Metadata/Data

2. **Processing: Staging Pipeline**
   - `stage-all` command
   - Schema validator (validates against procedures.yml)
   - Parallel processing (6 workers)

3. **Stage 2: Staged Data** (`data/02_stage/`)
   - Staged Parquet files organized by procedure
   - `manifest.parquet` (authoritative metadata)

4. **Processing: History Builder**
   - `build-all-histories` command
   - Groups manifest by chip, adds seq numbers

5. **Stage 2.5: Chip Histories** (`data/02_stage/chip_histories/`)
   - Per-chip Parquet histories
   - Includes `parquet_path` column

6. **Processing: Derived Metrics Pipeline**
   - `derive-all-metrics` command
   - Metric extractors (CNP, photoresponse, calibration)
   - Parallel extraction

7. **Stage 3: Derived Metrics** (`data/03_derived/`)
   - `metrics.parquet` (extracted quantities)
   - Enriched chip histories

8. **Processing: History Enrichment**
   - `enrich-history` command
   - Joins calibrations and metrics

9. **Viewing & Analysis** (NEW in v3.1)
   - `show-history` command with `--format` flag
   - `inspect-manifest` command with `--format` flag
   - Output formatters (RichTableFormatter, JSONFormatter, CSVFormatter)

10. **Output Formats**
    - Rich Table (default, colored terminal)
    - JSON (machine-readable, metadata included)
    - CSV (spreadsheet-compatible)

11. **Plotting Pipeline**
    - Plot commands (ITS, IVg, VVg, Vt, transconductance, CNP, photoresponse)
    - `read_measurement_parquet()` utility
    - Publication figures (PDF/PNG)

12. **External Tools Integration**
    - jq (JSON filtering)
    - Excel/Sheets (CSV import)
    - Python scripts (pandas integration)

13. **Unified Pipeline Command**
    - `full-pipeline` executes complete end-to-end processing

---

## Regenerating the Diagram

**Quick Method:** Use the provided script:

```bash
# From project root
./docs/render_pipeline_diagram.sh
```

This script will regenerate all formats (PNG, SVG, PDF) from the DOT source.

**Prerequisites:** Graphviz must be installed
- macOS: `brew install graphviz`
- Linux: `apt-get install graphviz` or `yum install graphviz`
- Windows: Download from https://graphviz.org/download/

**Manual Method:** Run `dot` commands individually:

```bash
dot -Tpng docs/pipeline_architecture.dot -o docs/pipeline_architecture.png
dot -Tsvg docs/pipeline_architecture.dot -o docs/pipeline_architecture.svg
dot -Tpdf docs/pipeline_architecture.dot -o docs/pipeline_architecture.pdf
```

---

## Technical Details

### Graphviz Features Used

- **Subgraphs** (clusters) - Organize related components
- **Color coding** - Distinguish stages and types
- **Edge styling** - Show data flow direction and importance
  - Solid lines: Primary data flow
  - Dashed lines: Optional/secondary flow
  - Line width: Importance/volume
- **Rank direction** - Top-to-bottom flow (TB)
- **Node shapes** - Different shapes for different types
- **HTML-like labels** - Rich formatting within nodes

### Rendering Commands

```bash
# Generate all formats
dot -Tpng docs/pipeline_architecture.dot -o docs/pipeline_architecture.png
dot -Tsvg docs/pipeline_architecture.dot -o docs/pipeline_architecture.svg
dot -Tpdf docs/pipeline_architecture.dot -o docs/pipeline_architecture.pdf
```

**Prerequisites:** Graphviz installed
- macOS: `brew install graphviz`
- Linux: `apt-get install graphviz` or `yum install graphviz`
- Windows: Download from https://graphviz.org/download/

---

## Diagram Highlights

### 1. Complete Pipeline Flow

Shows the entire data journey:
```
Raw CSV → Staging → Parquet + Manifest → Histories → Metrics → Enriched Histories → Plots
```

### 2. Output Formatters Integration

Clearly shows how the new v3.1 formatters integrate:
- `show-history` command connects to formatters
- `inspect-manifest` command connects to formatters
- Formatters produce three output types: Table, JSON, CSV
- External tools (jq, spreadsheets) connect to JSON/CSV

### 3. Processing Commands

All major commands visualized:
- `stage-all` - CSV to Parquet
- `build-all-histories` - Manifest to chip histories
- `derive-all-metrics` - Extract metrics
- `enrich-history` - Join calibrations and metrics
- `show-history` - View and export data
- `inspect-manifest` - View manifest data
- `plot-*` - Generate plots
- `full-pipeline` - Unified orchestration

### 4. Data Artifacts

All major data files shown:
- Raw CSVs
- Staged Parquet files (by procedure)
- `manifest.parquet`
- Chip histories
- `metrics.parquet`
- Enriched chip histories
- Publication figures

### 5. Configuration

Shows `config/procedures.yml` integration with schema validator

---

## Benefits

### For Users

✅ **Visual learning** - Understand entire pipeline at a glance
✅ **Documentation** - Reference for workflow planning
✅ **Onboarding** - New users can see complete architecture
✅ **Debugging** - Trace data flow for troubleshooting

### For Developers

✅ **Architecture documentation** - Shows design decisions
✅ **Integration points** - Clear module boundaries
✅ **Extension planning** - Visualize where new features fit
✅ **Code navigation** - Map diagram to source files

### For Documentation

✅ **Central reference** - Single source of truth for architecture
✅ **Multiple formats** - PNG for docs, PDF for printing, SVG for web
✅ **Editable source** - DOT file can be updated as pipeline evolves
✅ **Cross-references** - Linked from README.md and CLAUDE.md

---

## Future Updates

When the pipeline architecture changes:

1. **Edit** `docs/pipeline_architecture.dot` (Graphviz source)
2. **Regenerate** all formats using `dot` commands
3. **Update** cross-references in documentation
4. **Commit** all formats to version control

### Common Updates

- **New commands** - Add new rounded box in appropriate section
- **New data artifacts** - Add new folder/cylinder
- **New processing steps** - Add new component
- **New features** - Add new subgraph cluster

---

## Integration with Documentation

The diagram is referenced in:

1. **`CLAUDE.md`** (line 219)
   - Architecture section
   - "Visual Overview" bullet point

2. **`docs/README.md`**
   - "Pipeline Architecture Diagram" section (top of file)
   - Links to all four formats

3. **`docs/OUTPUT_FORMATTERS_COMPLETE.md`** (line 191)
   - Technical Achievements > Architecture section

---

## Metrics

**Creation Time:** ~30 minutes
**Diagram Complexity:**
- 13 subgraph clusters
- 40+ nodes
- 50+ edges
- 20 KB source file
- 657 KB PNG (high quality)

**Documentation Impact:**
- 3 files updated
- 60+ lines added
- 4 new diagram files

---

## Conclusion

The pipeline architecture diagram provides a comprehensive visual overview of the entire optothermal processing pipeline, including the newly implemented output formatters feature. It serves as a central reference for users, developers, and documentation.

**Status:** Production-ready and integrated into documentation.

---

**Questions or suggestions?** Edit `docs/pipeline_architecture.dot` and regenerate!
