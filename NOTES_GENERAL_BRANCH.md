# `general` branch — migration notes

This branch generalizes the `biotite` data-processing tool into a multi-app
`graphene` CLI that can also host the historic graphene-on-SiO₂ chips
(per-sample architectures, paired W×L layouts, optional Al₂O₃ passivation).
`main` is preserved as-is; everything in this document either lives on
`general` already or is queued for follow-up work.

## Status at a glance

| Step | What landed | Commit |
|------|-------------|--------|
| 1 | `config/chip_apps.yaml` + `src/core/chip_metadata.py` (loader, `ChipId`, `resolve_chip_id`, `list_samples`) + 22 unit tests | additive |
| 2 | `config/chip_metadata/biotite.yaml` (mirrors per-chip block of `encap_characteristics.yaml`); `compare-first-ivg` routed through the loader | additive |
| 3 | `graphene` console script in `pyproject.toml`; `biotite` kept as a deprecation alias forwarding to the same Typer app | additive |
| 4a | `src/cli/_chip_args.py` (`CHIP_ARG`, `LIST_SAMPLES_OPTION`, `resolve_chip_cli_args`); `plot-its` (overlay + sequential) and `plot-ivg` migrated to variadic chip identifiers | breaking-CLI* |
| 4b | Remaining single-positional plot commands migrated: `plot-consecutive-sweep-diff`, `plot-vt`, `plot-cnp-time`, `plot-its-relaxation`, `plot-its-relaxation-batch`, `plot-its-suite`, `plot-transconductance`, `plot-vvg`, `plot-vts-suite`, `plot-ivg-by-sample` | breaking-CLI* |
| 5 | `sample` promoted to identity in `history_builder.generate_all_chip_histories`; new helper `chip_history_basename`; per-sample history filenames `{group}{number}_{sample}_history.parquet`; 9 new tests | additive (biotite path unchanged) |
| 6 | `config/chip_metadata/sio2_legacy.yaml` seeded with a documented `_example` paired-geometry block | additive |

\* breaking-CLI: the migrated commands no longer accept `--group / -g` as an
option; pass the group as a positional instead (`graphene plot-its Alisson 75`
or just `graphene plot-its 75` with the default group from `chip_apps.yaml`).

All commits keep `python3 -m pytest tests/` green (185 passing as of Step 6).

## What still needs doing on this branch

### 1. Two photoresponse commands still have the legacy single-int chip arg

`plot-its-photoresponse` and `plot-photoresponse` take a *second* positional
argument (the x-axis variable: `power | wavelength | time | gate_voltage`).
The variadic `CHIP_ARG` consumes all remaining positionals, so a clean
migration requires first promoting that second positional to a flag, e.g.
`--x-axis power`. Then apply the same Step 4 pattern. Until then these two
commands keep the `chip_number: int` + `--group / -g` interface and will not
benefit from sample inference or `--list-samples`.

### 2. Other `encap_characteristics.yaml` callers (mobility path)

`config/encap_characteristics.yaml` is kept as the live source-of-truth for:

- `src/derived/algorithms/mobility.py:177`
- `src/derived/extractors/mobility_extractor.py:94`
- `scripts/estimate_mobility.py`
- `scripts/plot_mobility_time_stability.py`
- `scripts/plot_ivg_365nm_triplet_compare.py`

`config/chip_metadata/biotite.yaml` mirrors the per-chip block but the shared
`geometry:` / `materials:` blocks live only in `encap_characteristics.yaml`.
The two files drift if a chip is added or edited only on one side. Migrate
these callers next: extend the chip-metadata loader (or a sibling module) to
expose `materials` and `geometry` defaults, then delete `encap_characteristics.yaml`.

### 3. Non-plot commands still use `chip_number: int = typer.Argument`

`export_latex.py`, `history.py`, `derived_metrics.py`, `export_history.py`
all take a chip_number positional. They probably don't need full variadic
support, but they do need to resolve the chip-group default through
`chip_apps.yaml` rather than the current hardcoded `"Alisson"` literal.

### 4. The CLI's auto-discovered `--group / -g` short flag

A few migrated commands previously offered `-g` as the short form of
`--group`. After Step 4, `-g` was freed up for new uses (e.g.
`plot-ivg-by-sample` already binds `-g` to `--conductance`). If a future
top-level option wants to reclaim `-g`, ensure no command-level conflict.

## Forward-going architecture (post-`general` work)

The current layout keeps everything in one package. The intended next phase
splits along a clean core/app boundary:

1. **Move graphene physics out of the core.** `src/derived/algorithms/`
   (Dirac parabola, FE mobility) and the photoresponse/relaxation analysis
   in `src/plotting/cnp_time.py`, `src/plotting/photoresponse.py`,
   `src/plotting/transconductance.py`, `src/plotting/ivg_by_sample.py` are
   "graphene-shared" — they assume a graphene transistor but are not
   biotite-specific. Move them under `src/graphene/` (or a top-level
   `graphene_physics/`) so the laser_setup core stays semantics-free.

2. **Extract a `labkit` core.** `src/core/` (staging, manifest, history
   builder), the procedure-agnostic plotting in `src/plotting/its.py`,
   `src/plotting/ivg.py`, `src/plotting/vt.py`, `src/plotting/vvg.py`, and
   `src/cli/plugin_system.py` are domain-agnostic (laser_setup CSVs and
   time-series experiment runs). They could become a separate
   `pip install`-able package.

3. **Apps become real Python packages.** Today `biotite` and `sio2_legacy`
   are YAML-driven; promote them to `src/apps/biotite/`, `src/apps/sio2_legacy/`
   with their own `__init__.py` registering chip-groups via entry points
   rather than via `chip_apps.yaml`. New apps (silicon nitride? something
   that isn't graphene?) drop in without touching the central config.

4. **Schema-version bump on `ManifestRow`.** Once every staging path
   populates `sample`, promote it from optional metadata to a required
   identity column and bump `schema_version` in `src/models/manifest.py`.

5. **Move `scripts/`.** Per-paper ad-hoc analysis scripts live in `scripts/`
   today, mixed across chip families. After the app split, each script lives
   under the app it analyzes (`apps/biotite/scripts/`, etc.).

## How to drive a historic chip through this branch

1. Add the real chip-group name (whatever replaces `_example`) to
   `config/chip_apps.yaml` under `apps.sio2_legacy.chip_groups`.
2. Populate the chip's metadata block in `config/chip_metadata/sio2_legacy.yaml`
   following the `_example` template (geometry_pairs or explicit samples,
   plus `sio2_thickness_nm` and optional `al2o3_thickness_nm`).
3. Drop the raw CSVs under `data/01_raw/` following the laser_setup naming.
4. `graphene stage-all` → `graphene build-all-histories`. Per-sample history
   files appear automatically under `data/02_stage/chip_histories/`.
5. `graphene plot-its <GROUP> <NUM> <SAMPLE>` (or `--list-samples` to
   discover available samples for that chip).
