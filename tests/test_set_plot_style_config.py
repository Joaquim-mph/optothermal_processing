"""Tests for `set_plot_style` polymorphic PlotConfig dispatch.

Covers four cases:
1. String-arg path applies the theme exactly as before.
2. A default PlotConfig() yields the same rcParams as passing "prism_rain".
3. `palette` override resolves to the right color list.
4. `legend_font_scale`, `legend_framealpha`, `legend_default_position`, and
   `show_grid` propagate from PlotConfig into rcParams.
"""

from __future__ import annotations

import matplotlib as mpl
import pytest

from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import (
    PALETTES,
    PRISM_RAIN_PALETTE,
    SCIENTIFIC_PALETTE,
    set_plot_style,
)


@pytest.fixture(autouse=True)
def _restore_rcparams():
    """Snapshot rcParams per-test so theme application doesn't leak."""
    snapshot = mpl.rcParams.copy()
    yield
    mpl.rcParams.update(snapshot)


def _cycle_colors() -> list[str]:
    return mpl.rcParams["axes.prop_cycle"].by_key()["color"]


class TestStringPath:
    """Backwards compatibility: passing a theme name string."""

    def test_prism_rain_applies_palette_and_legend(self):
        set_plot_style("prism_rain")
        assert _cycle_colors()[0] == PRISM_RAIN_PALETTE[0]
        assert mpl.rcParams["legend.fontsize"] == 30
        assert mpl.rcParams["axes.grid"] is False

    def test_invalid_theme_raises(self):
        with pytest.raises(ValueError, match="not found"):
            set_plot_style("nonexistent_theme")


class TestConfigPath:
    """PlotConfig dispatch and override layering."""

    def test_default_config_matches_string_path(self):
        """A default PlotConfig() should produce the same rc state as 'prism_rain'."""
        set_plot_style("prism_rain")
        string_state = {
            "legend.fontsize": mpl.rcParams["legend.fontsize"],
            "axes.grid": mpl.rcParams["axes.grid"],
            "legend.loc": mpl.rcParams["legend.loc"],
            "cycle[0]": _cycle_colors()[0],
        }

        set_plot_style(PlotConfig())
        assert mpl.rcParams["legend.fontsize"] == string_state["legend.fontsize"]
        assert mpl.rcParams["axes.grid"] == string_state["axes.grid"]
        assert mpl.rcParams["legend.loc"] == string_state["legend.loc"]
        assert _cycle_colors()[0] == string_state["cycle[0]"]

    def test_palette_override_resolves(self):
        cfg = PlotConfig(theme="prism_rain", palette="scientific")
        set_plot_style(cfg)
        assert _cycle_colors()[0] == SCIENTIFIC_PALETTE[0]

    def test_legend_font_scale_multiplies_theme_value(self):
        # prism_rain theme sets legend.fontsize = 30
        cfg = PlotConfig(theme="prism_rain", legend_font_scale=2.0)
        set_plot_style(cfg)
        assert mpl.rcParams["legend.fontsize"] == pytest.approx(60.0)

    def test_legend_and_grid_overrides_propagate(self):
        cfg = PlotConfig(
            theme="prism_rain",
            show_grid=True,
            legend_default_position="upper right",
            legend_framealpha=0.5,
        )
        set_plot_style(cfg)
        assert mpl.rcParams["axes.grid"] is True
        assert mpl.rcParams["legend.loc"] == "upper right"
        assert mpl.rcParams["legend.framealpha"] == 0.5

    def test_font_family_open_sans(self):
        set_plot_style(PlotConfig(theme="prism_rain", font_family="open_sans"))
        assert mpl.rcParams["font.sans-serif"][0] == "Open Sans"

    def test_font_family_source_sans_3(self):
        set_plot_style(PlotConfig(theme="prism_rain", font_family="source_sans_3"))
        assert mpl.rcParams["font.sans-serif"][0] == "Source Sans 3"

    def test_font_weight_bold(self):
        set_plot_style(PlotConfig(theme="prism_rain", font_weight="bold"))
        assert mpl.rcParams["font.weight"] == "bold"

    def test_font_defaults_match_common_rc(self):
        """Default PlotConfig should resolve to Open Sans / normal."""
        set_plot_style(PlotConfig(theme="prism_rain"))
        assert mpl.rcParams["font.sans-serif"][0] == "Open Sans"
        assert mpl.rcParams["font.weight"] == "normal"


class TestPalettesRegistry:
    """The PALETTES registry must cover every Literal value on PlotConfig.palette."""

    def test_registry_keys_match_plotconfig_literal(self):
        literal_values = {"prism_rain", "deep_rain", "scientific", "minimal", "vivid"}
        assert set(PALETTES.keys()) == literal_values


class TestFromCLIConfig:
    """PlotConfig.from_cli_config should forward only non-None CLI overrides."""

    def test_defaults_match_plotconfig_defaults(self):
        """A default CLIConfig should produce a PlotConfig equal to PlotConfig()."""
        from src.cli.config import CLIConfig
        cli = CLIConfig()
        plot = PlotConfig.from_cli_config(cli)
        # Equivalent on every field that doesn't depend on absolute path resolution.
        expected = PlotConfig(
            output_dir=cli.output_dir,
            format=cli.default_plot_format,
            dpi=cli.plot_dpi,
            theme=cli.plot_theme,
        )
        assert plot.model_dump() == expected.model_dump()

    def test_optional_overrides_propagate(self):
        from src.cli.config import CLIConfig
        cli = CLIConfig(
            plot_palette="scientific",
            plot_font_family="open_sans",
            plot_font_weight="bold",
            plot_legend_loc="upper right",
            plot_legend_font_scale=1.5,
            plot_legend_framealpha=0.5,
        )
        plot = PlotConfig.from_cli_config(cli)
        assert plot.palette == "scientific"
        assert plot.font_family == "open_sans"
        assert plot.font_weight == "bold"
        assert plot.legend_default_position == "upper right"
        assert plot.legend_font_scale == 1.5
        assert plot.legend_framealpha == 0.5

    def test_none_overrides_leave_plotconfig_defaults(self):
        """None on CLIConfig means: don't forward, let PlotConfig pick its default."""
        from src.cli.config import CLIConfig
        cli = CLIConfig()  # all plot_* overrides None
        plot = PlotConfig.from_cli_config(cli)
        defaults = PlotConfig()
        assert plot.palette == defaults.palette
        assert plot.font_family == defaults.font_family
        assert plot.legend_framealpha == defaults.legend_framealpha
