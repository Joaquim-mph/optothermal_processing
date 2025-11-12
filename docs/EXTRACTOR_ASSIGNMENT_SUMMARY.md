# Extractor Assignment Summary

**Updated:** November 8, 2025
**Purpose:** Clear documentation of which extractors run on which procedures

---

## Complete Extractor Assignment Table

| Procedure | Extractors | Metrics Extracted |
|-----------|-----------|-------------------|
| **It** | PhotoresponseExtractor<br>ITSRelaxationExtractor | `photoresponse` (simple ΔI)<br>`relaxation_time` (dark τ & β) |
| **ITt** | PhotoresponseExtractor<br>ITSThreePhaseFitExtractor | `photoresponse` (simple ΔI)<br>`its_three_phase_relaxation` (3-phase fit) |
| **ITS** | ITSThreePhaseFitExtractor | `its_three_phase_relaxation` (3-phase fit) |
| **Vt** | PhotoresponseExtractor | `photoresponse` (simple ΔV) |
| **IVg** | CNPExtractor | `cnp_voltage` |
| **VVg** | CNPExtractor | `cnp_voltage` |

---

## Extractor Details

### 1. PhotoresponseExtractor
**Metric:** `photoresponse` (or `delta_current` / `delta_voltage`)
**Method:** Simple subtraction: ΔI = I_last - I_first
**Applicable to:** It, ITt, Vt
**Speed:** Instant
**Purpose:** Quick photoresponse magnitude screening

**Output:**
```json
{
    "delta": 0.38e-6,
    "mean_on": 1.48e-6,
    "mean_off": 1.10e-6,
    "response_ratio": 0.345,
    "snr": 12.5
}
```

---

### 2. ITSRelaxationExtractor
**Metric:** `relaxation_time`
**Method:** Stretched exponential fitting (Numba-accelerated)
**Applicable to:** **It only** (dark segments)
**Configuration:** `fit_segment="dark"` (LED OFF periods)
**Speed:** 0.3-50 ms
**Purpose:** Dark relaxation dynamics from It measurements

**Output:**
```json
{
    "tau": 25.3,
    "beta": 0.68,
    "amplitude": -0.4e-6,
    "baseline": 1.0e-6,
    "r_squared": 0.94,
    "segment_type": "dark"
}
```

**Why It only:**
- It measurements are typically short with dark segments
- ITS measurements use ITSThreePhaseFitExtractor for complete 3-phase analysis
- Avoids redundant fitting (ITSThreePhaseFitExtractor already fits light & dark for ITS)

---

### 3. ITSThreePhaseFitExtractor
**Metric:** `its_three_phase_relaxation`
**Method:** 3× stretched exponential fits (PRE-DARK, LIGHT, POST-DARK)
**Applicable to:** ITS, ITt
**Speed:** ~1-10 ms (3 fits with Numba)
**Purpose:** Complete relaxation dynamics across full LED cycle

**Output:**
```json
{
    "pre_dark": {
        "tau": 125.3,
        "beta": 0.82,
        "r_squared": 0.89,
        ...
    },
    "light": {
        "tau": 15.2,
        "beta": 0.68,
        "r_squared": 0.96,
        ...
    },
    "post_dark": {
        "tau": 42.5,
        "beta": 0.71,
        "r_squared": 0.93,
        ...
    },
    "phases_fitted": ["pre_dark", "light", "post_dark"],
    "all_phases_present": true
}
```

**Why ITS/ITt:**
- ITS measurements are long with complete OFF→ON→OFF cycles
- Each phase ≥60s (meets minimum duration requirement)
- Provides comprehensive relaxation characterization

---

### 4. CNPExtractor
**Metric:** `cnp_voltage`
**Method:** Peak detection + hierarchical clustering
**Applicable to:** IVg, VVg
**Speed:** Fast (scipy-based)
**Purpose:** Charge neutrality point (Dirac point) extraction

**Output:**
```json
{
    "cnp_voltage": -0.42,
    "cnp_resistance": 125000.0,
    "n_cnps_detected": 3,
    "cluster_id": 1,
    ...
}
```

---

## Measurement Type Analysis

### It Measurements (Short, typically 10-60s)
```
Extractors that run:
├─ PhotoresponseExtractor → photoresponse
│   └─ Simple ΔI = I_last - I_first
│
└─ ITSRelaxationExtractor → relaxation_time
    └─ Fit dark segments (LED OFF periods)
    └─ Skip if no dark segments ≥10s
```

**Why both:**
- PhotoresponseExtractor gives total magnitude (fast)
- ITSRelaxationExtractor gives dark dynamics (detailed)

---

### ITS Measurements (Long, typically 100-1000s)
```
Extractors that run:
└─ ITSThreePhaseFitExtractor → its_three_phase_relaxation
    ├─ PRE-DARK phase: τ₁, β₁
    ├─ LIGHT phase: τ₂, β₂
    └─ POST-DARK phase: τ₃, β₃
```

**Why not PhotoresponseExtractor:**
- ITS doesn't match PhotoresponseExtractor.applicable_procedures
- Three-phase fit provides complete information

**Why not ITSRelaxationExtractor:**
- ITSRelaxationExtractor only applies to It (by design)
- Three-phase fit already covers light AND dark phases

---

### ITt Measurements (Mixed characteristics)
```
Extractors that run:
├─ PhotoresponseExtractor → photoresponse
│   └─ Simple ΔI for quick screening
│
└─ ITSThreePhaseFitExtractor → its_three_phase_relaxation
    └─ 3-phase fit if measurement has complete cycle
```

**Why both:**
- PhotoresponseExtractor always runs (simple, fast)
- ITSThreePhaseFitExtractor runs if phases ≥60s

---

## Key Design Decisions

### Why ITSRelaxationExtractor only on It?

**Original design (before):**
- Applied to: ITS, ITt
- Purpose: General relaxation fitting

**Updated design (now):**
- Applied to: **It only**
- Purpose: **Dark It measurements**
- Reason: Avoid redundancy with ITSThreePhaseFitExtractor

**Benefits:**
1. **Clear separation of concerns:**
   - It → Dark relaxation only (ITSRelaxationExtractor)
   - ITS → Complete 3-phase analysis (ITSThreePhaseFitExtractor)

2. **No redundant fitting:**
   - ITS gets comprehensive 3-phase fit (includes light & dark)
   - It gets focused dark relaxation fit

3. **Optimized for measurement type:**
   - It is typically shorter → single dark segment fit
   - ITS is longer → multi-phase fit

---

### Why PhotoresponseExtractor still on It?

Even though ITSRelaxationExtractor also runs on It, PhotoresponseExtractor serves a different purpose:

| Feature | PhotoresponseExtractor | ITSRelaxationExtractor |
|---------|------------------------|------------------------|
| **Method** | Simple subtraction | Stretched exponential fitting |
| **Speed** | Instant (<0.01 ms) | 0.3-50 ms |
| **Output** | Total ΔI magnitude | Full dynamics (τ, β) |
| **Use case** | Quick screening | Detailed analysis |
| **Segments** | Full LED ON period | Dark segments only |

**Both are useful!** Simple ΔI for quick assessment, fitting for detailed dynamics.

---

## Configuration

Current default configuration in `src/derived/metric_pipeline.py`:

```python
def _default_extractors(self):
    return [
        CNPExtractor(
            cluster_threshold_v=0.5,
            prominence_factor=0.1
        ),

        PhotoresponseExtractor(
            vl_threshold=0.1,
            min_samples_per_state=5
        ),

        ITSRelaxationExtractor(
            vl_threshold=0.1,
            min_led_on_time=10.0,
            min_points_for_fit=50,
            fit_segment="dark"  # ← Dark It only
        ),

        ITSThreePhaseFitExtractor(
            vl_threshold=0.1,
            min_phase_duration=60.0,  # 1 minute minimum
            min_points_for_fit=50,
            require_all_phases=True
        ),
    ]
```

---

## Usage Examples

### Extract all metrics
```bash
python3 process_and_analyze.py derive-all-metrics
```

### Extract for specific procedures
```bash
# It measurements (dark relaxation + simple ΔI)
python3 process_and_analyze.py derive-all-metrics --procedures It

# ITS measurements (3-phase relaxation)
python3 process_and_analyze.py derive-all-metrics --procedures ITS

# Gate sweeps (CNP)
python3 process_and_analyze.py derive-all-metrics --procedures IVg,VVg
```

### Extract for specific chip
```bash
python3 process_and_analyze.py derive-all-metrics --chip 67
```

---

## Expected Metrics Output

### For It measurement:
```
Chip 67, Seq 15 (It):
├─ photoresponse = 0.38 µA
│   └─ Simple ΔI (PhotoresponseExtractor)
│
└─ relaxation_time = 25.3 s
    └─ Dark τ (ITSRelaxationExtractor, fit_segment="dark")
```

### For ITS measurement:
```
Chip 67, Seq 52 (ITS):
└─ its_three_phase_relaxation
    ├─ PRE-DARK: τ₁=125s, β₁=0.82, R²=0.89
    ├─ LIGHT: τ₂=15.2s, β₂=0.68, R²=0.96
    └─ POST-DARK: τ₃=42.5s, β₃=0.71, R²=0.93
```

### For ITt measurement:
```
Chip 67, Seq 30 (ITt):
├─ photoresponse = 0.42 µA
│   └─ Simple ΔI (PhotoresponseExtractor)
│
└─ its_three_phase_relaxation
    └─ (Same as ITS if phases ≥60s)
```

### For IVg measurement:
```
Chip 67, Seq 8 (IVg):
└─ cnp_voltage = -0.42 V
    └─ CNP from resistance peak (CNPExtractor)
```

---

## Troubleshooting

### It: No relaxation_time extracted

**Possible causes:**
1. No dark segments (LED always on or very short off periods)
2. Dark segments < 10s (below minimum duration)
3. Dark segments < 50 points (below minimum point count)
4. Poor fit quality (R² < 0.5)

**Solutions:**
- Check VL column in measurement
- Lower `min_led_on_time` to 5s for shorter measurements
- Verify LED OFF periods are long enough

### ITS: No its_three_phase_relaxation extracted

**Possible causes:**
1. Incomplete LED cycle (missing PRE-DARK, LIGHT, or POST-DARK)
2. Phases < 60s (below minimum duration)
3. Poor fit quality in one or more phases

**Solutions:**
- Set `require_all_phases=False` to allow partial fitting
- Lower `min_phase_duration` to 45s or 30s
- Check that measurement has complete OFF→ON→OFF cycle

---

## Summary

| Measurement Type | Simple ΔI | Dark Relaxation | 3-Phase Relaxation |
|------------------|-----------|-----------------|-------------------|
| **It** | ✅ PhotoresponseExtractor | ✅ ITSRelaxationExtractor | ❌ |
| **ITt** | ✅ PhotoresponseExtractor | ❌ | ✅ ITSThreePhaseFitExtractor |
| **ITS** | ❌ | ❌ | ✅ ITSThreePhaseFitExtractor |
| **Vt** | ✅ PhotoresponseExtractor | ❌ | ❌ |
| **IVg/VVg** | ❌ | ❌ | ❌ CNPExtractor |

**Perfect separation!** Each extractor has a clear, non-overlapping purpose.

---

## Related Documentation

- **PhotoresponseExtractor:** `src/derived/extractors/photoresponse_extractor.py`
- **ITSRelaxationExtractor:** `docs/ITS_RELAXATION_TIME_EXTRACTOR.md`, `docs/DARK_ITS_RELAXATION_GUIDE.md`
- **ITSThreePhaseFitExtractor:** `docs/ITS_THREE_PHASE_FITTING_GUIDE.md`
- **CNPExtractor:** `docs/CNP_EXTRACTOR_GUIDE.md` (if exists)
- **Metric Pipeline:** `src/derived/metric_pipeline.py`
