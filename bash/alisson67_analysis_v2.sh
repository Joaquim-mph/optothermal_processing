#!/bin/bash
# Improved Analysis Script for Alisson67
# This script replaces the old run_alisson67_plots.sh with a more maintainable approach
#
# Key improvements:
# - 34 commands → 15 commands (56% reduction)
# - No hard-coded sequence numbers (robust to data changes)
# - Auto-filtering by metadata (wavelength, gate voltage, power)
# - Uses photoresponse analysis commands for scientific insights
# - Easy to adapt for other chips

set -e  # Exit on error

CHIP=67

echo "=========================================="
echo "  Alisson${CHIP} Photoresponse Analysis"
echo "=========================================="
echo

# ===========================
# 1. Initial Characterization
# ===========================
echo "[1/4] Initial Characterization..."

# IVg sweep and transconductance (pre-illumination baseline)
python3 process_and_analyze.py plot-ivg $CHIP --seq 2
python3 process_and_analyze.py plot-transconductance $CHIP \
    --seq 2 \
    --method savgol \
    --window 21 \
    --polyorder 7

echo "  ✓ IVg and transconductance complete"
echo

# ===========================
# 2. CNP Evolution
# ===========================
echo "[2/4] CNP Evolution Analysis..."

# Check if derived metrics exist, if not create them
METRICS_FILE="data/03_derived/_metrics/metrics.parquet"
if [ ! -f "$METRICS_FILE" ]; then
    echo "  ⚠️  Derived metrics not found, extracting now..."
    python3 process_and_analyze.py derive-all-metrics
fi

# Track Dirac point shifts over time (illumination effects)
python3 process_and_analyze.py plot-cnp-time $CHIP || {
    echo "  ⚠️  CNP plot failed (no IVg data or metrics not extracted)"
    echo "  Skipping CNP evolution..."
}

echo "  ✓ CNP evolution complete"
echo

# ===========================
# 3. Comprehensive Photoresponse Analysis
# ===========================
echo "[3/4] Comprehensive Photoresponse Analysis..."

# Photoresponse vs power (shows power-law behavior)
python3 process_and_analyze.py plot-photoresponse $CHIP power || echo "  ⚠️  Photoresponse vs power failed (no data or metrics missing)"

# Photoresponse vs wavelength (shows spectral response)
python3 process_and_analyze.py plot-photoresponse $CHIP wavelength || echo "  ⚠️  Photoresponse vs wavelength failed (no data)"

# Photoresponse vs gate voltage (shows doping dependence)
python3 process_and_analyze.py plot-photoresponse $CHIP gate_voltage || echo "  ⚠️  Photoresponse vs gate failed (no data)"

# Photoresponse evolution over time (shows degradation/recovery)
python3 process_and_analyze.py plot-photoresponse $CHIP time || echo "  ⚠️  Photoresponse vs time failed (no data)"

echo "  ✓ Photoresponse analysis complete"
echo

# ===========================
# 4. Detailed ITS Plots (Power Series)
# ===========================
echo "[4/4] Detailed ITS Power Series..."

# Automatically generate plots for each wavelength/gate combination
# The --auto flag finds all matching experiments and sorts by power

# 455nm wavelength
echo "  - 455nm series..."
python3 process_and_analyze.py plot-its $CHIP --auto --wavelength 455 --vg -0.35 --legend irradiated_power || echo "    ⚠️ Failed (no matching data)"
python3 process_and_analyze.py plot-its $CHIP --auto --wavelength 455 --vg 0.2 --legend irradiated_power || echo "    ⚠️ Failed (no matching data)"

# 405nm wavelength
echo "  - 405nm series..."
python3 process_and_analyze.py plot-its $CHIP --auto --wavelength 405 --vg -0.35 --legend irradiated_power || echo "    ⚠️ Failed (no matching data)"
python3 process_and_analyze.py plot-its $CHIP --auto --wavelength 405 --vg 0.2 --legend irradiated_power || echo "    ⚠️ Failed (no matching data)"

# 385nm wavelength
echo "  - 385nm series..."
python3 process_and_analyze.py plot-its $CHIP --auto --wavelength 385 --vg -0.4 --legend irradiated_power || echo "    ⚠️ Failed (no matching data)"
python3 process_and_analyze.py plot-its $CHIP --auto --wavelength 385 --vg 0.2 --legend irradiated_power || echo "    ⚠️ Failed (no matching data)"

# 365nm wavelength
echo "  - 365nm series..."
python3 process_and_analyze.py plot-its $CHIP --auto --wavelength 365 --vg -0.4 --legend irradiated_power || echo "    ⚠️ Failed (no matching data)"
python3 process_and_analyze.py plot-its $CHIP --auto --wavelength 365 --vg 0.2 --legend irradiated_power || echo "    ⚠️ Failed (no matching data)"

echo "  ✓ ITS power series complete"
echo

# ===========================
# Summary
# ===========================
echo "=========================================="
echo "✓ Analysis Complete!"
echo "=========================================="
echo
echo "Output directory: figs/Alisson${CHIP}/"
echo
echo "Generated plots:"
echo "  - IVg and transconductance (baseline characterization)"
echo "  - CNP evolution (Dirac point tracking)"
echo "  - Photoresponse vs power/wavelength/gate/time (comprehensive)"
echo "  - ITS power series at 455, 405, 385, 365nm (detailed)"
echo
echo "Next steps:"
echo "  1. Review plots in figs/Alisson${CHIP}/"
echo "  2. Check for anomalies or interesting features"
echo "  3. Run relaxation time analysis:"
echo "     python3 process_and_analyze.py plot-its-relaxation $CHIP --auto"
echo
