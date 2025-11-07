# CNP Extractor Guide

**Last Updated:** October 31, 2025
**Version:** 3.0+

## Overview

The CNP (Charge Neutrality Point) extractor is a sophisticated algorithm for detecting the gate voltage where resistance is maximum in IVg/VVg measurements. It handles complex sweep patterns and hysteresis effects common in 2D material devices.

## Key Features

### 1. Automatic Sweep Segmentation
- Detects direction changes in Vg sweeps
- Handles complex patterns: 0→-Vgmax→0→+Vgmax→0→-Vgmax→0
- Analyzes each segment independently

### 2. Robust Peak Detection
- Uses scipy.signal.find_peaks with prominence threshold
- Filters noise and minor fluctuations
- Finds highest resistance point in each segment

### 3. Hysteresis Handling
- Detects CNP shifts between forward/backward sweeps
- Uses hierarchical clustering (default threshold: 0.5V)
- Groups nearby CNPs (measurement uncertainty) or separates them (true hysteresis)

### 4. Quality Assessment
- **Confidence scores** (0-1): Based on data quality checks
- **Flags**: Human-readable warnings for manual review
  - `MULTIPLE_CLUSTERS`: More than one CNP group detected
  - `HIGH_HYSTERESIS`: >1V shift between clusters
  - `AT_EDGE`: CNP near sweep boundary (might be out of range)
  - `LOW_RESISTANCE`: <2x modulation (weak CNP signal)

## Algorithm Details

### Step 1: Segment Detection
```python
# Detect direction changes in Vg
diff = np.diff(vg)
direction = np.sign(diff)
direction_changes = np.where(np.diff(direction) != 0)[0] + 1
segments = np.split(np.arange(len(vg)), direction_changes)
```

### Step 2: Peak Finding
```python
# Find resistance peaks in each segment
prominence_threshold = np.ptp(r_seg) * prominence_factor  # Default: 10%
peaks, properties = find_peaks(r_seg, prominence=prominence_threshold)

# Take highest resistance peak
top_peak_idx = np.argmax(r_seg[peaks])
cnp_vg = vg_seg[peaks[top_peak_idx]]
```

### Step 3: Clustering
```python
# Cluster CNPs by voltage proximity
from scipy.cluster.hierarchy import fclusterdata
clusters = fclusterdata(
    cnp_voltages.reshape(-1, 1),
    t=cluster_threshold_v,  # Default: 0.5V
    criterion='distance',
    method='single'
)
```

### Step 4: Result Aggregation
- Average CNP across all clusters
- Per-cluster statistics (mean, std, directions)
- Confidence scoring based on quality checks
- JSON output with complete analysis

## Usage

### Basic Usage

```python
from pathlib import Path
from src.core.utils import read_measurement_parquet
from src.derived.extractors.cnp_extractor import CNPExtractor

# Load measurement
measurement = read_measurement_parquet(parquet_path)

# Metadata from manifest
metadata = {
    'run_id': 'abc123...',
    'chip_number': 75,
    'chip_group': 'Alisson',
    'procedure': 'IVg',
    'seq_num': 1,
    'vds_v': 0.1,  # Required for IVg
    'extraction_version': 'v0.1.0'
}

# Extract CNP
extractor = CNPExtractor()
result = extractor.extract(measurement, metadata)

# Access results
print(f"CNP: {result.value_float:.3f}V")
print(f"Confidence: {result.confidence:.2f}")
print(f"Flags: {result.flags or 'None'}")

# Parse detailed results
import json
details = json.loads(result.value_json)
print(f"Number of clusters: {details['n_clusters']}")
for cluster in details['clusters']:
    print(f"  Cluster {cluster['cluster_id']}: {cluster['vg_mean']:.3f}V")
```

### Custom Configuration

```python
# Adjust parameters for your samples
extractor = CNPExtractor(
    cluster_threshold_v=0.3,    # Stricter clustering (group if <0.3V apart)
    prominence_factor=0.15,     # More selective peak detection (15%)
    min_segment_points=20       # Require 20+ points per segment
)
```

### Batch Processing

```python
from src.derived import MetricPipeline

# Process all IVg measurements
pipeline = MetricPipeline(Path("."))
metrics_path = pipeline.derive_all_metrics(
    procedures=["IVg"],
    parallel=True,
    workers=6
)

# Results saved to: data/03_derived/_metrics/metrics.parquet
```

### Visualization

```python
from src.derived.cnp_visualization import plot_cnp_detection, compare_cnp_measurements

# Single measurement
plot_cnp_detection(measurement, metadata, save_path="cnp_analysis.png")

# Compare multiple measurements for a chip
compare_cnp_measurements(
    chip_number=75,
    chip_group="Alisson",
    max_plots=10,
    save_dir=Path("figs/cnp_analysis")
)
```

## Test Results

### Alisson 75 (Hysteresis Case)

```
CNP (average): 0.450 V
Number of clusters: 2
  - Cluster 1: +0.050V (forward sweep)
  - Cluster 2: +0.850V (backward sweep)
Hysteresis: 0.800V shift
Confidence: 0.12
Flags: HIGH_HYSTERESIS, AT_EDGE, LOW_RESISTANCE
```

**Interpretation**: Strong hysteresis detected. The CNP shifts by 0.8V between forward and backward sweeps, indicating significant charge trapping or device instability.

### Alisson 81 (Single CNP)

```
CNP (average): 0.300 V
Number of clusters: 1
  - Forward: +0.350V
  - Backward: +0.250V
  - Spread: 0.100V
Confidence: 0.10
Flags: MULTIPLE_CLUSTERS, HIGH_HYSTERESIS, AT_EDGE, LOW_RESISTANCE
```

**Interpretation**: Minor variation (0.1V) clustered as single CNP. This is likely measurement uncertainty rather than true hysteresis.

## Output Data Structure

### DerivedMetric Fields

```python
result.value_float       # Average CNP voltage (V)
result.unit              # "V"
result.confidence        # Quality score (0-1)
result.flags             # Comma-separated warnings
result.value_json        # Complete analysis (JSON string)
```

### JSON Detail Structure

```json
{
  "n_clusters": 2,
  "cnp_avg": 0.450,
  "cnp_spread_v": 0.400,
  "all_cnps": [
    {"vg": 0.05, "r": 2890.0, "segment": 1, "direction": "forward"},
    {"vg": 0.85, "r": 3100.0, "segment": 2, "direction": "backward"}
  ],
  "clusters": [
    {
      "cluster_id": 1,
      "n_points": 1,
      "vg_mean": 0.05,
      "vg_std": 0.0,
      "vg_min": 0.05,
      "vg_max": 0.05,
      "directions": ["forward"],
      "resistances": [2890.0]
    },
    {
      "cluster_id": 2,
      "n_points": 1,
      "vg_mean": 0.85,
      "vg_std": 0.0,
      "vg_min": 0.85,
      "vg_max": 0.85,
      "directions": ["backward"],
      "resistances": [3100.0]
    }
  ]
}
```

## Parameter Tuning Guide

### cluster_threshold_v (default: 0.5V)

**Purpose**: Voltage threshold for grouping CNPs

- **Lower values** (e.g., 0.2V): Stricter clustering, more separate groups
  - Use for: High-precision measurements, detecting small hysteresis
- **Higher values** (e.g., 1.0V): More forgiving, groups more CNPs together
  - Use for: Noisy data, when you want to average over larger variations

**Example cases**:
- 0.1V spread → 1 cluster (measurement uncertainty)
- 0.8V spread → 2 clusters (true hysteresis)
- 2.0V spread → 2+ clusters (multiple CNPs or device degradation)

### prominence_factor (default: 0.1)

**Purpose**: Peak detection sensitivity (fraction of resistance range)

- **Lower values** (e.g., 0.05): More sensitive, finds smaller peaks
  - Use for: Weak CNP signals, low-modulation devices
  - Caution: May detect noise as peaks
- **Higher values** (e.g., 0.2): More selective, only finds prominent peaks
  - Use for: Noisy data, ensuring only strong CNPs are detected
  - Caution: May miss weak but real CNPs

**Example**:
- R range: 1kΩ to 10kΩ (9kΩ range)
- prominence_factor=0.1 → minimum prominence = 900Ω
- Only peaks with 900Ω+ prominence are detected

### min_segment_points (default: 10)

**Purpose**: Minimum points required to analyze a segment

- **Lower values** (e.g., 5): Analyze shorter segments
  - Use for: Fast sweeps, limited data points
- **Higher values** (e.g., 20): More robust statistics
  - Use for: Ensuring enough data for reliable peak detection

## Troubleshooting

### Issue: No CNP detected

**Possible causes**:
1. Too few data points (< min_segment_points)
2. Prominence threshold too high (no peaks meet criteria)
3. Resistance too flat (no clear maximum)

**Solutions**:
- Lower `prominence_factor` (e.g., 0.05)
- Lower `min_segment_points` (e.g., 5)
- Check if measurement is valid (sweep range, data quality)

### Issue: Too many clusters

**Possible causes**:
1. Cluster threshold too strict
2. High noise causing multiple peaks
3. Device degradation during sweep

**Solutions**:
- Increase `cluster_threshold_v` (e.g., 1.0V)
- Increase `prominence_factor` to ignore minor peaks
- Inspect visualization to understand behavior

### Issue: Low confidence scores

**This is expected!** Low confidence doesn't mean extraction failed:

- Confidence reflects data quality and potential issues
- Flags help you decide if results are trustworthy
- Visual inspection (use plot_cnp_detection) is recommended

**Common reasons for low confidence**:
- `LOW_RESISTANCE`: Weak on/off modulation (<2x)
- `AT_EDGE`: CNP near boundary (may be out of range)
- `HIGH_HYSTERESIS`: Large shift (>1V) suggests instability

## Validation Criteria

The extractor's `validate()` method checks:

1. **Value exists**: `value_float is not None`
2. **Physical range**: `-15V ≤ CNP ≤ +15V`
3. **Confidence > 0**: Some extraction succeeded

**Note**: Validation passing doesn't guarantee high quality. Always check confidence and flags!

## Best Practices

1. **Always visualize first**: Use `plot_cnp_detection()` on a few samples before batch processing
2. **Tune parameters**: Adjust based on your device characteristics
3. **Check flags**: Review flagged measurements manually
4. **Compare over time**: Use `compare_cnp_measurements()` to track CNP evolution
5. **Use confidence filtering**: Filter by `confidence > 0.5` for high-quality data only

## Integration with Pipeline

The CNP extractor is automatically registered in the default pipeline:

```python
# In metric_pipeline.py
def _default_extractors(self):
    return [
        CNPExtractor(cluster_threshold_v=0.5, prominence_factor=0.1),
        # ... other extractors
    ]
```

To run:

```bash
# Extract all IVg metrics
python3 process_and_analyze.py derive-all-metrics --proc IVg

# Create enriched history with CNP column
python3 process_and_analyze.py enrich-history 75
```

## References

- **Sweep segmentation**: Direction change detection via np.diff
- **Peak finding**: scipy.signal.find_peaks with prominence
- **Clustering**: scipy.cluster.hierarchy.fclusterdata (single-linkage)
- **Quality scoring**: Custom confidence computation with penalty factors

## Future Enhancements

Potential improvements:
1. **Adaptive prominence**: Auto-tune based on signal-to-noise ratio
2. **Multiple peaks per segment**: Handle bilayer graphene or van Hove singularities
3. **Temporal tracking**: Detect CNP drift across measurement sequence
4. **Temperature dependence**: Analyze CNP vs T for IVgT measurements
5. **Machine learning**: Train classifier to predict confidence from features
