# Metric Extraction Filtering System

**How the pipeline decides which measurements get which extractors applied**

---

## 5-Level Filtering System

The metric extraction pipeline uses a **multi-level filtering cascade** to ensure extractors only run on appropriate measurements and only when they can produce valid results.

```
┌─────────────────────────────────────────────────────────────────┐
│ Level 1: PROCEDURE TYPE MATCHING                                │
│ (MetricPipeline extractor_map)                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────┐
         │ manifest.parquet (all measurements) │
         │ - IVg: 100 measurements             │
         │ - It: 50 measurements               │
         │ - ITS: 30 measurements ← MATCH!     │
         │ - LaserCalibration: 20 measurements │
         └────────────────────────────────────┘
                              ↓
         Filter: proc IN ["ITS", "ITt"]  (from applicable_procedures)
                              ↓
         ┌────────────────────────────────────┐
         │ ONLY ITS/ITt measurements pass     │
         │ 30 measurements → ITSRelaxationExtractor
         └────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────┐
│ Level 2: REQUIRED COLUMNS CHECK                                 │
│ (extractor.extract() - line 101)                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────┐
         │ Load measurement Parquet            │
         │ Check: {"t (s)", "I (A)", "VL (V)"} │
         └────────────────────────────────────┘
                              ↓
         Columns present?
           ├─ YES → Continue
           └─ NO  → return None (skip)


┌─────────────────────────────────────────────────────────────────┐
│ Level 3: LED STATE DETECTION                                    │
│ (extractor.extract() - line 111)                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────┐
         │ Check VL voltage values             │
         │ led_on_mask = (VL > 0.1)            │
         └────────────────────────────────────┘
                              ↓
         Any LED ON periods detected?
           ├─ YES → Continue
           └─ NO  → return None (dark measurement, no photoresponse)


┌─────────────────────────────────────────────────────────────────┐
│ Level 4: SEGMENT DURATION & DATA QUALITY                        │
│ (extractor.extract() - line 127)                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────┐
         │ Find longest LED ON segment        │
         │ Check duration & point count       │
         └────────────────────────────────────┘
                              ↓
         Duration ≥ 10s AND Points ≥ 50?
           ├─ YES → Attempt fitting
           └─ NO  → return None (too short for reliable fitting)


┌─────────────────────────────────────────────────────────────────┐
│ Level 5: FIT QUALITY VALIDATION                                 │
│ (extractor.extract() - line 145)                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────┐
         │ Run Numba-accelerated fitting      │
         │ Check convergence & R²             │
         └────────────────────────────────────┘
                              ↓
         Converged AND R² ≥ 0.5?
           ├─ YES → Extract metric
           └─ NO  → return None (poor fit, unusable result)


┌─────────────────────────────────────────────────────────────────┐
│ FINAL OUTPUT                                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────────────────────┐
         │ DerivedMetric with:                 │
         │ - τ (relaxation time)               │
         │ - β (stretching exponent)           │
         │ - Confidence score                  │
         │ - Warning flags (if any)            │
         └────────────────────────────────────┘
```

---

## Detailed Filtering Logic

### Level 1: Procedure Type Matching

**Location:** `MetricPipeline.__init__()` (line 111-116)

When the pipeline initializes, it builds an **extractor_map**:

```python
# In MetricPipeline.__init__
self.extractor_map = {}
for extractor in self.extractors:
    for proc in extractor.applicable_procedures:
        self.extractor_map[proc].append(extractor)

# Result:
# {
#   "IVg": [CNPExtractor()],
#   "VVg": [CNPExtractor()],
#   "It": [PhotoresponseExtractor()],
#   "Vt": [PhotoresponseExtractor()],
#   "ITS": [PhotoresponseExtractor(), ITSRelaxationExtractor()],  ← Multiple!
#   "ITt": [PhotoresponseExtractor(), ITSRelaxationExtractor()],
# }
```

**ITSRelaxationExtractor declares:**
```python
@property
def applicable_procedures(self) -> List[str]:
    return ["ITS", "ITt"]
```

**Result:** ITSRelaxationExtractor ONLY runs on ITS and ITt measurements.

---

**Location:** `MetricPipeline.derive_all_metrics()` (line 232-234)

```python
# Filter manifest to only procedures with extractors
applicable_procs = list(self.extractor_map.keys())
manifest = manifest.filter(pl.col("proc").is_in(applicable_procs))
```

**Example:**
- Total measurements: 500
- IVg: 100, It: 50, **ITS: 30**, IV: 200, LaserCalibration: 120
- After filter: 180 measurements (IVg + It + ITS only)

---

### Level 2: Required Columns Check

**Location:** `ITSRelaxationExtractor.extract()` (line 101-103)

```python
# Validate columns
required_cols = {"t (s)", "I (A)", "VL (V)"}
if not required_cols.issubset(measurement.columns):
    return None  # ← Silently skip, no metric extracted
```

**Why this is needed:**
- Old ITS measurements might not have VL column
- Different ITS variants might have different columns
- Schema evolution over time

**Result:** Measurements missing VL are skipped (can't detect LED state).

---

### Level 3: LED State Detection

**Location:** `ITSRelaxationExtractor.extract()` (line 111-115)

```python
# Identify LED ON period
led_on_mask = vl > self.vl_threshold  # Default: 0.1V

if not np.any(led_on_mask):
    # No LED ON period detected
    return None
```

**Physical interpretation:**
- `VL < 0.1V` → LED OFF (dark measurement)
- `VL > 0.1V` → LED ON (photoresponse expected)

**Example measurement:**
```
Time (s)  |  VL (V)  |  I (A)      |  State
----------|----------|-------------|--------
0         |  0.0     |  1.1e-6     |  DARK
10        |  0.0     |  1.1e-6     |  DARK
20        |  5.0     |  1.6e-6     |  LIGHT ← LED ON
80        |  5.0     |  1.3e-6     |  LIGHT
100       |  0.0     |  1.1e-6     |  DARK
```

**Result:** Only measurements with LED ON periods pass this filter.

**Edge cases that get filtered:**
- Completely dark ITS measurements (VL always 0)
- Measurements where LED failed (VL stuck at 0)

---

### Level 4: Segment Duration & Data Quality

**Location:** `ITSRelaxationExtractor.extract()` (line 127-131)

```python
# Find longest continuous LED ON segment
segment_start, segment_end = led_on_segment
segment_duration = time[segment_end] - time[segment_start]

# Check if segment is long enough
if segment_duration < self.min_led_on_time:  # Default: 10s
    return None

if segment_end - segment_start < self.min_points_for_fit:  # Default: 50
    return None
```

**Why both checks?**

1. **Duration check (≥ 10s):**
   - Stretched exponential fitting needs time to observe relaxation
   - Too short → can't distinguish τ values (everything looks instant)
   - Example: 2-second pulse looks the same whether τ=5s or τ=20s

2. **Point count check (≥ 50):**
   - Need enough data points for reliable Jacobian computation
   - Levenberg-Marquardt needs 4 parameters → at least 10-20x oversampling
   - Example: 20 points can't reliably fit 4 parameters

**Example scenarios:**

| Scenario | Duration | Points | Result |
|----------|----------|--------|--------|
| Long pulse, high sampling | 60s | 900 | ✅ PASS |
| Short pulse, high sampling | 3s | 150 | ❌ FAIL (too short) |
| Long pulse, low sampling | 60s | 20 | ❌ FAIL (too few points) |
| Multiple short pulses | 5s × 3 | 75 each | ❌ FAIL (uses longest=5s) |

---

### Level 5: Fit Quality Validation

**Location:** `ITSRelaxationExtractor.extract()` (line 145-147)

```python
# Check fit quality
if not fit_result['converged'] or fit_result['r_squared'] < 0.5:
    # Poor fit quality
    return None
```

**Two-part quality gate:**

1. **Convergence check:**
   - Levenberg-Marquardt reached convergence (cost change < tolerance)
   - If not converged → parameters unreliable

2. **R² threshold (≥ 0.5):**
   - R² = 1 - (SS_residual / SS_total)
   - R² < 0.5 means model explains < 50% of variance
   - Usually indicates wrong model or extremely noisy data

**What causes poor fits?**
- **Non-exponential photoresponse** (e.g., linear drift, step function)
- **Extreme noise** (sensor malfunction, electrical interference)
- **Temperature drift** (baseline shifts during measurement)
- **Multiple competing processes** (can't fit with single exponential)

**Example:**
```
Measurement A:
  R² = 0.95, converged = True   → ✅ PASS (excellent fit)

Measurement B:
  R² = 0.35, converged = True   → ❌ FAIL (model doesn't fit data)

Measurement C:
  R² = 0.88, converged = False  → ❌ FAIL (didn't converge)
```

---

## Complete Example

Let's trace one measurement through all 5 levels:

### Input: ITS measurement `Alisson67_052.csv`

**manifest.parquet row:**
```python
{
    "run_id": "abc123def456",
    "chip_number": 67,
    "chip_group": "Alisson",
    "proc": "ITS",  # ← Level 1: MATCHES!
    "parquet_path": "data/02_stage/raw_measurements/ITS/abc123def456.parquet",
    "timestamp_local": "2024-10-15 14:30:00",
    ...
}
```

**Level 1 - Procedure Match:**
```python
extractor_map["ITS"]  # → [PhotoresponseExtractor, ITSRelaxationExtractor]
# ✅ PASS: ITS is in applicable_procedures
```

---

**Load measurement data:**
```python
measurement = pl.DataFrame({
    "t (s)": [0, 1, 2, ..., 200],   # 3000 points
    "I (A)": [1.1e-6, ...],
    "VL (V)": [0.0, ..., 5.0, ..., 0.0],  # LED pulse
    "Vds (V)": [0.1, ...]
})
```

**Level 2 - Column Check:**
```python
required_cols = {"t (s)", "I (A)", "VL (V)"}
measurement.columns = ["t (s)", "I (A)", "VL (V)", "Vds (V)"]
# ✅ PASS: All required columns present
```

---

**Level 3 - LED Detection:**
```python
vl = [0, 0, 0, ..., 5.0, 5.0, 5.0, ..., 0, 0]  # 3000 values
led_on_mask = vl > 0.1
# → [False, False, ..., True, True, True, ..., False]
np.any(led_on_mask)  # → True
# ✅ PASS: LED ON period detected (t=20s to t=80s)
```

---

**Level 4 - Segment Quality:**
```python
# Find longest segment
segment_start = 300   # index where VL goes high
segment_end = 1200    # index where VL goes low
segment_duration = time[1200] - time[300]  # = 60s
n_points = 1200 - 300  # = 900 points

segment_duration >= 10.0  # 60 >= 10 → ✅ PASS
n_points >= 50            # 900 >= 50 → ✅ PASS
```

---

**Level 5 - Fit Quality:**
```python
# Extract segment and fit
t_segment = time[300:1200] - time[300]  # Reset to 0
i_segment = current[300:1200]

fit_result = fit_stretched_exponential(t_segment, i_segment)
# → {
#     'tau': 18.5,
#     'beta': 0.68,
#     'r_squared': 0.94,  # ← Good fit!
#     'converged': True,  # ← Converged!
#     ...
# }

fit_result['converged']  # True  → ✅
fit_result['r_squared'] >= 0.5  # 0.94 >= 0.5 → ✅ PASS
```

---

**FINAL RESULT:**
```python
DerivedMetric(
    run_id="abc123def456",
    chip_number=67,
    metric_name="relaxation_time",
    metric_category="photoresponse",
    value_float=18.5,  # τ in seconds
    value_json='{"tau": 18.5, "beta": 0.68, "r_squared": 0.94, ...}',
    confidence=0.92,  # High confidence (good R²)
    flags=None,  # No warnings
    ...
)
```

---

## What Gets Filtered Out?

### ❌ Measurements that NEVER reach the extractor

**Reason:** Wrong procedure type (Level 1)

```python
# These procedures don't have ITSRelaxationExtractor
manifest.proc = "IVg"  → CNPExtractor only
manifest.proc = "It"   → PhotoresponseExtractor only
manifest.proc = "IV"   → No extractors
```

### ❌ Measurements that fail column check (Level 2)

**Reason:** Missing VL column

```
Old ITS measurements before VL was added:
  columns = ["t (s)", "I (A)", "Vds (V)"]  # No VL
  → return None
```

### ❌ Measurements that fail LED detection (Level 3)

**Reason:** Dark measurements (no LED ON period)

```
Dark stability test:
  VL = [0.0, 0.0, 0.0, ..., 0.0]  # LED never turned on
  → return None (can't fit relaxation without photoresponse)
```

### ❌ Measurements that fail segment quality (Level 4)

**Reason:** Too short or too few points

```
Short LED pulse:
  LED ON: 20s → 25s (duration = 5s)
  → return None (< 10s minimum)

Low sampling rate:
  LED ON: 20s → 80s (duration = 60s)
  Points: 30 (0.5 Hz sampling)
  → return None (< 50 points minimum)
```

### ❌ Measurements that fail fit quality (Level 5)

**Reason:** Poor fit or non-convergence

```
Temperature drift during measurement:
  Baseline shifts from 1.0e-6 to 1.5e-6 during LED ON
  → Stretched exponential model doesn't fit
  → R² = 0.25 (< 0.5 threshold)
  → return None
```

---

## Summary Table

| Level | Filter | Pass Rate | Typical Failures |
|-------|--------|-----------|------------------|
| 1. Procedure | `proc IN ["ITS", "ITt"]` | 5-10% | Wrong measurement type |
| 2. Columns | Has `t, I, VL` | 95-100% | Old data without VL |
| 3. LED State | `any(VL > 0.1)` | 70-90% | Dark measurements |
| 4. Segment | Duration ≥ 10s, Points ≥ 50 | 80-95% | Short pulses, low sampling |
| 5. Fit Quality | Converged & R² ≥ 0.5 | 85-98% | Noisy data, wrong model |

**Overall pass rate:** ~30-50% of all measurements get relaxation time extracted

**This is expected!** Not every measurement is suitable for relaxation time fitting:
- Dark measurements (testing LED-off baseline)
- Short LED pulses (different analysis)
- Gate voltage sweeps during LED ON (changing conditions)
- Calibration measurements (different purpose)

---

## Configuration

You can adjust the filtering thresholds:

```python
from src.derived.extractors import ITSRelaxationExtractor

# Relaxed filtering (more measurements pass)
extractor = ITSRelaxationExtractor(
    vl_threshold=0.05,       # Lower LED detection (default: 0.1)
    min_led_on_time=5.0,     # Accept shorter pulses (default: 10.0)
    min_points_for_fit=30    # Fewer points required (default: 50)
)

# Strict filtering (only highest quality)
extractor = ITSRelaxationExtractor(
    vl_threshold=0.2,        # Higher LED detection (default: 0.1)
    min_led_on_time=30.0,    # Only long exposures (default: 10.0)
    min_points_for_fit=100   # More points for stability (default: 50)
)
```

**Trade-offs:**
- **Relaxed:** More metrics extracted, but lower average quality
- **Strict:** Fewer metrics, but higher confidence in results

---

## See Also

- **Implementation:** `src/derived/extractors/its_relaxation_extractor.py`
- **Pipeline:** `src/derived/metric_pipeline.py`
- **Usage:** `docs/ITS_RELAXATION_TIME_EXTRACTOR.md`
- **Architecture:** `docs/DERIVED_METRICS_ARCHITECTURE.md`
