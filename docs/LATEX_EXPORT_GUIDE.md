# LaTeX Export Guide

## Overview

The LaTeX export commands generate professional, publication-ready tables from chip experiment histories with **color-coded procedures** for easy visual identification.

## Features

- **Color-coded rows** by procedure type (IVg=blue, It=orange, etc.)
- **Multi-page support** using `longtable` environment
- **Formatted columns** with proper units and scientific notation
- **Automatic legend** showing procedure colors
- **Enriched data support** (includes CNP, photoresponse metrics)
- **Filtering options** (by procedure, light status, date range)

## Color Scheme

| Procedure | Color | RGB |
|-----------|-------|-----|
| **IVg** | Light Blue | (200, 230, 255) |
| **It** | Light Orange | (255, 240, 200) |
| **IVgT** | Light Green | (230, 255, 230) |
| **LaserCalibration** | Light Purple | (255, 230, 255) |
| **IV** | Light Yellow | (255, 255, 200) |
| **Vt** | Light Red | (255, 220, 220) |
| **VVg** | Light Cyan | (220, 255, 255) |
| **Tt** | Light Gray | (240, 240, 240) |

## Commands

### Export Single Chip

```bash
# Export full history for chip 81
python3 process_and_analyze.py export-latex 81

# Export only IVg experiments
python3 process_and_analyze.py export-latex 81 --proc IVg

# Export only light experiments
python3 process_and_analyze.py export-latex 81 --light light

# Export last 50 experiments
python3 process_and_analyze.py export-latex 81 --limit 50

# Export without timestamp (cleaner filename)
python3 process_and_analyze.py export-latex 81 --no-timestamp

# Custom output directory
python3 process_and_analyze.py export-latex 81 --output-dir ~/my_latex_tables
```

### Export All Chips

```bash
# Export LaTeX tables for all chips
python3 process_and_analyze.py export-all-latex

# Export without timestamps
python3 process_and_analyze.py export-all-latex --no-timestamp
```

## Output Structure

Files are organized in a chip-specific directory:

```
data/04_exports/latex/
  ├── Alisson67/
  │   ├── Alisson67_table_20251114_002848.tex
  │   ├── Alisson67_table_ivg_20251114_003012.tex
  │   └── Alisson67_table.tex  (if --no-timestamp)
  ├── Alisson75/
  │   └── Alisson75_table_20251114_002901.tex
  └── Alisson81/
      └── Alisson81_table_20251114_002848.tex
```

## Compiling to PDF

### Using pdflatex (Command Line)

```bash
# Navigate to the output directory
cd data/04_exports/latex/Alisson81/

# Compile to PDF (may need to run twice for page numbers)
pdflatex Alisson81_table_20251114_002848.tex
pdflatex Alisson81_table_20251114_002848.tex

# View the PDF
open Alisson81_table_20251114_002848.pdf  # macOS
xdg-open Alisson81_table_20251114_002848.pdf  # Linux
```

### Using LaTeX Editors

- **Overleaf**: Upload the .tex file to [overleaf.com](https://www.overleaf.com)
- **TeXShop** (macOS): Open .tex file and click "Typeset"
- **TeXstudio** (cross-platform): Open .tex file and press F5
- **TeXworks**: Open .tex file and click green play button

## Table Columns

The generated table includes:

| Column | Description | Format |
|--------|-------------|--------|
| **Seq** | Sequential experiment number | Integer |
| **Datetime** | Date of experiment | YYYY-MM-DD |
| **Time** | Time of experiment | HH:MM:SS |
| **Proc** | Procedure type | String |
| **Light** | Light status | Yes/No |
| **λ [nm]** | Wavelength | Integer (nm) |
| **Vg [V]** | Gate voltage | Float (2 decimals) |
| **Vlaser [V]** | Laser voltage | Float (2 decimals) |
| **CNP [V]** | Charge neutrality point | Float (3 decimals) |
| **ΔI [A]** | Delta current (photoresponse) | Scientific notation |

## LaTeX Packages Required

The generated .tex files use these packages (included in most LaTeX distributions):

- `inputenc`, `fontenc` - Character encoding
- `geometry` - Page margins
- `booktabs` - Professional tables
- `longtable` - Multi-page tables
- `xcolor`, `colortbl` - Color support
- `array` - Column formatting

## Customization

### Modify Colors

Edit the color definitions in `src/cli/commands/export_latex.py`:

```python
PROCEDURE_COLORS = {
    "IVg": {"rgb": (200, 230, 255), "name": "lightblue"},  # Change RGB values here
    "It": {"rgb": (255, 240, 200), "name": "lightorange"},
    # ... etc
}
```

### Add New Columns

Modify the `generate_latex_table()` function to include additional columns from the history DataFrame.

### Change Table Layout

Edit the column width definitions in the longtable preamble:

```latex
\begin{longtable}{
    >{\centering\arraybackslash}p{0.8cm}  % Seq column (adjust width)
    >{\centering\arraybackslash}p{2.2cm}  % Datetime column
    % ... etc
}
```

## Troubleshooting

### Missing Derived Metrics

If CNP or ΔI columns show `--` for all rows:

```bash
# Generate derived metrics first
python3 process_and_analyze.py derive-all-metrics

# Enrich chip histories
python3 process_and_analyze.py enrich-history -a

# Then export LaTeX
python3 process_and_analyze.py export-latex 81
```

### Compilation Errors

If `pdflatex` fails:

1. Check that all packages are installed (use `tlmgr install <package>` or install full TeX Live)
2. Look at the `.log` file for specific errors
3. Verify the .tex file has valid UTF-8 encoding

### Special Characters

The export function automatically escapes LaTeX special characters (`&`, `%`, `$`, `#`, `_`, etc.). If you see issues with special characters, check the `escape_latex()` function.

## Examples

### Example 1: Conference Paper Table

```bash
# Export only IVg experiments for chip 67 (no timestamp for version control)
python3 process_and_analyze.py export-latex 67 --proc IVg --no-timestamp

# Output: data/04_exports/latex/Alisson67/Alisson67_table_ivg.tex
# Ready to \input{} into your conference paper
```

### Example 2: Full Device Characterization

```bash
# Export complete history with all procedures
python3 process_and_analyze.py export-latex 81

# Compile to PDF
cd data/04_exports/latex/Alisson81/
pdflatex Alisson81_table_*.tex
```

### Example 3: Photoresponse Summary

```bash
# Export only light experiments (It procedure)
python3 process_and_analyze.py export-latex 81 --proc It --light light

# Creates color-coded table showing only photoresponse measurements
```

## Integration with Batch Export

Combine with other export formats for complete dataset sharing:

```bash
# Export all formats for chip 81
python3 process_and_analyze.py export-history 81 --format csv
python3 process_and_analyze.py export-history 81 --format json
python3 process_and_analyze.py export-latex 81

# Results in:
# - Alisson81_history.csv (for Excel)
# - Alisson81_history.json (for Python/scripts)
# - Alisson81_table.tex (for publications)
```

## See Also

- `docs/BATCH_PLOTTING_GUIDE.md` - Automated plotting workflows
- `docs/EXPORTING_HISTORY_DATA.md` - General data export guide
- `CLAUDE.md` - Complete pipeline documentation
