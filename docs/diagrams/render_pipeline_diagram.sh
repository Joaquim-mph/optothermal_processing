#!/bin/bash
#
# Render Pipeline Architecture Diagrams
#
# This script generates PNG, SVG, and PDF versions of all pipeline architecture
# diagrams from the Graphviz DOT source files.
#
# Versions:
#   - Full detail (for documentation)
#   - Presentation (high-level overview)
#   - Simple (single-slide overview)
#   - Formatters (v3.1 feature focus)
#
# Requirements: Graphviz installed (brew install graphviz)
#
# Usage: ./docs/render_pipeline_diagram.sh [--all|--presentation|--doc]
#        --all           Generate all versions (default)
#        --presentation  Generate only presentation versions
#        --doc           Generate only documentation version

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Mode selection
MODE="${1:-all}"

echo -e "${BOLD}${BLUE}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║  Pipeline Architecture Diagram Renderer          ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if Graphviz is installed
if ! command -v dot &> /dev/null; then
    echo -e "${RED}Error: Graphviz 'dot' command not found${NC}"
    echo ""
    echo "Please install Graphviz:"
    echo "  macOS:   brew install graphviz"
    echo "  Linux:   sudo apt-get install graphviz"
    echo "  Windows: Download from https://graphviz.org/download/"
    exit 1
fi

# Function to render a single diagram
render_diagram() {
    local dot_file="$1"
    local base_name="$2"
    local description="$3"

    if [ ! -f "$dot_file" ]; then
        echo -e "${RED}  ✗ Source file not found: $dot_file${NC}"
        return 1
    fi

    echo -e "${YELLOW}${description}${NC}"
    echo "  Source: $(basename "$dot_file")"

    # PNG
    local png_file="${SCRIPT_DIR}/${base_name}.png"
    dot -Tpng "$dot_file" -o "$png_file" 2>/dev/null
    local png_size=$(du -h "$png_file" | cut -f1)
    echo -e "  ${GREEN}✓${NC} PNG: $png_size"

    # SVG
    local svg_file="${SCRIPT_DIR}/${base_name}.svg"
    dot -Tsvg "$dot_file" -o "$svg_file" 2>/dev/null
    local svg_size=$(du -h "$svg_file" | cut -f1)
    echo -e "  ${GREEN}✓${NC} SVG: $svg_size"

    # PDF
    local pdf_file="${SCRIPT_DIR}/${base_name}.pdf"
    dot -Tpdf "$dot_file" -o "$pdf_file" 2>/dev/null
    local pdf_size=$(du -h "$pdf_file" | cut -f1)
    echo -e "  ${GREEN}✓${NC} PDF: $pdf_size"

    echo ""
}

# Render based on mode
case "$MODE" in
    --doc)
        echo -e "${BLUE}Mode: Documentation version only${NC}"
        echo ""
        render_diagram \
            "$SCRIPT_DIR/pipeline_architecture.dot" \
            "pipeline_architecture" \
            "📚 Full Documentation Diagram"
        ;;

    --presentation)
        echo -e "${BLUE}Mode: Presentation versions only${NC}"
        echo ""
        render_diagram \
            "$SCRIPT_DIR/pipeline_architecture_presentation.dot" \
            "pipeline_architecture_presentation" \
            "🎯 Presentation Version (High-Level)"

        render_diagram \
            "$SCRIPT_DIR/pipeline_architecture_simple.dot" \
            "pipeline_architecture_simple" \
            "📊 Simple Overview (Single Slide)"

        render_diagram \
            "$SCRIPT_DIR/pipeline_architecture_formatters.dot" \
            "pipeline_architecture_formatters" \
            "✨ Output Formatters Feature (v3.1)"

        render_diagram \
            "$SCRIPT_DIR/pipeline_architecture_extractors.dot" \
            "pipeline_architecture_extractors" \
            "⚙️  Metric Extractors Explained"
        ;;

    --all|*)
        if [ "$MODE" != "--all" ] && [ "$MODE" != "" ]; then
            echo -e "${YELLOW}Unknown mode: $MODE, using --all${NC}"
            echo ""
        fi

        echo -e "${BLUE}Mode: All versions${NC}"
        echo ""

        echo -e "${BOLD}Documentation Version:${NC}"
        echo "─────────────────────────────────"
        render_diagram \
            "$SCRIPT_DIR/pipeline_architecture.dot" \
            "pipeline_architecture" \
            "📚 Full Documentation Diagram"

        echo -e "${BOLD}Presentation Versions:${NC}"
        echo "─────────────────────────────────"
        render_diagram \
            "$SCRIPT_DIR/pipeline_architecture_presentation.dot" \
            "pipeline_architecture_presentation" \
            "🎯 Presentation Version (High-Level)"

        render_diagram \
            "$SCRIPT_DIR/pipeline_architecture_simple.dot" \
            "pipeline_architecture_simple" \
            "📊 Simple Overview (Single Slide)"

        render_diagram \
            "$SCRIPT_DIR/pipeline_architecture_formatters.dot" \
            "pipeline_architecture_formatters" \
            "✨ Output Formatters Feature (v3.1)"

        render_diagram \
            "$SCRIPT_DIR/pipeline_architecture_extractors.dot" \
            "pipeline_architecture_extractors" \
            "⚙️  Metric Extractors Explained"
        ;;
esac

# Summary
echo -e "${BOLD}${GREEN}✓ Rendering complete!${NC}"
echo ""
echo -e "${BOLD}Generated Files:${NC}"
echo "────────────────────────────────────────────"

if [ "$MODE" == "--doc" ] || [ "$MODE" == "--all" ] || [ "$MODE" == "" ]; then
    echo -e "${BLUE}Documentation:${NC}"
    echo "  docs/pipeline_architecture.{png,svg,pdf}"
fi

if [ "$MODE" == "--presentation" ] || [ "$MODE" == "--all" ] || [ "$MODE" == "" ]; then
    echo -e "${BLUE}Presentation:${NC}"
    echo "  docs/pipeline_architecture_presentation.{png,svg,pdf}"
    echo "  docs/pipeline_architecture_simple.{png,svg,pdf}"
    echo "  docs/pipeline_architecture_formatters.{png,svg,pdf}"
    echo "  docs/pipeline_architecture_extractors.{png,svg,pdf}"
fi

echo ""
echo -e "${BOLD}Quick View:${NC}"
echo "  macOS:   open docs/pipeline_architecture_presentation.png"
echo "  Linux:   xdg-open docs/pipeline_architecture_presentation.png"
echo ""
echo -e "${BOLD}Usage Tip:${NC}"
echo "  For presentations, use the *_presentation.* or *_simple.* versions"
echo "  For documentation, use the pipeline_architecture.* version"
