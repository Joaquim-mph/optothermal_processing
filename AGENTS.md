# Repository Guidelines

This project stages optothermal CSV measurements into validated Parquet datasets, builds chip histories, and powers a Textual plotting assistant.

## Project Structure & Module Organization
- `src/core/` holds ingestion, staging, and history builders (`stage_raw_measurements.py`, `history_builder.py`, `utils.py`). Treat it as the canonical data layer consumed everywhere else.
- `src/cli/` exposes Typer commands aggregated in `main.py`; `process_and_analyze.py` re-exports that entry point for compatibility.
- `src/plotting/` contains ITS/IVg/transconductance plotters that read staged Parquet via `src/core.utils`. `src/models/` stores Pydantic schemas; `src/tui/` and `tui_app.py` deliver the interactive PlotterApp.
- Configuration and reference assets live in `config/` (YAML schemas), `data/01_raw → 03_history` (pipeline artifacts), and `figs/` (rendered outputs).

## Build, Test, and Development Commands
- Create a virtualenv and install dependencies: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
- Run the whole pipeline: `python process_and_analyze.py full-pipeline` (stages raw CSVs, refreshes histories, prints outputs).
- Run focused steps with `python process_and_analyze.py stage-all`, `... build-all-histories`, `... validate-manifest`, plus plotting commands (`plot-its`, `plot-ivg`, `plot-transconductance`).
- Launch the Textual UI with `python tui_app.py` to validate user-facing flows before shipping UX changes.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation, type hints, and `snake_case` for modules/functions; reserve `CamelCase` for Pydantic models and Textual widgets.
- Favor pure functions within `src/core/`, keep Polars expressions vectorized, and mirror existing rich console patterns in CLI output.
- Document non-obvious decisions with concise docstrings and keep module-level constants grouped near the top of each file.

## Testing Guidelines
- Use `pytest` (install with `pip install pytest`) and place cases under `tests/` with fixtures in `tests/fixtures/`. Mirror examples in `src/core/README.md`.
- Target staging regressions with manifest-based fixtures and assert on Parquet schema. For CLI flows, cover Typer callbacks via `typer.testing.CliRunner`.
- Before submitting, run `pytest` and exercise impacted CLI commands with `--help` or dry runs to catch runtime regressions.

## Commit & Pull Request Guidelines
- Follow the repo’s short, imperative commit style (`tui working with parquets`, `history from stage`). Group related changes per commit.
- Open PRs from feature branches, include a concise summary, list affected commands, and attach representative plots or manifest diffs when applicable.
- Reference tracking issues, note data sources touched (`data/01_raw`, manifest paths), and call out required re-runs for downstream consumers.
