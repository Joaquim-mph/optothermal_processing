# file: src/process_all.py
#!/usr/bin/env python3
"""
Process ALL days automatically with robust path handling.

Fixes duplicate-join bugs like:
  wrong: raw_data/raw_data/Alisson_15_sept/Alisson_15_sept/It2025-09-15_12.csv
  right:  raw_data/Alisson_15_sept/It2025-09-15_12.csv

Strategy:
- Normalize meta["source_file"] to be always relative to raw_data/.
- Always pass base_dir=raw_data to plotters.
- Discover days in both forms:
    A) metadata/<day>/metadata.csv  (mirrored)
    B) * *_metadata.csv             (day-level files)
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import polars as pl

# Optional styling (safe if present)
try:
    from src.plotting.styles import set_plot_style
    import scienceplots  # noqa: F401
    set_plot_style("prism_rain")
except Exception:
    pass

# Plotting utils (your repo)
from src.plotting.plots import (
    load_and_prepare_metadata,
    plot_ivg_sequence,
    plot_ivg_transconductance,
    plot_its_by_vg,
    plot_its_by_vg_delta,
    plot_its_wavelength_overlay_delta_for_chip,
    ivg_sequence_gif,
)

log = logging.getLogger("process_all")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


# ────────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────────

def extract_date_from_filename(filename: str) -> str:
    match = re.search(r'(\d+)_([a-zA-Z]+)', filename)
    if match:
        day, month = match.groups()
        month_map = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'sept': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        month_num = month_map.get(month.lower())
        if month_num:
            return f"2024_{month_num}_{day.zfill(2)}"
    return "unknown_date"

def day_from_metadata_path(metadata_csv: Path) -> str:
    """
    Determine day folder name:
    - metadata/<day>/metadata.csv → '<day>'
    - *_metadata.csv              → name without suffix '_metadata.csv'
    """
    if metadata_csv.name.endswith("_metadata.csv"):
        return metadata_csv.name[:-len("_metadata.csv")]
    # mirrored case
    return metadata_csv.parent.name

def setup_chip_output_dir(chip_num: int, metadata_csv: Path) -> Path:
    """
    Create output directory structure that mirrors raw_data organization:
    figs/<day>/<chip>/IVg|ITS/...
    """
    day = day_from_metadata_path(metadata_csv)
    date_str = extract_date_from_filename(metadata_csv.name)

    # Mirror the day structure: figs/Alisson_04_sept/Chip68_2024_09_04/
    chip_dir = Path("figs") / day / f"Chip{chip_num:02d}_{date_str}"

    for sub in [
        "IVg/sequence", "IVg/pairs", "IVg/triplets", "IVg/gif", "IVg/transconductance",
        "ITS/regular", "ITS/delta", "ITS/overlays",
    ]:
        (chip_dir / sub).mkdir(parents=True, exist_ok=True)
    return chip_dir

def _set_plots_fig_dir(tmp_dir: Path) -> None:
    try:
        import src.plotting.plots as plots
        if hasattr(plots, "FIG_DIR"):
            plots.FIG_DIR = tmp_dir
    except Exception:
        pass

def _infer_chips_from_metadata(metadata_csv: str) -> List[float]:
    df = pl.read_csv(metadata_csv, infer_schema_length=1000)
    for c in ["Chip number", "chip", "Chip", "CHIP", "Chip_number", "chip_number"]:
        if c in df.columns:
            vals = df[c].drop_nulls().to_list()
            try:
                return sorted({float(x) for x in vals})
            except Exception:
                return sorted({float(str(x).strip()) for x in vals if str(x).strip()})
    raise RuntimeError(f"Chip column not found in {metadata_csv}. Columns: {list(df.columns)}")

def fix_source_paths(meta: pl.DataFrame, day: str, raw_root: Path) -> pl.DataFrame:
    """
    Normalize meta['source_file'] to be path strings relative to raw_root.
    
    The key insight: plotting functions will join base_dir + source_file,
    so source_file should be the path RELATIVE TO base_dir.
    
    Rules:
      - If absolute path → keep as-is (plotters ignore base_dir)
      - If already starts with day/ → keep as-is  
      - If bare filename or nested path → prefix with day/
      - Remove any raw_data/ prefix since base_dir handles that
    """
    def _norm(s: str) -> str:
        if not s:
            return s
            
        p = Path(s)
        
        # Absolute paths are kept as-is
        if p.is_absolute():
            return s
            
        parts = p.parts
        if not parts:
            return s
            
        # Remove raw_data prefix if present since base_dir will add it
        if parts[0] == raw_root.name:
            if len(parts) == 1:
                return s  # Just "raw_data" - keep as-is
            # Remove the raw_data/ prefix
            p = Path(*parts[1:])
            parts = p.parts
        
        # If it starts with the day folder, it's already correct
        if parts[0] == day:
            return str(p)
            
        # Otherwise, prefix with day/
        return str(Path(day) / p)

    if "source_file" not in meta.columns:
        return meta

    return meta.with_columns(
        pl.col("source_file").cast(pl.Utf8, strict=False).map_elements(_norm).alias("source_file")
    )

# ────────────────────────────────────────────────────────────────────────────────
# Plotting orchestration (ALWAYS base_dir = raw_root)
# ────────────────────────────────────────────────────────────────────────────────

def process_chip_ivg(meta: pl.DataFrame, raw_root: Path, tag: str, out_dir: Path, generate_gifs: bool) -> None:
    import src.plotting.plots as plots
    ivg_data = meta.filter(pl.col("proc") == "IVg")
    if ivg_data.height == 0:
        log.info("No IVg for this chip.")
        return

    seq_dir = out_dir / "IVg" / "sequence"
    pairs_dir = out_dir / "IVg" / "pairs"
    trips_dir = out_dir / "IVg" / "triplets"
    gif_dir = out_dir / "IVg" / "gif"
    gm_dir = out_dir / "IVg" / "transconductance"

    orig = getattr(plots, "FIG_DIR", None)
    try:
        # Generate IVg sequence plots
        _set_plots_fig_dir(seq_dir)
        plot_ivg_sequence(ivg_data, raw_root, tag)

        # Generate transconductance plots
        _set_plots_fig_dir(gm_dir)
        plot_ivg_transconductance(ivg_data, raw_root, tag)

        file_indices = []
        if "file_idx" in ivg_data.columns:
            file_indices = sorted(set(ivg_data["file_idx"].drop_nulls().to_list()))

        # Generate pair plots (both IVg and transconductance)
        if len(file_indices) >= 2:
            _set_plots_fig_dir(pairs_dir)
            for i in range(len(file_indices) - 1):
                pair = (file_indices[i], file_indices[i + 1])
                meta_subset = ivg_data.filter(pl.col("file_idx").is_in(pair))
                plot_ivg_sequence(meta_subset, raw_root, f"{tag}_pair_{pair[0]}_{pair[1]}")

            # Transconductance for pairs
            _set_plots_fig_dir(gm_dir)
            for i in range(len(file_indices) - 1):
                pair = (file_indices[i], file_indices[i + 1])
                meta_subset = ivg_data.filter(pl.col("file_idx").is_in(pair))
                plot_ivg_transconductance(meta_subset, raw_root, f"{tag}_pair_{pair[0]}_{pair[1]}")

        # Generate triplet plots (both IVg and transconductance)
        if len(file_indices) >= 3:
            _set_plots_fig_dir(trips_dir)
            for i in range(len(file_indices) - 2):
                triplet = (file_indices[i], file_indices[i + 1], file_indices[i + 2])
                meta_subset = ivg_data.filter(pl.col("file_idx").is_in(triplet))
                plot_ivg_sequence(meta_subset, raw_root, f"{tag}_triplet_{triplet[0]}_{triplet[-1]}")

            # Transconductance for triplets
            _set_plots_fig_dir(gm_dir)
            for i in range(len(file_indices) - 2):
                triplet = (file_indices[i], file_indices[i + 1], file_indices[i + 2])
                meta_subset = ivg_data.filter(pl.col("file_idx").is_in(triplet))
                plot_ivg_transconductance(meta_subset, raw_root, f"{tag}_triplet_{triplet[0]}_{triplet[-1]}")

        if generate_gifs:
            _set_plots_fig_dir(gif_dir)
            try:
                ivg_sequence_gif(ivg_data, raw_root, tag, fps=2, cumulative=True)
            except Exception as e:
                log.warning(f"IVg GIF failed: {e}")
    finally:
        if orig is not None:
            try:
                plots.FIG_DIR = orig
            except Exception:
                pass

def process_chip_its(meta: pl.DataFrame, raw_root: Path, tag: str, out_dir: Path, chip_num: int, overlays: bool) -> None:
    import src.plotting.plots as plots
    its_data = meta.filter(pl.col("proc") == "ITS")
    if its_data.height == 0:
        log.info("No ITS for this chip.")
        return

    reg_dir = out_dir / "ITS" / "regular"
    delta_dir = out_dir / "ITS" / "delta"
    overlay_dir = out_dir / "ITS" / "overlays"

    orig = getattr(plots, "FIG_DIR", None)
    try:
        vgs = its_data["VG_meta"].drop_nulls().unique().to_list() if "VG_meta" in its_data.columns else []
        wls = (
            sorted(float(w) for w in its_data["Laser wavelength"].drop_nulls().unique().to_list())
            if "Laser wavelength" in its_data.columns else []
        )

        _set_plots_fig_dir(reg_dir)
        for vg in (sorted(vgs) if vgs else [None]):
            for wl in (wls if wls else [None]):
                try:
                    plot_its_by_vg(meta, raw_root, tag, vgs=[vg] if vg is not None else None, wavelengths=[wl] if wl is not None else None)
                except Exception as e:
                    log.warning(f"ITS regular failed (VG={vg}, WL={wl}): {e}")

        _set_plots_fig_dir(delta_dir)
        for vg in (sorted(vgs) if vgs else [None]):
            for wl in (wls if wls else [None]):
                try:
                    plot_its_by_vg_delta(meta, raw_root, tag, vgs=[vg] if vg is not None else None, wavelengths=[wl] if wl is not None else None, baseline_t=60.0, clip_t_min=20.0)
                except Exception as e:
                    log.warning(f"ITS delta failed (VG={vg}, WL={wl}): {e}")

        if overlays:
            _set_plots_fig_dir(overlay_dir)
            vg_center, vg_window = -5.0, 1.5
            baseline_t, clip_t_min = 60.0, 40.0

            # a) ALL
            try:
                plot_its_wavelength_overlay_delta_for_chip(
                    meta, raw_root, f"{tag}_all_wavelengths",
                    chip=int(chip_num), vg_center=vg_center, vg_window=vg_window,
                    wavelengths=None, baseline_t=baseline_t, clip_t_min=clip_t_min,
                )
            except Exception as e:
                log.warning(f"Overlay (all) failed: {e}")

            # b) UV/blue
            uv_blue = [wl for wl in wls if wl <= 455.0]
            if len(uv_blue) >= 2:
                try:
                    plot_its_wavelength_overlay_delta_for_chip(
                        meta, raw_root, f"{tag}_UV_blue",
                        chip=int(chip_num), vg_center=vg_center, vg_window=vg_window,
                        wavelengths=uv_blue, baseline_t=baseline_t, clip_t_min=clip_t_min,
                    )
                except Exception as e:
                    log.warning(f"Overlay (UV_blue) failed: {e}")

            # c) green+red/orange
            longer = [wl for wl in wls if wl > 455.0]
            if len(longer) >= 2:
                try:
                    plot_its_wavelength_overlay_delta_for_chip(
                        meta, raw_root, f"{tag}_green_red",
                        chip=int(chip_num), vg_center=vg_center, vg_window=vg_window,
                        wavelengths=longer, baseline_t=baseline_t, clip_t_min=clip_t_min,
                    )
                except Exception as e:
                    log.warning(f"Overlay (green_red) failed: {e}")
    finally:
        if orig is not None:
            try:
                plots.FIG_DIR = orig
            except Exception:
                pass

def process_single_chip(
    metadata_csv: Path,
    chip_num: float,
    raw_root: Path,
    generate_gifs: bool,
    overlays: bool,
) -> None:
    chip_i = int(chip_num)
    log.info(f"\n{'='*64}\nPROCESSING CHIP {chip_i:02d} – {metadata_csv.name}\n{'='*64}")
    out_dir = setup_chip_output_dir(chip_i, metadata_csv)
    meta = load_and_prepare_metadata(str(metadata_csv), chip_num)
    if meta.height == 0:
        log.info(f"No data for chip {chip_num}, skipping."); return

    # Normalize source_file to be relative to raw_root
    day = day_from_metadata_path(metadata_csv)
    meta = fix_source_paths(meta, day, raw_root)

    tag = metadata_csv.stem
    procs = set(meta.get_column("proc").to_list())
    if "ITS" in procs:
        process_chip_its(meta, raw_root, tag, out_dir, chip_num=chip_i, overlays=overlays)
    if "IVg" in procs:
        process_chip_ivg(meta, raw_root, tag, out_dir, generate_gifs=generate_gifs)

def process_day_experiments(
    metadata_csv: Path,
    raw_root: Path,
    chips_filter: Optional[List[float]],
    generate_gifs: bool,
    overlays: bool,
) -> None:
    chips = chips_filter or _infer_chips_from_metadata(str(metadata_csv))
    log.info(f"Chips for {metadata_csv.name}: {chips}")
    for chip in chips:
        try:
            process_single_chip(metadata_csv, chip, raw_root, generate_gifs, overlays)
        except Exception as e:
            log.error(f"Chip {chip}: failed for {metadata_csv.name}: {e}")

# ────────────────────────────────────────────────────────────────────────────────
# Discovery
# ────────────────────────────────────────────────────────────────────────────────

def discover_jobs(raw_root: Path, meta_root: Path) -> List[Path]:
    """
    Return list of metadata CSVs:
      - metadata/<day>/metadata.csv
      - metadata/*_metadata.csv
      - *_metadata.csv in project root
    """
    jobs: list[Path] = []
    jobs += list(meta_root.rglob("metadata.csv"))
    jobs += list(meta_root.glob("*_metadata.csv"))
    jobs += [p for p in Path(".").glob("*_metadata.csv") if meta_root not in p.parents]
    # Dedup
    uniq: dict[Path, None] = {}
    for m in jobs:
        uniq[m.resolve()] = None
    return list(uniq.keys())

# ────────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Process all days with robust path handling.")
    ap.add_argument("--raw", type=Path, default=Path("raw_data"), help="Root of raw data (default: raw_data)")
    ap.add_argument("--meta", type=Path, default=Path("metadata"), help="Root of metadata (default: metadata)")
    ap.add_argument("--chips", type=float, nargs="*", help="Optional chip filter, e.g. --chips 68 75")
    ap.add_argument("--no-gif", action="store_true", help="Disable IVg GIFs")
    ap.add_argument("--no-overlays", action="store_true", help="Disable ITS overlays")
    return ap.parse_args()

def main() -> int:
    args = parse_args()
    raw_root: Path = args.raw
    meta_root: Path = args.meta

    if not raw_root.exists():
        log.error(f"Raw root not found: {raw_root}"); return 2
    if not meta_root.exists():
        log.error(f"Metadata root not found: {meta_root}"); return 2

    metas = discover_jobs(raw_root, meta_root)
    if not metas:
        log.warning("No metadata files found."); return 1

    log.info(f"Discovered {len(metas)} day(s):")
    for i, m in enumerate(sorted(metas), 1):
        log.info(f"  {i:02d}. {m}")

    for m in metas:
        try:
            process_day_experiments(
                m, raw_root,
                chips_filter=args.chips,
                generate_gifs=not args.no_gif,
                overlays=not args.no_overlays,
            )
        except Exception as e:
            log.error(f"Failed: {m} → {e}")

    log.info("All done.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())