## Plot Utils Migration - COMPLETED ✓

### What Was Done

**1. Created centralized `plot_utils.py`** with:
   - Metadata extractors: `get_wavelength_nm()`, `get_gate_voltage()`, `get_led_voltage()`, `get_irradiated_power()`
   - Column normalization: `ensure_standard_columns()` (replaces ~10 lines of inline code per module)
   - Baseline utilities: `interpolate_baseline()`
   - CNP extraction: `extract_cnp_for_plotting()` (for IVg/VVg overlays)
   - Context manager: `plot_context()` (for future theme/output configuration)
   - Caching: `ParquetCache()` class
   - Rich console helpers: `print_info()`, `print_warning()`, `print_error()`, `print_success()`

**2. Updated plotting modules:**
   - ✅ `its.py` - Uses all plot_utils functions
   - ✅ `vt.py` - Fixed 3 function name bugs (`_get_wavelength_nm` → `get_wavelength_nm`, etc.)
   - ✅ `ivg.py` - Replaced inline column normalization
   - ✅ `vvg.py` - Replaced inline column normalization
   - ✅ `transconductance.py` - Replaced 2 instances of inline normalization

**3. Code reduction:**
   - Eliminated ~50-100 lines of duplicated column normalization code
   - Centralized metadata extraction logic (easier to maintain)
   - All syntax checks passed ✓

### Testing Checklist

Run these commands to verify plots still generate correctly:

```bash
# Test ITS plotting (most complex module with baseline modes)
python3 process_and_analyze.py plot-its 67 --auto

# Test Vt plotting (just fixed 3 bugs)
python3 process_and_analyze.py plot-vt 67 --auto

# Test IVg plotting (voltage sweep)
python3 process_and_analyze.py plot-ivg 67 --auto

# Test VVg plotting (voltage sweep)
python3 process_and_analyze.py plot-vvg 67 --auto

# Test transconductance (derivative calculations)
python3 process_and_analyze.py plot-transconductance 67 --auto
```

### Files Modified

- `src/plotting/plot_utils.py` - **NEW** centralized utilities
- `src/plotting/its.py` - Updated to use plot_utils
- `src/plotting/vt.py` - Fixed bugs + uses plot_utils
- `src/plotting/ivg.py` - Simplified with plot_utils
- `src/plotting/vvg.py` - Simplified with plot_utils
- `src/plotting/transconductance.py` - Simplified with plot_utils

### Future Enhancements (Optional)

- Migrate remaining modules (cnp_time.py, photoresponse.py, laser_calibration.py) if they have inline normalization
- Use `plot_context()` manager to make themes/output dirs configurable from CLI
- Add `ParquetCache` to overlay functions for performance boost on repeated reads
- Consider moving more shared plotting logic (light window calculation, y-axis padding) to plot_utils
