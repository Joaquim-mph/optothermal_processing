# Pipeline Architecture Diagrams - Complete Guide

**Created:** November 8, 2025 | **Last Updated**: January 2025
**Purpose:** Presentation-optimized diagrams with large fonts and clean layouts

---

## Quick Start

### Generate All Presentation Versions

```bash
# From project root
./docs/render_pipeline_diagram.sh --presentation
```

This creates:
- `pipeline_architecture_simple.{png,svg,pdf}`
- `pipeline_architecture_presentation.{png,svg,pdf}`
- `pipeline_architecture_formatters.{png,svg,pdf}`
- `pipeline_architecture_extractors.{png,svg,pdf}`

### Generate All Versions (Including Documentation)

```bash
./docs/render_pipeline_diagram.sh --all
# or just
./docs/render_pipeline_diagram.sh
```

### Essential Commands

```bash
# View presentation diagrams
open docs/pipeline_architecture_simple.png
open docs/pipeline_architecture_presentation.png
open docs/pipeline_architecture_formatters.png

# Regenerate all
./docs/render_pipeline_diagram.sh --presentation
```

---

## Available Versions

| Version | Detail Level | Font Size | Best Use | File Size |
|---------|--------------|-----------|----------|-----------|
| **Simple** | ⭐☆☆☆☆ | 28-32pt | Quick overview, opening slide | ~144 KB PNG |
| **Presentation** | ⭐⭐⭐☆☆ | 20-24pt | Technical talk, architecture | ~220 KB PNG |
| **Extractors** | ⭐⭐⭐☆☆ | 18-24pt | Metrics pipeline deep-dive | ~170 KB PNG |
| **Formatters** | ⭐⭐☆☆☆ | 20-24pt | v3.1 feature focus | ~216 KB PNG |
| **Full Documentation** | ⭐⭐⭐⭐⭐ | 11-14pt | Reference only (not for slides) | ~704 KB PNG |

### 1. 📊 Simple Overview (`pipeline_architecture_simple.*`)

**Best for:** Opening slide, executive summary, quick overview

**Features:**
- Landscape orientation (16:9)
- Very large fonts (28-32pt)
- Only 5 main stages: RAW → STAGED → METRICS → EXPORT → PLOTS
- Single unified `full-pipeline` command highlighted
- Minimal details, maximum readability
- **Readable from 20 feet away**

**When to use:**
- First slide of presentation
- High-level management overview
- Quick team standup (1-minute explanation)
- 5-minute demos

### 2. 🎯 Presentation Version (`pipeline_architecture_presentation.*`)

**Best for:** Detailed technical presentation, team meeting, training

**Features:**
- Portrait orientation with large sections
- Large fonts (20-24pt)
- All 4 stages clearly separated by color
- Key commands shown (stage-all, derive-all-metrics, enrich-history)
- Legend included
- NEW v3.1 features highlighted
- **Readable from 10 feet away**

**When to use:**
- Technical team presentations
- Architecture discussions
- Training sessions (15-minute talks)
- Detailed walkthroughs

### 3. ⚙️ Metric Extractors (`pipeline_architecture_extractors.*`)

**Best for:** Explaining how derived metrics are computed

**Features:**
- Portrait orientation
- Shows complete extractor workflow (4 steps)
- Includes code example
- Visual data flow from measurement to metric
- Available extractors list
- Key features highlighted
- Large fonts (18-24pt)

**When to use:**
- Explaining derived metrics pipeline
- Developer onboarding
- Technical deep-dive on metric extraction
- Algorithm/implementation discussions

### 4. ✨ Output Formatters Focus (`pipeline_architecture_formatters.*`)

**Best for:** Presenting the new v3.1 formatters feature

**Features:**
- Portrait orientation
- Focuses on data export capabilities
- Shows three output formats: Table, JSON, CSV
- Use cases clearly displayed (interactive, automation, analysis)
- Example commands included
- Large fonts (20-24pt)

**When to use:**
- Feature announcement (v3.1)
- Data export workflow training
- Automation/scripting presentations
- Showing integration with external tools

### 5. 📚 Full Documentation (`pipeline_architecture.*`)

**Best for:** Documentation, deep technical reference, code reviews

**Features:**
- Very detailed with all components
- Shows all processing stages
- Complete data flow paths
- All commands and utilities
- Module organization
- Standard fonts (11-14pt)

**When to use:**
- Technical documentation
- Code review reference
- Comprehensive architecture documentation
- **NOT for presentations** (too detailed)

---

## File Formats

Each diagram is available in 3 formats:

| Format | Best For | Notes |
|--------|----------|-------|
| **PNG** | PowerPoint, Keynote, Google Slides | High quality, ~150 DPI |
| **SVG** | Web pages, scalable displays | Vector format, smallest file |
| **PDF** | Print, LaTeX, high-quality documents | Vector format, embedded fonts |

---

## Presentation Tips

### Recommended Slide Order

**15-Minute Technical Talk:**

1. **Slide 1 - Overview:** `pipeline_architecture_simple.png` (3 min)
   - "Here's our complete pipeline in 5 stages"
   - Show the unified `full-pipeline` command

2. **Slide 2 - Detailed Flow:** `pipeline_architecture_presentation.png` (5 min)
   - "Let's dive into each stage"
   - Explain staging → metrics → enrichment → output

3. **Slide 3 - How Extractors Work:** `pipeline_architecture_extractors.png` (4 min)
   - "How do we compute derived metrics?"
   - Show extractor workflow with code example

4. **Slide 4 - New Feature:** `pipeline_architecture_formatters.png` (3 min)
   - "NEW in v3.1: Output Formatters"
   - Show JSON/CSV export capabilities

**5-Minute Standup:**
Use **only** `pipeline_architecture_simple.png`:
- "Here's what we built"
- "These are the 5 stages"
- "Run `full-pipeline` for everything"

**v3.1 Feature Demo:**
Use `pipeline_architecture_formatters.png` (1 slide)

### Font Sizes & Readability

All presentation versions use **large fonts** optimized for screen viewing:

| Element | Documentation | Presentation | Simple |
|---------|--------------|--------------|--------|
| Title | 16pt | 36pt | 40pt |
| Section headers | 12pt | 24pt | 28pt |
| Node labels | 11pt | 22pt | 28pt |
| Edge labels | 10pt | 18pt | 24pt |
| **Readability from** | **Desk** | **10 feet** | **20 feet** |

### Color Scheme

Consistent across all versions:

- 🔵 **Blue** - Raw data (Stage 1)
- 🟢 **Green** - Staged data (Stage 2)
- 🟠 **Orange** - Derived metrics (Stage 3)
- 🟣 **Purple** - Processing steps
- 🔴 **Red** - Output formats and plots
- 🟡 **Yellow** - Special highlights (full-pipeline, examples)

**Color Psychology:**
- **Blue:** Trust, stability (raw data)
- **Green:** Growth, processing (staged data)
- **Orange:** Analysis, insight (metrics)
- **Red:** Action, results (output)
- **Purple:** Logic, transformation (processing)
- **Yellow:** Attention, importance (highlights)

---

## Inserting into Slides

### PowerPoint / Keynote / Google Slides

1. Use **PNG** format for best compatibility
2. Insert → Picture → `pipeline_architecture_simple.png`
3. Resize to fit slide (maintains aspect ratio)
4. No need to crop - designed for full-slide display

**Example:**
```
Insert → Picture → docs/pipeline_architecture_simple.png
```

### LaTeX Beamer

```latex
\begin{frame}{Pipeline Architecture}
    \centering
    \includegraphics[width=\textwidth]{docs/pipeline_architecture_simple.pdf}
\end{frame}
```

Use **PDF** format for best quality in LaTeX.

### Web Presentations (reveal.js, etc.)

```html
<section>
    <h2>Pipeline Architecture</h2>
    <img src="docs/pipeline_architecture_simple.svg" alt="Pipeline" />
</section>
```

Use **SVG** format for web presentations (smaller file, scales perfectly).

---

## Customization

### 1. Edit DOT Source

```bash
# Open in your favorite editor
nano docs/pipeline_architecture_simple.dot
```

### 2. Adjust Font Sizes

Find these lines and adjust:
```dot
graph [
    fontsize=40  // Main title
]

node [fontsize=28]  // Box labels
edge [fontsize=24]  // Connection labels
```

**Make fonts larger:**
```dot
graph [fontsize=50]     // Increase from 40
node [fontsize=36]      // Increase from 28
edge [fontsize=28]      // Increase from 24
```

### 3. Change Colors

Find color definitions:
```dot
fillcolor="#bbdefb"  // Light blue
color="#1976d2"      // Dark blue border
```

### 4. Change Aspect Ratio

For 4:3 slides instead of 16:9:
```dot
size="12,9!"  // 4:3 ratio instead of 16:9
```

### 5. Change Layout Direction

```dot
rankdir=TB  // Top-to-bottom (portrait)
rankdir=LR  // Left-to-right (landscape)
```

### 6. Regenerate

After making changes:
```bash
./docs/render_pipeline_diagram.sh --presentation
```

---

## Technical Details

### Design Decisions

**Why 16:9 aspect ratio?**
- Modern standard for presentations
- Matches most projectors and displays
- More horizontal space for data flow

**Why large fonts?**
- Readable from back of room (20+ feet)
- Accessible for vision-impaired
- Professional presentation standard

**Why multiple versions?**
- **Simple:** For audiences unfamiliar with system
- **Presentation:** For technical teams needing details
- **Extractors:** For algorithm/implementation discussions
- **Formatters:** For feature-specific demonstrations

**Why PNG + SVG + PDF?**
- PNG: Universal compatibility, good for slides
- SVG: Web presentations, perfect scaling
- PDF: LaTeX, print, vector quality

### Rendering Script

**Script**: `render_pipeline_diagram.sh`

**Features:**
- ✅ Supports multiple diagram versions
- ✅ Mode selection: `--all`, `--presentation`, `--doc`
- ✅ Colored output with status indicators
- ✅ File size reporting
- ✅ Error checking

**Usage:**
```bash
# Generate all presentation versions
./docs/render_pipeline_diagram.sh --presentation

# Generate all versions (documentation + presentation)
./docs/render_pipeline_diagram.sh --all

# Generate only documentation version
./docs/render_pipeline_diagram.sh --doc
```

**Output Example:**
```
╔═══════════════════════════════════════════════════╗
║  Pipeline Architecture Diagram Renderer          ║
╚═══════════════════════════════════════════════════╝

Mode: Presentation versions only

🎯 Presentation Version (High-Level)
  Source: pipeline_architecture_presentation.dot
  ✓ PNG: 220K
  ✓ SVG:  24K
  ✓ PDF: 268K

📊 Simple Overview (Single Slide)
  Source: pipeline_architecture_simple.dot
  ✓ PNG: 144K
  ✓ SVG:  12K
  ✓ PDF: 288K

✨ Output Formatters Feature (v3.1)
  Source: pipeline_architecture_formatters.dot
  ✓ PNG: 216K
  ✓ SVG:  20K
  ✓ PDF: 256K

✓ Rendering complete!
```

### File Manifest

**All files in `docs/`:**

```
📁 docs/
├── 📄 DOT Source Files (editable)
│   ├── pipeline_architecture.dot (20 KB)
│   ├── pipeline_architecture_simple.dot (1.9 KB)
│   ├── pipeline_architecture_presentation.dot (6.8 KB)
│   ├── pipeline_architecture_formatters.dot (6.3 KB)
│   └── pipeline_architecture_extractors.dot (5.2 KB)
│
├── 🖼️  PNG Images (for slides)
│   ├── pipeline_architecture_simple.png (143 KB) ⭐ PRESENTATION
│   ├── pipeline_architecture_presentation.png (217 KB) ⭐ PRESENTATION
│   ├── pipeline_architecture_formatters.png (215 KB) ⭐ PRESENTATION
│   ├── pipeline_architecture_extractors.png (170 KB) ⭐ PRESENTATION
│   └── pipeline_architecture.png (657 KB) - Documentation
│
├── 🎨 SVG Images (for web)
│   ├── pipeline_architecture_simple.svg (8.6 KB)
│   ├── pipeline_architecture_presentation.svg (21 KB)
│   ├── pipeline_architecture_formatters.svg (17 KB)
│   ├── pipeline_architecture_extractors.svg (14 KB)
│   └── pipeline_architecture.svg (66 KB)
│
├── 📄 PDF Images (for print/LaTeX)
│   ├── pipeline_architecture_simple.pdf (286 KB)
│   ├── pipeline_architecture_presentation.pdf (266 KB)
│   ├── pipeline_architecture_formatters.pdf (256 KB)
│   ├── pipeline_architecture_extractors.pdf (240 KB)
│   └── pipeline_architecture.pdf (124 KB)
│
├── 📜 Scripts
│   └── render_pipeline_diagram.sh (executable)
│
└── 📚 Documentation
    └── PRESENTATION_DIAGRAMS.md (this file)
```

### File Statistics

**Total files created:** 20 files
- 5 DOT source files
- 15 rendered images (5 versions × 3 formats)

**Total size:** ~2.8 MB
- DOT sources: 40 KB
- PNG images: 1.4 MB
- SVG images: 140 KB
- PDF images: 1.2 MB

**Rendering time:** ~6 seconds (all versions)

---

## Troubleshooting

### Fonts Too Small?

Edit the DOT file and increase `fontsize` values:

```dot
graph [fontsize=50]     // Increase from 40
node [fontsize=36]      // Increase from 28
edge [fontsize=28]      // Increase from 24
```

Then regenerate:
```bash
./docs/render_pipeline_diagram.sh --presentation
```

### Diagram Too Wide for Slide?

The diagrams are designed for 16:9 aspect ratio. If using 4:3 slides:

1. Use **portrait** versions (presentation, extractors, or formatters)
2. Or adjust `size` parameter in DOT file:
   ```dot
   size="12,9!"  // 4:3 ratio instead of 16:9
   ```

### Colors Not Showing?

Check that your viewer supports color:
- PNG: Always shows colors
- PDF: Requires color-capable PDF viewer
- SVG: Requires SVG-capable browser/viewer

### Wrong Aspect Ratio?

Edit `size="16,9!"` in DOT file to `size="4,3!"` for older projectors, then regenerate.

### Need Different Layout?

Change the `rankdir` parameter:
- `rankdir=TB` for top-to-bottom (portrait)
- `rankdir=LR` for left-to-right (landscape)

### Rendering Errors?

Ensure Graphviz is installed:
```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz

# Verify
dot -V
```

---

## Creation Summary

### What Was Created

**3 presentation-ready versions** of the pipeline architecture diagram, optimized for screen viewing with large fonts (20-32pt) and clean layouts. All versions use 16:9 aspect ratio for modern presentation software.

### Before vs. After

**Before (Documentation Only):**
- ❌ 1 diagram version (too detailed for presentations)
- ❌ Small fonts (11-14pt)
- ❌ Complex layout (all components shown)
- ❌ Only suitable for documentation

**After (5 Versions):**
- ✅ 5 diagram versions (documentation + 4 presentation)
- ✅ Large fonts (20-32pt for presentation)
- ✅ Clean layouts optimized for slides
- ✅ Suitable for diverse audiences

### Features

All presentation diagrams are optimized for:
- ✅ Screen viewing (150 DPI)
- ✅ Large rooms (fonts 20-32pt)
- ✅ Projectors (high contrast colors)
- ✅ Print (vector PDF available)

---

## See Also

- **Main Documentation**: `CLAUDE.md`
- **Pipeline Architecture**: `docs/pipeline_architecture.png` (full detail)
- **Rendering Script**: `docs/render_pipeline_diagram.sh`

---

**Ready to present? Your diagrams are in `docs/pipeline_architecture_*.{png,svg,pdf}`**

**Quick access:**
```bash
# View presentation diagrams
open docs/pipeline_architecture_simple.png
open docs/pipeline_architecture_presentation.png
open docs/pipeline_architecture_formatters.png
open docs/pipeline_architecture_extractors.png

# Regenerate all
./docs/render_pipeline_diagram.sh --presentation
```

---

**Credits:**
- **Created by:** Claude Code Assistant
- **Tool:** Graphviz (DOT language)
- **Render script:** Bash with Graphviz `dot` command
- **Fonts:** Arial Bold (system font)

**Last Updated:** January 2025
