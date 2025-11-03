#!/bin/bash

# Converted Python commands to shell script

# Plot IVG and transconductance
python process_and_analyze.py plot-ivg 67 --seq 2

python process_and_analyze.py plot-transconductance 67 \
  --seq 2 \
  --method savgol --window 21 \
  --polyorder 7

# Plot ITS measurements

# 1) 405 nm, negative gate
python process_and_analyze.py plot-its 67 \
  --seq 15-18 \
  --legend irradiated_power

# 1) 405 nm, negative gate
python process_and_analyze.py plot-its-sequential 67 \
  --seq 15-18 \
  --legend irradiated_power



# 2) 405 nm, positive gate
python process_and_analyze.py plot-its 67 \
  --seq 21-24 \
  --legend irradiated_power

# 2) 405 nm, positive gate
python process_and_analyze.py plot-its-sequential 67 \
  --seq 21-24 \
  --legend irradiated_power


# 3) 385 nm, negative gate
python process_and_analyze.py plot-its 67 \
  --seq 27-30 \
  --legend irradiated_power

# 3) 385 nm, negative gate
python process_and_analyze.py plot-its-sequential 67 \
  --seq 27-30 \
  --legend irradiated_power




# 4) 385 nm, positive gate
python process_and_analyze.py plot-its 67 \
  --seq 32-35 \
  --legend irradiated_power

# 4) 385 nm, positive gate
python process_and_analyze.py plot-its-sequential 67 \
  --seq 32-35 \
  --legend irradiated_power


# 5) 365 nm, negative gate
python process_and_analyze.py plot-its 67 \
  --seq 38-39 \
  --legend irradiated_power

# 5) 365 nm, negative gate
python process_and_analyze.py plot-its-sequential 67 \
  --seq 38-39 \
  --legend irradiated_power

# 8) 365 nm, negative gate, same power different response
python process_and_analyze.py plot-its 67 \
  --seq 38,41,52,57,65 \
  --legend irradiated_power



python process_and_analyze.py plot-its 67 \
  --seq 40-44 \
  --legend irradiated_power

# 6) 365 nm, negative gate
python process_and_analyze.py plot-its-sequential 67 \
  --seq 40-44 \
  --legend irradiated_power



# 6) 365 nm, positive gate
python process_and_analyze.py plot-its 67 \
  --seq 46-49 \
  --legend irradiated_power

# 7) 365 nm, positive gate
python process_and_analyze.py plot-its-sequential 67 \
  --seq 46-49 \
  --legend irradiated_power



# 7) 365 nm, -0.40 V gate
python process_and_analyze.py plot-its 67 \
  --seq 57-60 \
  --legend irradiated_power

# 8) 365 nm, positive gate
python process_and_analyze.py plot-its-sequential 67 \
  --seq 57-60 \
  --legend irradiated_power


# 8) 365 nm, positive gate
python process_and_analyze.py plot-its-sequential 67 \
  --seq 65,66 \
  --legend irradiated_power

# 8) 365 nm, positive gate
python process_and_analyze.py plot-its-sequential 67 \
  --seq 73,74 \
  --legend irradiated_power

# 7) 365 nm, -0.40 V gate
python process_and_analyze.py plot-its 67 \
  --seq 76 \
  --legend irradiated_power

python process_and_analyze.py plot-its 67 \
  --seq 80,82,85,87 \
  --legend irradiated_power


# 7) 365 nm, -0.40 V gate
python process_and_analyze.py plot-its 67 \
  --seq 80,82 \
  --legend irradiated_power


python process_and_analyze.py plot-its-sequential 67 \
  --seq 85-87 \
  --legend irradiated_power

python process_and_analyze.py plot-its 67 \
  --seq 85,87 \
  --legend irradiated_power


