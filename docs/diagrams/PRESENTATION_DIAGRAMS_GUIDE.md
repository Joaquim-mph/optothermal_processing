# Pipeline Architecture Diagrams - Presentation Guide

**Created:** November 8, 2025
**Purpose:** Presentation-optimized diagrams with large fonts and clean layouts

---

## Available Versions

### 1. 📊 Simple Overview (`pipeline_architecture_simple.*`)

**Best for:** Opening slide, executive summary, quick overview

**Features:**
- Landscape orientation (16:9)
- Very large fonts (28-32pt)
- Only 5 main stages: RAW → STAGED → METRICS → EXPORT → PLOTS
- Single unified `full-pipeline` command highlighted
- Minimal details, maximum readability

**When to use:**
- First slide of presentation
- High-level management overview
- Quick team standup
- 1-minute explanation

**File size:** ~144 KB PNG

---

### 2. 🎯 Presentation Version (`pipeline_architecture_presentation.*`)

**Best for:** Detailed technical presentation, team meeting, training

**Features:**
- Portrait orientation with large sections
- Large fonts (20-24pt)
- All 4 stages clearly separated by color
- Key commands shown (stage-all, derive-all-metrics, enrich-history)
- Legend included
- NEW v3.1 features highlighted

**When to use:**
- Technical team presentations
- Architecture discussions
- Training sessions
- Detailed walkthroughs

**File size:** ~220 KB PNG

---

### 3. ✨ Output Formatters Focus (`pipeline_architecture_formatters.*`)

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

**File size:** ~216 KB PNG

---

### 4. ⚙️ Metric Extractors (`pipeline_architecture_extractors.*`)

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

**File size:** ~170 KB PNG

---

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
- NOT for presentations (too detailed)

**File size:** ~704 KB PNG

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

### Generate All Versions (Including Documentation)

```bash
./docs/render_pipeline_diagram.sh --all
# or just
./docs/render_pipeline_diagram.sh
```

### Generate Only Documentation Version

```bash
./docs/render_pipeline_diagram.sh --doc
```

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

### Slide Order Recommendation

1. **Slide 1 - Overview:** `pipeline_architecture_simple.png`
   - "Here's our complete pipeline in 5 stages"
   - Show the unified `full-pipeline` command

2. **Slide 2 - Detailed Flow:** `pipeline_architecture_presentation.png`
   - "Let's dive into each stage"
   - Explain staging → metrics → enrichment → output

3. **Slide 3 - How Extractors Work:** `pipeline_architecture_extractors.png`
   - "How do we compute derived metrics?"
   - Show extractor workflow with code example

4. **Slide 4 - New Feature:** `pipeline_architecture_formatters.png`
   - "NEW in v3.1: Output Formatters"
   - Show JSON/CSV export capabilities

### Font Sizes

All presentation versions use **large fonts** optimized for screen viewing:

- **Titles:** 32-40pt
- **Section headers:** 24-28pt
- **Node labels:** 20-24pt
- **Edge labels:** 18-20pt
- **Legend:** 18-20pt

### Color Scheme

Consistent across all versions:

- 🔵 **Blue** - Raw data (Stage 1)
- 🟢 **Green** - Staged data (Stage 2)
- 🟠 **Orange** - Derived metrics (Stage 3)
- 🟣 **Purple** - Processing steps
- 🔴 **Red** - Output formats and plots
- 🟡 **Yellow** - Special highlights (full-pipeline, examples)

---

## Customization

To modify diagrams for your presentation:

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

### 3. Change Colors

Find color definitions:
```dot
fillcolor="#bbdefb"  // Light blue
color="#1976d2"      // Dark blue border
```

### 4. Regenerate

```bash
./docs/render_pipeline_diagram.sh --presentation
```

---

## Inserting into Slides

### PowerPoint / Keynote / Google Slides

1. Use **PNG** format for compatibility
2. Insert → Picture → `pipeline_architecture_simple.png`
3. Resize to fit slide (maintains aspect ratio)
4. No need to crop - designed for full-slide display

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

## Comparison Table

| Version | Detail Level | Font Size | Best Use | Slide Count |
|---------|--------------|-----------|----------|-------------|
| Simple | ⭐☆☆☆☆ | 28-32pt | Quick overview | 1 slide |
| Presentation | ⭐⭐⭐☆☆ | 20-24pt | Technical talk | 1-2 slides |
| Extractors | ⭐⭐⭐☆☆ | 18-24pt | Algorithm deep-dive | 1 slide |
| Formatters | ⭐⭐☆☆☆ | 20-24pt | Feature focus | 1 slide |
| Full Documentation | ⭐⭐⭐⭐⭐ | 11-14pt | Reference only | Not for slides |

---

## Troubleshooting

### Fonts Too Small?

Edit the DOT file and increase `fontsize` values:

```dot
graph [fontsize=50]     // Increase from 40
node [fontsize=36]      // Increase from 28
edge [fontsize=28]      // Increase from 24
```

### Diagram Too Wide for Slide?

The diagrams are designed for 16:9 aspect ratio. If using 4:3 slides:

1. Use **portrait** versions (presentation or formatters)
2. Or adjust `size` parameter in DOT file:
   ```dot
   size="12,9!"  // 4:3 ratio instead of 16:9
   ```

### Colors Not Showing?

Check that your viewer supports color:
- PNG: Always shows colors
- PDF: Requires color-capable PDF viewer
- SVG: Requires SVG-capable browser/viewer

---

## Sample Presentation Structure

### 15-Minute Technical Talk

1. **Title Slide** (1 min)
   - Project overview

2. **Simple Overview** (3 min)
   - Show `pipeline_architecture_simple.png`
   - Explain 5 stages
   - Highlight `full-pipeline` command

3. **Detailed Architecture** (5 min)
   - Show `pipeline_architecture_presentation.png`
   - Walk through each stage
   - Explain key commands

4. **New Features** (4 min)
   - Show `pipeline_architecture_formatters.png`
   - Demo JSON/CSV export
   - Show external tool integration

5. **Q&A** (2 min)

### 5-Minute Standup

Use **only** `pipeline_architecture_simple.png`:
- "Here's what we built"
- "These are the 5 stages"
- "Run `full-pipeline` for everything"

---

## File Locations

All diagrams are in `docs/`:

```
docs/
├── pipeline_architecture.dot              (documentation version source)
├── pipeline_architecture_simple.dot       (simple overview source)
├── pipeline_architecture_presentation.dot (presentation version source)
├── pipeline_architecture_formatters.dot   (formatters focus source)
│
├── pipeline_architecture_simple.{png,svg,pdf}       ← USE THESE
├── pipeline_architecture_presentation.{png,svg,pdf} ← FOR YOUR
├── pipeline_architecture_formatters.{png,svg,pdf}   ← PRESENTATION
│
└── pipeline_architecture.{png,svg,pdf}    (documentation - too detailed)
```

---

## Questions?

**Need different aspect ratio?** Edit `size="16,9!"` in DOT file
**Need different colors?** Edit `fillcolor` and `color` attributes
**Need bigger fonts?** Edit `fontsize` values
**Need different layout?** Edit `rankdir` (TB=top-to-bottom, LR=left-to-right)

After changes, run:
```bash
./docs/render_pipeline_diagram.sh --presentation
```

---

## License & Attribution

These diagrams are part of the optothermal processing pipeline project.
Feel free to use in presentations, include attribution to the project.

---

**Ready to present? Your diagrams are in `docs/pipeline_architecture_*.{png,svg,pdf}`**

**Quick view:**
```bash
open docs/pipeline_architecture_simple.png
open docs/pipeline_architecture_presentation.png
open docs/pipeline_architecture_formatters.png
```
