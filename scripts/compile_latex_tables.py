#!/usr/bin/env python3
"""
Batch compile all LaTeX files in data/04_exports/latex directory.

This script finds all .tex files in the exports directory and compiles them
to PDF using pdflatex. Compilation is done in parallel for efficiency.
"""

import subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Tuple
import sys


def compile_latex(tex_file: Path) -> Tuple[Path, bool, str]:
    """
    Compile a single LaTeX file to PDF.

    Args:
        tex_file: Path to the .tex file

    Returns:
        Tuple of (tex_file, success, message)
    """
    output_dir = tex_file.parent

    # Run pdflatex twice for proper cross-references (if any)
    # Use -interaction=nonstopmode to avoid hanging on errors
    cmd = [
        "pdflatex",
        "-interaction=nonstopmode",
        "-output-directory", str(output_dir),
        str(tex_file)
    ]

    try:
        # First pass
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            # Extract relevant error from log
            error_lines = [line for line in result.stdout.split('\n')
                          if 'Error' in line or '!' in line]
            error_msg = '\n'.join(error_lines[:5])  # First 5 error lines
            return (tex_file, False, f"Compilation failed:\n{error_msg}")

        # Second pass for cross-references
        subprocess.run(cmd, capture_output=True, timeout=30)

        # Clean up auxiliary files
        for ext in ['.aux', '.log', '.out']:
            aux_file = tex_file.with_suffix(ext)
            if aux_file.exists():
                aux_file.unlink()

        pdf_file = tex_file.with_suffix('.pdf')
        if pdf_file.exists():
            return (tex_file, True, f"✓ {pdf_file.name}")
        else:
            return (tex_file, False, "PDF not created")

    except subprocess.TimeoutExpired:
        return (tex_file, False, "Timeout (>30s)")
    except Exception as e:
        return (tex_file, False, f"Error: {str(e)}")


def main():
    """Main entry point."""
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    latex_dir = project_root / "data" / "04_exports" / "latex"

    if not latex_dir.exists():
        print(f"❌ LaTeX directory not found: {latex_dir}")
        sys.exit(1)

    # Find all .tex files
    tex_files = sorted(latex_dir.rglob("*.tex"))

    if not tex_files:
        print(f"❌ No .tex files found in {latex_dir}")
        sys.exit(1)

    print(f"Found {len(tex_files)} LaTeX files to compile")
    print(f"Location: {latex_dir}")
    print("-" * 60)

    # Compile in parallel
    successful = 0
    failed = 0
    max_workers = 4  # Parallel compilation

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all jobs
        futures = {executor.submit(compile_latex, tex_file): tex_file
                   for tex_file in tex_files}

        # Process as they complete
        for future in as_completed(futures):
            tex_file, success, message = future.result()

            if success:
                print(message)
                successful += 1
            else:
                print(f"❌ {tex_file.name}: {message}")
                failed += 1

    print("-" * 60)
    print(f"Compilation complete: {successful} succeeded, {failed} failed")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
