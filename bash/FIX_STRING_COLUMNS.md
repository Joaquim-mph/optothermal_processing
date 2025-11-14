# Fix for String Column Types in Enriched History

## Problem

Your enriched history files have `cnp_voltage` and `delta_current` stored as **strings** instead of **floats**. This causes errors when plotting:

```
InvalidOperationError: `is_not_nan` operation not supported for dtype `str`
```

## Cause

This happens when:
1. The enriched history was created with an older version of the pipeline
2. The metrics were extracted incorrectly as strings

## Solution (Quick Fix - RECOMMENDED)

**Option 1: Regenerate enriched history** (Best solution)

```bash
source .venv/bin/activate

# Remove old enriched history
rm -rf data/03_derived/chip_histories_enriched/

# Regenerate with correct types
python3 process_and_analyze.py enrich-history -a
```

This will:
- ✅ Reload metrics with correct float types
- ✅ Create properly typed enriched histories
- ✅ Fix all string column issues

**Option 2: Use fixed scripts** (Temporary workaround)

I've already fixed the plotting code to handle string columns automatically, so the scripts will work now. But for best performance and to avoid future issues, I recommend Option 1.

## Verification

After regenerating, verify the types are correct:

```bash
python3 -c "
import polars as pl
history = pl.read_parquet('data/03_derived/chip_histories_enriched/chip_67_history.parquet')
print('cnp_voltage type:', history.schema['cnp_voltage'])
print('delta_current type:', history.schema['delta_current'])
"
```

Expected output:
```
cnp_voltage type: Float64
delta_current type: Float64
```

## What I Fixed

I've updated these files to handle string columns gracefully:
1. **`src/cli/commands/plot_cnp.py`** - Detects and reloads string `cnp_voltage`
2. **`src/plotting/photoresponse.py`** - Casts string `delta_current` to float
3. **`bash/alisson67_analysis_v2.sh`** - Uses correct `--wavelength` flag and graceful error handling

## Run the Script Again

Now you can run the improved script:

```bash
source .venv/bin/activate
./bash/alisson67_analysis_v2.sh
```

It should complete successfully! If you get other errors, they're likely due to missing data (not type issues).
