# ITS Three-Phase Relaxation Fitting

**Feature:** Complete relaxation dynamics extraction from illuminated ITS measurements
**Added:** November 8, 2025
**Extractor:** `ITSThreePhaseFitExtractor`
**Metric:** `its_three_phase_relaxation`

---

## Overview

For **illuminated ITS measurements** with complete LED cycles (OFF → ON → OFF), this extractor fits stretched exponentials to **all THREE phases** separately:

```
┌──────────────┬────────────────────────┬──────────────┐
│  PRE-DARK    │       LIGHT            │  POST-DARK   │
│  (Phase 1)   │      (Phase 2)         │  (Phase 3)   │
├──────────────┼────────────────────────┼──────────────┤
│ VL = 0V      │ VL = 5V (LED ON)       │ VL = 0V      │
│ Dark         │ Photoresponse buildup  │ Photoresponse│
│ baseline     │ during illumination    │ decay        │
│              │                        │              │
│ Fit: τ₁, β₁  │ Fit: τ₂, β₂            │ Fit: τ₃, β₃  │
└──────────────┴────────────────────────┴──────────────┘
```

**Output:** 3 complete relaxation characterizations (τ, β, R², etc.) from a single measurement!

---

## Why Three Phases?

### Phase 1: PRE-DARK (Before Illumination)
- **Captures:** Dark baseline stability, drift, spontaneous relaxation
- **Physics:** Thermal equilibration, trap state distribution at dark
- **τ₁ interpretation:** Baseline relaxation time (usually long or none)

### Phase 2: LIGHT (LED ON)
- **Captures:** Photoresponse buildup dynamics
- **Physics:** Photocarrier generation, trap filling
- **τ₂ interpretation:** Photoresponse rise time constant

### Phase 3: POST-DARK (After LED OFF)
- **Captures:** Photoresponse decay back to baseline
- **Physics:** Photocarrier recombination, trap emptying
- **τ₃ interpretation:** Photoresponse decay time constant

**Comparing all three reveals:**
- Trap depth distribution (τ₃ vs τ₂)
- Baseline stability (quality of τ₁ fit)
- Hysteresis effects (baseline shift between Phase 1 and Phase 3)

---

## Separation from Delta Current

This extractor is **completely separate** from the simple photoresponse extractor:

| Feature | **PhotoresponseExtractor** | **ITSThreePhaseFitExtractor** |
|---------|----------------------------|-------------------------------|
| **Metric name** | `photoresponse` (or `delta_current`) | `its_three_phase_relaxation` |
| **Method** | Simple subtraction: ΔI = I_last - I_first | Stretched exponential fitting (3×) |
| **Output** | Single ΔI value | 3× (τ, β, amplitude, R², ...) |
| **Speed** | Instant | ~1-10 ms (still very fast with Numba) |
| **Information** | Total photoresponse magnitude | Complete dynamics for all 3 phases |
| **Use case** | Quick screening, total response | Detailed relaxation analysis |
| **Applicable to** | It, ITt, Vt | ITS, ITt |

**Both extractors run independently!** You get both metrics:
- `photoresponse`: 0.38 µA (simple difference)
- `its_three_phase_relaxation`: τ₁=120s, τ₂=15s, τ₃=42s (detailed dynamics)

---

## Usage

### Automatic (Default Pipeline)

The extractor is **automatically included** in the default pipeline:

```bash
# Extract all metrics including three-phase relaxation
python3 process_and_analyze.py derive-all-metrics

# Extract only from ITS/ITt
python3 process_and_analyze.py derive-all-metrics --procedures ITS,ITt

# Extract for specific chip
python3 process_and_analyze.py derive-all-metrics --chip 67
```

### Manual Extraction

```python
from pathlib import Path
from src.derived.extractors import ITSThreePhaseFitExtractor
from src.core.utils import read_measurement_parquet
import json

# Create extractor
extractor = ITSThreePhaseFitExtractor(
    vl_threshold=0.1,
    min_phase_duration=60.0,     # 1 minute minimum per phase
    min_points_for_fit=50,
    require_all_phases=True      # Must fit all 3 phases
)

# Load measurement
measurement = read_measurement_parquet(
    Path("data/02_stage/raw_measurements/ITS/abc123.parquet")
)

metadata = {
    "run_id": "abc123def456",
    "chip_number": 67,
    "chip_group": "Alisson",
    "proc": "ITS",
    "seq_num": 52
}

# Extract three-phase relaxation
metric = extractor.extract(measurement, metadata)

if metric:
    details = json.loads(metric.value_json)

    # Access each phase
    if details["pre_dark"]:
        print(f"PRE-DARK: τ={details['pre_dark']['tau']:.2f}s, "
              f"β={details['pre_dark']['beta']:.3f}, "
              f"R²={details['pre_dark']['r_squared']:.3f}")

    if details["light"]:
        print(f"LIGHT: τ={details['light']['tau']:.2f}s, "
              f"β={details['light']['beta']:.3f}, "
              f"R²={details['light']['r_squared']:.3f}")

    if details["post_dark"]:
        print(f"POST-DARK: τ={details['post_dark']['tau']:.2f}s, "
              f"β={details['post_dark']['beta']:.3f}, "
              f"R²={details['post_dark']['r_squared']:.3f}")
```

---

## Configuration Parameters

### `vl_threshold` (default: 0.1 V)
LED ON detection threshold.

### `min_phase_duration` (default: 60.0 s)
**Minimum duration for each phase.**

Your measurements have phases ≥1 minute, so default 60s is perfect!

**Adjust if:**
- Shorter measurements: Decrease to 30s or 45s
- Only want long high-quality phases: Increase to 90s or 120s

### `min_points_for_fit` (default: 50)
Minimum number of data points per phase.

**Adjust if:**
- Low sampling rate: Decrease to 30
- Very high sampling rate: Increase to 100 for better fits

### `require_all_phases` (default: True)
**Whether all 3 phases must be present.**

- `True`: Only extract if PRE-DARK, LIGHT, and POST-DARK all fit successfully
- `False`: Extract whatever phases are available (could be just 1 or 2)

**When to use `False`:**
- PRE-DARK is just noise (no relaxation)
- Measurement doesn't have clean 3-phase structure
- Want partial results for incomplete measurements

---

## Output Format

### Primary Value
```python
metric.value_float  # τ_light (Phase 2 relaxation time)
```

The light phase τ is used as the primary value since it's typically the most important for photoresponse analysis.

### Complete JSON Structure
```python
import json
details = json.loads(metric.value_json)

{
    "pre_dark": {
        "phase": "pre_dark",
        "tau": 125.3,              # Relaxation time (s)
        "beta": 0.82,              # Stretching exponent
        "amplitude": 0.05e-6,      # Fitted amplitude (A)
        "baseline": 1.0e-6,        # Fitted baseline (A)
        "r_squared": 0.89,         # Fit quality
        "n_iterations": 45,        # Optimization iterations
        "converged": True,         # Convergence status
        "segment_start": 0.0,      # Phase start time (s)
        "segment_end": 79.8,       # Phase end time (s)
        "segment_duration": 79.8,  # Phase duration (s)
        "n_points_fitted": 1197,   # Data points used
        "confidence": 0.82         # Confidence score (0-1)
    },

    "light": {
        "phase": "light",
        "tau": 15.2,               # Light relaxation time (s)
        "beta": 0.68,              # Stretching exponent
        "amplitude": 0.42e-6,      # Photoresponse amplitude (A)
        "baseline": 1.0e-6,        # Dark baseline (A)
        "r_squared": 0.96,         # Fit quality
        "converged": True,
        "segment_start": 80.0,
        "segment_end": 199.9,
        "segment_duration": 119.9,
        "n_points_fitted": 1799,
        "confidence": 0.95
    },

    "post_dark": {
        "phase": "post_dark",
        "tau": 42.5,               # Dark relaxation time (s)
        "beta": 0.71,              # Stretching exponent
        "amplitude": -0.38e-6,     # Negative (decay)
        "baseline": 1.05e-6,       # Final baseline (A)
        "r_squared": 0.93,
        "converged": True,
        "segment_start": 200.0,
        "segment_end": 299.9,
        "segment_duration": 99.9,
        "n_points_fitted": 1499,
        "confidence": 0.91
    },

    "phases_fitted": ["pre_dark", "light", "post_dark"],
    "n_phases": 3,
    "all_phases_present": True
}
```

### Metadata
```python
metric.metric_name           # "its_three_phase_relaxation"
metric.metric_category       # "photoresponse"
metric.unit                  # "s" (seconds)
metric.extraction_method     # "three_phase_stretched_exponential"
metric.confidence            # Average of phase confidences
metric.flags                 # Warning flags (if any)
```

---

## Quality Checks & Flags

### Confidence Score
Overall confidence is the **average** of individual phase confidences.

**Each phase confidence** penalized for:
- R² < 0.95: ×0.8
- R² < 0.90: ×0.7
- R² < 0.80: ×0.5
- Not converged: ×0.6
- Many iterations (>80): ×0.9

### Warning Flags

| Flag | Meaning |
|------|---------|
| `MISSING_PRE_DARK` | PRE-DARK phase not fitted |
| `MISSING_LIGHT` | LIGHT phase not fitted |
| `MISSING_POST_DARK` | POST-DARK phase not fitted |
| `PRE_DARK_NOT_CONVERGED` | PRE-DARK fit didn't converge |
| `LIGHT_NOT_CONVERGED` | LIGHT fit didn't converge |
| `POST_DARK_NOT_CONVERGED` | POST-DARK fit didn't converge |
| `PRE_DARK_LOW_R2` | PRE-DARK R² < 0.8 |
| `LIGHT_LOW_R2` | LIGHT R² < 0.8 |
| `POST_DARK_LOW_R2` | POST-DARK R² < 0.8 |
| `PRE_DARK_VERY_FAST` | τ₁ < 1s |
| `LIGHT_VERY_FAST` | τ₂ < 1s |
| `POST_DARK_VERY_FAST` | τ₃ < 1s |
| `PRE_DARK_VERY_SLOW` | τ₁ > 100s |
| `LIGHT_VERY_SLOW` | τ₂ > 100s |
| `POST_DARK_VERY_SLOW` | τ₃ > 100s |
| `PRE_DARK_HIGHLY_STRETCHED` | β₁ < 0.3 |
| `LIGHT_HIGHLY_STRETCHED` | β₂ < 0.3 |
| `POST_DARK_HIGHLY_STRETCHED` | β₃ < 0.3 |

---

## Data Analysis Examples

### Compare Light vs Dark Relaxation

```python
import polars as pl
import json

# Load metrics
metrics = pl.read_parquet("data/03_derived/_metrics/metrics.parquet")

# Filter to three-phase relaxation
three_phase = metrics.filter(
    pl.col("metric_name") == "its_three_phase_relaxation"
)

# Extract τ values for each phase
results = []
for row in three_phase.iter_rows(named=True):
    details = json.loads(row["value_json"])

    if details["all_phases_present"]:
        results.append({
            "chip": row["chip_number"],
            "run_id": row["run_id"],
            "τ_pre": details["pre_dark"]["tau"],
            "τ_light": details["light"]["tau"],
            "τ_post": details["post_dark"]["tau"],
            "β_light": details["light"]["beta"],
            "β_post": details["post_dark"]["beta"]
        })

df = pl.DataFrame(results)

# Calculate ratios
df = df.with_columns([
    (pl.col("τ_post") / pl.col("τ_light")).alias("decay_rise_ratio"),
    (pl.col("β_post") / pl.col("β_light")).alias("beta_ratio")
])

print(df)

# Interpretation:
# - decay_rise_ratio > 1: Slower decay than rise (deep traps)
# - decay_rise_ratio < 1: Faster decay than rise (shallow traps)
```

### Plot Relaxation Time Evolution

```python
import matplotlib.pyplot as plt

# Assuming you have chip history with three-phase metrics joined
history = pl.read_parquet("data/03_derived/chip_histories_enriched/67/chip_67_history.parquet")

# Filter to ITS with three-phase data
its = history.filter(
    (pl.col("proc") == "ITS") &
    (pl.col("its_three_phase_relaxation").is_not_null())
)

# Extract τ values
tau_data = []
for row in its.iter_rows(named=True):
    details = json.loads(row["its_three_phase_relaxation"])
    if details["all_phases_present"]:
        tau_data.append({
            "seq": row["seq_num"],
            "timestamp": row["timestamp_local"],
            "τ_light": details["light"]["tau"],
            "τ_post": details["post_dark"]["tau"]
        })

df = pl.DataFrame(tau_data)

# Plot
plt.figure(figsize=(10, 6))
plt.plot(df["seq"], df["τ_light"], 'o-', label='τ_light (rise)')
plt.plot(df["seq"], df["τ_post"], 's-', label='τ_post (decay)')
plt.xlabel('Sequence Number')
plt.ylabel('Relaxation Time (s)')
plt.title('Photoresponse Dynamics Evolution')
plt.legend()
plt.grid(True)
plt.savefig('relaxation_evolution.png', dpi=300)
```

---

## Comparison with Other Extractors

For ITS measurements, you now get **three separate metrics**:

### 1. PhotoresponseExtractor → `photoresponse` (also runs on ITt)
```python
{
    "delta": 0.38e-6,           # ΔI = I_last - I_first
    "mean_on": 1.48e-6,         # Average during LED ON
    "mean_off": 1.10e-6,        # Average during LED OFF
    "response_ratio": 0.345,    # Fractional change
    "snr": 12.5                 # Signal-to-noise ratio
}
```
**Use:** Quick photoresponse magnitude

### 2. ITSRelaxationExtractor → `relaxation_time`
```python
{
    "tau": 18.5,                # Single τ from longest segment
    "beta": 0.68,
    "r_squared": 0.94,
    "segment_type": "light"     # or "dark"
}
```
**Use:** Single relaxation time (configurable: light, dark, or both)

### 3. ITSThreePhaseFitExtractor → `its_three_phase_relaxation`
```python
{
    "pre_dark": {...},          # τ₁, β₁, R², etc.
    "light": {...},             # τ₂, β₂, R², etc.
    "post_dark": {...},         # τ₃, β₃, R², etc.
    "phases_fitted": ["pre_dark", "light", "post_dark"]
}
```
**Use:** Complete 3-phase characterization

**All three run independently!** No conflicts.

---

## Troubleshooting

### No metrics extracted

**Possible causes:**

1. **Phases too short**
   - Check that each phase is ≥60s (or your configured threshold)
   - Solution: Lower `min_phase_duration` to 30s or 45s

2. **Incomplete LED cycle**
   - Measurement doesn't have clean OFF → ON → OFF structure
   - Solution: Set `require_all_phases=False`

3. **Poor fit quality**
   - Data too noisy, or no clear relaxation
   - Check R² values in failed attempts

### Only 1 or 2 phases fitted

**Common scenario:** PRE-DARK is just noise (no relaxation)

**Solution:**
```python
# Allow partial fitting
ITSThreePhaseFitExtractor(
    vl_threshold=0.1,
    min_phase_duration=60.0,
    min_points_for_fit=50,
    require_all_phases=False  # ← Accept 1 or 2 phases
)
```

### Very different τ values than expected

**Check:**
1. **Phase boundaries** - Verify in `value_json` that segments match LED cycle
2. **Baseline stability** - Large drift can cause poor fits
3. **Temperature stability** - Thermal drift affects relaxation dynamics

### Flags: `HIGHLY_STRETCHED`

**Meaning:** β < 0.3 indicates very distributed relaxation processes

**Interpretation:**
- Multiple trap depths
- Complex carrier dynamics
- May need multi-exponential model (future enhancement)

---

## Performance

**Speed:** ~1-10 ms per ITS measurement (3 fits with Numba acceleration)

- 100-point segment: ~0.5 ms per fit
- 1000-point segment: ~3 ms per fit
- 5000-point segment: ~15 ms per fit

**Memory:** Minimal - processes each measurement independently

**Parallelization:** Full support via MetricPipeline (default 6 workers)

---

## Future Enhancements

Potential improvements (TODO):

1. **Multi-exponential fitting** for highly stretched cases
2. **Automatic phase detection** for multi-pulse measurements
3. **Temperature-dependent analysis** (Arrhenius fitting across phases)
4. **Hysteresis quantification** (baseline shift between Phase 1 and Phase 3)
5. **Phase correlation analysis** (how τ₂ predicts τ₃)

---

## Related Documentation

- **Implementation:** `src/derived/extractors/its_three_phase_fit_extractor.py`
- **Numba algorithms:** `src/derived/algorithms/stretched_exponential.py`
- **Simple photoresponse:** `src/derived/extractors/photoresponse_extractor.py`
- **Single-phase relaxation:** `docs/ITS_RELAXATION_TIME_EXTRACTOR.md`
- **Dark relaxation:** `docs/DARK_ITS_RELAXATION_GUIDE.md`

---

## Quick Start

```bash
# Extract three-phase relaxation from all ITS measurements
python3 process_and_analyze.py derive-all-metrics --procedures ITS

# View results
python3 -c "
import polars as pl
import json

metrics = pl.read_parquet('data/03_derived/_metrics/metrics.parquet')
three_phase = metrics.filter(pl.col('metric_name') == 'its_three_phase_relaxation')

for row in three_phase.iter_rows(named=True):
    details = json.loads(row['value_json'])
    print(f\"\nChip {row['chip_number']}, Seq {row['seq_num']}:\")
    if details['all_phases_present']:
        print(f\"  τ_pre = {details['pre_dark']['tau']:.2f} s\")
        print(f\"  τ_light = {details['light']['tau']:.2f} s\")
        print(f\"  τ_post = {details['post_dark']['tau']:.2f} s\")
"

# Enrich chip histories
python3 process_and_analyze.py enrich-history -a
```

---

**Questions? Issues?** See `docs/ITS_RELAXATION_TIME_EXTRACTOR.md` for general relaxation fitting concepts.
