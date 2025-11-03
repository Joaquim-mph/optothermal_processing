#!/usr/bin/env python3
"""
Generate Beamer frame snippets for figures.

For each subdirectory in the figs/ directory (configurable), this script
creates a .txt file containing one Beamer frame per figure. Each frame places
the corresponding image as the sole slide content so it can be copied into the
main presentation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}


def latex_escape(text: str) -> str:
    """Escape characters that LaTeX treats as special."""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def build_frame_snippet(rel_path: str, frame_title: str) -> str:
    """Return a Beamer frame snippet that only contains the given figure."""
    return (
        r"\begin{frame}{" + frame_title + "}\n"
        r"    \centering" + "\n"
        r"    \includegraphics[width=\linewidth]{" + rel_path + "}\n"
        r"\end{frame}"
    )


def generate_snippets(figs_dir: Path, output_dir: Path) -> None:
    """Create one .txt file per subdirectory with frame snippets per image."""
    project_root = figs_dir.parent
    for subdir in sorted([p for p in figs_dir.iterdir() if p.is_dir()]):
        frames = []
        for image in sorted(subdir.iterdir()):
            if image.is_file() and image.suffix.lower() in IMAGE_EXTENSIONS:
                title = latex_escape(image.stem.replace("_", " "))
                rel_path = image.relative_to(project_root).as_posix()
                frames.append(build_frame_snippet(rel_path, title))

        if not frames:
            continue

        output_path = output_dir / f"{subdir.name}.txt"
        output_path.write_text("\n\n".join(frames) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Beamer frame snippets for figure subdirectories.",
    )
    parser.add_argument(
        "--figs-dir",
        type=Path,
        default=Path("figs"),
        help="Path to the directory that contains figure subdirectories (default: figs).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Where to place the generated .txt files. Defaults to the figs directory "
            "itself."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    figs_dir = args.figs_dir.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else figs_dir

    if not figs_dir.is_dir():
        raise SystemExit(f"figs directory not found: {figs_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    generate_snippets(figs_dir, output_dir)


if __name__ == "__main__":
    main()
