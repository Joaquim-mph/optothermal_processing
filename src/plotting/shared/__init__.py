"""Shared plotting infrastructure.

Cross-cutting modules used by every plot type:
- config.py: PlotConfig and output-path resolution
- styles.py: Matplotlib style/theme configuration
- formatters.py: Legend/label formatters (wavelength, voltage, power, ...)
- plot_utils.py: Shared data-prep and helper functions
- transforms.py: Resistance/conductance conversions
- batch.py: Batch-plot orchestration from YAML configs
"""
