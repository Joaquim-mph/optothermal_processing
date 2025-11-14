#!/bin/bash

# Test script for inverse plotting functionality
# Generates comparison plots for IVg and VVg procedures

set -e  # Exit on error

echo "=========================================="
echo "Inverse Plotting Test Suite"
echo "=========================================="
echo ""

# Test chip and sequences
CHIP_IVG=81
SEQ_IVG="1,2,3"
CHIP_VVG=81
SEQ_VVG="203,204,205"

echo "Testing IVg inverse conductance (chip $CHIP_IVG, seq $SEQ_IVG)"
echo "----------------------------------------------------------"

# IVg Test 1: Baseline (current)
echo "[1/6] Generating IVg current plot (baseline)..."
python3 process_and_analyze.py plot-ivg $CHIP_IVG --seq $SEQ_IVG --tag "test_current"

# IVg Test 2: Conductance G=I/V
echo "[2/6] Generating IVg conductance plot (G = I/V)..."
python3 process_and_analyze.py plot-ivg $CHIP_IVG --seq $SEQ_IVG --conductance --tag "test_conductance"

# IVg Test 3: Inverse conductance 1/G=V/I
echo "[3/6] Generating IVg inverse conductance plot (1/G = V/I)..."
python3 process_and_analyze.py plot-ivg $CHIP_IVG --seq $SEQ_IVG --conductance --inverse --tag "test_inv_conductance"

echo ""
echo "Testing VVg inverse resistance (chip $CHIP_VVG, seq $SEQ_VVG)"
echo "----------------------------------------------------------"

# VVg Test 1: Baseline (voltage)
echo "[4/6] Generating VVg voltage plot (baseline)..."
python3 process_and_analyze.py plot-vvg $CHIP_VVG --seq $SEQ_VVG --tag "test_voltage"

# VVg Test 2: Resistance R=V/I
echo "[5/6] Generating VVg resistance plot (R = V/I)..."
python3 process_and_analyze.py plot-vvg $CHIP_VVG --seq $SEQ_VVG --resistance --tag "test_resistance"

# VVg Test 3: Inverse resistance 1/R=I/V
echo "[6/6] Generating VVg inverse resistance plot (1/R = I/V)..."
python3 process_and_analyze.py plot-vvg $CHIP_VVG --seq $SEQ_VVG --resistance --inverse --tag "test_inv_resistance"

echo ""
echo "=========================================="
echo "Test Complete!"
echo "=========================================="
echo ""
echo "Generated plots in figs/Encap$CHIP_IVG/:"
echo "  IVg plots:"
echo "    - encap${CHIP_IVG}_IVg_test_current.png         (baseline: Id vs Vg)"
echo "    - encap${CHIP_IVG}_IVg_test_conductance_G.png   (G = I/V)"
echo "    - encap${CHIP_IVG}_IVg_test_inv_conductance_invG.png (1/G = V/I)"
echo ""
echo "  VVg plots:"
echo "    - encap${CHIP_VVG}_VVg_test_voltage.png         (baseline: Vds vs Vg)"
echo "    - encap${CHIP_VVG}_VVg_test_resistance_R.png    (R = V/I)"
echo "    - encap${CHIP_VVG}_VVg_test_inv_resistance_invR.png (1/R = I/V)"
echo ""
echo "Visual verification:"
echo "  - IVg: 1/G plot should show resistance units (Ω, kΩ, MΩ)"
echo "  - VVg: 1/R plot should show conductance units (µS, mS, S)"
echo "  - Both inverse plots should have ylim(bottom=0)"
echo ""
