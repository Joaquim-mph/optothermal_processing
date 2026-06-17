"""
Animated responsivity (R, A/W) vs wavelength for a vertical TikTok-style video.

Four devices, revealed in stages to dramatize that biotite's peak responsivity
dwarfs hBN's:
  1. hBN curves (81, 67) draw on left-to-right, staying low and flat. ~1.5 s
  2. Hold on the flat hBN lines.                                       ~0.5 s
  3. Biotite curves (74, 75) rise from the floor with an overshoot.    ~2.6 s
  4. A large "~14×" annotation scales in near the biotite peak.        ~1.0 s
  5. End hold.                                                         ~0.4 s

Output: 9:16 portrait (1080x1920) H.264 MP4 at 30 fps, ~6 s.

Reuses the data pipeline from
  scripts/spectral plots/compare_corrected_It_67_72_74_75_80_81_pairs.py
(imported by path because the filename contains a space).

Run from repo root:
    source .venv/bin/activate
    pip install imageio-ffmpeg      # one-time
    python "scripts/spectral plots/animate_responsivity_74_75_81_67.py"
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import imageio_ffmpeg
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FFMpegWriter, FuncAnimation  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

# Point matplotlib at the bundled ffmpeg binary.
plt.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()

# --- Reuse the existing data module (filename has a space -> import by path) ---
_SRC = Path("scripts/spectral plots/compare_corrected_It_67_72_74_75_80_81_pairs.py")
_spec = importlib.util.spec_from_file_location("corrected_it_module", _SRC)
data_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(data_mod)

OUTPUT_PATH = Path("figs/drift_unified_67_72_74_75_80_81/responsivity_animation.mp4")

# Device grouping.
BIOTITE_CHIPS = [74, 75]
HBN_CHIPS = [81, 67]

# --- Styling (phone-legible, muted) ---
BG = "#0A0A0F"
FG = "#EDEDF2"
BIOTITE_COLOR = "#FF2D95"  # hot magenta
HBN_COLOR = "#6B7A99"  # muted gray-blue
LINE_WIDTH = 6.0
LABEL_FS = 30
TICK_FS = 22
ANNOT_FS = 64  # target fontsize for the "~14x" callout

# --- Frame budget (30 fps) ---
FPS = 30
F_HBN = 59  # phase 1: hBN draw-on
F_HOLD = 40  # phase 2: hold
F_RISE = 101  # phase 3: biotite rise
F_TEXT = 39  # phase 4: text scale-in
F_END = 16  # phase 5: end hold
N_FRAMES = F_HBN + F_HOLD + F_RISE + F_TEXT + F_END

# Phase start indices.
S_HOLD = F_HBN
S_RISE = S_HOLD + F_HOLD
S_TEXT = S_RISE + F_RISE
S_END = S_TEXT + F_TEXT

Y_MAX = 5800.0
DENSE_N = 240  # interpolation resolution for smooth pen-trace / curves


def collect_points() -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Per-chip sorted (wavelength, responsivity) arrays, densified for smooth
    curves. Reuses collect_chip_traces / responsivity_at_post from data_mod."""
    areas = data_mod.device_areas_um2()
    out: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for chip in BIOTITE_CHIPS + HBN_CHIPS:
        traces = data_mod.collect_chip_traces(chip)
        area = areas.get(chip)
        pts = []
        for tr in traces:
            wl = tr["wavelength_nm"]
            r = data_mod.responsivity_at_post(tr, area)
            if np.isfinite(wl) and np.isfinite(r):
                pts.append((float(wl), float(r)))
        pts.sort()
        wl = np.array([p[0] for p in pts])
        r = np.array([p[1] for p in pts])
        # Densify on a fine wavelength grid so the line draws/rises smoothly.
        wl_dense = np.linspace(wl.min(), wl.max(), DENSE_N)
        r_dense = np.interp(wl_dense, wl, r)
        out[chip] = (wl_dense, r_dense)
    return out


# --- Easing helpers ---
def smoothstep(p: float) -> float:
    p = min(max(p, 0.0), 1.0)
    return p * p * (3.0 - 2.0 * p)


def ease_out_back(p: float, overshoot: float = 1.7) -> float:
    """Ease-out with a kinetic overshoot-and-settle (0 -> ~1.08 -> 1.0)."""
    p = min(max(p, 0.0), 1.0)
    c1 = overshoot
    c3 = c1 + 1.0
    return 1.0 + c3 * (p - 1.0) ** 3 + c1 * (p - 1.0) ** 2


def main() -> None:
    points = collect_points()

    # 1080x1920 portrait.
    dpi = 180
    fig = plt.figure(figsize=(6.0, 10.667), dpi=dpi)
    fig.patch.set_facecolor(BG)
    # Plot occupies the upper-middle; leave headroom for the callout.
    ax = fig.add_axes([0.26, 0.30, 0.68, 0.50])
    ax.set_facecolor(BG)

    wl_all = np.concatenate([points[c][0] for c in points])
    x_min, x_max = float(wl_all.min()), float(wl_all.max())
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0.0, Y_MAX)

    # Axis cosmetics.
    ax.set_xlabel("Wavelength (nm)", fontsize=LABEL_FS, color=FG, labelpad=12)
    ax.set_ylabel("R (A/W)", fontsize=LABEL_FS, color=FG, labelpad=12)
    ax.tick_params(axis="both", labelsize=TICK_FS, colors=FG, length=8, width=2)
    for spine in ax.spines.values():
        spine.set_color(FG)
        spine.set_linewidth(2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Pre-create artists.
    hbn_lines: dict[int, Line2D] = {}
    for chip in HBN_CHIPS:
        (ln,) = ax.plot([], [], color=HBN_COLOR, lw=LINE_WIDTH, solid_capstyle="round")
        hbn_lines[chip] = ln

    biotite_lines: dict[int, Line2D] = {}
    for chip in BIOTITE_CHIPS:
        (ln,) = ax.plot(
            [], [], color=BIOTITE_COLOR, lw=LINE_WIDTH, solid_capstyle="round"
        )
        biotite_lines[chip] = ln

    annot_text = "~×14"

    # Position the callout near the biotite peak (365 nm, high up).
    annot = ax.text(
        x_min + 0.10 * (x_max - x_min),
        0.86 * Y_MAX,
        annot_text,
        color=BIOTITE_COLOR,
        fontsize=ANNOT_FS,
        fontweight="bold",
        ha="left",
        va="center",
        alpha=0.0,
    )

    # Minimal legend: one proxy per material.
    legend_proxies = [
        Line2D([0], [0], color=BIOTITE_COLOR, lw=LINE_WIDTH, label="biotite"),
        Line2D([0], [0], color=HBN_COLOR, lw=LINE_WIDTH, label="hBN"),
    ]
    leg = ax.legend(
        handles=legend_proxies,
        loc="center right",
        fontsize=TICK_FS,
        frameon=False,
        labelcolor=FG,
    )
    for txt in leg.get_texts():
        txt.set_color(FG)

    def update(frame: int):
        # --- Phase 1/2: hBN draw-on left-to-right, then hold ---
        if frame < S_HOLD:
            p = smoothstep((frame + 1) / F_HBN)
        else:
            p = 1.0
        cutoff = x_min + p * (x_max - x_min)
        for chip, ln in hbn_lines.items():
            wl, r = points[chip]
            mask = wl <= cutoff
            ln.set_data(wl[mask], r[mask])

        # --- Phase 3: biotite rise (full x-extent, y scaled 0 -> overshoot -> 1) ---
        if frame < S_RISE:
            s = 0.0
        elif frame < S_TEXT:
            p_rise = (frame - S_RISE + 1) / F_RISE
            s = max(0.0, ease_out_back(p_rise))
        else:
            s = 1.0
        for chip, ln in biotite_lines.items():
            wl, r = points[chip]
            ln.set_data(wl, r * s)

        # --- Phase 4/5: "~14x" callout scale-in (oversized -> snap to final) ---
        if frame < S_TEXT:
            annot.set_alpha(0.0)
        else:
            p_txt = smoothstep((frame - S_TEXT + 1) / F_TEXT)
            annot.set_alpha(p_txt)
            scale = 1.4 - 0.4 * p_txt  # 1.4x -> 1.0x
            annot.set_fontsize(ANNOT_FS * scale)

        return (*hbn_lines.values(), *biotite_lines.values(), annot)

    anim = FuncAnimation(fig, update, frames=N_FRAMES, blit=False, interval=1000 / FPS)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    writer = FFMpegWriter(
        fps=FPS,
        codec="libx264",
        bitrate=6000,
        extra_args=["-pix_fmt", "yuv420p"],
    )
    anim.save(
        str(OUTPUT_PATH), writer=writer, dpi=dpi, savefig_kwargs={"facecolor": BG}
    )
    plt.close(fig)
    print(
        f"saved {OUTPUT_PATH}  ({N_FRAMES} frames, {N_FRAMES / FPS:.1f} s @ {FPS} fps)"
    )


if __name__ == "__main__":
    main()
