# TUI Reorganization Plan - Comprehensive Implementation Guide

**Project:** Optothermal Processing - Experiment Plotting Assistant
**Version:** 4.0 (TUI Reorganization)
**Date:** 2025-01-15
**Status:** Planning Phase

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Goals & Principles](#goals--principles)
3. [Main Menu Structure](#main-menu-structure)
4. [Detailed Screen Specifications](#detailed-screen-specifications)
5. [Implementation Phases](#implementation-phases)
6. [Technical Implementation Notes](#technical-implementation-notes)
7. [Migration Strategy](#migration-strategy)
8. [Testing Plan](#testing-plan)

---

## Overview

### Current State (v3.x)
- **Main Menu:** 9 buttons (flat structure)
- **Total Screens:** ~15
- **Organization:** Feature-based, but growing unwieldy
- **Issues:**
  - Hard to find features
  - No logical grouping
  - Difficult to scale
  - Main menu getting crowded

### Target State (v4.0)
- **Main Menu:** 6 top-level hubs
- **Total Screens:** ~30 (better organized)
- **Organization:** Hierarchical with logical hubs
- **Benefits:**
  - Clear functional areas
  - Easy to discover features
  - Scalable architecture
  - Better user experience

---

## Goals & Principles

### Design Goals
1. ✅ **Simplicity at Entry** - Main menu has only 6 options
2. ✅ **Logical Grouping** - Related features together
3. ✅ **Progressive Disclosure** - Complexity revealed when needed
4. ✅ **Scalability** - Easy to add features to hubs
5. ✅ **Discoverability** - Users can find what they need
6. ✅ **Consistency** - Predictable navigation patterns
7. ✅ **Preserve Wizard Flow** - Don't break existing workflows

### Navigation Principles
- **Every screen** has `[← Back]` and `[Home]`
- **Breadcrumbs** show current location
- **Global shortcuts** work from anywhere (Ctrl+N, Ctrl+H, Ctrl+Q)
- **Esc** always goes back one level
- **Enter** always selects focused item

---

## Main Menu Structure

### New Main Menu (6 Hubs)

```
┌─────────────────────────────────────────────────┐
│  🔬 Experiment Plotting Assistant               │
│     NanoLab - Device Characterization           │
├─────────────────────────────────────────────────┤
│                                                 │
│  📊 Plots                                       │
│  📂 Chip Histories                              │
│  ⚙️  Process New Data                           │
│  🛠️  Settings                                   │
│  ❓ Help                                        │
│  🚪 Quit                                        │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Hub Responsibilities

| Hub | Purpose | Sub-screens |
|-----|---------|-------------|
| **Plots** | All plotting activities | 5 |
| **Chip Histories** | Data exploration & analysis | 6 |
| **Process New Data** | Data pipeline management | 6 |
| **Settings** | Configuration & preferences | 4 |
| **Help** | Documentation & support | 4 |
| **Quit** | Exit application | 0 (direct action) |

**Total Sub-screens:** 25 + existing wizard screens

---

## Detailed Screen Specifications

---

## 📊 HUB 1: PLOTS

### Overview
**Purpose:** Central hub for all plotting activities
**Users:** Lab members creating plots
**Entry from:** Main Menu → Plots

---

### Screen 1.0: Plots Hub Menu

**Layout:**
```
┌─ Plots ─────────────────────────────────────────┐
│  Main Menu > Plots                              │
├─────────────────────────────────────────────────┤
│                                                 │
│  🆕 New Plot                                    │
│  📦 Batch Mode                                  │
│  🔄 Recent Configurations (3)                   │
│  🎨 Plot Presets                                │
│  🖼️  Browse Generated Plots                     │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Buttons:**
- **New Plot** → Screen 1.1 (Existing wizard)
- **Batch Mode** → Screen 1.2
- **Recent Configurations** → Screen 1.3
- **Plot Presets** → Screen 1.4
- **Browse Generated Plots** → Screen 1.5

**Implementation Notes:**
- Count of recent configs shown dynamically `(N)`
- Most common action is "New Plot" → make it primary variant
- This is a new screen (create `src/tui/screens/navigation/plots_hub.py`)

---

### Screen 1.1: New Plot Wizard

**Flow:** (EXISTING - No changes needed)
```
New Plot
  ↓
Chip Selector
  ↓
Plot Type Selector
  ↓
Config Mode Selector (Quick/Custom/Preset)
  ↓
Plot Configuration (ITS/IVg/VVg/Vt/etc.)
  ↓
Experiment Selector
  ↓
[OPTIONAL] Data Preview (plotext)
  ↓
Preview Configuration
  ↓
Generate Plot
  ↓
Success/Error Screen
```

**Implementation Notes:**
- **KEEP AS-IS** - This workflow already works
- Entry point: `router.go_to_chip_selector(mode="plot")`
- No changes to existing wizard screens
- Optional: Add Data Preview step (discussed earlier)

---

### Screen 1.2: Batch Mode

**Purpose:** Run multiple plots from YAML config

**Layout:**
```
┌─ Batch Mode ────────────────────────────────────┐
│  Main Menu > Plots > Batch Mode                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  📁 Recent Batch Configs:                       │
│  ├─ alisson67_plots.yaml                        │
│  ├─ encap81_plots.yaml                          │
│  └─ weekly_batch.yaml                           │
│                                                 │
│  🆕 Create New Batch Config                     │
│  📂 Browse Batch Configs                        │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Sub-flow:**

**Option A: Select Existing Config**
```
Select Config (e.g., alisson67_plots.yaml)
  ↓
Review Batch Config Screen
  ├─ Chip: 67
  ├─ Plots: 12 plots
  ├─ Estimated time: ~2 minutes
  └─ Output: figs/Alisson67/
  ↓
Confirm Settings:
  ├─ Parallel Workers: [1-8] (default 4)
  └─ Dry Run: [Yes/No]
  ↓
Execute Batch
  ↓
Progress Screen (live updates)
  ├─ Plot 5/12: IVg_seq_2_8_14
  ├─ Progress: [██████░░░░] 42%
  └─ Errors: 0
  ↓
Batch Complete Summary
  ├─ ✅ Success: 11
  ├─ ❌ Failed: 1 (show details)
  └─ Total time: 1m 45s
  ↓
[View Plots] [View Errors] [Done]
```

**Option B: Create New Config**
```
Create New Batch Config
  ↓
Config Form:
  ├─ Name: [_______]
  ├─ Chip: [Select]
  ├─ Chip Group: [_______]
  └─ Default Legend By: [Select]
  ↓
Add Plots (loop):
  ├─ Plot Type: [Select]
  ├─ Seq Numbers: [_______]
  ├─ Tag: [_______]
  └─ Custom Options: [Configure]
  ↓
  [Add Another Plot] [Done Adding]
  ↓
Review Config (YAML preview)
  ↓
Save Config
  ├─ Path: config/batch_plots/[name].yaml
  └─ [Save] [Edit] [Cancel]
  ↓
[Run Now] or [Save & Exit]
```

**Implementation Notes:**
- New screen: `src/tui/screens/batch/batch_mode_hub.py`
- New screen: `src/tui/screens/batch/batch_config_review.py`
- New screen: `src/tui/screens/batch/batch_progress.py`
- New screen: `src/tui/screens/batch/batch_complete.py`
- Reuse existing `src/plotting/batch.py` backend
- Auto-discover YAML files in `config/batch_plots/`

---

### Screen 1.3: Recent Configurations

**Purpose:** Quick access to recently used plot configs

**Layout:**
```
┌─ Recent Configurations ─────────────────────────┐
│  Main Menu > Plots > Recent Configurations      │
├─────────────────────────────────────────────────┤
│                                                 │
│  Sort: [Date ▼] [Chip] [Type]                  │
│  Filter: [______] 🔍                            │
│                                                 │
│  📅 2 hours ago                                 │
│  ├─ ITS - Alisson67 - Seq 52,57,58             │
│  │  Legend: Wavelength | Baseline: 60s          │
│  │  [Run] [Edit] [Delete]                      │
│                                                 │
│  📅 Yesterday                                   │
│  ├─ IVg - Encap81 - Seq 2,8,14                 │
│  │  [Run] [Edit] [Delete]                      │
│                                                 │
│  ├─ Transconductance - Alisson67 - Seq 2       │
│  │  [Run] [Edit] [Delete]                      │
│                                                 │
│  [Clear All] [Export] [Home] [← Back]          │
└─────────────────────────────────────────────────┘
```

**Flow:**

**Action: Run**
```
Select Config → Run
  ↓
Confirm: "Run this config again?"
  ↓
Generate Plot (skip wizard)
  ↓
Success/Error Screen
```

**Action: Edit**
```
Select Config → Edit
  ↓
Load Config into Wizard
  ↓
Jump to Config Screen (ITS/IVg/etc.)
  ↓
Continue Wizard Flow
  ↓
Generate Plot
```

**Action: Delete**
```
Select Config → Delete
  ↓
Confirm: "Delete this configuration?"
  ↓
Remove from ConfigManager
  ↓
Refresh list
```

**Implementation Notes:**
- Use existing `src/tui/config_manager.py`
- New screen: `src/tui/screens/plots/recent_configs_list.py`
- Add search/filter capability
- Add sorting (by date, chip, type)
- Pagination if >20 configs

---

### Screen 1.4: Plot Presets

**Purpose:** Quick access to predefined plot configurations

**Layout:**
```
┌─ Plot Presets ──────────────────────────────────┐
│  Main Menu > Plots > Plot Presets               │
├─────────────────────────────────────────────────┤
│                                                 │
│  Filter by Type: [All ▼] [ITS] [IVg] [VVg]     │
│                                                 │
│  📊 ITS Presets:                                │
│  ├─ Photoresponse 365nm                         │
│  │  Baseline: Auto | Legend: Wavelength         │
│  │  [Use Preset]                                │
│                                                 │
│  ├─ Photoresponse 405nm                         │
│  │  [Use Preset]                                │
│                                                 │
│  ├─ Gate Voltage Sweep                          │
│  │  [Use Preset]                                │
│                                                 │
│  📈 Vt Presets:                                 │
│  ├─ Voltage Dynamics                            │
│  │  [Use Preset]                                │
│                                                 │
│  [Create Custom Preset] [Home] [← Back]        │
└─────────────────────────────────────────────────┘
```

**Flow:**
```
Select Preset
  ↓
Preset Details Screen
  ├─ Name: Photoresponse 365nm
  ├─ Description: Standard photoresponse plot...
  ├─ Settings:
  │   ├─ Legend By: Wavelength
  │   ├─ Baseline: Auto
  │   ├─ Filters: Wavelength = 365nm
  │   └─ Padding: 0.05
  └─ Example: [Preview image if available]
  ↓
[Use This Preset] [Back]
  ↓
Select Chip
  ↓
Select Experiments (pre-filtered by preset)
  ↓
Generate Plot
```

**Implementation Notes:**
- Use existing `src/plotting/its_presets.py`
- Extend to other plot types (Vt, VVg presets)
- New screen: `src/tui/screens/plots/preset_selector.py`
- New screen: `src/tui/screens/plots/preset_details.py`
- Support custom user-defined presets (saved in `config/user_presets/`)

---

### Screen 1.5: Browse Generated Plots

**Purpose:** View, manage, and regenerate existing plots

**Layout:**
```
┌─ Browse Plots ──────────────────────────────────┐
│  Main Menu > Plots > Browse Plots               │
├─────────────────────────────────────────────────┤
│                                                 │
│  Filters:                                       │
│  ├─ Chip: [All ▼]                               │
│  ├─ Type: [All ▼]                               │
│  └─ Date: [Last 7 days ▼]                       │
│                                                 │
│  Search: [______] 🔍                            │
│                                                 │
│  📊 Results (24 plots):                         │
│                                                 │
│  📅 Today                                       │
│  ├─ encap67_ITS_seq_52_57_58.png               │
│  │  Created: 2 hours ago | Size: 245 KB        │
│  │  [View] [Regenerate] [Delete]               │
│                                                 │
│  ├─ encap81_IVg_seq_2_8_14.png                 │
│  │  [View] [Regenerate] [Delete]               │
│                                                 │
│  📅 Yesterday                                   │
│  ├─ encap67_gm_savgol_seq_2.png                │
│  │  [View] [Regenerate] [Delete]               │
│                                                 │
│  [Open Output Folder] [Home] [← Back]          │
└─────────────────────────────────────────────────┘
```

**Flow:**

**Action: View**
```
Select Plot → View
  ↓
Plot Details Screen
  ├─ Filename: encap67_ITS_seq_52_57_58.png
  ├─ Path: figs/Alisson67/It/
  ├─ Size: 245 KB
  ├─ Created: 2 hours ago
  ├─ Config Used:
  │   ├─ Seq: 52, 57, 58
  │   ├─ Legend: Wavelength
  │   └─ Baseline: 60s
  └─ [Thumbnail if possible]
  ↓
[Open in System Viewer] [Regenerate] [Delete] [Back]
```

**Action: Regenerate**
```
Select Plot → Regenerate
  ↓
Confirm: "Regenerate this plot?"
  ├─ Load saved config if available
  └─ Or: "Config not found, create new?"
  ↓
If config exists:
  ├─ Generate Plot (skip wizard)
  └─ Overwrite confirmation
If config missing:
  ├─ Start wizard with pre-filled values
  └─ (Chip, seq numbers, type inferred from filename)
  ↓
Success/Error Screen
```

**Implementation Notes:**
- New screen: `src/tui/screens/plots/plot_browser.py`
- New screen: `src/tui/screens/plots/plot_details.py`
- Scan `figs/` directory recursively
- Parse filenames to extract metadata
- Cache plot list (refresh on demand)
- Optional: Generate thumbnails using PIL/imageio
- Link to config if saved in ConfigManager

---

## 📂 HUB 2: CHIP HISTORIES

### Overview
**Purpose:** Data exploration, metrics analysis, and experiment browsing
**Users:** Researchers analyzing data
**Entry from:** Main Menu → Chip Histories

---

### Screen 2.0: Chip Histories Hub Menu

**Layout:**
```
┌─ Chip Histories ────────────────────────────────┐
│  Main Menu > Chip Histories                     │
├─────────────────────────────────────────────────┤
│                                                 │
│  📊 View Standard History                       │
│  ✨ View Enriched History                       │
│  🔬 Metrics Explorer                            │
│  🔍 Experiment Browser                          │
│  👁️  Data Preview (plotext)                     │
│  📤 Export History                              │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Buttons:**
- **View Standard History** → Screen 2.1
- **View Enriched History** → Screen 2.2
- **Metrics Explorer** → Screen 2.3
- **Experiment Browser** → Screen 2.4
- **Data Preview** → Screen 2.5
- **Export History** → Screen 2.6

**Implementation Notes:**
- New screen: `src/tui/screens/navigation/histories_hub.py`
- This is the central hub for all data exploration

---

### Screen 2.1: View Standard History

**Purpose:** Browse chip experiment history (standard columns)

**Layout:**
```
┌─ Standard History ──────────────────────────────┐
│  Main Menu > Histories > Standard History       │
├─────────────────────────────────────────────────┤
│                                                 │
│  Select Chip: [Alisson67 ▼]                     │
│                                                 │
│  Filters:                                       │
│  ├─ Procedure: [All ▼]                          │
│  ├─ Date: [All time ▼]                          │
│  ├─ Light: [All ▼]                              │
│  └─ VG: [Any]                                   │
│                                                 │
│  Results: 127 experiments                       │
│                                                 │
│  Seq │ Date       │ Proc │ VG   │ Light │ λ    │
│  ────┼────────────┼──────┼──────┼───────┼──────│
│   52 │ 2025-01-10 │ It   │ -0.4 │ 💡    │ 365  │
│   57 │ 2025-01-10 │ It   │ -0.4 │ 💡    │ 405  │
│   58 │ 2025-01-10 │ It   │ -0.4 │ 💡    │ 530  │
│    2 │ 2025-01-09 │ IVg  │ ---  │ 🌙    │ ---  │
│                                                 │
│  [↑↓ Navigate] [Enter=Details] [P=Preview]     │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Flow:**
```
Select Chip
  ↓
Apply Filters (optional)
  ↓
Table View (paginated, sortable)
  ↓
Select Experiment (Enter)
  ↓
Experiment Details Screen
  ├─ All metadata (seq, date, procedure, params)
  ├─ Parquet path
  ├─ File size
  └─ Actions:
      ├─ [Preview Data] → plotext preview
      ├─ [Create Plot] → Jump to wizard with pre-fill
      └─ [Export] → Export this experiment data
  ↓
[Back to Table]
```

**Implementation Notes:**
- Reuse/enhance existing `src/tui/screens/analysis/history_browser.py`
- Use Polars DataFrames for fast filtering/sorting
- Pagination: 50 experiments per page
- Keyboard shortcuts: P for preview, Enter for details
- Cache loaded history (reload on demand)

---

### Screen 2.2: View Enriched History

**Purpose:** Browse chip history WITH derived metrics

**Layout:**
```
┌─ Enriched History ──────────────────────────────┐
│  Main Menu > Histories > Enriched History       │
├─────────────────────────────────────────────────┤
│                                                 │
│  Select Chip: [Alisson67 ▼]                     │
│                                                 │
│  ⚠️  Enriched history available ✓               │
│  Last updated: 2 hours ago                      │
│  [Refresh Metrics]                              │
│                                                 │
│  Filters:                                       │
│  ├─ Procedure: [IVg ▼]                          │
│  ├─ CNP Voltage: [Any]                          │
│  └─ Photoresponse: [> 0 µA]                     │
│                                                 │
│  Seq │ Date │ Proc │ CNP(V) │ PR(µA) │ τ(s) │   │
│  ────┼──────┼──────┼────────┼────────┼──────┼───│
│   52 │ 01/10│ It   │ ---    │ 2.34   │ 45.2 │   │
│   57 │ 01/10│ It   │ ---    │ 1.87   │ 43.1 │   │
│    2 │ 01/09│ IVg  │ -0.23  │ ---    │ ---  │   │
│    8 │ 01/09│ IVg  │ -0.19  │ ---    │ ---  │   │
│                                                 │
│  [↑↓ Navigate] [Enter=Details] [M=Metrics]     │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Flow:**
```
Select Chip
  ↓
Check if enriched history exists
  ├─ If NO:
  │   ├─ Show: "No enriched history found"
  │   └─ Offer: [Run Enrichment Now]
  │       ↓
  │       Run: enrich-history <chip>
  │       ↓
  │       Progress Screen
  │       ↓
  │       Reload enriched history
  │
  └─ If YES:
      ↓
      Display table with metrics columns
      ↓
      Apply filters (including metric filters)
      ↓
      Select Experiment
      ↓
      Experiment Details + Derived Metrics
      ├─ Standard metadata
      ├─ Derived metrics (CNP, PR, relaxation, etc.)
      └─ Quality flags (fit quality, warnings)
      ↓
      [Back to Table]
```

**Implementation Notes:**
- New screen: `src/tui/screens/histories/enriched_history_browser.py`
- Load from `data/03_derived/chip_histories_enriched/`
- Show metric columns conditionally (based on procedure)
- Support metric-based filtering (e.g., CNP > -0.5V)
- Offer to run enrichment if missing
- Show last enrichment timestamp

---

### Screen 2.3: Metrics Explorer

**Purpose:** Visualize and analyze derived metrics over time

**Layout:**
```
┌─ Metrics Explorer ──────────────────────────────┐
│  Main Menu > Histories > Metrics Explorer       │
├─────────────────────────────────────────────────┤
│                                                 │
│  Select Chip: [Alisson81 ▼]                     │
│                                                 │
│  Select Metric:                                 │
│  ├─ 📈 CNP Evolution (Dirac point over time)    │
│  ├─ 💡 Photoresponse Analysis                   │
│  ├─ ⏱️  Relaxation Times                         │
│  ├─ 📊 Mobility Trends                          │
│  └─ 🔍 Custom Metric Query                      │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Sub-flow: CNP Evolution**
```
Select: CNP Evolution
  ↓
CNP Evolution Screen
  ├─ Terminal plot (plotext): CNP vs Time
  │   ├─ X-axis: Experiment date
  │   └─ Y-axis: CNP Voltage (V)
  │
  ├─ Statistics:
  │   ├─ Mean CNP: -0.21 V
  │   ├─ Std Dev: 0.03 V
  │   ├─ Range: [-0.25, -0.18] V
  │   └─ Trend: Increasing ↗
  │
  └─ Actions:
      ├─ [Export Data (CSV)]
      ├─ [Create Full Plot] → Jump to plot wizard
      └─ [View Details] → Table of CNP values
```

**Sub-flow: Photoresponse Analysis**
```
Select: Photoresponse Analysis
  ↓
Filters:
  ├─ Wavelength: [365nm ▼]
  ├─ Gate Voltage: [-0.4V ▼]
  └─ Date Range: [Last 30 days ▼]
  ↓
Photoresponse Screen
  ├─ Terminal plot: ΔI vs Time
  ├─ Statistics:
  │   ├─ Mean ΔI: 2.1 µA
  │   ├─ Max ΔI: 2.8 µA
  │   └─ Min ΔI: 1.5 µA
  └─ Actions:
      ├─ [Compare Wavelengths] → Multi-wavelength plot
      ├─ [Export Data]
      └─ [Create Full Plot]
```

**Sub-flow: Relaxation Times**
```
Select: Relaxation Times
  ↓
Relaxation Times Screen
  ├─ Terminal plot: τ vs Experiment
  ├─ Fit quality indicators
  │   ├─ Good fits: 12
  │   ├─ Poor fits: 3 (flagged)
  │   └─ Failed: 1
  ├─ Statistics:
  │   ├─ Mean τ: 45.2 s
  │   ├─ Mean β: 0.78
  │   └─ R² range: [0.85, 0.99]
  └─ Actions:
      ├─ [View Poor Fits] → Inspect flagged experiments
      ├─ [Export Data]
      └─ [Refit Selected] → Re-run extraction
```

**Implementation Notes:**
- New screen: `src/tui/screens/histories/metrics_explorer_hub.py`
- New screen: `src/tui/screens/histories/cnp_evolution.py`
- New screen: `src/tui/screens/histories/photoresponse_analysis.py`
- New screen: `src/tui/screens/histories/relaxation_times.py`
- Use plotext for terminal visualization
- Load enriched history
- Filter by metric availability
- Export to CSV functionality

---

### Screen 2.4: Experiment Browser

**Purpose:** Advanced search/filter for experiments across chips

**Layout:**
```
┌─ Experiment Browser ────────────────────────────┐
│  Main Menu > Histories > Experiment Browser     │
├─────────────────────────────────────────────────┤
│                                                 │
│  🔍 ADVANCED SEARCH                             │
│                                                 │
│  Chip(s): [☑ Alisson67] [☐ Encap81] [☐ All]    │
│                                                 │
│  Procedure(s):                                  │
│  ├─ [☑] IVg  [☑] It  [☐] VVg  [☐] Vt           │
│                                                 │
│  Date Range:                                    │
│  ├─ From: [2025-01-01]                          │
│  └─ To:   [2025-01-15]                          │
│                                                 │
│  Light: [☑ Dark] [☑ Light]                      │
│                                                 │
│  Gate Voltage (V):                              │
│  ├─ Min: [-1.0]                                 │
│  └─ Max: [ 1.0]                                 │
│                                                 │
│  Wavelength (nm): [☐ 365] [☐ 405] [☐ 530]      │
│                                                 │
│  Derived Metrics:                               │
│  └─ [☑] Has CNP  [☑] Has Photoresponse          │
│                                                 │
│  [Search] [Clear Filters] [Home] [← Back]      │
└─────────────────────────────────────────────────┘
```

**Flow:**
```
Configure Filters
  ↓
[Search]
  ↓
Results Screen
  ├─ Found: 47 experiments across 2 chips
  │
  ├─ Table View (all matching experiments)
  │   Seq │ Chip │ Date │ Proc │ VG │ Light │ ...
  │
  └─ Actions per experiment:
      ├─ [Preview] → plotext preview
      ├─ [Details] → Full metadata
      ├─ [Add to Selection] → Multi-select for batch
      └─ [Create Plot] → Jump to wizard
  ↓
Multi-Select Actions (if multiple selected):
  ├─ [Create Batch Plot] → Auto-generate batch config
  ├─ [Export Selection] → Export selected experiments
  └─ [Clear Selection]
```

**Implementation Notes:**
- New screen: `src/tui/screens/histories/experiment_browser.py`
- New screen: `src/tui/screens/histories/search_results.py`
- Load histories from multiple chips
- Support multi-select (checkbox list)
- Persist search filters in session
- Export search results as CSV
- Create batch config from selection

---

### Screen 2.5: Data Preview (plotext)

**Purpose:** Quick terminal-based visualization of raw data

**Layout:**
```
┌─ Data Preview ──────────────────────────────────┐
│  Main Menu > Histories > Data Preview           │
├─────────────────────────────────────────────────┤
│                                                 │
│  Select Chip: [Alisson67 ▼]                     │
│  Select Procedure: [It ▼]                       │
│  Select Experiments: [52, 57, 58]               │
│                                                 │
│  [Start Preview]                                │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Flow:**
```
Select Chip + Procedure + Experiments
  ↓
[Start Preview]
  ↓
Preview Screen (plotext)
  ┌────────────────────────────────────────────┐
  │  Experiment 1/3 - Seq 52                   │
  │  Procedure: It | VG: -0.4V | λ: 365nm      │
  │  Light: 💡 | Date: 2025-01-10              │
  ├────────────────────────────────────────────┤
  │                                            │
  │   2.5 ┤       ╭────────╮                   │
  │       │      ╭╯        ╰╮                  │
  │   2.0 ┤     ╭╯          ╰╮                 │
  │       │    ╭╯            ╰╮                │
  │   1.5 ┼───╯               ╰────            │
  │                                            │
  │       0    50   100   150   200  (s)       │
  │                                            │
  ├────────────────────────────────────────────┤
  │  [← Prev] [→ Next] [R]efresh [P]lot [Q]uit│
  └────────────────────────────────────────────┘
```

**Keyboard Controls:**
- **← / →** - Navigate experiments
- **R** - Refresh current plot
- **P** - Create full plot from current experiment
- **Q** - Quit preview, back to menu

**Implementation Notes:**
- **USE the ExperimentPreviewScreen we created earlier!**
- File: `src/tui/screens/analysis/experiment_preview.py`
- Just add entry point from histories hub
- Supports all procedures: It, IVg, VVg, Vt, LaserCalibration
- plotext renders terminal plots
- Fast loading (data already staged)

---

### Screen 2.6: Export History

**Purpose:** Export chip history data to various formats

**Layout:**
```
┌─ Export History ────────────────────────────────┐
│  Main Menu > Histories > Export History         │
├─────────────────────────────────────────────────┤
│                                                 │
│  Select Chip(s):                                │
│  ├─ [☑] Alisson67                              │
│  ├─ [☐] Encap81                                │
│  └─ [☐] All Chips                              │
│                                                 │
│  Export Type:                                   │
│  ├─ (•) Standard History                       │
│  ├─ ( ) Enriched History                       │
│  └─ ( ) Both                                   │
│                                                 │
│  Output Format:                                 │
│  ├─ (•) CSV                                    │
│  ├─ ( ) JSON                                   │
│  └─ ( ) Parquet                                │
│                                                 │
│  Apply Filters:                                 │
│  ├─ [☐] Use current filters                    │
│  └─ [☑] Export all experiments                 │
│                                                 │
│  Output Path: [exports/]                        │
│                                                 │
│  [Export] [Home] [← Back]                      │
└─────────────────────────────────────────────────┘
```

**Flow:**
```
Configure Export Options
  ↓
[Export]
  ↓
Confirm Export
  ├─ Chip(s): Alisson67
  ├─ Type: Standard History
  ├─ Format: CSV
  ├─ Experiments: 127
  └─ Size: ~5 MB
  ↓
Export Progress
  ├─ Reading history...
  ├─ Converting to CSV...
  └─ Writing to file...
  ↓
Export Complete
  ├─ ✅ Exported: exports/Alisson67_history.csv
  ├─ Size: 4.8 MB
  └─ Rows: 127
  ↓
[Open Folder] [Export Another] [Done]
```

**Implementation Notes:**
- New screen: `src/tui/screens/histories/export_history.py`
- Support CSV, JSON, Parquet formats
- Apply same filters as history browser
- Export both standard and enriched
- Progress bar for large exports
- Open output folder in system file browser

---

## ⚙️ HUB 3: PROCESS NEW DATA

### Overview
**Purpose:** Data pipeline management (staging, histories, metrics)
**Users:** Lab members processing new measurements
**Entry from:** Main Menu → Process New Data

---

### Screen 3.0: Process New Data Hub Menu

**Layout:**
```
┌─ Process New Data ──────────────────────────────┐
│  Main Menu > Process New Data                   │
├─────────────────────────────────────────────────┤
│                                                 │
│  📥 Stage Raw Data (CSV → Parquet)              │
│  🏗️  Build Chip Histories                       │
│  ✨ Extract Derived Metrics                     │
│  🔄 Full Pipeline (All Steps)                   │
│  ✅ Validate Manifest                           │
│  📊 Pipeline Status                             │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Buttons:**
- **Stage Raw Data** → Screen 3.1
- **Build Chip Histories** → Screen 3.2
- **Extract Derived Metrics** → Screen 3.3
- **Full Pipeline** → Screen 3.4
- **Validate Manifest** → Screen 3.5
- **Pipeline Status** → Screen 3.6

**Implementation Notes:**
- New screen: `src/tui/screens/navigation/process_hub.py`
- Show last run timestamps for each operation
- Reuse existing `src/tui/screens/processing/` screens where applicable

---

### Screen 3.1: Stage Raw Data

**Purpose:** Convert raw CSV files to Parquet with validation

**Layout:**
```
┌─ Stage Raw Data ────────────────────────────────┐
│  Main Menu > Process > Stage Raw Data           │
├─────────────────────────────────────────────────┤
│                                                 │
│  Configuration:                                 │
│                                                 │
│  Raw Data Path:                                 │
│  [data/01_raw] [Browse]                         │
│                                                 │
│  Options:                                       │
│  ├─ Force Overwrite:  [☐] (re-stage existing)  │
│  ├─ Strict Mode:      [☐] (fail on errors)     │
│  └─ Parallel Workers: [6 ▼] (1-16)             │
│                                                 │
│  Advanced:                                      │
│  └─ [Show Advanced Options]                     │
│                                                 │
│  Estimated files: ~120 CSV files                │
│                                                 │
│  [Start Staging] [Home] [← Back]                │
└─────────────────────────────────────────────────┘
```

**Flow:**
```
Configure Options
  ↓
[Start Staging]
  ↓
Confirm: "Stage 120 files?"
  ↓
Processing Screen (live progress)
  ┌────────────────────────────────────────────┐
  │  Staging Raw Data                          │
  ├────────────────────────────────────────────┤
  │                                            │
  │  Progress: [████████░░] 82% (98/120)       │
  │                                            │
  │  Current: Alisson67_098.csv                │
  │  Status: Validating schema...              │
  │                                            │
  │  ✅ Processed: 96                          │
  │  ⚠️  Warnings: 5 (missing optional cols)   │
  │  ❌ Errors: 2 (schema mismatch)            │
  │                                            │
  │  Elapsed: 1m 23s | ETA: 18s                │
  │                                            │
  │  [View Errors] [Cancel]                    │
  └────────────────────────────────────────────┘
  ↓
Summary Screen
  ├─ ✅ Successfully staged: 118 files
  ├─ ⚠️  Warnings: 5 files (view details)
  ├─ ❌ Errors: 2 files (view details)
  ├─ Total time: 1m 41s
  └─ Manifest updated: 118 new entries
  ↓
[View Errors] [Retry Failed] [Done]
```

**Error Details View:**
```
Errors (2):

❌ Alisson67_023.csv
   ├─ Error: Schema mismatch
   ├─ Expected column "vds_v" not found
   └─ Line: 15

❌ Encap81_102.csv
   ├─ Error: Invalid procedure type
   ├─ Found: "<IVgX>" (unknown)
   └─ Valid types: IVg, It, VVg, Vt, etc.

[Export Error Log] [Back]
```

**Implementation Notes:**
- Reuse/enhance existing process confirmation screen
- Use `src/core/stage_raw_measurements.py` backend
- New screen: `src/tui/screens/processing/staging_progress.py`
- New screen: `src/tui/screens/processing/staging_summary.py`
- Show live progress with worker pool
- Detailed error reporting
- Retry failed files individually

---

### Screen 3.2: Build Chip Histories

**Purpose:** Generate chip history Parquet files from manifest

**Layout:**
```
┌─ Build Chip Histories ──────────────────────────┐
│  Main Menu > Process > Build Chip Histories     │
├─────────────────────────────────────────────────┤
│                                                 │
│  Scope:                                         │
│  ├─ (•) All Chips (auto-discover)              │
│  └─ ( ) Specific Chip(s)                       │
│                                                 │
│  Discovered Chips (8):                          │
│  ├─ Alisson67   (127 experiments)              │
│  ├─ Encap81     (234 experiments)              │
│  ├─ Encap75     (89 experiments)               │
│  └─ ...                                        │
│                                                 │
│  Options:                                       │
│  └─ Force Rebuild: [☐] (rebuild existing)      │
│                                                 │
│  [Start Build] [Home] [← Back]                 │
└─────────────────────────────────────────────────┘
```

**Flow:**
```
Select Scope + Options
  ↓
[Start Build]
  ↓
Processing Screen
  ├─ Building histories for 8 chips...
  ├─ Progress: [███████░░░] 70% (5/8)
  ├─ Current: Encap75
  ├─ Experiments added: 89
  └─ Elapsed: 12s | ETA: 5s
  ↓
Summary Screen
  ├─ ✅ Built histories for: 8 chips
  ├─ Total experiments: 847
  ├─ Output: data/02_stage/chip_histories/
  └─ Time: 17s
  ↓
[View Histories] [Done]
```

**Implementation Notes:**
- Use `src/core/history_builder.py` backend
- Auto-discover chips from manifest
- Show experiment counts per chip
- Progress bar per chip
- Option to select specific chips (multi-select)

---

### Screen 3.3: Extract Derived Metrics

**Purpose:** Extract CNP, photoresponse, relaxation times, etc.

**Layout:**
```
┌─ Extract Derived Metrics ───────────────────────┐
│  Main Menu > Process > Extract Derived Metrics  │
├─────────────────────────────────────────────────┤
│                                                 │
│  Chip(s):                                       │
│  ├─ (•) All Chips                              │
│  └─ ( ) Specific Chip(s): [Select]             │
│                                                 │
│  Procedures to Process:                         │
│  ├─ [☑] IVg  (CNP extraction)                  │
│  ├─ [☑] It   (Photoresponse, Relaxation)       │
│  ├─ [☐] VVg                                    │
│  └─ [☑] LaserCalibration (Power matching)      │
│                                                 │
│  Options:                                       │
│  ├─ Force Re-extract:     [☐]                  │
│  ├─ Update Enriched:      [☑]                  │
│  └─ Parallel Workers:     [4 ▼]                │
│                                                 │
│  Estimated: ~350 measurements to process        │
│                                                 │
│  [Start Extraction] [Home] [← Back]             │
└─────────────────────────────────────────────────┘
```

**Flow:**
```
Configure Options
  ↓
[Start Extraction]
  ↓
Processing Screen (multi-stage)
  ├─ Stage 1: Extracting CNP from IVg
  │   Progress: [████████░░] 80% (45/56)
  │
  ├─ Stage 2: Extracting Photoresponse from It
  │   Progress: Pending...
  │
  ├─ Stage 3: Extracting Relaxation Times
  │   Progress: Pending...
  │
  └─ Stage 4: Matching Laser Calibrations
      Progress: Pending...
  ↓
Summary Screen
  ├─ ✅ CNP: 56 measurements (45 success, 11 no peak)
  ├─ ✅ Photoresponse: 128 measurements
  ├─ ✅ Relaxation Times: 128 measurements (5 poor fits)
  ├─ ✅ Calibrations: 234 light experiments matched
  ├─ Total time: 2m 14s
  └─ Enriched histories updated: 8 chips
  ↓
[View Poor Fits] [View Metrics] [Done]
```

**Implementation Notes:**
- Use `src/derived/metric_pipeline.py` backend
- Use existing extractors in `src/derived/extractors/`
- Multi-stage progress (per extractor)
- Show extraction statistics
- Flag poor fits for review
- Update enriched histories automatically

---

### Screen 3.4: Full Pipeline

**Purpose:** Run all pipeline steps in sequence

**Layout:**
```
┌─ Full Pipeline ─────────────────────────────────┐
│  Main Menu > Process > Full Pipeline            │
├─────────────────────────────────────────────────┤
│                                                 │
│  Pipeline Steps:                                │
│  ├─ 1️⃣  Stage Raw Data                          │
│  ├─ 2️⃣  Build Chip Histories                    │
│  ├─ 3️⃣  Extract Derived Metrics                 │
│  └─ 4️⃣  Validate Manifest                       │
│                                                 │
│  Configuration:                                 │
│  ├─ Workers: [6 ▼]                              │
│  ├─ Strict Mode: [☐]                           │
│  └─ Force Overwrite: [☐]                       │
│                                                 │
│  Advanced:                                      │
│  └─ [Configure Individual Steps]                │
│                                                 │
│  Estimated time: ~3-5 minutes                   │
│                                                 │
│  [Start Pipeline] [Home] [← Back]               │
└─────────────────────────────────────────────────┘
```

**Flow:**
```
Configure Pipeline
  ↓
[Start Pipeline]
  ↓
Multi-Step Progress Screen
  ┌────────────────────────────────────────────┐
  │  Full Data Pipeline                        │
  ├────────────────────────────────────────────┤
  │                                            │
  │  Step 1/4: Staging Raw Data                │
  │  [████████░░] 82% - Processing file 98/120 │
  │                                            │
  │  Step 2/4: Build Histories                 │
  │  [░░░░░░░░░░] Pending...                   │
  │                                            │
  │  Step 3/4: Extract Metrics                 │
  │  [░░░░░░░░░░] Pending...                   │
  │                                            │
  │  Step 4/4: Validate Manifest               │
  │  [░░░░░░░░░░] Pending...                   │
  │                                            │
  │  Total Progress: [██░░░░░░░░] 25%          │
  │  Elapsed: 1m 23s | ETA: 4m 12s             │
  │                                            │
  │  [View Current Log] [Cancel]               │
  └────────────────────────────────────────────┘
  ↓
Pipeline Complete
  ├─ Step 1: ✅ Staged 118 files (2 errors)
  ├─ Step 2: ✅ Built 8 chip histories
  ├─ Step 3: ✅ Extracted 350 metrics
  ├─ Step 4: ✅ Manifest valid
  ├─ Total time: 5m 34s
  └─ [View Full Report]
  ↓
[Done]
```

**Implementation Notes:**
- Use `src/core/pipeline.py` (Pipeline builder)
- Supports resume from checkpoint on failure
- Rollback on error (optional)
- Detailed logging for each step
- Can configure individual steps before running

---

### Screen 3.5: Validate Manifest

**Purpose:** Check manifest integrity and data quality

**Layout:**
```
┌─ Validate Manifest ─────────────────────────────┐
│  Main Menu > Process > Validate Manifest        │
├─────────────────────────────────────────────────┤
│                                                 │
│  Running validation checks...                   │
│                                                 │
│  ✅ Schema Validation                           │
│     All columns present and correct types       │
│                                                 │
│  ✅ File Existence                              │
│     All parquet_path files found (1,234/1,234)  │
│                                                 │
│  ✅ Duplicate Detection                         │
│     No duplicate run_ids found                  │
│                                                 │
│  ⚠️  Data Quality Checks                        │
│     3 warnings found (view details)             │
│                                                 │
│  ❌ Orphaned Files                              │
│     2 parquet files not in manifest             │
│                                                 │
│  Overall: PASS (with warnings)                  │
│                                                 │
│  [View Warnings] [View Orphans] [Export Report] │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Validation Checks:**
1. **Schema Validation**
   - All required columns present
   - Correct data types
   - No null values in required fields

2. **File Existence**
   - All `parquet_path` files exist
   - Files are readable
   - File sizes reasonable

3. **Duplicate Detection**
   - No duplicate `run_id` values
   - No duplicate (chip, seq) pairs

4. **Data Quality**
   - Timestamps in valid range
   - Voltage/current values reasonable
   - Procedure types valid

5. **Orphaned Files**
   - Parquet files in staging without manifest entry
   - Offer to clean up

**Implementation Notes:**
- Use CLI `validate-manifest` backend
- New screen: `src/tui/screens/processing/validate_manifest.py`
- Detailed warning/error reports
- Export validation report as text file
- Offer to fix issues (e.g., remove orphans)

---

### Screen 3.6: Pipeline Status

**Purpose:** Dashboard showing pipeline state and statistics

**Layout:**
```
┌─ Pipeline Status ───────────────────────────────┐
│  Main Menu > Process > Pipeline Status          │
├─────────────────────────────────────────────────┤
│                                                 │
│  📊 PIPELINE OVERVIEW                           │
│                                                 │
│  Last Operations:                               │
│  ├─ Staging:       2 hours ago ✅               │
│  ├─ Histories:     2 hours ago ✅               │
│  ├─ Metrics:       3 hours ago ✅               │
│  └─ Validation:    3 hours ago ✅               │
│                                                 │
│  📈 DATA STATISTICS                             │
│  ├─ Manifest Entries:    1,234                  │
│  ├─ Chips Tracked:       8                      │
│  ├─ Total Experiments:   1,234                  │
│  ├─ Enriched Histories:  8                      │
│  └─ Derived Metrics:     847                    │
│                                                 │
│  💾 STORAGE                                     │
│  ├─ Staged Data:         2.3 GB                 │
│  ├─ Histories:           145 MB                 │
│  ├─ Derived Metrics:     23 MB                  │
│  └─ Total:               2.47 GB                │
│                                                 │
│  [Refresh] [View Logs] [Home] [← Back]          │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- New screen: `src/tui/screens/processing/pipeline_status.py`
- Query manifest for statistics
- Check file timestamps for "last run"
- Calculate directory sizes
- Refresh on demand (cache for 5 minutes)
- Link to View Logs screen

---

## 🛠️ HUB 4: SETTINGS

### Overview
**Purpose:** Application configuration and preferences
**Users:** All users (customize experience)
**Entry from:** Main Menu → Settings

---

### Screen 4.0: Settings Hub Menu

**Layout:**
```
┌─ Settings ──────────────────────────────────────┐
│  Main Menu > Settings                           │
├─────────────────────────────────────────────────┤
│                                                 │
│  🎨 Theme                                       │
│  📁 Output Paths                                │
│  ⚙️  Default Parameters                         │
│  🔌 Plugin Configuration                        │
│  💾 Export/Import Settings                      │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Buttons:**
- **Theme** → Screen 4.1
- **Output Paths** → Screen 4.2
- **Default Parameters** → Screen 4.3
- **Plugin Configuration** → Screen 4.4
- **Export/Import Settings** → Screen 4.5

**Implementation Notes:**
- Enhance existing theme settings screen
- New hub screen: `src/tui/screens/navigation/settings_hub.py`

---

### Screen 4.1: Theme Settings

**Layout:**
```
┌─ Theme Settings ────────────────────────────────┐
│  Main Menu > Settings > Theme                   │
├─────────────────────────────────────────────────┤
│                                                 │
│  Select Theme:                                  │
│  ├─ (•) Tokyo Night (current)                  │
│  ├─ ( ) Light Mode                             │
│  ├─ ( ) Dark Mode                              │
│  └─ ( ) Matrix                                 │
│                                                 │
│  Preview:                                       │
│  ┌──────────────────────────────────────────┐  │
│  │ [Button]  Text  •••••••  Accent          │  │
│  └──────────────────────────────────────────┘  │
│                                                 │
│  [Apply] [Reset to Default] [Home] [← Back]    │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- Use existing `src/tui/screens/navigation/theme_settings.py`
- Add preview box showing current theme colors
- Live preview when selecting theme

---

### Screen 4.2: Output Paths

**Layout:**
```
┌─ Output Paths ──────────────────────────────────┐
│  Main Menu > Settings > Output Paths            │
├─────────────────────────────────────────────────┤
│                                                 │
│  Figures Output:                                │
│  [figs/                       ] [Browse]        │
│                                                 │
│  Staged Data:                                   │
│  [data/02_stage/raw_measurements/] [Browse]     │
│                                                 │
│  Chip Histories:                                │
│  [data/02_stage/chip_histories/  ] [Browse]     │
│                                                 │
│  Enriched Histories:                            │
│  [data/03_derived/chip_histories_enriched/]     │
│  [Browse]                                       │
│                                                 │
│  Batch Configs:                                 │
│  [config/batch_plots/            ] [Browse]     │
│                                                 │
│  [Save] [Reset to Defaults] [Home] [← Back]    │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- New screen: `src/tui/screens/settings/output_paths.py`
- Validate paths on save
- Create directories if missing (with confirmation)
- Store in app config (persistent)

---

### Screen 4.3: Default Parameters

**Layout:**
```
┌─ Default Parameters ────────────────────────────┐
│  Main Menu > Settings > Default Parameters      │
├─────────────────────────────────────────────────┤
│                                                 │
│  Select Plot Type: [ITS ▼]                      │
│                                                 │
│  ITS Defaults:                                  │
│  ├─ Baseline (s):    [60.0  ]                   │
│  ├─ Legend By:       [Wavelength ▼]             │
│  ├─ Padding:         [0.05  ]                   │
│  └─ Baseline Mode:   [Fixed ▼]                  │
│                                                 │
│  Pipeline Defaults:                             │
│  ├─ Workers:         [6 ▼]                      │
│  ├─ Strict Mode:     [☐]                       │
│  └─ Auto-enrich:     [☑]                       │
│                                                 │
│  [Save] [Reset to Defaults] [Home] [← Back]    │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- New screen: `src/tui/screens/settings/default_parameters.py`
- Dropdown to select plot type (ITS, IVg, VVg, Vt, etc.)
- Show relevant defaults for selected type
- Store in app config
- Apply defaults when starting new plot wizard

---

### Screen 4.4: Plugin Configuration

**Layout:**
```
┌─ Plugin Configuration ──────────────────────────┐
│  Main Menu > Settings > Plugin Configuration    │
├─────────────────────────────────────────────────┤
│                                                 │
│  Available Plugins:                             │
│                                                 │
│  ✅ Batch Plotting                              │
│     Status: Enabled                             │
│     [Configure] [Disable]                       │
│                                                 │
│  ✅ ITS Presets                                 │
│     Status: Enabled                             │
│     [Configure] [Disable]                       │
│                                                 │
│  ✅ Derived Metrics                             │
│     Status: Enabled (12 extractors)             │
│     [Configure] [Disable]                       │
│                                                 │
│  [Scan for Plugins] [Home] [← Back]             │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- New screen: `src/tui/screens/settings/plugin_config.py`
- Read from `config/cli_plugins.yaml`
- Enable/disable plugin groups
- Per-plugin settings (if applicable)

---

### Screen 4.5: Export/Import Settings

**Layout:**
```
┌─ Export/Import Settings ────────────────────────┐
│  Main Menu > Settings > Export/Import           │
├─────────────────────────────────────────────────┤
│                                                 │
│  Export Settings:                               │
│  ├─ Format: JSON                                │
│  ├─ Includes: Paths, Defaults, Theme            │
│  └─ Path: [config/tui_settings.json]           │
│                                                 │
│  [Export Settings]                              │
│                                                 │
│  ─────────────────────────────────              │
│                                                 │
│  Import Settings:                               │
│  ├─ File: [Browse]                             │
│  └─ ⚠️  This will overwrite current settings    │
│                                                 │
│  [Import Settings]                              │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- New screen: `src/tui/screens/settings/export_import.py`
- Export all app settings to JSON
- Import from JSON (with validation)
- Backup current settings before import

---

## ❓ HUB 5: HELP

### Overview
**Purpose:** Documentation, guides, and support
**Users:** All users (especially new users)
**Entry from:** Main Menu → Help

---

### Screen 5.0: Help Hub Menu

**Layout:**
```
┌─ Help ──────────────────────────────────────────┐
│  Main Menu > Help                               │
├─────────────────────────────────────────────────┤
│                                                 │
│  ⌨️  Keyboard Shortcuts                         │
│  📖 Workflow Guide                              │
│  📝 View Logs                                   │
│  📚 Documentation                               │
│  ℹ️  About                                      │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- New screen: `src/tui/screens/navigation/help_hub.py`

---

### Screen 5.1: Keyboard Shortcuts

**Layout:**
```
┌─ Keyboard Shortcuts ────────────────────────────┐
│  Main Menu > Help > Keyboard Shortcuts          │
├─────────────────────────────────────────────────┤
│                                                 │
│  📊 PLOTTING                                    │
│  • Ctrl+N - New Plot (from anywhere)            │
│  • B      - Batch Mode (main menu)              │
│  • R      - Recent Configs (main menu)          │
│                                                 │
│  📂 NAVIGATION                                  │
│  • ↑↓     - Navigate items                      │
│  • Enter  - Select item                         │
│  • Esc    - Go back                             │
│  • Ctrl+Q - Quit (from anywhere)                │
│  • Home   - Return to main menu                 │
│                                                 │
│  🔍 HISTORIES                                   │
│  • Ctrl+H - View Histories (from anywhere)      │
│  • P      - Preview Data (in history tables)    │
│                                                 │
│  ⚙️  PROCESSING                                 │
│  • Ctrl+P - Process New Data (main menu)        │
│                                                 │
│  [Close]                                        │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- New screen: `src/tui/screens/help/keyboard_shortcuts.py`
- Categorized shortcuts
- Scrollable if list is long

---

### Screen 5.2: Workflow Guide

**Layout:**
```
┌─ Workflow Guide ────────────────────────────────┐
│  Main Menu > Help > Workflow Guide              │
├─────────────────────────────────────────────────┤
│                                                 │
│  Select Topic:                                  │
│                                                 │
│  🚀 Getting Started (First-time users)          │
│  📊 Creating Your First Plot                    │
│  📥 Processing New Data                         │
│  📦 Using Batch Mode                            │
│  🔬 Exploring Derived Metrics                   │
│  🐛 Troubleshooting                             │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Topic Example: Creating Your First Plot**
```
┌─ Guide: Creating Your First Plot ───────────────┐
│                                                 │
│  STEP 1: Start from Main Menu                   │
│  Press 'Plots' or use Ctrl+N                    │
│                                                 │
│  STEP 2: Select Your Chip                       │
│  Choose from auto-discovered chips              │
│  (e.g., Alisson67, Encap81)                     │
│                                                 │
│  STEP 3: Choose Plot Type                       │
│  • ITS - Current vs Time (photoresponse)        │
│  • IVg - Gate voltage sweeps                    │
│  • VVg - Voltage sweeps                         │
│  • Vt  - Voltage dynamics                       │
│                                                 │
│  STEP 4: Configure Parameters                   │
│  Quick mode: Use defaults (recommended)         │
│  Custom mode: Fine-tune settings                │
│                                                 │
│  STEP 5: Select Experiments                     │
│  Choose from chip history by seq number         │
│                                                 │
│  STEP 6: Preview & Generate                     │
│  Review settings and generate plot              │
│                                                 │
│  [Next Topic] [Home] [← Back]                   │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- New screen: `src/tui/screens/help/workflow_guide.py`
- New screen per topic
- Step-by-step instructions
- Screenshots or ASCII diagrams if helpful

---

### Screen 5.3: View Logs

**Layout:**
```
┌─ View Logs ─────────────────────────────────────┐
│  Main Menu > Help > View Logs                   │
├─────────────────────────────────────────────────┤
│                                                 │
│  Select Log:                                    │
│  ├─ (•) Today (live tail)                      │
│  ├─ ( ) Yesterday                              │
│  └─ ( ) Older Logs                             │
│                                                 │
│  Filter: [INFO ▼] [WARNING] [ERROR]             │
│  Search: [______] 🔍                            │
│                                                 │
│  [View Log]                                     │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Log Viewer:**
```
┌─ Log Viewer: Today ─────────────────────────────┐
│                                                 │
│  2025-01-15 14:23:45 [INFO] Staging started     │
│  2025-01-15 14:23:46 [INFO] Processing file...  │
│  2025-01-15 14:24:12 [WARNING] Optional col...  │
│  2025-01-15 14:25:03 [ERROR] Schema mismatch... │
│  2025-01-15 14:26:15 [INFO] Staging complete    │
│                                                 │
│  [↑↓ Scroll] [/ Search] [F Filter] [Q Quit]    │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- Use existing log viewer or create new
- Read from `logs/` directory
- Filter by level (INFO, WARNING, ERROR)
- Search functionality
- Live tail for today's log
- Export logs option

---

### Screen 5.4: Documentation

**Layout:**
```
┌─ Documentation ─────────────────────────────────┐
│  Main Menu > Help > Documentation               │
├─────────────────────────────────────────────────┤
│                                                 │
│  📚 Available Documentation:                    │
│                                                 │
│  📖 User Guide (Markdown)                       │
│     View in external browser                    │
│     [Open]                                      │
│                                                 │
│  📋 CLAUDE.md (Project Instructions)            │
│     For developers and contributors             │
│     [Open]                                      │
│                                                 │
│  🔗 GitHub Repository                           │
│     https://github.com/.../optothermal_...      │
│     [Copy Link] [Open in Browser]               │
│                                                 │
│  [Home] [← Back]                                │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- New screen: `src/tui/screens/help/documentation.py`
- Link to external documentation
- Open markdown files in system viewer
- Copy links to clipboard

---

### Screen 5.5: About

**Layout:**
```
┌─ About ─────────────────────────────────────────┐
│  Main Menu > Help > About                       │
├─────────────────────────────────────────────────┤
│                                                 │
│  🔬 Experiment Plotting Assistant               │
│     NanoLab - Device Characterization           │
│                                                 │
│  Version: 4.0.0 (TUI Reorganization)            │
│  Pipeline: Parquet-based                        │
│  Python: 3.11+                                  │
│                                                 │
│  Libraries:                                     │
│  ├─ Polars 0.19+                               │
│  ├─ Textual 6.3.0                              │
│  ├─ Matplotlib 3.7+                            │
│  ├─ Pydantic 2.0+                              │
│  └─ NumPy, SciPy, scienceplots                 │
│                                                 │
│  GitHub:                                        │
│  https://github.com/.../optothermal_processing  │
│                                                 │
│  License: [View License]                        │
│                                                 │
│  [Close]                                        │
└─────────────────────────────────────────────────┘
```

**Implementation Notes:**
- New screen: `src/tui/screens/help/about.py`
- Show version info
- List key dependencies with versions
- Link to GitHub
- Display license (MIT/BSD/etc.)

---

## 🚪 HUB 6: QUIT

**Implementation:**
Direct action from main menu - prompts confirmation and exits.

```python
def action_quit(self) -> None:
    """Quit the application."""
    self.app.exit()
```

Optional: Add confirmation dialog if unsaved changes.

---

## Implementation Phases

### Phase 1: Foundation & Main Menu (Week 1)

**Goal:** New main menu + routing infrastructure

**Tasks:**
1. ✅ Create new main menu (6 buttons)
   - File: `src/tui/screens/navigation/main_menu_v4.py`
   - Replace existing main menu
2. ✅ Create hub menu screens (empty shells)
   - `plots_hub.py`
   - `histories_hub.py`
   - `process_hub.py`
   - `settings_hub.py`
   - `help_hub.py`
3. ✅ Update router for new navigation
   - Add `go_to_plots_hub()`
   - Add `go_to_histories_hub()`
   - Add `go_to_process_hub()`
   - Add `go_to_settings_hub()`
   - Add `go_to_help_hub()`
4. ✅ Add breadcrumb system
   - Track navigation path
   - Display at top of screens
5. ✅ Add global shortcuts
   - Ctrl+N → New Plot
   - Ctrl+H → Histories
   - Ctrl+Q → Quit
   - Home → Main menu

**Deliverable:** Working main menu with hub navigation (no functionality yet)

---

### Phase 2: Plots Hub (Week 2-3)

**Goal:** Complete plots hub with all sub-screens

**Tasks:**
1. ✅ Plots Hub Menu (Screen 1.0)
   - 5 buttons functional
2. ✅ Keep existing New Plot wizard (Screen 1.1)
   - No changes needed
   - Just link from hub
3. ✅ Batch Mode (Screen 1.2)
   - `batch_mode_hub.py`
   - `batch_config_review.py`
   - `batch_progress.py`
   - `batch_complete.py`
   - YAML browser
   - Config creator
4. ✅ Recent Configurations (Screen 1.3)
   - `recent_configs_list.py`
   - Enhance existing ConfigManager
   - Search/filter/sort
5. ✅ Plot Presets (Screen 1.4)
   - `preset_selector.py`
   - `preset_details.py`
   - Extend ITS presets to other types
6. ✅ Browse Plots (Screen 1.5)
   - `plot_browser.py`
   - `plot_details.py`
   - File scanning
   - Regenerate feature

**Deliverable:** Fully functional Plots hub

---

### Phase 3: Chip Histories Hub (Week 4-5)

**Goal:** Complete histories hub with data exploration

**Tasks:**
1. ✅ Histories Hub Menu (Screen 2.0)
2. ✅ Standard History Browser (Screen 2.1)
   - Enhance existing history browser
   - Add filters, sorting
3. ✅ Enriched History Browser (Screen 2.2)
   - `enriched_history_browser.py`
   - Metric columns
   - Metric filters
4. ✅ Metrics Explorer (Screen 2.3)
   - `metrics_explorer_hub.py`
   - `cnp_evolution.py`
   - `photoresponse_analysis.py`
   - `relaxation_times.py`
   - plotext visualizations
5. ✅ Experiment Browser (Screen 2.4)
   - `experiment_browser.py`
   - `search_results.py`
   - Advanced filters
   - Multi-select
6. ✅ Data Preview (Screen 2.5)
   - **Use existing ExperimentPreviewScreen!**
   - Just add entry point
7. ✅ Export History (Screen 2.6)
   - `export_history.py`
   - CSV/JSON/Parquet export

**Deliverable:** Fully functional Histories hub

---

### Phase 4: Process New Data Hub (Week 6)

**Goal:** Complete pipeline management hub

**Tasks:**
1. ✅ Process Hub Menu (Screen 3.0)
2. ✅ Stage Raw Data (Screen 3.1)
   - `staging_config.py`
   - `staging_progress.py`
   - `staging_summary.py`
   - Reuse backend
3. ✅ Build Histories (Screen 3.2)
   - Simple progress screen
4. ✅ Extract Metrics (Screen 3.3)
   - Multi-stage progress
   - Statistics display
5. ✅ Full Pipeline (Screen 3.4)
   - Use Pipeline builder
   - Multi-step progress
6. ✅ Validate Manifest (Screen 3.5)
   - Validation results
   - Error details
7. ✅ Pipeline Status (Screen 3.6)
   - Dashboard view
   - Statistics

**Deliverable:** Fully functional Process hub

---

### Phase 5: Settings & Help Hubs (Week 7)

**Goal:** Complete settings and help hubs

**Tasks:**
1. ✅ Settings Hub
   - Theme (enhance existing)
   - Output Paths
   - Default Parameters
   - Plugin Config
   - Export/Import
2. ✅ Help Hub
   - Keyboard Shortcuts
   - Workflow Guides
   - View Logs
   - Documentation
   - About

**Deliverable:** Fully functional Settings & Help hubs

---

### Phase 6: Polish & Testing (Week 8)

**Goal:** Bug fixes, UX improvements, testing

**Tasks:**
1. ✅ User testing with lab members
2. ✅ Fix bugs and UX issues
3. ✅ Optimize navigation flows
4. ✅ Add missing features
5. ✅ Write user documentation
6. ✅ Performance optimization
7. ✅ Accessibility improvements

**Deliverable:** Production-ready TUI v4.0

---

## Technical Implementation Notes

### File Structure

```
src/tui/
├── screens/
│   ├── navigation/
│   │   ├── main_menu.py (replace with v4)
│   │   ├── plots_hub.py (NEW)
│   │   ├── histories_hub.py (NEW)
│   │   ├── process_hub.py (NEW)
│   │   ├── settings_hub.py (NEW)
│   │   └── help_hub.py (NEW)
│   ├── plots/
│   │   ├── batch_mode_hub.py (NEW)
│   │   ├── batch_config_review.py (NEW)
│   │   ├── batch_progress.py (NEW)
│   │   ├── batch_complete.py (NEW)
│   │   ├── recent_configs_list.py (NEW)
│   │   ├── preset_selector.py (NEW)
│   │   ├── preset_details.py (NEW)
│   │   ├── plot_browser.py (NEW)
│   │   └── plot_details.py (NEW)
│   ├── histories/
│   │   ├── enriched_history_browser.py (NEW)
│   │   ├── metrics_explorer_hub.py (NEW)
│   │   ├── cnp_evolution.py (NEW)
│   │   ├── photoresponse_analysis.py (NEW)
│   │   ├── relaxation_times.py (NEW)
│   │   ├── experiment_browser.py (NEW)
│   │   ├── search_results.py (NEW)
│   │   └── export_history.py (NEW)
│   ├── processing/
│   │   ├── staging_config.py (NEW)
│   │   ├── staging_progress.py (NEW)
│   │   ├── staging_summary.py (NEW)
│   │   ├── validate_manifest.py (NEW)
│   │   └── pipeline_status.py (NEW)
│   ├── settings/
│   │   ├── output_paths.py (NEW)
│   │   ├── default_parameters.py (NEW)
│   │   ├── plugin_config.py (NEW)
│   │   └── export_import.py (NEW)
│   └── help/
│       ├── keyboard_shortcuts.py (NEW)
│       ├── workflow_guide.py (NEW)
│       ├── documentation.py (NEW)
│       └── about.py (NEW)
├── router.py (UPDATE with new hub methods)
├── app.py (UPDATE main menu reference)
└── session.py (ADD breadcrumb tracking)
```

### Router Updates

```python
# src/tui/router.py

def go_to_plots_hub(self) -> None:
    """Navigate to Plots hub."""
    from src.tui.screens.navigation import PlotsHub
    self.app.push_screen(PlotsHub())

def go_to_histories_hub(self) -> None:
    """Navigate to Histories hub."""
    from src.tui.screens.navigation import HistoriesHub
    self.app.push_screen(HistoriesHub())

def go_to_process_hub(self) -> None:
    """Navigate to Process hub."""
    from src.tui.screens.navigation import ProcessHub
    self.app.push_screen(ProcessHub())

def go_to_settings_hub(self) -> None:
    """Navigate to Settings hub."""
    from src.tui.screens.navigation import SettingsHub
    self.app.push_screen(SettingsHub())

def go_to_help_hub(self) -> None:
    """Navigate to Help hub."""
    from src.tui.screens.navigation import HelpHub
    self.app.push_screen(HelpHub())

# ... many more for sub-screens ...
```

### Breadcrumb System

```python
# src/tui/session.py

class PlotSession(BaseModel):
    # ... existing fields ...

    # Navigation breadcrumbs
    breadcrumb_path: List[str] = Field(
        default_factory=list,
        description="Navigation path breadcrumbs"
    )

    def push_breadcrumb(self, screen_name: str) -> None:
        """Add screen to breadcrumb trail."""
        self.breadcrumb_path.append(screen_name)

    def pop_breadcrumb(self) -> Optional[str]:
        """Remove last screen from breadcrumb trail."""
        return self.breadcrumb_path.pop() if self.breadcrumb_path else None

    def get_breadcrumb_str(self) -> str:
        """Get breadcrumb trail as string."""
        return " > ".join(self.breadcrumb_path)
```

### Base Hub Screen

```python
# src/tui/screens/base/hub_screen.py

class HubScreen(WizardScreen):
    """Base class for hub menu screens."""

    def compose_header(self) -> ComposeResult:
        """Show breadcrumb trail."""
        breadcrumb = self.app.session.get_breadcrumb_str()
        yield Static(breadcrumb, id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def on_mount(self) -> None:
        """Track breadcrumb."""
        self.app.session.push_breadcrumb(self.SCREEN_TITLE)

    def action_back(self) -> None:
        """Pop breadcrumb and go back."""
        self.app.session.pop_breadcrumb()
        super().action_back()
```

---

## Migration Strategy

### Backward Compatibility

**Keep old screens during migration:**
- Don't delete old main menu until Phase 6
- Run both versions in parallel during testing
- Add feature flag to toggle between old/new

```python
# tui_app.py

USE_NEW_MENU = True  # Feature flag

if USE_NEW_MENU:
    from src.tui.screens.navigation.main_menu import MainMenuScreen
else:
    from src.tui.screens.navigation.main_menu_legacy import MainMenuScreen
```

### User Migration

**Gradual rollout:**
1. **Alpha (Phase 2):** Internal testing only
2. **Beta (Phase 4):** Power users + feedback
3. **RC (Phase 5):** All lab members
4. **GA (Phase 6):** Remove old menu

### Data Migration

**No data migration needed:**
- Same backend (Parquet, manifest, histories)
- Same CLI commands
- Only TUI screens change

---

## Testing Plan

### Unit Tests

**Per screen:**
- Screen renders correctly
- Buttons navigate to correct screens
- Forms validate input
- Actions execute correctly

### Integration Tests

**Per hub:**
- Complete workflow from hub menu → action → result
- Example: Plots hub → New Plot → Generate → Success

### User Acceptance Testing

**Lab members test:**
- Create plots (ITS, IVg, VVg, Vt)
- Browse histories
- Process new data
- Use batch mode
- Explore metrics

**Feedback focus:**
- Discoverability (can they find features?)
- Navigation flow (logical?)
- Performance (fast enough?)
- Bugs and edge cases

---

## Success Metrics

**Quantitative:**
- ✅ All 25+ sub-screens implemented
- ✅ <5 bugs reported in beta
- ✅ <3s navigation time (any screen → any screen)
- ✅ 100% feature parity with v3.x

**Qualitative:**
- ✅ Lab members find features easily
- ✅ New users can create plots without help
- ✅ Positive feedback on organization
- ✅ Reduced support requests

---

## Next Steps

**Immediate Actions:**
1. ✅ Review this plan
2. ✅ Approve or request changes
3. ✅ Start Phase 1 (Main Menu + Hubs)

**First Implementation:**
- Create new main menu (6 buttons)
- Create empty hub screens
- Update router
- Test navigation

**Timeline:**
- **Phase 1:** Week 1 (Foundation)
- **Phase 2:** Week 2-3 (Plots Hub) ← START HERE
- **Phase 3:** Week 4-5 (Histories Hub)
- **Phase 4:** Week 6 (Process Hub)
- **Phase 5:** Week 7 (Settings/Help)
- **Phase 6:** Week 8 (Polish)

---

## Appendix

### Design Mockup Tools Used
- ASCII art for screen layouts
- Textual CSS for styling
- Mermaid for flow diagrams (if needed)

### References
- Textual Documentation: https://textual.textualize.io/
- plotext Documentation: https://github.com/piccolomo/plotext
- CLAUDE.md (project instructions)

### Version History
- v1.0 (2025-01-15): Initial plan
- v1.1 (TBD): Updates based on feedback

---

**End of Plan**

This document will be updated as implementation progresses. All changes should be tracked with version numbers and dates.
