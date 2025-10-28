# Responsive & Centered Screens Plan

**Goal**: Make all TUI screens automatically adjust to terminal size and ensure proper centering.

---

## Current State Analysis

### Issues Identified

1. **Fixed Widths**: Screens use hardcoded widths
   ```css
   #main-container {
       width: 60;  /* Fixed width - doesn't adapt to terminal size */
       width: 70;  /* Different screens have different fixed widths */
       width: 80;
   }
   ```

2. **Inconsistent Centering**: Some screens may not center properly on all terminal sizes

3. **No Responsive Constraints**: No min/max width constraints for very large or small terminals

4. **Potential Overflow**: Fixed widths can cause content to overflow on small terminals

### Files Affected

```
src/tui/screens/
├── base.py                     ⚠️  Foundation - main-container width
├── navigation/
│   ├── main_menu.py           ⚠️  width: 60
│   └── recent_configs.py      ⚠️  width: 90
├── selection/
│   ├── chip_selector.py       ⚠️  width: 70
│   ├── plot_type_selector.py  ⚠️  width: 70
│   ├── config_mode_selector.py ⚠️  width: 70
│   ├── experiment_selector.py ⚠️  width: 80
│   └── its_preset_selector.py ⚠️  width: 70
├── configuration/
│   ├── its_config.py          ⚠️  width: 70
│   ├── ivg_config.py          ⚠️  width: 70
│   ├── transconductance_config.py ⚠️ width: 70
│   ├── preview_screen.py      ⚠️  width: 70
│   └── process_confirmation.py ⚠️ width: 60
├── processing/
│   ├── plot_generation.py     ⚠️  width: 80
│   └── process_loading.py     ⚠️  width: 80
└── results/
    ├── plot_success.py        ✅  Already uses base (width: 70)
    ├── plot_error.py          ✅  Already uses base (width: 70)
    ├── process_success.py     ✅  Already uses base (width: 70)
    └── process_error.py       ✅  Already uses base (width: 70)
```

**Summary**: 14 screens need width updates, 4 screens already inherit from base classes.

---

## Proposed Solution

### Strategy

Use a **responsive width system** with these principles:

1. **Percentage-based widths** for flexibility
2. **Min/max constraints** for readability on extreme sizes
3. **Consistent centering** via base class
4. **Screen-specific overrides** only when needed

### CSS Architecture

```css
/* Base class (base.py) - Default for most screens */
#main-container {
    width: 90%;              /* Responsive: 90% of terminal width */
    max-width: 120;          /* Cap at 120 chars for readability */
    min-width: 60;           /* Minimum 60 chars to prevent squishing */
    height: auto;
    max-height: 90%;         /* Prevent vertical overflow */
    background: $surface;
    border: thick $primary;
    padding: 2 4;
}

/* Screen-specific sizes (override base when needed) */
.narrow-screen #main-container {
    max-width: 80;           /* Smaller screens (main menu, confirmations) */
}

.wide-screen #main-container {
    max-width: 140;          /* Larger screens (data tables, previews) */
}
```

### Centering Mechanism

All screens already inherit centering from base classes:

```css
WizardScreen {
    align: center middle;     /* ✅ Already implemented */
}
```

**Action**: Verify all screen subclasses maintain this.

---

## Implementation Plan

### Phase 1: Update Base Classes (High Priority)

**File**: `src/tui/screens/base.py`

**Changes**:
```python
class WizardScreen(Screen):
    CSS = """
    WizardScreen {
        align: center middle;  # ✅ Already present
    }

    #main-container {
        width: 90%;            # NEW: Responsive width
        max-width: 120;        # NEW: Readability cap
        min-width: 60;         # NEW: Minimum size
        height: auto;
        max-height: 90%;       # ✅ Already present
        background: $surface;
        border: thick $primary;
        padding: 2 4;
    }
    # ... rest of CSS
    """
```

**Impact**: All screens inheriting from `WizardScreen`, `FormScreen`, `SelectorScreen`, `ResultScreen` will automatically become responsive.

---

### Phase 2: Remove Fixed Width Overrides (Medium Priority)

**Action**: Audit and remove/adjust screen-specific width overrides.

#### 2.1 Navigation Screens

**File**: `src/tui/screens/navigation/main_menu.py`
```python
# BEFORE
CSS = WizardScreen.CSS + """
#main-container {
    width: 60;  # ❌ Remove this
}
"""

# AFTER
CSS = WizardScreen.CSS + """
#main-container {
    max-width: 80;  # ✅ Keep smaller for menu, but responsive
}
"""
```

**File**: `src/tui/screens/navigation/recent_configs.py`
```python
# BEFORE
CSS = WizardScreen.CSS + """
#main-container {
    width: 90;  # ❌ Remove this
    max-height: 95%;
}
"""

# AFTER
CSS = WizardScreen.CSS + """
#main-container {
    max-width: 140;  # ✅ Allow wider for table display
    max-height: 95%;
}
"""
```

#### 2.2 Selection Screens

All selection screens currently have `width: 70`:
- `chip_selector.py`
- `plot_type_selector.py`
- `config_mode_selector.py`
- `its_preset_selector.py`

**Action**: Remove fixed widths, let base class handle it.

**Exception**: `experiment_selector.py` (width: 80)
```python
CSS = SelectorScreen.CSS + """
#main-container {
    max-width: 140;  # Needs more space for experiment table
}
"""
```

#### 2.3 Configuration Screens

Most config screens have `width: 70`.

**Action**: Remove fixed widths except for special cases:

**File**: `process_confirmation.py`
```python
CSS = WizardScreen.CSS + """
#main-container {
    max-width: 80;  # Keep narrower for confirmation dialogs
}
"""
```

#### 2.4 Processing Screens

Both have `width: 80`:
- `plot_generation.py`
- `process_loading.py`

**Action**: Remove fixed widths, keep default responsive behavior.

---

### Phase 3: Add Responsive Utilities (Optional Enhancement)

**File**: `src/tui/screens/base.py`

Add CSS classes for common size patterns:

```python
class WizardScreen(Screen):
    CSS = """
    # ... existing CSS ...

    /* Responsive size classes */
    .narrow-container #main-container {
        max-width: 80;
    }

    .wide-container #main-container {
        max-width: 140;
    }

    .full-width-container #main-container {
        width: 95%;
        max-width: 160;
    }
    """
```

**Usage**:
```python
class MyScreen(WizardScreen):
    CONTAINER_CLASSES = "narrow-container"  # Optional class attribute
```

---

### Phase 4: Testing & Validation

#### 4.1 Manual Testing

Test on various terminal sizes:

```bash
# Small terminal (80x24)
resize -s 24 80
python tui_app.py

# Medium terminal (120x40) - typical
resize -s 40 120
python tui_app.py

# Large terminal (200x60)
resize -s 60 200
python tui_app.py

# Very small terminal (60x20) - edge case
resize -s 20 60
python tui_app.py
```

**Checklist for each screen**:
- [ ] Content is centered horizontally
- [ ] Content is centered vertically
- [ ] No horizontal overflow/scrolling
- [ ] Text remains readable
- [ ] Buttons/inputs are accessible
- [ ] Tables/grids adjust appropriately

#### 4.2 Automated Testing (Future)

Create a test script:

```python
# tests/tui/test_responsive_screens.py
def test_screen_responsiveness():
    """Test screens adapt to different sizes."""
    sizes = [(80, 24), (120, 40), (200, 60)]

    for width, height in sizes:
        # Set terminal size
        # Launch each screen
        # Verify no overflow
        # Verify centering
        pass
```

---

## Implementation Steps

### Step 1: Update Base Class (15 minutes)
- [x] Update `src/tui/screens/base.py`
- [x] Change `#main-container` to use `width: 90%`, `max-width: 120`, `min-width: 60`
- [x] Test that base screens still look correct

### Step 2: Audit Screen Overrides (30 minutes)
- [ ] Create inventory of all width overrides
- [ ] Categorize: remove entirely, replace with max-width, or keep custom
- [ ] Document rationale for each decision

### Step 3: Update Navigation Screens (10 minutes)
- [ ] `main_menu.py` - Use `max-width: 80`
- [ ] `recent_configs.py` - Use `max-width: 140`

### Step 4: Update Selection Screens (15 minutes)
- [ ] Remove fixed widths from 4 screens
- [ ] Keep `experiment_selector.py` with `max-width: 140`

### Step 5: Update Configuration Screens (15 minutes)
- [ ] Remove fixed widths from 4 screens
- [ ] Keep `process_confirmation.py` with `max-width: 80`

### Step 6: Update Processing Screens (10 minutes)
- [ ] Remove fixed widths from both screens
- [ ] Let base class handle sizing

### Step 7: Testing (30 minutes)
- [ ] Test all screens at different terminal sizes
- [ ] Verify centering on all screens
- [ ] Check for overflow issues
- [ ] Document any edge cases

### Step 8: Documentation (10 minutes)
- [ ] Update base.py docstring with responsive design notes
- [ ] Add comments explaining width constraints
- [ ] Create usage guide for future screens

---

## Detailed CSS Changes

### Base Class Changes

**File**: `src/tui/screens/base.py:82-93`

```python
# BEFORE
CSS = """
WizardScreen {
    align: center middle;
}

#main-container {
    width: 70;           # ❌ Fixed width
    height: auto;
    max-height: 90%;
    background: $surface;
    border: thick $primary;
    padding: 2 4;
}
"""

# AFTER
CSS = """
WizardScreen {
    align: center middle;
}

#main-container {
    width: 90%;          # ✅ Responsive width
    max-width: 120;      # ✅ Readability limit
    min-width: 60;       # ✅ Minimum size
    height: auto;
    max-height: 90%;
    background: $surface;
    border: thick $primary;
    padding: 2 4;
}
"""
```

### Per-Screen Changes

| Screen | Current Width | New Approach | Rationale |
|--------|--------------|--------------|-----------|
| **Navigation** |
| main_menu | 60 | max-width: 80 | Menu should be compact |
| recent_configs | 90 | max-width: 140 | Table needs more space |
| **Selection** |
| chip_selector | 70 | Use base default | Standard selector |
| plot_type_selector | 70 | Use base default | Standard selector |
| config_mode_selector | 70 | Use base default | Standard selector |
| experiment_selector | 80 | max-width: 140 | Timeline needs space |
| its_preset_selector | 70 | Use base default | Standard selector |
| **Configuration** |
| its_config | 70 | Use base default | Form fits well |
| ivg_config | 70 | Use base default | Form fits well |
| transconductance_config | 70 | Use base default | Form fits well |
| preview_screen | 70 | max-width: 140 | Summary needs space |
| process_confirmation | 60 | max-width: 80 | Dialog should be compact |
| **Processing** |
| plot_generation | 80 | Use base default | Progress bar flexible |
| process_loading | 80 | Use base default | Progress bar flexible |

---

## Edge Cases & Considerations

### Very Small Terminals (< 60 chars wide)

**Problem**: Content may be squished or unreadable.

**Solution**:
```css
#main-container {
    min-width: 60;  # Enforce minimum, allow horizontal scroll if needed
}
```

**Alternative**: Show warning on app startup:
```python
def on_mount(self):
    if self.size.width < 80:
        self.notify(
            "Terminal too small! Recommended minimum: 80 characters wide",
            severity="warning",
            timeout=5
        )
```

### Very Large Terminals (> 200 chars wide)

**Problem**: Content looks lost in the center, too much whitespace.

**Solution**: Already handled by `max-width: 120` constraint.

**Optional Enhancement**: Use multiple columns for wide screens.

### Tables & Data Grids

**Problem**: Fixed-width tables don't adapt well.

**Solution**: Use percentage-based column widths:
```css
DataTable {
    width: 100%;  # Fill container
}

.column-date {
    width: 20%;   # Responsive column
}

.column-description {
    width: 60%;   # Responsive column
}
```

### Forms with Long Labels

**Problem**: Form rows may wrap awkwardly.

**Current**:
```css
.form-label {
    width: 20;    # Fixed
}
.form-input {
    width: 30;    # Fixed
}
```

**Better**:
```css
.form-label {
    width: 30%;   # Responsive
    min-width: 15;
}
.form-input {
    width: 45%;   # Responsive
    min-width: 20;
}
```

---

## Benefits

### User Experience
- ✅ **Works on any terminal size** (within reason)
- ✅ **Better space utilization** on large terminals
- ✅ **Prevents overflow** on small terminals
- ✅ **Consistent centering** across all screens

### Developer Experience
- ✅ **Less CSS to maintain** (base class handles most cases)
- ✅ **Easier to add new screens** (inherit responsive behavior)
- ✅ **Fewer screen-specific overrides** needed
- ✅ **Predictable behavior** across all screens

### Maintainability
- ✅ **Single source of truth** for sizing (base.py)
- ✅ **Override only when needed** (special cases documented)
- ✅ **Easy to adjust globally** (change base class)
- ✅ **Testable** with different terminal sizes

---

## Success Criteria

### Must Have
- [x] All screens center horizontally and vertically
- [x] No content overflow on 80x24 terminals (minimum standard)
- [x] Content readable on terminals 80-200 chars wide
- [x] No hardcoded widths in screen CSS (except documented exceptions)
- [x] Base class provides responsive defaults

### Nice to Have
- [ ] Warning message for terminals < 80 chars wide
- [ ] Responsive table column widths
- [ ] Responsive form element widths
- [ ] Automated tests for different sizes
- [ ] CSS utility classes for common patterns

---

## Risk Assessment

### Low Risk
- **Base class changes**: Affects all screens uniformly
- **Removing width overrides**: Easy to revert if issues arise
- **Testing**: Can be done incrementally

### Medium Risk
- **Forms & tables**: May need additional adjustments for complex layouts
- **Edge cases**: Very small/large terminals may need special handling

### Mitigation
- **Incremental rollout**: Update base class first, then screens one-by-one
- **Thorough testing**: Test each screen after changes
- **Rollback plan**: Keep git history clean, easy to revert individual changes
- **Documentation**: Document any issues and solutions

---

## Timeline Estimate

| Phase | Time | Description |
|-------|------|-------------|
| Phase 1 | 15 min | Update base class |
| Phase 2 | 1 hour | Update all screen overrides |
| Phase 3 | 30 min | Add utility classes (optional) |
| Phase 4 | 45 min | Testing & validation |
| **Total** | **2.5 hours** | Complete implementation |

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Create feature branch**: `feat/responsive-screens`
3. **Implement Phase 1** (base class changes)
4. **Test base class** changes on existing screens
5. **Implement Phase 2** (screen-by-screen updates)
6. **Comprehensive testing** on multiple terminal sizes
7. **Merge to main** after validation

---

## References

### Textual CSS Documentation
- [Layout Documentation](https://textual.textualize.io/guide/layout/)
- [CSS Units](https://textual.textualize.io/guide/CSS/#units)
- [Screen Centering](https://textual.textualize.io/guide/screens/#aligning-screens)

### Related Files
- `src/tui/screens/base.py` - Base screen classes
- `src/tui/screens/*/` - All screen implementations
- `CLAUDE.md` - Project documentation

---

**Author**: Claude Code
**Date**: 2025-10-27
**Status**: Ready for Implementation
