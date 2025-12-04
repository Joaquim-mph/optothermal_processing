#!/usr/bin/env python3
"""
Fix unescaped underscores in LaTeX table files.

Some generated LaTeX files have unescaped underscores in filenames within
\texttt{} commands, causing compilation errors. This script fixes them.
"""

import re
from pathlib import Path


def fix_latex_underscores(tex_file: Path) -> bool:
    """
    Fix unescaped underscores in \texttt{} commands.

    Args:
        tex_file: Path to the .tex file

    Returns:
        True if file was modified, False otherwise
    """
    content = tex_file.read_text()
    original = content

    # Pattern: Find \texttt{...} blocks and escape underscores within them
    # This regex finds \texttt{...} and captures the content, handling nested braces
    def escape_underscores_in_texttt(match):
        """Escape underscores in the matched \texttt{} content."""
        inner_text = match.group(1)
        # Only escape underscores that aren't already escaped
        # Look for _ that is not preceded by backslash
        fixed_text = re.sub(r'(?<!\\)_', r'\\_', inner_text)
        return f'\\texttt{{{fixed_text}}}'

    # Apply the fix - need to handle nested braces like \textbackslash{}
    # This pattern matches \texttt{ followed by content with possible nested braces
    # We'll process line by line for lines containing \texttt
    lines = content.split('\n')
    modified_lines = []

    for line in lines:
        if r'\texttt{' in line:
            # Find all \texttt{...} in this line and fix them
            # We need to properly handle nested braces like \textbackslash{}
            new_line = line
            # Pattern to find \texttt and its matching closing brace
            start_idx = 0
            result_parts = []

            while True:
                # Find next \texttt{
                idx = new_line.find(r'\texttt{', start_idx)
                if idx == -1:
                    result_parts.append(new_line[start_idx:])
                    break

                # Add everything before \texttt{
                result_parts.append(new_line[start_idx:idx])

                # Find matching closing brace
                brace_count = 1
                content_start = idx + 8  # len('\texttt{')
                i = content_start
                while i < len(new_line) and brace_count > 0:
                    if new_line[i] == '{':
                        brace_count += 1
                    elif new_line[i] == '}':
                        brace_count -= 1
                    i += 1

                if brace_count == 0:
                    # Found matching brace
                    content_end = i - 1
                    texttt_content = new_line[content_start:content_end]
                    # Fix underscores in this content
                    fixed_content = re.sub(r'(?<!\\)_', r'\\_', texttt_content)
                    result_parts.append(f'\\texttt{{{fixed_content}}}')
                    start_idx = i
                else:
                    # Malformed - just keep original
                    result_parts.append(new_line[idx:])
                    break

            modified_lines.append(''.join(result_parts))
        else:
            modified_lines.append(line)

    content = '\n'.join(modified_lines)

    # Write back if changed
    if content != original:
        tex_file.write_text(content)
        return True
    return False


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    latex_dir = project_root / "data" / "04_exports" / "latex"

    if not latex_dir.exists():
        print(f"❌ LaTeX directory not found: {latex_dir}")
        return

    # Find all .tex files
    tex_files = sorted(latex_dir.rglob("*.tex"))

    if not tex_files:
        print(f"❌ No .tex files found in {latex_dir}")
        return

    print(f"Checking {len(tex_files)} LaTeX files for underscore issues...")
    print("-" * 60)

    fixed = 0
    for tex_file in tex_files:
        if fix_latex_underscores(tex_file):
            print(f"✓ Fixed: {tex_file.name}")
            fixed += 1

    print("-" * 60)
    if fixed > 0:
        print(f"Fixed {fixed} file(s)")
    else:
        print("No files needed fixing")


if __name__ == "__main__":
    main()
