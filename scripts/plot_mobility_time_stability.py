"""Mobility stability versus calendar time / time in air.

Looks at every IVg's measurement timestamp and plots how each chip's
field-effect mobility evolves across its lab life. Two views:

    * Left panel — μ trajectory: log-μ vs days since the chip's first IVg.
      One coloured trace per chip (colour = bottom dielectric); separate
      lines for hole and electron branches. Reveals slow drift /
      degradation that doesn't show up in the index-based history plot.

    * Right panel — retention bar chart: median μ in the latest measurement
      session divided by the initial-session median, expressed as a
      percentage. >100 % = improved, <100 % = degraded. Annotated with the
      elapsed days.

A CSV with the underlying numbers lives next to the figure.

Only chips with ≥ ``MIN_SPAN_DAYS`` of measurement span and ≥ 2 sessions
make it into the retention bar chart; the trajectory panel shows all
chips so the single-session experiments (e.g. chip 79's gate-burn run)
are still visible.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.patches import Patch
from rich.console import Console
from rich.table import Table

from src.plotting.styles import set_plot_style

METRICS_PARQUET = Path("data/03_derived/_metrics/metrics.parquet")
MANIFEST_PARQUET = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
ENCAP_YAML = Path("config/encap_characteristics.yaml")
OUTPUT_DIR = Path("figs/mobility")

# Drop low-confidence rows (saturated / out-of-range / etc.) before stats.
MIN_CONFIDENCE = 0.5

# Retention bar chart skips chips whose IVgs span less than this many days
# of calendar time — they're single-session experiments, not stability data.
MIN_SPAN_DAYS = 7.0

# Two timestamps within this many hours are considered the same "session"
# for the initial/final medians. The repo's typical session is one
# afternoon, so 24h is a safe boundary.
SESSION_WINDOW_HOURS = 24.0

COLOR_BY_MATERIAL = {"hBN": "tab:blue", "biotite": "tab:orange"}
BRANCH_MARKER = {"holes": "o", "electrons": "s"}

console = Console()


def load_rows() -> tuple[pl.DataFrame, dict[int, str]]:
    """Return (rows_per_(measurement,branch), {chip_number: bottom_material})."""
    import yaml
    with ENCAP_YAML.open() as f:
        encap = yaml.safe_load(f)
    material = {int(k): (v or {}).get("material") for k, v in encap.items() if isinstance(k, int)}

    mdf = pl.read_parquet(METRICS_PARQUET)
    man = pl.read_parquet(MANIFEST_PARQUET).with_columns(
        pl.col("start_time_utc").str.to_datetime(
            format="%Y-%m-%d %H:%M:%S%.f%z", strict=False, time_zone="UTC"
        ).alias("t")
    )

    mob = (
        mdf.filter(pl.col("metric_name").str.starts_with("mobility_fe_"))
        .with_columns(
            pl.col("metric_name").str.replace("mobility_fe_", "").alias("branch")
        )
        .rename({"value_float": "mu_central"})
        .filter(pl.col("confidence") > MIN_CONFIDENCE)
    )
    rows = mob.join(man.select(["run_id", "t", "has_light"]), on="run_id")
    rows = rows.with_columns(
        pl.col("chip_number").replace_strict(material, default=None).alias("bottom_material")
    )
    # Days since this chip's first IVg.
    rows = rows.with_columns(
        (
            (pl.col("t") - pl.col("t").min().over("chip_number"))
            .dt.total_seconds() / 86400.0
        ).alias("days_in_air")
    )
    return rows, material


def retention_table(rows: pl.DataFrame) -> pl.DataFrame:
    """One row per (chip, branch) with initial / final / retention numbers."""
    out = []
    for (chip, branch), sub in rows.group_by(["chip_number", "branch"], maintain_order=True):
        if sub.height == 0:
            continue
        t0 = sub["t"].min()
        t1 = sub["t"].max()
        span = (t1 - t0).total_seconds() / 86400.0
        # Initial session = all rows within the first SESSION_WINDOW_HOURS hours.
        from datetime import timedelta
        init_mask = sub["t"] <= (t0 + timedelta(hours=SESSION_WINDOW_HOURS))
        fin_mask = sub["t"] >= (t1 - timedelta(hours=SESSION_WINDOW_HOURS))
        mu_init = float(sub.filter(init_mask)["mu_central"].median())
        mu_fin = float(sub.filter(fin_mask)["mu_central"].median())
        out.append({
            "chip_number": int(chip),
            "bottom_material": sub["bottom_material"][0],
            "branch": branch,
            "days_in_air": span,
            "n_total": sub.height,
            "n_initial_session": int(init_mask.sum()),
            "n_final_session": int(fin_mask.sum()),
            "mu_initial_median": mu_init,
            "mu_final_median": mu_fin,
            "retention_pct": 100.0 * mu_fin / mu_init if mu_init > 0 else float("nan"),
        })
    return pl.DataFrame(out).sort(["bottom_material", "chip_number", "branch"])


def print_summary(stats: pl.DataFrame) -> None:
    t = Table(title=(
        f"Mobility retention per chip "
        f"(initial vs final {SESSION_WINDOW_HOURS:.0f}-h session medians, "
        f"confidence > {MIN_CONFIDENCE})"
    ))
    t.add_column("chip", justify="right")
    t.add_column("mat")
    t.add_column("branch")
    t.add_column("days", justify="right")
    t.add_column("n init", justify="right")
    t.add_column("n final", justify="right")
    t.add_column("μ initial", justify="right")
    t.add_column("μ final", justify="right")
    t.add_column("retention", justify="right")
    for r in stats.iter_rows(named=True):
        ret = r["retention_pct"]
        if not np.isfinite(ret):
            ret_s = "—"
        elif ret >= 90:
            ret_s = f"[green]{ret:5.1f}%[/green]"
        elif ret >= 50:
            ret_s = f"[yellow]{ret:5.1f}%[/yellow]"
        else:
            ret_s = f"[red]{ret:5.1f}%[/red]"
        t.add_row(
            str(r["chip_number"]),
            r["bottom_material"] or "?",
            r["branch"],
            f"{r['days_in_air']:.1f}",
            str(r["n_initial_session"]),
            str(r["n_final_session"]),
            f"{r['mu_initial_median']:,.0f}",
            f"{r['mu_final_median']:,.0f}",
            ret_s,
        )
    console.print(t)


def _plot_trajectory(ax_t, rows: pl.DataFrame) -> None:
    # ── μ trajectory ──
    chips = sorted(rows["chip_number"].unique().to_list())
    for chip in chips:
        for branch in ("holes", "electrons"):
            sub = rows.filter(
                (pl.col("chip_number") == chip) & (pl.col("branch") == branch)
            ).sort("days_in_air")
            if sub.height == 0:
                continue
            mat = sub["bottom_material"][0]
            c = COLOR_BY_MATERIAL.get(mat, "0.4")
            ls = "-" if branch == "holes" else "--"
            ax_t.plot(
                sub["days_in_air"].to_numpy(), sub["mu_central"].to_numpy(),
                ls, color=c, alpha=0.55, lw=1.0,
                marker=BRANCH_MARKER[branch], ms=3, mec="none",
            )
        # Label the chip at its last point.
        last = rows.filter(
            (pl.col("chip_number") == chip) & (pl.col("branch") == "electrons")
        ).sort("days_in_air")
        if last.height:
            xy = (last["days_in_air"][-1], last["mu_central"][-1])
            ax_t.annotate(str(chip), xy, fontsize=7,
                          xytext=(3, 0), textcoords="offset points",
                          va="center", color="0.25")

    ax_t.set_xscale("symlog", linthresh=1.0)
    ax_t.set_yscale("log")
    ax_t.set_xlabel("days since first IVg")
    ax_t.set_ylabel(r"$\mu_{FE}$ (cm$^2$ V$^{-1}$ s$^{-1}$)")
    ax_t.set_title("Mobility trajectory (log–log)")
    legend = [
        Patch(facecolor="tab:blue", label="bottom = hBN"),
        Patch(facecolor="tab:orange", label="bottom = biotite"),
        plt.Line2D([0], [0], color="0.3", lw=1, marker="o", ms=4, label="holes (solid)"),
        plt.Line2D([0], [0], color="0.3", lw=1, ls="--", marker="s", ms=4, label="electrons (dashed)"),
    ]
    ax_t.legend(handles=legend, loc="best", fontsize=8)


def _plot_retention(ax_r, stats: pl.DataFrame) -> None:
    # ── retention bars (only chips with ≥ MIN_SPAN_DAYS span) ──
    keepers = stats.filter(pl.col("days_in_air") >= MIN_SPAN_DAYS).sort(
        ["bottom_material", "chip_number", "branch"]
    )
    if keepers.height == 0:
        ax_r.axis("off")
    else:
        # One group per chip, two bars (holes / electrons).
        chip_list = list(dict.fromkeys(keepers["chip_number"].to_list()))
        x = np.arange(len(chip_list))
        w = 0.4
        for k, branch in enumerate(("holes", "electrons")):
            ys = []
            cs = []
            for chip in chip_list:
                r = keepers.filter(
                    (pl.col("chip_number") == chip) & (pl.col("branch") == branch)
                )
                if r.height:
                    ys.append(float(r["retention_pct"][0]))
                    cs.append(COLOR_BY_MATERIAL.get(r["bottom_material"][0], "0.4"))
                else:
                    ys.append(0.0)
                    cs.append("0.7")
            offset = (-w / 2) if branch == "holes" else (w / 2)
            ax_r.bar(
                x + offset, ys, w,
                color="white" if branch == "holes" else cs,
                edgecolor=cs, hatch="//" if branch == "holes" else None,
                linewidth=1.2,
                label="holes" if branch == "holes" else "electrons",
            )
        # Reference line at 100 %.
        ax_r.axhline(100.0, color="0.4", lw=0.8, ls="--",
                     label="100 % (no change)")
        ax_r.set_xticks(x)
        labels = [
            f"{c}\n({keepers.filter(pl.col('chip_number')==c)['days_in_air'][0]:.0f} d)"
            for c in chip_list
        ]
        ax_r.set_xticklabels(labels)
        ax_r.set_xlabel("chip (days in air)")
        ax_r.set_ylabel(r"$\mu_{\rm final}/\mu_{\rm initial}$ (%)")
        ax_r.set_title("Mobility retention (median of last vs first session)")
        ax_r.legend(loc="best", fontsize=8)


def plot_time_stability(rows: pl.DataFrame, stats: pl.DataFrame, path: Path) -> None:
    set_plot_style()
    plt.rcParams.update({
        "font.size": 11, "axes.labelsize": 12, "axes.titlesize": 12,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 9,
        "figure.figsize": (16, 7),
    })
    fig, (ax_t, ax_r) = plt.subplots(1, 2, figsize=(16, 7),
                                     gridspec_kw={"width_ratios": [1.3, 1.1]})
    _plot_trajectory(ax_t, rows)
    _plot_retention(ax_r, stats)

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_index_normalized_history(
    rows: pl.DataFrame, stats: pl.DataFrame, path: Path
) -> None:
    """One row per chip (with ≥ MIN_SPAN_DAYS span); μ normalized to its
    first measurement, plotted vs sequential IVg index. Shared x-axis."""
    set_plot_style()
    plt.rcParams.update({
        "font.size": 11, "axes.labelsize": 11, "axes.titlesize": 11,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 9,
    })

    keepers = stats.filter(pl.col("days_in_air") >= MIN_SPAN_DAYS)
    chip_list = sorted(set(keepers["chip_number"].to_list()))
    n = len(chip_list)
    if n == 0:
        return

    fig, axes = plt.subplots(n, 1, figsize=(9, 1.6 * n + 1), sharex=True)
    if n == 1:
        axes = [axes]

    for ax, chip in zip(axes, chip_list):
        chip_rows = rows.filter(pl.col("chip_number") == chip)
        mat = chip_rows["bottom_material"][0] if chip_rows.height else None
        c = COLOR_BY_MATERIAL.get(mat, "0.4")
        for branch in ("holes", "electrons"):
            sub = chip_rows.filter(pl.col("branch") == branch).sort("t")
            if sub.height == 0:
                continue
            mu = sub["mu_central"].to_numpy()
            n_pts = len(mu)
            idx = np.arange(n_pts) / (n_pts - 1) if n_pts > 1 else np.zeros(1)
            ls = "-" if branch == "holes" else "--"
            ax.plot(
                idx, mu, ls, color=c, alpha=0.85, lw=1.2,
                marker=BRANCH_MARKER[branch], ms=4, mec="none",
                label=branch,
            )
        # Days in air for this chip (max across branches).
        days = float(
            keepers.filter(pl.col("chip_number") == chip)["days_in_air"].max()
        )
        ax.text(
            0.98, 0.92, f"chip {chip} · {mat or '?'} · {days:.0f} d",
            transform=ax.transAxes, ha="right", va="top", fontsize=9,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=2),
        )
        ax.set_ylabel(r"$\mu_{FE}$")
        ax.set_yscale("log")

    axes[-1].set_xlabel("normalized IVg index (current / final)")
    axes[0].legend(loc="best", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_index_normalized_history_combined(
    rows: pl.DataFrame, stats: pl.DataFrame, path: Path
) -> None:
    """All chips (with ≥ MIN_SPAN_DAYS span) overlaid: μ vs normalized
    IVg index (current/final). Colour = bottom material; linestyle = branch."""
    set_plot_style()
    plt.rcParams.update({
        "font.size": 11, "axes.labelsize": 12, "axes.titlesize": 12,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 9,
    })
    keepers = stats.filter(pl.col("days_in_air") >= MIN_SPAN_DAYS)
    chip_list = sorted(set(keepers["chip_number"].to_list()))
    if not chip_list:
        return

    fig, ax = plt.subplots(figsize=(9, 6))
    for chip in chip_list:
        chip_rows = rows.filter(pl.col("chip_number") == chip)
        mat = chip_rows["bottom_material"][0] if chip_rows.height else None
        c = COLOR_BY_MATERIAL.get(mat, "0.4")
        for branch in ("holes", "electrons"):
            sub = chip_rows.filter(pl.col("branch") == branch).sort("t")
            if sub.height == 0:
                continue
            mu = sub["mu_central"].to_numpy()
            n_pts = len(mu)
            idx = np.arange(n_pts) / (n_pts - 1) if n_pts > 1 else np.zeros(1)
            ls = "-" if branch == "holes" else "--"
            ax.plot(
                idx, mu, ls, color=c, alpha=0.75, lw=1.2,
                marker=BRANCH_MARKER[branch], ms=3, mec="none",
            )
        # Label each chip at its last electron point (fall back to holes).
        for branch in ("electrons", "holes"):
            sub = chip_rows.filter(pl.col("branch") == branch).sort("t")
            if sub.height:
                ax.annotate(
                    str(chip), (1.0, sub["mu_central"][-1]),
                    fontsize=7, xytext=(3, 0), textcoords="offset points",
                    va="center", color="0.25",
                )
                break

    ax.set_yscale("log")
    ax.set_xlabel("normalized IVg index (current / final)")
    ax.set_ylabel(r"$\mu_{FE}$ (cm$^2$ V$^{-1}$ s$^{-1}$)")
    ax.set_title("Mobility vs normalized IVg index — all chips")
    legend = [
        Patch(facecolor="tab:blue", label="bottom = hBN"),
        Patch(facecolor="tab:orange", label="bottom = biotite"),
        plt.Line2D([0], [0], color="0.3", lw=1, marker="o", ms=4, label="holes (solid)"),
        plt.Line2D([0], [0], color="0.3", lw=1, ls="--", marker="s", ms=4, label="electrons (dashed)"),
    ]
    ax.legend(handles=legend, loc="best", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_retention_only(stats: pl.DataFrame, path: Path) -> None:
    set_plot_style()
    plt.rcParams.update({
        "font.size": 11, "axes.labelsize": 12, "axes.titlesize": 12,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 9,
    })
    fig, ax_r = plt.subplots(figsize=(9, 6))
    _plot_retention(ax_r, stats)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    rows, _ = load_rows()
    if rows.height == 0:
        raise SystemExit("No mobility rows pass the confidence filter.")
    stats = retention_table(rows)
    print_summary(stats)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "mobility_time_stability.csv"
    fig_path = OUTPUT_DIR / "mobility_time_stability.png"
    retention_path = OUTPUT_DIR / "mobility_retention.png"
    history_path = OUTPUT_DIR / "mobility_index_history.png"
    history_combined_path = OUTPUT_DIR / "mobility_index_history_combined.png"
    stats.write_csv(csv_path)
    plot_time_stability(rows, stats, fig_path)
    plot_retention_only(stats, retention_path)
    plot_index_normalized_history(rows, stats, history_path)
    plot_index_normalized_history_combined(rows, stats, history_combined_path)
    console.print(f"\nWrote {csv_path}")
    console.print(f"Wrote {fig_path}")
    console.print(f"Wrote {retention_path}")
    console.print(f"Wrote {history_path}")
    console.print(f"Wrote {history_combined_path}")


if __name__ == "__main__":
    main()
