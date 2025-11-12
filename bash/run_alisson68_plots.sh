#!/usr/bin/env bash
set -euo pipefail

# source .venv/bin/activate   # <- uncomment if you need your venv

echo "=== Alisson68 plotting batch ==="

###############################################################################
# 0) Dark / baseline figures
# IVg seqs:
#  1-2
#  3-6
#  8-10
#  12-13
#  16
#  18-24
#  26-29
#  31
#  33-40
#  41-42
#  52-59
#  69
###############################################################################

# IVG_SEQS="1-2,3-6,8-10,12-13,16,18-24,26-29,31,33-40,41-42,52-59,69"

# echo "[1/??] plot-ivg (full baseline)"
# python process_and_analyze.py plot-ivg 68 \
#   --seq "$IVG_SEQS"

# echo "[2/??] plot-transconductance (full baseline)"
# python process_and_analyze.py plot-transconductance 68 \
#   --seq "$IVG_SEQS" \
#   --method savgol --window 21 --polyorder 7


###############################################################################
# 1) 2025-09-15 VIS/IR scan (120 s, many wavelengths, mostly single shots)
# light ITS on that day:
#  7  : 850 nm,  Vg ~ -5.04
#  11 : 680 nm,  Vg ~ -4.81
#  14-15 : 625 nm, Vg ~ -4.70  (two shots)
#  17 : 590 nm,  Vg ~ -4.41
#  20 : 565 nm,  Vg ~ -5.70  (note: positive ΔI)
#  25 : 505 nm,  Vg ~ -5.77  (positive ΔI)
#  28 : 455 nm,  Vg ~ -4.85
#  30 : 405 nm,  Vg ~ -4.02
#  32 : 385 nm,  Vg ~ -6.02
#  38 : 365 nm,  Vg ~ -5.81
# We’ll do: (a) one big overlay, (b) sequential view.
###############################################################################

EARLY_LIGHT_SEQS="7,11,14-15,17,20,25,28,30,32,38"

echo "[3/??] ITS overlay — 2025-09-15 spectral sweep"
python process_and_analyze.py plot-its 68 \
  --seq "$EARLY_LIGHT_SEQS" \
  --legend led_voltage

echo "[4/??] ITS sequential — 2025-09-15 spectral sweep"
python process_and_analyze.py plot-its-sequential 68 \
  --seq "$EARLY_LIGHT_SEQS" \
  --legend irradiated_power


###############################################################################
# 2) 365 nm, Vg ≈ -5.46, period 240 s, power-ladder, day 2025-09-22
# This comes in three triplets:
#   43-45  (6, 18, 30 mW)
#   46-48  (6, 18, 30 mW)
#   49-51  (6, 18, 30 mW)
###############################################################################

echo "[5/??] 365 nm, Vg≈-5.46, triplet #1 (43-45)"
python process_and_analyze.py plot-its 68 \
  --seq 43-45 \
  --legend irradiated_power

echo "[6/??] 365 nm, Vg≈-5.46, triplet #2 (46-48)"
python process_and_analyze.py plot-its 68 \
  --seq 46-48 \
  --legend irradiated_power

echo "[7/??] 365 nm, Vg≈-5.46, triplet #3 (49-51)"
python process_and_analyze.py plot-its 68 \
  --seq 49-51 \
  --legend irradiated_power

echo "[8/??] 365 nm, Vg≈-5.46, ALL triplets (43-51)"
python process_and_analyze.py plot-its 68 \
  --seq 43-51 \
  --legend irradiated_power

# Sequential views for the same 240 s blocks

echo "[9/??] SEQ: 365 nm, Vg≈-5.46, triplet #1 (43-45)"
python process_and_analyze.py plot-its-sequential 68 \
  --seq 43-45 \
  --legend irradiated_power

echo "[10/??] SEQ: 365 nm, Vg≈-5.46, triplet #2 (46-48)"
python process_and_analyze.py plot-its-sequential 68 \
  --seq 46-48 \
  --legend irradiated_power

echo "[11/??] SEQ: 365 nm, Vg≈-5.46, triplet #3 (49-51)"
python process_and_analyze.py plot-its-sequential 68 \
  --seq 49-51 \
  --legend irradiated_power

echo "[12/??] SEQ: 365 nm, Vg≈-5.46, ALL (43-51)"
python process_and_analyze.py plot-its-sequential 68 \
  --seq 43-51 \
  --legend irradiated_power


###############################################################################
# 3) 365 nm, Vg = +1.16, period 240 s, day 2025-09-22
# Also in three triplets:
#   60-62
#   63-65
#   66-68
###############################################################################

echo "[13/??] 365 nm, Vg=+1.16, triplet #1 (60-62)"
python process_and_analyze.py plot-its 68 \
  --seq 60-62 \
  --legend irradiated_power

echo "[14/??] 365 nm, Vg=+1.16, triplet #2 (63-65)"
python process_and_analyze.py plot-its 68 \
  --seq 63-65 \
  --legend irradiated_power

echo "[15/??] 365 nm, Vg=+1.16, triplet #3 (66-68)"
python process_and_analyze.py plot-its 68 \
  --seq 66-68 \
  --legend irradiated_power

echo "[16/??] 365 nm, Vg=+1.16, ALL triplets (60-68)"
python process_and_analyze.py plot-its 68 \
  --seq 60-68 \
  --legend irradiated_power

# Sequential versions

echo "[17/??] SEQ: 365 nm, Vg=+1.16, triplet #1 (60-62)"
python process_and_analyze.py plot-its-sequential 68 \
  --seq 60-62 \
  --legend irradiated_power

echo "[18/??] SEQ: 365 nm, Vg=+1.16, triplet #2 (63-65)"
python process_and_analyze.py plot-its-sequential 68 \
  --seq 63-65 \
  --legend irradiated_power

echo "[19/??] SEQ: 365 nm, Vg=+1.16, triplet #3 (66-68)"
python process_and_analyze.py plot-its-sequential 68 \
  --seq 66-68 \
  --legend irradiated_power

echo "[20/??] SEQ: 365 nm, Vg=+1.16, ALL (60-68)"
python process_and_analyze.py plot-its-sequential 68 \
  --seq 60-68 \
  --legend irradiated_power


###############################################################################
# 4) Comparisons (negative gate vs positive gate, same day, same 365 nm)
###############################################################################

echo "[21/??] COMP: 365 nm, Vg≈-5.46 (43-51) vs Vg=+1.16 (60-68)"
python process_and_analyze.py plot-its 68 \
  --seq 43-51,60-68 \
  --legend irradiated_power

echo "[22/??] SEQ: 365 nm, ALL 240s runs (43-51,60-68)"
python process_and_analyze.py plot-its-sequential 68 \
  --seq 43-51,60-68 \
  --legend irradiated_power


echo "=== Done (Alisson68) ==="
