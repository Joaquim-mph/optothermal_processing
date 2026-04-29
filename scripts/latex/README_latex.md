# LaTeX Table Compilation Scripts

This directory contains scripts for batch compiling LaTeX table files exported from the data pipeline.

## Quick Start

To compile all LaTeX files in `data/04_exports/latex`:

```bash
# From project root
python3 scripts/compile_latex_tables.py
```

## Scripts

### `compile_latex_tables.py`

Batch compiles all `.tex` files in the exports directory to PDF.

**Features:**
- Parallel compilation (4 workers by default)
- Automatic cleanup of auxiliary files (`.aux`, `.log`, `.out`)
- Progress reporting
- Error handling with detailed messages

**Usage:**
```bash
python3 scripts/compile_latex_tables.py
```

**Output:**
- Generates `.pdf` files in the same directory as source `.tex` files
- Shows compilation progress with ✓/❌ indicators
- Reports summary: succeeded/failed counts

### `fix_latex_underscores.py`

Fixes unescaped underscores in `\texttt{}` commands that cause LaTeX compilation errors.

**When to use:**
- If you see "Missing $ inserted" errors during compilation
- If you see "Extra }, or forgotten $" errors
- After generating new LaTeX tables from the pipeline

**Usage:**
```bash
python3 scripts/fix_latex_underscores.py
```

**What it does:**
- Scans all `.tex` files in exports directory
- Finds unescaped underscores in `\texttt{}` blocks
- Replaces `_` with `\_` where needed
- Handles nested braces correctly (e.g., `\textbackslash{}`)

## Workflow

Recommended workflow when you have new LaTeX exports:

```bash
# 1. Fix any formatting issues (run always, it's safe)
python3 scripts/fix_latex_underscores.py

# 2. Compile all tables to PDF
python3 scripts/compile_latex_tables.py
```

## Common Issues

### Issue: Some files fail to compile

**Solution:**
1. Run `fix_latex_underscores.py` first
2. Re-run `compile_latex_tables.py`

### Issue: Compilation timeout

If you have very large tables, you may need to increase the timeout in `compile_latex_tables.py`:

```python
# In compile_latex.py, line ~52
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=60  # Increase this value (in seconds)
)
```

### Issue: Need to compile single file

Use `pdflatex` directly:

```bash
cd data/04_exports/latex/Alisson67
pdflatex Alisson67_table_20251114_122530.tex
```

## Output Organization

Compiled PDFs are saved alongside their source `.tex` files:

```
data/04_exports/latex/
├── Alisson67/
│   ├── Alisson67_table_20251114_111233.tex
│   ├── Alisson67_table_20251114_111233.pdf  ← Generated
│   └── ...
├── Alisson81/
│   └── ...
└── ...
```

## Performance

Compilation times (approximate):
- Single file: 2-5 seconds
- 45 files (parallel, 4 workers): 30-60 seconds
- 45 files (sequential): 2-4 minutes
