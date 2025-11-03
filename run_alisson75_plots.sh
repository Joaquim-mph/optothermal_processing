#!/usr/bin/env bash
set -euo pipefail

# Optional venv:
# source .venv/bin/activate

echo "=== Alisson75 plotting batch ==="

###############################################################################
# 0) Dark / baseline figures
# IVg are at: 1, 2-4, 10, 16-17, 23, 29-34, 40, 46, 48, 49-51, 57-59
# (that's basically all IVg across the 3 days)
###############################################################################

echo "[1/??] plot-ivg (full dark baseline)"
python process_and_analyze.py plot-ivg 75 \
  --seq 1,2-4,10,16-17,23,29-34,40,46,48,49-51,57-59

echo "[2/??] plot-transconductance (full dark baseline)"
python process_and_analyze.py plot-transconductance 75 \
  --seq 1,2-4,10,16-17,23,29-34,40,46,48,49-51,57-59 \
  --method savgol --window 21 --polyorder 7


###############################################################################
# 1) ITS overlays (per wavelength, per gate)
# 365 nm @ Vg = -3.00 : 5-9
# 365 nm @ Vg = +3.00 : 11-15
# 455 nm @ Vg = -3.00 : 18-22
# 455 nm @ Vg = +3.00 : 24-28
# 565 nm @ Vg = -3.00 : 35-39
# 565 nm @ Vg = +3.00 : 41-45
# 365 nm @ Vg = -3.87 : 52-56   (second day, stronger negative gate)
###############################################################################

echo "[3/??] 365 nm, Vg = -3.00 (seq 5-9)"
python process_and_analyze.py plot-its 75 \
  --seq 5-9 \
  --legend irradiated_power

echo "[4/??] 365 nm, Vg = +3.00 (seq 11-15)"
python process_and_analyze.py plot-its 75 \
  --seq 11-15 \
  --legend irradiated_power

echo "[5/??] 455 nm, Vg = -3.00 (seq 18-22)"
python process_and_analyze.py plot-its 75 \
  --seq 18-22 \
  --legend irradiated_power

echo "[6/??] 455 nm, Vg = +3.00 (seq 24-28)"
python process_and_analyze.py plot-its 75 \
  --seq 24-28 \
  --legend irradiated_power

echo "[7/??] 565 nm, Vg = -3.00 (seq 35-39)"
python process_and_analyze.py plot-its 75 \
  --seq 35-39 \
  --legend irradiated_power

echo "[8/??] 565 nm, Vg = +3.00 (seq 41-45)"
python process_and_analyze.py plot-its 75 \
  --seq 41-45 \
  --legend irradiated_power

echo "[9/??] 365 nm, Vg = -3.87 (second day, seq 52-56)"
python process_and_analyze.py plot-its 75 \
  --seq 52-56 \
  --legend irradiated_power


###############################################################################
# 2) ITS sequential views (time-ordered blocks)
# Same blocks as above, but "played" one after another to show cadence
###############################################################################

echo "[10/??] SEQ: 365 nm, Vg = -3.00 (5-9)"
python process_and_analyze.py plot-its-sequential 75 \
  --seq 5-9 \
  --legend irradiated_power

echo "[11/??] SEQ: 365 nm, Vg = +3.00 (11-15)"
python process_and_analyze.py plot-its-sequential 75 \
  --seq 11-15 \
  --legend irradiated_power

echo "[12/??] SEQ: 455 nm, Vg = -3.00 (18-22)"
python process_and_analyze.py plot-its-sequential 75 \
  --seq 18-22 \
  --legend irradiated_power

echo "[13/??] SEQ: 455 nm, Vg = +3.00 (24-28)"
python process_and_analyze.py plot-its-sequential 75 \
  --seq 24-28 \
  --legend irradiated_power

echo "[14/??] SEQ: 565 nm, Vg = -3.00 (35-39)"
python process_and_analyze.py plot-its-sequential 75 \
  --seq 35-39 \
  --legend irradiated_power

echo "[15/??] SEQ: 565 nm, Vg = +3.00 (41-45)"
python process_and_analyze.py plot-its-sequential 75 \
  --seq 41-45 \
  --legend irradiated_power

echo "[16/??] SEQ: 365 nm, Vg = -3.87 (52-56)"
python process_and_analyze.py plot-its-sequential 75 \
  --seq 52-56 \
  --legend irradiated_power


###############################################################################
# 3) Optional comparative / mixed selections
# - compare 365@-3.00 (5-9) vs 365@+3.00 (11-15)
# - compare 365@-3.00 (5-9) vs 365@-3.87 (52-56) to see day-to-day change
###############################################################################

echo "[17/??] COMP: 365 nm, negative vs positive gate (5-9 vs 11-15)"
python process_and_analyze.py plot-its 75 \
  --seq 5-9,11-15 \
  --legend led_voltage

echo "[18/??] COMP: 365 nm, -3.00 day1 vs -3.87 day3 (5-9 vs 52-56)"
python process_and_analyze.py plot-its 75 \
  --seq 5-9,52-56 \
  --legend led_voltage

echo "=== Done (Alisson75) ==="
