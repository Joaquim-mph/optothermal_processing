# Compare photoresponse spectra: Alisson72 (hBN) vs Alisson81 (biotite)

## Purpose

Produce a single figure (plus a semilogy variant) that overlays the wavelength-sweep photoresponse (Δcurrent vs wavelength at matched laser power) of chip Alisson72 and chip Alisson81, so the effect of the gate dielectric (hBN on 72 vs biotite on 81) can be read off directly.

Both chips already have a same-power wavelength sweep configured in their batch-plot YAML files. This design adds a cross-chip overlay that those per-chip configs cannot produce.

## Scope

**In scope:**

- One standalone Python script that, when run, writes two PNGs under `figs/compare/`.
- Reuses existing plotting/data-loading code — no new library modules, no CLI plugin, no batch-plot entry.

**Out of scope (YAGNI):**

- CLI command integration (will be added once more dielectrics are characterised).
- Normalised / responsivity y-axes.
- Configurable chip pairs, argument parsing, or YAML config.
- Tests.

## Inputs

Hardcoded at the top of the script as module-level constants, mirroring the entries already in `config/batch_plots/alisson72_plots.yaml` and `config/batch_plots/alisson81_plots.yaml`:

| Chip | Group | Label    | Seq numbers                                  |
|------|-------|----------|----------------------------------------------|
| 72   | Alisson | `72 (hBN)`     | `[11, 16, 20, 24, 26, 28, 30, 32, 34, 36]`   |
| 81   | Alisson | `81 (biotite)` | `[4, 6, 8, 10, 12, 14, 16, 18, 33, 35]`      |

Enriched chip histories read from `data/03_derived/chip_histories_enriched/Alisson{N}_history.parquet`.

## Architecture

Single file: `scripts/compare_photoresponse_72_81.py`.

```
main()
├── for each (chip_number, label, seq_list) in CHIPS:
│   └── load_chip_curve(chip_number, seq_list) → (wavelengths_nm, delta_current_uA)
│       ├── read enriched Parquet via polars
│       ├── filter: seq ∈ seq_list, proc == "It", has_light == True
│       ├── resolve delta_current:
│       │     • if "delta_current" column present and not null → use it
│       │     • else call src.plotting.its_photoresponse._extract_delta_current_from_its
│       │       per row (uses parquet_path → read_measurement_parquet)
│       ├── sort by wavelength_nm
│       └── return numpy arrays (wavelength nm, |Δi| * 1e6)
├── make_figure(curves, axtype="linear") → PNG path
└── make_figure(curves, axtype="semilogy") → PNG path
```

`_extract_delta_current_from_its` is imported from `src.plotting.its_photoresponse` rather than copied. It already handles the VL-column light-window detection and the on-the-fly fallback.

`make_figure` is a local helper in the same script (not promoted to a library module yet). It:

- applies the repo style via `set_plot_style(PlotConfig().theme)`;
- uses `fig, ax = plt.subplots(figsize=PlotConfig().figsize_derived)`;
- plots each chip as `ax.plot(wl, di_uA, "o-", label=label)`;
- sets `ax.set_xlabel("Wavelength (nm)")` and `ax.set_ylabel("Δ Current (µA)")`;
- calls `ax.set_yscale("log")` only when `axtype == "semilogy"`;
- calls `ax.legend(loc="best", framealpha=0.9)`;
- no title, no `ax.grid(...)` (repo convention);
- saves with `PlotConfig().dpi` and `bbox_inches="tight"`.

## Outputs

Two files, both written to `figs/compare/` (directory created if missing — this is outside the standard chip-first hierarchy because it is a cross-chip plot):

- `alisson72_vs_81_ITS_photoresponse_vs_wavelength.png` (linear y)
- `alisson72_vs_81_ITS_photoresponse_vs_wavelength_semilogy.png` (log y)

Each file path is printed to stdout on save.

## Error handling

The script is one-shot, so failures should be loud and precise rather than recoverable:

- **Enriched history file missing** → raise `FileNotFoundError` with the expected path and a hint to run `biotite enrich-history <N>`.
- **Filtered history empty** after applying seq / proc / has_light → raise `ValueError` naming the chip and the seqs that survived each filter step, so it is obvious which filter dropped the rows.
- **`delta_current` column absent AND on-the-fly extraction returns None for every row** → raise `ValueError` for that chip; do not silently emit an empty curve.

No try/except swallowing — let exceptions propagate so the script exits non-zero.

## Dependencies

- `polars` — history loading and filtering.
- `numpy` — array math.
- `matplotlib.pyplot` — figures.
- `src.plotting.config.PlotConfig` — theme, dpi, figsize.
- `src.plotting.styles.set_plot_style` — matches repo aesthetic.
- `src.plotting.its_photoresponse._extract_delta_current_from_its` — on-the-fly fallback.
- `src.core.utils.read_measurement_parquet` — only reached via the fallback extractor.

All already present in the repo. No new pip installs.

## How it will be run

```bash
source .venv/bin/activate
python scripts/compare_photoresponse_72_81.py
```

Prerequisite: `biotite enrich-history 72` and `biotite enrich-history 81` have been run (or the on-the-fly fallback succeeds).

## Assumptions to verify at implementation time

1. `scripts/` directory exists or can be created at the repo root — check before writing.
2. Enriched histories for chips 72 and 81 exist on disk (`data/03_derived/chip_histories_enriched/Alisson72_history.parquet`, `…/Alisson81_history.parquet`) — verified earlier in the exploration step, both present.
3. The `seq` column in the enriched history matches the integers in the YAML seq lists (i.e. 1-indexed experiment numbers per chip, not global run IDs). This is how every other `plot-its-*` command consumes the YAML configs, so the assumption is safe but will be sanity-checked on the first run by printing the number of rows surviving each filter.
