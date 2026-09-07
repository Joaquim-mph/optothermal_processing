"""First-IVg transfer curves + field-effect mobility, hBN vs biotite devices.

Two chip groups, one per column:

    left  — 67, 72, 80, 81   (hBN bottom dielectric)
    right — 74, 75, 76, 68   (biotite bottom dielectric)

For every chip the **first measured IVg** (earliest dark IVg in the chip
history) is used, restricted to the two full-range monotonic legs of the
looped sweep (0 -> V_start -> V_end -> V_start -> 0); the initial and
trailing partial ramps from/to 0 V are dropped.

The transfer panels draw both legs in one style per chip, so each chip
reads as a closed hysteresis loop. The mobility panels draw the **forward
leg only**, Sav-Gol smoothed.

Mobility is the gate-resolved field-effect mobility

    mu_FE(Vg) = (L/W) * |gm(Vg)| / (C_ox * |Vds|)      [cm^2 / V s]

with gm = dI/dVg from the Savitzky-Golay derivative used by the derived-
metrics pipeline (`peak_gm_on_leg`), and C_ox from each chip's top-hBN +
bottom-dielectric stack in `config/encap_characteristics.yaml`. This is
the same estimator as `MobilityExtractor`, evaluated over the whole leg
instead of only at the branch peaks. `peak_gm_on_leg` edge-trims and
Sav-Gol smooths gm (see `smoothed_gm_on_leg`), so each curve's branch
extrema equal that sweep's `mobility_fe_{holes,electrons}_forward`
metrics exactly. mu_FE is plotted signed (following gm, not |gm|), so the
hole branch runs negative and the electron branch positive.

Chips are distinguished by color and by the linestyle cycle from
`biotite compare-first-ivg --linestyle mixed`.

Caveat: the gate is driven by two Tenma supplies that hand over at
Vg = 0, which puts a genuine step of ~1-3 uA in I at that point. The
9-point Sav-Gol derivative smears it across +-0.20 V, so mu_FE within
that window is instrument-limited, not device physics. It is left in
these figures deliberately.

Outputs (figs/first_ivg_transfer_mobility/):
    first_IVg_transfer_mobility_2x2.pdf   row 1 transfer, row 2 mobility
    first_IVg_transfer_1x2.pdf            transfer curves only
    first_IVg_mobility_1x2.pdf            mobility only

Run from the repo root:
    .venv/bin/python "scripts/IVg Analysis/plot_first_ivg_transfer_mobility_hbn_vs_biotite.py"
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from src.core.utils import read_measurement_parquet
from src.derived.algorithms.cnp_parabola import split_full_range_legs
from src.derived.algorithms.mobility import (
    chip_geometry,
    cox_per_area,
    load_encap_config,
    peak_gm_on_leg,
)
from src.cli.commands.compare_first_ivg import LINESTYLE_SETS
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

ENRICHED_DIR = Path("data/03_derived/chip_histories_enriched")
STAGE_DIR = Path("data/02_stage/chip_histories")
OUTPUT_DIR = Path("figs/first_ivg_transfer_mobility")

# Column groups: left = hBN-encapsulated, right = biotite-encapsulated.
GROUP_LEFT: list[int] = [67, 72, 80, 81]
GROUP_RIGHT: list[int] = [74, 75, 76, 68]

# Every chip keeps its own color across all three figures. The two columns
# are drawn side by side, so the groups get disjoint colors rather than both
# restarting the palette cycle. Values are from PRISM_RAIN_PALETTE.
CHIP_COLORS: dict[int, str] = {
    67: "#e41a1c",  # red
    72: "#377eb8",  # blue
    80: "#4daf4a",  # green
    81: "#984ea3",  # purple
    74: "#ff7f00",  # orange
    75: "#007a87",  # deep teal
    76: "#b8326b",  # deep rose
    68: "#8a532b",  # walnut brown
}

# Legend font and line weight match
# scripts/spectral plots/compare_corrected_It_67_72_74_75_80_81_pairs.py:
# 2 pt over the "small" relative size, resolved against the active theme's
# base font size so it stays correct regardless of theme. Theme default
# line width is 4.0; these figures use the heavier 5.5.
LEGEND_FONTSIZE_BUMP = 2.0
LINEWIDTH = 5.5

# Sample styles come from the `biotite compare-first-ivg --linestyle mixed`
# cycle, so a chip is distinguished by style as well as color.
LINESTYLES: list[str] = LINESTYLE_SETS["mixed"]


@dataclass(frozen=True)
class ChipCurves:
    """First-IVg legs for one chip, plus the mobility conversion factor."""

    chip_number: int
    material: str
    seq: int
    date: str
    vds_v: float
    # direction -> (vg ascending, I in A, gm = dI/dVg in S)
    legs: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]
    # direction -> CNP voltage (V)
    cnps: dict[str, float]
    # mu_cm2 = mu_factor * |gm|;  None when the chip stack is unknown.
    mu_factor: float | None

    @property
    def label(self) -> str:
        return f"{self.chip_number} ({self.material})"


# ── Data loading ────────────────────────────────────────────────────────


def _history_path(chip_number: int) -> Path:
    """Enriched history if present, else the staged one."""
    enriched = ENRICHED_DIR / f"Alisson{chip_number}_history.parquet"
    return enriched if enriched.exists() else STAGE_DIR / f"Alisson{chip_number}_history.parquet"


def _first_dark_ivg_row(chip_number: int) -> dict | None:
    path = _history_path(chip_number)
    if not path.exists():
        print(f"[warn] no history for Alisson{chip_number}; skipping")
        return None
    hist = pl.read_parquet(path).filter(pl.col("proc") == "IVg")
    if "has_light" in hist.columns:
        dark = hist.filter(~pl.col("has_light").fill_null(False))
        if dark.height:
            hist = dark
    if hist.height == 0:
        print(f"[warn] Alisson{chip_number}: no IVg sweeps in history; skipping")
        return None
    return hist.sort("start_time").row(0, named=True)


def load_chip(chip_number: int, encap_cfg) -> ChipCurves | None:
    """First dark IVg of `chip_number`, split into forward/backward legs."""
    row = _first_dark_ivg_row(chip_number)
    if row is None:
        return None

    parquet_path = Path(row["parquet_path"])
    if not parquet_path.exists():
        print(f"[warn] Alisson{chip_number}: missing parquet {parquet_path}; skipping")
        return None

    df = read_measurement_parquet(parquet_path)
    if not {"Vg (V)", "I (A)"} <= set(df.columns):
        print(f"[warn] Alisson{chip_number}: no Vg/I columns in {parquet_path}; skipping")
        return None

    vg = df["Vg (V)"].to_numpy()
    i = df["I (A)"].to_numpy()

    legs: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    cnps: dict[str, float] = {}
    for vg_leg, i_leg, direction in split_full_range_legs(vg, i):
        # peak_gm_on_leg sorts the leg ascending and runs the same Sav-Gol
        # derivative the mobility extractor uses, so the curves below and
        # the pipeline's peak-mobility metrics come from identical gm.
        *_, vg_s, i_s, gm, cnp = peak_gm_on_leg(vg_leg, i_leg)
        if gm.size == 0:
            continue
        legs[direction] = (vg_s, i_s, gm)
        if cnp is not None and np.isfinite(cnp):
            cnps[direction] = float(cnp)
    if not legs:
        print(
            f"[warn] Alisson{chip_number} seq {row['seq']}: sweep is not a full "
            "forward/backward loop; skipping"
        )
        return None

    geom = chip_geometry(encap_cfg, chip_number)
    vds = row.get("vds_v")
    mu_factor = None
    if geom is None:
        print(
            f"[warn] Alisson{chip_number}: no stack in encap_characteristics.yaml; "
            "mobility panel will omit this chip"
        )
    elif vds is None or not np.isfinite(vds) or vds == 0:
        print(f"[warn] Alisson{chip_number}: no usable vds_v; mobility omitted")
    else:
        cox = cox_per_area(
            geom["top_hBN_nm"], geom["eps_top"],
            geom["bottom_dielectric_nm"], geom["eps_bot"],
        )
        # mu_cm2 = (L/W) * |gm| / (C_ox * |Vds|) * 1e4
        mu_factor = geom["LW"] / (cox * abs(float(vds))) * 1e4

    material = (geom or {}).get("bottom_material") or "?"
    curves = ChipCurves(
        chip_number=chip_number,
        material=material,
        seq=int(row["seq"]),
        date=str(row["date"]),
        vds_v=float(vds) if vds is not None else float("nan"),
        legs=legs,
        cnps=cnps,
        mu_factor=mu_factor,
    )
    print(
        f"[{curves.label}] seq={curves.seq} date={curves.date} "
        f"Vds={curves.vds_v:g} V legs={sorted(legs)} "
        f"Vg=[{vg.min():.1f}, {vg.max():.1f}] V"
    )
    return curves


# ── Panel drawing ───────────────────────────────────────────────────────


def _legend_fontsize(relative: str = "small") -> float:
    from matplotlib.font_manager import font_scalings

    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


def draw_transfer_panel(
    ax,
    chips: list[ChipCurves],
    *,
    chip_loc: str = "best",
) -> None:
    """I_ds vs Vg, one color per chip.

    Both full-range legs are drawn in the same style, so each chip reads as
    a single closed hysteresis loop rather than a forward/backward pair.
    """
    for idx, chip in enumerate(chips):
        color = CHIP_COLORS.get(chip.chip_number)
        style = LINESTYLES[idx % len(LINESTYLES)]
        first = True
        for direction in ("forward", "backward"):
            leg = chip.legs.get(direction)
            if leg is None:
                continue
            vg_s, i_s, _gm = leg
            ax.plot(
                vg_s,
                i_s * 1e6,
                color=color,
                linestyle=style,
                linewidth=LINEWIDTH,
                label=chip.label if first else None,
            )
            first = False

    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
    ax.set_ylim(bottom=0)
    ax.legend(loc=chip_loc, framealpha=0.9, fontsize=_legend_fontsize())
    ax.set_box_aspect(1)


def draw_mobility_panel(
    ax,
    chips: list[ChipCurves],
    *,
    chip_loc: str = "upper left",
    box_aspect: float = 1.0,
) -> None:
    """mu_FE vs Vg for the forward leg only, one color+style per chip.

    Edge trimming and Sav-Gol smoothing both happen inside
    `peak_gm_on_leg`, so these curves and the pipeline's stored
    `mobility_fe_*` metrics come from the same gm by construction.

    mu_FE is drawn signed, following gm rather than |gm|: the hole branch
    (Vg < CNP, gm < 0) runs negative and the electron branch positive, so
    the curve crosses zero at the CNP instead of cusping there. The two
    extrema are the chip's `mobility_fe_{holes,electrons}_forward` pipeline
    metrics, which stay positive magnitudes — the hole extremum is minus
    the stored value.
    """
    for idx, chip in enumerate(chips):
        if chip.mu_factor is None:
            continue
        leg = chip.legs.get("forward")
        if leg is None:
            continue
        vg_s, _i_s, gm = leg
        ax.plot(
            vg_s,
            chip.mu_factor * gm * 1e-4,
            color=CHIP_COLORS.get(chip.chip_number),
            linestyle=LINESTYLES[idx % len(LINESTYLES)],
            linewidth=LINEWIDTH,
            label=chip.label,
        )

    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{\\mu_{FE}\\ (10^4\\ cm^2\\,V^{-1}\\,s^{-1})}$")
    ax.legend(loc=chip_loc, framealpha=0.9, fontsize=_legend_fontsize())
    ax.set_box_aspect(box_aspect)


def _annotate_panel_letters(
    axes, letters: list[str], x: float | list[float] = -0.13
) -> None:
    """Stamp bold 'a', 'b', ... outside each axes, above the y-axis label."""
    flat = np.asarray(axes).ravel()
    xs = [x] * len(flat) if isinstance(x, (int, float)) else list(x)
    for ax, letter, x_off in zip(flat, letters, xs):
        ax.text(
            x_off,
            1.0,
            f"{letter}",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontweight="bold",
            fontsize=56,
        )


# ── Figures ─────────────────────────────────────────────────────────────


def _save(fig, config: PlotConfig, filename: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / filename
    fig.savefig(out, dpi=config.dpi)
    plt.close(fig)
    print(f"saved {out}")


def _share_y(ax_left, ax_right) -> None:
    """Unify y-limits and hide the right panel's y-axis labels."""
    y0 = min(ax_left.get_ylim()[0], ax_right.get_ylim()[0])
    y1 = max(ax_left.get_ylim()[1], ax_right.get_ylim()[1])
    ax_left.set_ylim(y0, y1)
    ax_right.set_ylim(y0, y1)
    ax_right.set_ylabel("")
    ax_right.tick_params(labelleft=False)


def plot_transfer_mobility_2x2(
    left: list[ChipCurves], right: list[ChipCurves], config: PlotConfig
) -> None:
    """Row 1 transfer curves, row 2 mobility; left = hBN, right = biotite."""
    fig, axes = plt.subplots(2, 2, figsize=(40, 40), gridspec_kw={"wspace": 0.28})

    draw_transfer_panel(axes[0, 0], left)
    draw_transfer_panel(axes[0, 1], right)
    draw_mobility_panel(axes[1, 0], left)
    draw_mobility_panel(axes[1, 1], right)

    _share_y(axes[1, 0], axes[1, 1])

    _annotate_panel_letters(axes, ["a", "b", "c", "d"])
    fig.tight_layout()
    _save(fig, config, "first_IVg_transfer_mobility_2x2.pdf")


def plot_transfer_1x2(
    left: list[ChipCurves], right: list[ChipCurves], config: PlotConfig
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(40, 20), gridspec_kw={"wspace": 0.28})
    draw_transfer_panel(axes[0], left)
    draw_transfer_panel(axes[1], right)

    _annotate_panel_letters(axes, ["a", "b"])
    fig.tight_layout()
    _save(fig, config, "first_IVg_transfer_1x2.pdf")


def plot_mobility_1x2(
    left: list[ChipCurves], right: list[ChipCurves], config: PlotConfig
) -> None:
    # Standalone mobility figure uses 4:3 panels (height/width = 3/4).
    fig, axes = plt.subplots(1, 2, figsize=(40, 17), gridspec_kw={"wspace": 0.28})
    draw_mobility_panel(axes[0], left, box_aspect=3 / 4)
    draw_mobility_panel(axes[1], right, box_aspect=3 / 4)

    _share_y(axes[0], axes[1])

    _annotate_panel_letters(axes, ["a", "b"])
    fig.tight_layout()
    _save(fig, config, "first_IVg_mobility_1x2.pdf")


def plot_mobility_1x2_square(
    left: list[ChipCurves], right: list[ChipCurves], config: PlotConfig
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(40, 20), gridspec_kw={"wspace": 0.28})
    draw_mobility_panel(axes[0], left, box_aspect=1.0)
    draw_mobility_panel(axes[1], right, box_aspect=1.0)

    _share_y(axes[0], axes[1])

    _annotate_panel_letters(axes, ["a", "b"])
    fig.tight_layout()
    _save(fig, config, "first_IVg_mobility_1x2_square.pdf")


def _chip_table_row(chip: ChipCurves) -> tuple[float, float, float, float] | None:
    """Return (V_CNP_avg, delta_V_CNP, mu_h_avg, mu_e_avg) or None."""
    if chip.mu_factor is None:
        return None
    cnp_f = chip.cnps.get("forward")
    cnp_b = chip.cnps.get("backward")
    if cnp_f is None or cnp_b is None:
        return None

    v_cnp = (cnp_f + cnp_b) / 2
    dv_cnp = abs(cnp_f - cnp_b)

    mu_vals: dict[str, tuple[float, float]] = {}
    for direction in ("forward", "backward"):
        leg = chip.legs.get(direction)
        if leg is None:
            continue
        _vg, _i, gm = leg
        mu = chip.mu_factor * gm * 1e-4
        mu_vals[direction] = (abs(float(np.min(mu))), float(np.max(mu)))

    if not mu_vals:
        return None
    mu_h = np.mean([v[0] for v in mu_vals.values()])
    mu_e = np.mean([v[1] for v in mu_vals.values()])
    return v_cnp, dv_cnp, float(mu_h), float(mu_e)


def write_mobility_table(
    left: list[ChipCurves], right: list[ChipCurves]
) -> None:
    """Write a LaTeX table matching the publication format."""

    def _group_rows(chips: list[ChipCurves], material: str) -> list[str]:
        sorted_chips = sorted(chips, key=lambda c: c.chip_number)
        lines: list[str] = []
        for i, chip in enumerate(sorted_chips):
            vals = _chip_table_row(chip)
            if vals is None:
                continue
            v_cnp, dv_cnp, mu_h, mu_e = vals
            prefix = f"\\multirow{{{len(sorted_chips)}}}{{*}}{{{material}}}" if i == 0 else ""
            lines.append(
                f"        {prefix}\n"
                f"        & {chip.chip_number}"
                f" & {v_cnp:.2f}"
                f" & {dv_cnp:.2f}"
                f" & {mu_h:.2f} & {mu_e:.2f} \\\\"
            )
        return lines

    hbn_rows = _group_rows(left, "hBN")
    bio_rows = _group_rows(right, "biotite")

    tex = r"""\begin{table}[h!]
    \centering
    \caption{
        Transport parameters extracted from the initial transfer curves.
        $V_{\mathrm{CNP}}$ is the average of the CNP voltages
        obtained from the forward and reverse sweeps,
        and $\Delta V_{\mathrm{CNP}}$ is their difference.
        The hole and electron field-effect mobilities,
        $\mu_h$ and $\mu_e$, are averaged over the two sweep directions.
    }
    \label{tab:extracted_params}
    \begin{tabular}{ l c c c c c}
        \toprule
        \textbf{Back-gate material}
        & \textbf{Device ID}
        & {\textbf{\boldmath $V_{\mathrm{CNP}}$ (\unit{\volt})}}
        & {\textbf{\boldmath $\Delta V_{\mathrm{CNP}}$ (\unit{\volt})}}
        & \multicolumn{2}{c}{%
            \textbf{\boldmath $\mu$
            ($10^{4}$~\unit{\centi\meter\squared\per\volt\per\second})}
        } \\
        \cmidrule(lr){5-6}
        & & {} & {} & {\textbf{\boldmath $\mu_h$}} & {\textbf{\boldmath $\mu_e$}} \\
        \midrule

"""
    tex += "\n".join(hbn_rows) + "\n\n        \\midrule\n\n"
    tex += "\n".join(bio_rows) + "\n\n"
    tex += r"""        \bottomrule
    \end{tabular}
\end{table}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "first_IVg_mobility_table.tex"
    out.write_text(tex)
    print(f"saved {out}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config)

    encap_cfg = load_encap_config()

    left = [c for c in (load_chip(n, encap_cfg) for n in GROUP_LEFT) if c is not None]
    right = [c for c in (load_chip(n, encap_cfg) for n in GROUP_RIGHT) if c is not None]
    if not left or not right:
        print("[error] one of the chip groups is empty; nothing to plot")
        return

    plot_transfer_mobility_2x2(left, right, config)
    plot_transfer_1x2(left, right, config)
    plot_mobility_1x2(left, right, config)
    plot_mobility_1x2_square(left, right, config)
    write_mobility_table(left, right)


if __name__ == "__main__":
    main()
