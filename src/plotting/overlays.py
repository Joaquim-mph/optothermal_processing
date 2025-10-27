"""Multi-experiment overlay and animation functions."""

from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import polars as pl

from src.core.utils import read_measurement_parquet

try:
    import imageio.v3 as iio
except ImportError:
    import imageio as iio

# Configuration (will be overridden by CLI)
FIG_DIR = Path("figs")


def ivg_sequence_gif(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    fps: float = 2.0,            # frames per second
    cumulative: bool = False,    # False = one curve per frame; True = overlay grows
    y_unit_uA: bool = True,      # plot in µA
    show_grid: bool = True
):
    """
    Create an animated GIF from all IVg curves in the DataFrame.

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame with IVg experiments
    base_dir : Path
        Base directory containing measurement files
    tag : str
        Tag for output filename
    fps : float
        Frames per second for GIF animation
    cumulative : bool
        False = one curve per frame; True = overlay grows with each frame
    y_unit_uA : bool
        If True, plot current in µA; if False, in A
    show_grid : bool
        If True, show grid on plots
    """
    matplotlib.use('Agg')  # Use non-interactive backend

    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        print("[warn] no IVg rows to animate")
        return

    # -------- load & cache all curves; compute global limits --------
    curves = []
    xs_min, xs_max = +np.inf, -np.inf
    ys_min, ys_max = +np.inf, -np.inf

    for row in ivg.iter_rows(named=True):
        p = base_dir / row["source_file"]
        if not p.exists():
            print(f"[warn] missing file: {p}")
            continue
        d = read_measurement_parquet(p)

        # Normalize column names (handle both formats)
        col_map = {}
        if "VG (V)" in d.columns:
            col_map["VG (V)"] = "VG"
        elif "Vg (V)" in d.columns:
            col_map["Vg (V)"] = "VG"
        if "I (A)" in d.columns:
            col_map["I (A)"] = "I"
        if col_map:
            d = d.rename(col_map)

        if not {"VG", "I"} <= set(d.columns):
            print(f"[warn] {p} lacks VG/I; got {d.columns}")
            continue

        x = d["VG"].to_numpy()
        y = d["I"].to_numpy()
        if y_unit_uA:
            y = y * 1e6

        # legend label: "#idx  light/dark  [λ=… nm]"
        label = f"#{int(row['file_idx'])}  {'light' if row.get('has_light', False) else 'dark'}"
        # show λ only if Laser toggle is true
        if bool(row.get("Laser toggle", False)):
            wl = row.get("Laser wavelength", None)
            if wl is not None and str(wl) != "nan":
                try:
                    label += f"  λ={float(wl):.0f} nm"
                except Exception:
                    pass

        curves.append({"x": x, "y": y, "label": label})

        # update global limits
        if x.size and y.size:
            xs_min = min(xs_min, np.nanmin(x))
            xs_max = max(xs_max, np.nanmax(x))
            ys_min = min(ys_min, np.nanmin(y))
            ys_max = max(ys_max, np.nanmax(y))

    if not curves:
        print("[warn] nothing loadable to animate")
        return

    # pad y limits a bit to avoid touching edges
    yr = ys_max - ys_min if np.isfinite(ys_max - ys_min) else 1.0
    ys_min_pad = ys_min - 0.05 * yr
    ys_max_pad = ys_max + 0.05 * yr

    # -------- render frames to memory using PIL instead of matplotlib canvas --------
    frames = []
    chip_txt = f"Encap{int(df['chip_number'][0])}" if "chip_number" in df.columns else "Chip"

    for i in range(len(curves)):
        plt.close("all")
        fig, ax = plt.subplots()

        if cumulative:
            rng = range(0, i + 1)
        else:
            rng = [i]

        for j in rng:
            ax.plot(curves[j]["x"], curves[j]["y"], label=curves[j]["label"])

        ax.set_xlim(xs_min, xs_max)
        ax.set_ylim(ys_min_pad, ys_max_pad)
        ax.set_xlabel("VG (V)")
        ax.set_ylabel("Current (µA)" if y_unit_uA else "Current (A)")
        ax.set_title(f"{chip_txt} — IVg sequence ({i+1}/{len(curves)})")
        if show_grid:
            ax.grid(True)

        # Save to temporary buffer and convert to PIL Image
        import io
        from PIL import Image

        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        img = Image.open(buf)
        frames.append(np.array(img))
        buf.close()
        plt.close(fig)

    # -------- write GIF --------
    out = FIG_DIR / f"{chip_txt}_IVg_sequence_{tag}.gif"
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Try with imageio
        iio.imwrite(out, frames, duration=1.0 / fps, loop=0)
        print(f"saved {out}")
    except Exception as e:
        print(f"[warn] GIF save failed with imageio: {e}")
        # Fallback: save individual frames as PNGs
        for i, frame in enumerate(frames):
            frame_out = FIG_DIR / f"{chip_txt}_IVg_sequence_{tag}_frame_{i:03d}.png"
            iio.imwrite(frame_out, frame)
        print(f"[info] saved {len(frames)} individual frames instead")
