#!/bin/bash
# Generic Chip Analysis Script
#
# Usage:
#   ./bash/analyze_chip.sh 67              # Analyze chip 67
#   ./bash/analyze_chip.sh 75 --quick      # Quick analysis (skip detailed ITS)
#   ./bash/analyze_chip.sh 81 --photoresponse-only  # Only photoresponse analysis
#
# This script automatically discovers wavelengths and gate voltages from the data,
# making it robust to different experimental configurations.

set -e  # Exit on error

# ===========================
# Parse Arguments
# ===========================
CHIP=$1
MODE=${2:-full}  # full, quick, photoresponse-only

if [ -z "$CHIP" ]; then
    echo "Usage: $0 <chip_number> [--quick|--photoresponse-only]"
    echo
    echo "Examples:"
    echo "  $0 67                      # Full analysis"
    echo "  $0 75 --quick              # Skip detailed ITS plots"
    echo "  $0 81 --photoresponse-only # Only photoresponse analysis"
    exit 1
fi

echo "=========================================="
echo "  Analyzing Chip ${CHIP}"
echo "  Mode: ${MODE}"
echo "=========================================="
echo

# ===========================
# Check if enriched history exists
# ===========================
HISTORY_FILE="data/02_stage/chip_histories_enriched/chip_${CHIP}_history.parquet"
if [ ! -f "$HISTORY_FILE" ]; then
    echo "⚠️  Enriched history not found. Running enrich-history first..."
    python3 process_and_analyze.py enrich-history $CHIP
    echo
fi

# ===========================
# 1. Initial Characterization
# ===========================
if [ "$MODE" != "photoresponse-only" ]; then
    echo "[1/4] Initial Characterization..."

    # IVg sweep and transconductance (auto-selects first IVg)
    python3 process_and_analyze.py plot-ivg $CHIP --auto || echo "  ⚠️  No IVg data found"
    python3 process_and_analyze.py plot-transconductance $CHIP --auto \
        --method savgol --window 21 --polyorder 7 || echo "  ⚠️  No IVg data for transconductance"

    echo "  ✓ Initial characterization complete"
    echo
fi

# ===========================
# 2. CNP Evolution
# ===========================
if [ "$MODE" != "photoresponse-only" ]; then
    echo "[2/4] CNP Evolution Analysis..."

    python3 process_and_analyze.py plot-cnp-time $CHIP || echo "  ⚠️  No CNP data found (run derive-all-metrics first)"

    echo "  ✓ CNP evolution complete"
    echo
fi

# ===========================
# 3. Comprehensive Photoresponse Analysis
# ===========================
echo "[3/4] Comprehensive Photoresponse Analysis..."

# These commands automatically group by wavelength/gate/power
python3 process_and_analyze.py plot-photoresponse $CHIP power || echo "  ⚠️  No photoresponse data"
python3 process_and_analyze.py plot-photoresponse $CHIP wavelength || echo "  ⚠️  No multi-wavelength data"
python3 process_and_analyze.py plot-photoresponse $CHIP gate_voltage || echo "  ⚠️  No gate voltage sweep data"
python3 process_and_analyze.py plot-photoresponse $CHIP time || echo "  ⚠️  No time-series data"

echo "  ✓ Photoresponse analysis complete"
echo

# ===========================
# 4. Detailed ITS Plots (Auto-Discovery)
# ===========================
if [ "$MODE" = "full" ]; then
    echo "[4/4] Detailed ITS Power Series (Auto-Discovery)..."

    # Use simple approach: get unique wavelength/gate combinations from show-history
    # and generate plots for each
    python3 process_and_analyze.py show-history $CHIP --proc It --format json | \
    python3 -c "
import json
import sys
import subprocess

data = json.load(sys.stdin)
experiments = data['data']

# Filter for illuminated measurements
its = [e for e in experiments if e['has_light'] and e['proc'] == 'It']

if not its:
    print('  ⚠️  No illuminated It measurements found')
    sys.exit(0)

# Get unique wavelength/gate combinations
groups = {}
for e in its:
    wl = e['wavelength_nm']
    vg = e['vg_fixed_v']
    key = (wl, vg)
    if key not in groups:
        groups[key] = 0
    groups[key] += 1

# Sort by wavelength, then gate voltage
sorted_groups = sorted(groups.items(), key=lambda x: (x[0][0], x[0][1]))

print(f'  Found {len(sorted_groups)} wavelength/gate combinations:')
chip = ${CHIP}

for (wl, vg), count in sorted_groups:
    print(f'    - λ={wl}nm, Vg={vg}V ({count} experiments)')

    # Run plot command
    cmd = [
        'python3', 'process_and_analyze.py', 'plot-its', str(chip),
        '--auto', '--wl', str(wl), '--vg', str(vg),
        '--legend', 'irradiated_power'
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f'      ⚠️  Failed: {e.stderr}')

print('  ✓ ITS power series complete')
"

    echo
fi

# ===========================
# Summary
# ===========================
echo "=========================================="
echo "✓ Analysis Complete!"
echo "=========================================="
echo
echo "Output directory: figs/Encap${CHIP}/ (or Alisson${CHIP}/)"
echo
echo "Generated plots:"
if [ "$MODE" != "photoresponse-only" ]; then
    echo "  ✓ IVg and transconductance (baseline characterization)"
    echo "  ✓ CNP evolution (Dirac point tracking)"
fi
echo "  ✓ Photoresponse vs power/wavelength/gate/time (comprehensive)"
if [ "$MODE" = "full" ]; then
    echo "  ✓ ITS power series (all wavelength/gate combinations)"
fi
echo
echo "Next steps:"
echo "  1. Review plots in figs/"
echo "  2. Check for anomalies or interesting features"
echo "  3. Run relaxation time analysis:"
echo "     python3 process_and_analyze.py plot-its-relaxation $CHIP --auto"
echo "  4. Export data for publication:"
echo "     python3 process_and_analyze.py show-history $CHIP --format csv > chip_${CHIP}_data.csv"
echo
