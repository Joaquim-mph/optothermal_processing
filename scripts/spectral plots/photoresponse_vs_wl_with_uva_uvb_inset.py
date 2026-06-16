"""
Combined |ΔI_corr| vs wavelength plot:

  Main axes : chips 67/72/74/75/80/81  (visible-light sweep, see
              compare_corrected_It_67_72_74_75_80_81_pairs.py)
  Inset     : chips 68/75/80           (UVA/UVB session, no 76; see
              compare_corrected_It_uva_uvb_68_75_76.py)

Two versions: linear y-axis and semilogy.

Reuses `collect_chip_traces` / `photoresponse_at_post` / `CHIPS` /
`CHIP_COLORS` / `CHIP_MARKERS` from the two reference scripts via path-based
import (their parent folder has a space and can't be imported as a package).

Run from repo root:
    python "scripts/spectral plots/photoresponse_vs_wl_with_uva_uvb_inset.py"
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import matplotlib.pyplot as plt
import numpy as np

from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import DEEP_RAIN_PALETTE, set_plot_style

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path("figs/photoresponse_vs_wl_combined")

UV_CHIPS = [68, 75, 80]  # inset; chip 76 excluded (died mid-run)

# Drift-fit residual (RMSE) on the pre-illumination window, refit per chip,
# sits at ~0.005-0.05 µA across the dataset. The 0.05 µA upper envelope is the
# practical noise floor below which |ΔI| cannot be distinguished from leftover
# stretched-exp drift residual. See diagnostic in chat 2026-05-27.
NOISE_FLOOR_UA = 0.05

# Inset uses the DEEP_RAIN palette from src.plotting.shared.styles, one color
# per chip in UV_CHIPS order.
UV_CHIP_COLORS = {chip: DEEP_RAIN_PALETTE[i] for i, chip in enumerate(UV_CHIPS)}


def _load_sibling(filename: str) -> ModuleType:
    """Load a sibling script as a module (parent dir has a space, so no
    normal import works)."""
    path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"failed to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _curve(traces: list[dict], photoresponse_fn) -> tuple[np.ndarray, np.ndarray]:
    pts = []
    for tr in traces:
        wl = tr["wavelength_nm"]
        di = photoresponse_fn(tr)
        # photoresponse_at_post in the main script returns signed value;
        # in the UVA/UVB script it returns abs. Take abs here to unify.
        if np.isfinite(wl) and np.isfinite(di):
            pts.append((wl, abs(di)))
    pts.sort()
    if not pts:
        return np.array([]), np.array([])
    wls = np.array([p[0] for p in pts])
    dis = np.array([p[1] for p in pts])
    return wls, dis


def _plot_curves(ax, chip_nums, traces_by_chip, mod, *, legend_kwargs,
                 color_override: dict[int, str] | None = None):
    for chip_num in chip_nums:
        traces = traces_by_chip.get(chip_num, [])
        wls, dis = _curve(traces, mod.photoresponse_at_post)
        if wls.size == 0:
            continue
        color = (color_override or {}).get(chip_num) or mod.CHIP_COLORS.get(chip_num, "k")
        ax.plot(
            wls, dis,
            color=color,
            marker=mod.CHIP_MARKERS.get(chip_num, "o"),
            linestyle="-",
            label=mod.CHIPS[chip_num]["label"].replace("biotite", "Bio"),
        )
    if legend_kwargs is not None:
        ax.legend(**legend_kwargs)


def plot_combined(
    traces_main: dict[int, list[dict]],
    traces_uv: dict[int, list[dict]],
    main_mod: ModuleType,
    uv_mod: ModuleType,
    config: PlotConfig,
    yscale: str,
    output_path: Path,
) -> None:
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side, side))

    # Main axes: 67/72/74/75/80/81
    # Main data goes high-left → low-right at both scales. Inset sits in the
    # upper-right; pick a legend corner that's empty for each y-scale.
    main_legend_loc = "lower left" if yscale == "log" else "lower right"
    _plot_curves(
        ax,
        list(main_mod.CHIPS.keys()),
        traces_main,
        main_mod,
        legend_kwargs=dict(loc=main_legend_loc, framealpha=0.9, ncol=2,
                           fontsize="small"),
    )
    ax.set_xlabel(r"Wavelength (nm)")
    ax.set_ylabel(r"$|\Delta I_{\mathrm{corr}}|\ (\mu\mathrm{A})$")
    ax.set_box_aspect(1.0)
    if yscale == "log":
        ax.set_yscale("log")

    # Noise-floor warning line: points below this are within the drift-fit
    # residual and shouldn't be read as real photoresponse.
    ax.axhline(NOISE_FLOOR_UA, color="gray", linestyle="--", linewidth=1.0,
               alpha=0.7, zorder=0)
    if yscale == "log":
        # Place label at the right edge, just above the line.
        x_lo, x_hi = ax.get_xlim()
        ax.text(x_hi, NOISE_FLOOR_UA * 1.15, "noise floor",
                fontsize="x-small", color="gray",
                ha="right", va="bottom")

    # Inset: 68/75/80 (UVA/UVB) — upper-right corner.
    # Format mirrors the reference inset in
    # scripts/power_sweeps/plot_photoresponse_vs_power_loglog_alisson75_two_dates.py:
    # compact size, medium-ish labels, NO legend (each curve labelled at its end),
    # explicit major ticks.
    # Semilogy version: shrink inset height ~5 % so its aspect is a bit wider.
    inset_h = 0.34 * 0.90 if yscale == "log" else 0.34
    inset_y = 0.66 if yscale == "log" else 0.63
    inset = ax.inset_axes([0.63, inset_y, 0.34, inset_h])
    _plot_curves(
        inset,
        UV_CHIPS,
        traces_uv,
        uv_mod,
        legend_kwargs=dict(loc="upper right", framealpha=0.85,
                           fontsize="xx-small", handlelength=1.2,
                           handletextpad=0.4, borderpad=0.3, labelspacing=0.2),
        color_override=UV_CHIP_COLORS,
    )
    inset.set_xlabel(r"$\lambda\ (\mathrm{nm})$", fontsize="small", labelpad=2)
    inset.set_ylabel(r"$|\Delta I_{\mathrm{corr}}|\ (\mu\mathrm{A})$",
                     fontsize="small", labelpad=2)
    inset.tick_params(axis="both", labelsize="small", pad=2)
    # 5 % padding on each side so 280 and 455 sit slightly inside the frame.
    _pad = 0.05 * (455 - 280)
    inset.set_xlim(280 - _pad, 455 + _pad)
    inset.set_xticks([280, 365, 455])
    if yscale == "log":
        inset.set_yscale("log")
    inset.axhline(NOISE_FLOOR_UA, color="gray", linestyle="--", linewidth=0.8,
                  alpha=0.7, zorder=0)


    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    main_mod = _load_sibling("compare_corrected_It_67_72_74_75_80_81_pairs.py")
    uv_mod = _load_sibling("compare_corrected_It_uva_uvb_68_75_76.py")

    traces_main: dict[int, list[dict]] = {}
    for chip_num in main_mod.CHIPS:
        print(f"[main chip {chip_num}] collecting traces…")
        traces_main[chip_num] = main_mod.collect_chip_traces(chip_num)

    traces_uv: dict[int, list[dict]] = {}
    for chip_num in UV_CHIPS:
        print(f"[uv chip {chip_num}] collecting traces…")
        traces_uv[chip_num] = uv_mod.collect_chip_traces(chip_num)

    for yscale in ("linear", "log"):
        plot_combined(
            traces_main, traces_uv, main_mod, uv_mod, config, yscale,
            OUTPUT_DIR / f"photoresponse_vs_wl_with_uva_uvb_inset_{yscale}.pdf",
        )


if __name__ == "__main__":
    main()
