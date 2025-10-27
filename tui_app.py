#!/usr/bin/env python3
"""
TUI Application Entry Point.

Launch the Experiment Plotting Assistant with:
    python tui_app.py

This provides a wizard-style interface for lab members to generate plots
from experimental data without command-line knowledge.
"""

from pathlib import Path
from src.tui.app import PlotterApp


def main():
    """Launch the TUI application."""
    # Default configuration paths (Parquet-based pipeline)
    stage_dir = Path("data/02_stage/raw_measurements")
    history_dir = Path("data/03_history")
    output_dir = Path("figs")
    chip_group = "Alisson"

    # Create and run the app
    app = PlotterApp(
        stage_dir=stage_dir,
        history_dir=history_dir,
        output_dir=output_dir,
        chip_group=chip_group,
    )

    # Run the application
    app.run()


if __name__ == "__main__":
    main()
