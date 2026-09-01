"""
Low- vs high-irradiance regime comparison, 365 nm, as a 1x2 figure.

Panel a  -- low irradiance:  the 2026-05-15 session (3-6 µW LED,
            2.5-5.0 mW/cm² at the beam spot).
Panel b  -- high irradiance: the 2026-05-14 session (6-24 µW LED,
            5.0-20.0 mW/cm²), which is the range suspected of sitting in the
            channel-current saturation regime and which motivated the
            2026-05-15 re-measurement.

Chip 72 is left out of the low-irradiance panel (see PANELS). Each panel has its
own legend, carrying that panel's gamma; markers encode the stack (square =
biotite, circle = hBN) and color the individual chip.

Both panels share the (log) y axis, so the two regimes can be read against each
other directly; only the x range differs. Each panel is forced to a 1:1 box
aspect. Points are the drift-corrected photoresponse of each chip, lines are the
independent power-law fits |Δi| ∝ P^γ per panel, and γ is reported in the
legends -- the regime comparison is exactly the change in γ between panels.

Two figures are written, same layout and same fits, differing only in the y
quantity:
    photoresponse   |Δi_corr| (µA)
    responsivity    R = |Δi| / P_incident (A/W), P_incident the flake-area
                    fraction of the beam (see the sibling scripts)

Chip selection, drift correction, flake areas and per-chip colors/markers are
reused verbatim from the two session scripts, which are imported by path:
    scripts/power_sweeps/plot_photoresponse_vs_power_semilogy_2026-05-15.py
    scripts/power_sweeps/plot_photoresponse_vs_power_semilogy_2026-05-14.py
so each session keeps its own gate voltages and per-chip quirks (chip 72's
mislabeled history, dropped first attempts, per-trace fit windows). Chips 80 and
67 exist only in the 2026-05-14 session and therefore appear only in panel b.

Run from repo root:
    python scripts/power_sweeps/plot_irradiance_regimes_1x2_365nm.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

SCRIPT_DIR = Path("scripts/power_sweeps")
OUTPUT_SUBDIR = Path("figs/power_sweeps/irradiance_regimes")

# Marker by material, so the two stacks are told apart by shape and the chips
# within a stack by color. Overrides the per-chip markers of the session
# scripts, which are unique per chip; those scripts are left untouched.
MATERIAL_MARKERS = {"biotite": "s", "hBN": "o"}
MARKER_SIZE = 27.0
FIT_LINEWIDTH = 3.0
# Publication convention: legend font sits 2 pt above the theme size; another
# 2 pt on top of that for this figure, to match the enlarged markers.
LEGEND_FONTSIZE = 34.0
PANEL_LETTER_FONTSIZE = 56.0
# Panel letter x position, in axes fractions. Panel a is pushed further out than
# panel b because only it carries the y tick labels and the y-axis label.
PANEL_LETTER_X = {"a": -0.20, "b": -0.13}


def _load_session(name: str, filename: str) -> ModuleType:
    """Import one session script by path (they are scripts, not a package)."""
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LOW = _load_session("session_low", "plot_photoresponse_vs_power_semilogy_2026-05-15.py")
HIGH = _load_session(
    "session_high", "plot_photoresponse_vs_power_semilogy_2026-05-14.py"
)

# (module, panel letter, LED powers whose irradiance gets an x tick, chips to
#  drop from that panel, number of legend columns)
# Chip 72 is dropped from the low-irradiance panel: only three points survive
# there (3, 4, 5 µW) and they come out of the mislabeled 2026-05-15 CSVs that
# the session script reads from Alisson67's history.
PANELS = [
    (LOW, "a", [3, 4, 5, 6], {72}, 2),
    (HIGH, "b", [6, 12, 18, 24], set(), 2),
]


def load_histories(session: ModuleType) -> dict[int, pl.DataFrame]:
    histories: dict[int, pl.DataFrame] = {}
    for chip in session.CHIPS:
        hist_chip = chip.get("history_chip", chip["chip"])
        histories[chip["chip"]] = pl.read_parquet(
            Path(
                f"data/03_derived/chip_histories_enriched/Alisson{hist_chip}_history.parquet"
            )
        )
    return histories


def plot_panel(
    ax: plt.Axes,
    session: ModuleType,
    histories: dict[int, pl.DataFrame],
    quantity: str,
    exclude_chips: set[int],
    legend_ncol: int,
) -> None:
    """One regime panel: points + power-law fits vs beam irradiance.

    The fit is always done on the photoresponse itself, |Δi| ∝ P^γ, exactly as
    on the per-session comparison figures; for the responsivity figure the
    fitted curve is then divided by P and the beam-fill fraction so the drawn
    line stays the same fit.

    Each panel carries its own legend, since gamma is what differs between the
    regimes and so has to be reported per panel.
    """
    entries: list[tuple[str | None, mpl.lines.Line2D]] = []

    for chip in session.CHIPS:
        if chip["chip"] in exclude_chips:
            continue
        p, di = session.curve_for_chip(histories[chip["chip"]], chip)
        mask = p > 0
        p, di = p[mask], di[mask]
        if p.size == 0:
            print(f"[warn] no data for {session.label_for_chip(chip)}")
            continue

        gamma, p_fit, di_fit = session.power_law_fit(p, di)
        if abs(gamma) < 5e-3:  # avoid printing "-0.00"
            gamma = 0.0

        if quantity == "responsivity":
            flake_area = session._CHIP_FLAKE_AREAS.get(chip["chip"])
            if flake_area is None:
                print(f"[warn] no flake area for {session.label_for_chip(chip)}")
                continue
            fill_fraction = flake_area / session.BEAM_AREA_UM2
            y = (di / p) / fill_fraction
            y_fit = (di_fit / p_fit) / fill_fraction if p_fit.size else di_fit
        else:
            y, y_fit = di, di_fit

        material = session._CHIP_MATERIALS.get(chip["chip"])
        (handle,) = ax.plot(
            session.irradiance_mW_per_cm2(p),
            y,
            marker=MATERIAL_MARKERS.get(material, chip["marker"]),
            linestyle="none",
            color=chip["color"],
            markersize=MARKER_SIZE,
            label=f"{session.label_for_chip(chip, include_vg=False)}, "
            f"$\\gamma={gamma:.2f}$",
        )
        entries.append((material, handle))
        if p_fit.size:
            ax.plot(
                session.irradiance_mW_per_cm2(p_fit),
                y_fit,
                linestyle="-",
                color=chip["color"],
                linewidth=FIT_LINEWIDTH,
            )

        print(
            f"{session.DATE}  {session.label_for_chip(chip)}  n={p.size}  "
            f"Phi=[{session.irradiance_mW_per_cm2(p).min():.2f},"
            f"{session.irradiance_mW_per_cm2(p).max():.2f}] mW/cm²  "
            f"y=[{y.min():.3g},{y.max():.3g}]  γ={gamma:.3f}"
        )

    ax.set_yscale("log")
    ax.set_box_aspect(1)  # 1:1 panel
    ax.set_xlabel(r"Irradiance (mW/cm$^2$)")

    # hBN references first, then the biotite devices, each in session order.
    handles = [h for mat, h in entries if mat == "hBN"]
    handles += [h for mat, h in entries if mat != "hBN"]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=legend_ncol,
        framealpha=0.9,
        fontsize=LEGEND_FONTSIZE,
    )


def annotate_panel_letter(ax: plt.Axes, letter: str) -> None:
    """Bold panel letter outside the axes, above the y-axis label."""
    ax.text(
        PANEL_LETTER_X.get(letter, -0.13),
        1.0,
        letter,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontweight="bold",
        fontsize=PANEL_LETTER_FONTSIZE,
    )


def build_figure(config: PlotConfig, quantity: str, filename: str) -> None:
    # 40 x 20: at 1:1 box aspect each panel comes out ~14.3 in square. Narrowing
    # the figure to close the gap between the panels also shrinks them, because
    # tight_layout then has to squeeze the axes to fit the legend under it
    # (29 in -> 10.2 in panels), so the width stays at 40.
    fig, axes = plt.subplots(1, 2, figsize=(40, 20), sharey=True)

    for ax, (session, letter, power_ticks, exclude_chips, legend_ncol) in zip(
        axes, PANELS
    ):
        plot_panel(
            ax, session, load_histories(session), quantity, exclude_chips, legend_ncol
        )
        ticks = session.irradiance_mW_per_cm2(power_ticks)
        ax.set_xticks(ticks)
        # 3 significant figures: the low-regime ticks are 10/3 and 25/6 mW/cm².
        ax.set_xticklabels([f"{v:.3g}" for v in ticks])
        annotate_panel_letter(ax, letter)

    if quantity == "responsivity":
        axes[0].set_ylabel(r"$R$ (A/W)")
    else:
        axes[0].set_ylabel(r"$|\Delta i_{\mathrm{corr}}|$ ($\mu$A)")

    # Headroom above the tallest series (0.2 decade on the shared log axis).
    _lo, _hi = axes[0].get_ylim()
    axes[0].set_ylim(_lo, 10 ** (np.log10(_hi) + 0.2))

    # Shared log y: label the 1-2-5 decade steps plainly instead of 10^n.
    axes[0].yaxis.set_major_locator(
        mpl.ticker.LogLocator(base=10.0, subs=(1.0, 2.0, 5.0))
    )
    axes[0].yaxis.set_minor_locator(plt.NullLocator())
    axes[0].yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _p: f"{v:g}"))

    plt.tight_layout()
    out = config.get_output_path(filename, create_dirs=True)
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def main() -> None:
    config = PlotConfig(
        output_dir=OUTPUT_SUBDIR,
        chip_subdir_enabled=False,
        use_proc_subdirs=False,
        auto_subcategories=False,
    )
    set_plot_style(config.theme)

    build_figure(
        config,
        quantity="photoresponse",
        filename="photoresponse_vs_irradiance_regimes_1x2_365nm",
    )
    build_figure(
        config,
        quantity="responsivity",
        filename="responsivity_vs_irradiance_regimes_1x2_365nm",
    )


if __name__ == "__main__":
    main()
