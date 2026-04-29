#!/bin/bash
# Convenience script to fix and compile all LaTeX tables
# Usage: ./scripts/compile_all_latex.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "LaTeX Table Compilation Pipeline"
echo "=========================================="
echo ""

echo "Step 1/2: Fixing underscore issues..."
python3 scripts/fix_latex_underscores.py

echo ""
echo "Step 2/2: Compiling LaTeX files to PDF..."
python3 scripts/compile_latex_tables.py

echo ""
echo "=========================================="
echo "Done! PDFs are in data/04_exports/latex/"
echo "=========================================="
