"""
Base Screen Classes for TUI Wizard Flow.

Provides shared functionality and styling for all TUI screens:
- WizardScreen: Base class with common layout and navigation
- FormScreen: Specialized for configuration forms
- SelectorScreen: Specialized for selection screens (grids, lists)
- ResultScreen: Specialized for success/error result screens

Benefits:
- Eliminates CSS duplication across 15+ screens
- Standard compose() structure with override points
- Shared navigation patterns
- Consistent styling and behavior
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button
from textual.binding import Binding

if TYPE_CHECKING:
    from src.tui.app import PlotterApp


class WizardScreen(Screen):
    """
    Base class for wizard flow screens with shared styling and navigation.

    All wizard screens should inherit from this class or one of its specialized
    subclasses (FormScreen, SelectorScreen, ResultScreen).

    Override in Subclasses
    ----------------------
    - SCREEN_TITLE: str
        Title displayed at the top of the screen
    - STEP_NUMBER: int | None
        Current step number (e.g., 1 for "Step 1/6"). None hides the indicator.
    - TOTAL_STEPS: int
        Total number of steps in the wizard (default: 6)
    - compose_content(): ComposeResult
        Screen-specific content (must override)

    Standard Layout
    ---------------
    The base compose() provides:
    - Header (app-level)
    - Main container with border
    - Title and step indicator
    - Content area (from compose_content())
    - Footer (app-level)

    Example
    -------
    >>> class MyScreen(WizardScreen):
    ...     SCREEN_TITLE = "Select Option"
    ...     STEP_NUMBER = 2
    ...
    ...     def compose_content(self) -> ComposeResult:
    ...         yield Static("Choose an option:")
    ...         yield Button("Option A")
    ...         yield Button("Option B")
    """

    # Override in subclasses
    SCREEN_TITLE: str = "Wizard Screen"
    STEP_NUMBER: Optional[int] = None
    TOTAL_STEPS: int = 6

    # Common bindings (subclasses can extend with BINDINGS = WizardScreen.BINDINGS + [...])
    BINDINGS = [
        Binding("escape", "back", "Back", priority=True),
        Binding("ctrl+b", "back", "Back", show=False),
    ]

    # Shared CSS (applied to all WizardScreen subclasses)
    CSS = """
    WizardScreen {
        width: 100%;
        height: 100%;
        layout: vertical;
        align: center middle;
        content-align: center middle;
    }

    #screen-body {
        width: 100%;
        height: 100%;
        layout: vertical;
        align: center middle;
        content-align: center middle;
    }

    #main-container {
        width: 90%;
        max-width: 120;
        min-width: 60;
        min-height: 50%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 4;
    }

    #header-container {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
    }

    #chip-info {
        width: 100%;
        content-align: center middle;
        color: $accent;
        margin-bottom: 1;
    }

    #step-indicator {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    #button-container {
        width: 100%;
        height: auto;
        layout: horizontal;
        margin-top: 1;
        align-horizontal: center;
    }

    .nav-button {
        width: 1fr;
        max-width: 1fr;
        min-width: 0;
        height: 1;
        margin: 0 1;
        padding: 0 1;
    }

    .nav-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }

    .nav-button:hover {
        background: $primary;
        color: $primary-background;
    }

    .section-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
    }

    /* Subtitle styling (used by MainMenu and config screens) */
    #subtitle {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-bottom: 1;
    }

    /* Help text (bottom of screen) */
    #help-text {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-top: 1;
        text-style: dim;
    }

    /* Info text boxes (standardized across screens) */
    .info-text {
        width: 100%;
        padding: 1;
        background: $panel;
        color: $text;
        margin-bottom: 0;
    }
    """

    # Type hint for app (provides access to session and router)
    app: PlotterApp

    def compose_header(self) -> ComposeResult:
        """
        Compose standard wizard header with title and step indicator.

        Override this if you need custom header content (e.g., chip info).
        """
        yield Static(self.SCREEN_TITLE, id="title")
        if self.STEP_NUMBER is not None:
            yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose(self) -> ComposeResult:
        """
        Compose standard wizard layout.

        DO NOT override this method. Override compose_content() instead.
        """
        yield Header()

        with Container(id="screen-body"):
            with Container(id="main-container"):
                with Vertical(id="header-container"):
                    yield from self.compose_header()

                yield from self.compose_content()

        yield Footer()

    def compose_content(self) -> ComposeResult:
        """
        Compose screen-specific content.

        MUST be overridden in subclasses.

        Raises
        ------
        NotImplementedError
            If not overridden in subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement compose_content()"
        )

    def action_back(self) -> None:
        """
        Standard back navigation (pops current screen).

        Override if custom back behavior is needed.
        """
        self.app.pop_screen()


class FormScreen(WizardScreen):
    """
    Base class for configuration form screens.

    Extends WizardScreen with form-specific styling:
    - Form rows with labels and inputs
    - Form help text
    - Input styling (focus, disabled states)

    Example
    -------
    >>> class ConfigScreen(FormScreen):
    ...     SCREEN_TITLE = "Configure Plot"
    ...     STEP_NUMBER = 4
    ...
    ...     def compose_content(self) -> ComposeResult:
    ...         yield Static("── Options ──", classes="section-title")
    ...         with Horizontal(classes="form-row"):
    ...             yield Label("Baseline (s):", classes="form-label")
    ...             yield Input(value="60.0", classes="form-input")
    ...             yield Static("Baseline time", classes="form-help")
    """

    CSS = WizardScreen.CSS + """
    .form-row {
        height: auto;
        min-height: 3;
        margin-bottom: 0;
    }

    .form-label {
        width: 20;
        padding-top: 1;
        color: $text;
    }

    .form-input {
        width: 30;
    }

    .form-input:focus {
        border: tall $accent;
    }

    .form-input:disabled {
        opacity: 0.5;
        color: $text-muted;
    }

    .form-help {
        width: 1fr;
        padding-top: 1;
        padding-left: 2;
        color: $text-muted;
        text-style: dim;
    }

    Checkbox {
        margin-bottom: 0;
    }

    RadioSet {
        height: auto;
        margin-bottom: 1;
    }

    RadioButton {
        margin: 0 2 0 0;
    }

    Select {
        width: auto;
    }
    """


class SelectorScreen(WizardScreen):
    """
    Base class for selection screens (chip selector, plot type, etc.).

    Extends WizardScreen with selector-specific styling:
    - Grid layouts for multi-item selection
    - Button grids with focus states
    - List containers

    Example
    -------
    >>> class ChipSelectorScreen(SelectorScreen):
    ...     SCREEN_TITLE = "Select Chip"
    ...     STEP_NUMBER = 1
    ...
    ...     def compose_content(self) -> ComposeResult:
    ...         with Container(id="chip-grid-container"):
    ...             yield Grid(id="chip-grid")
    """

    CSS = WizardScreen.CSS + """
    #chip-grid-container,
    #selection-container {
        width: 100%;
        height: auto;
        border: solid $primary;
        padding: 2;
        margin-bottom: 1;
    }

    #chip-grid,
    .selection-grid {
        width: 100%;
        height: auto;
        grid-size: 5;
        grid-gutter: 1 2;
    }

    .chip-button,
    .selection-button {
        width: 100%;
        height: 3;
        min-width: 10;
    }

    .chip-button:focus,
    .selection-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }

    .chip-button:hover,
    .selection-button:hover {
        background: $primary;
        color: $primary-background;
    }

    #loading-text {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin: 1 0;
    }

    #error-text {
        width: 100%;
        content-align: center middle;
        color: $error;
        margin: 2 0;
    }

    .plot-description,
    .option-description {
        width: 100%;
        color: $text-muted;
        margin: 0 2 1 2;
        padding: 1;
        background: $panel-lighten-1;
    }
    """


class ResultScreen(WizardScreen):
    """
    Base class for result screens (success/error after processing).

    Extends WizardScreen with result-specific styling:
    - Success/error borders and colors
    - Info rows for displaying results
    - Button navigation patterns

    Example
    -------
    >>> class SuccessScreen(ResultScreen):
    ...     SCREEN_TITLE = "Plot Generated Successfully!"
    ...
    ...     def compose_content(self) -> ComposeResult:
    ...         yield Static("Output file:", classes="section-title")
    ...         yield Static("/path/to/plot.png", classes="info-row")
    """

    # ResultScreen doesn't show step indicators
    STEP_NUMBER = None

    CSS = WizardScreen.CSS + """
    .info-row {
        color: $text;
        margin-left: 2;
        margin-bottom: 0;
    }

    .error-text {
        color: $text;
        margin-left: 2;
        margin-bottom: 1;
    }

    .suggestion-text {
        color: $warning;
        margin-left: 2;
        margin-bottom: 1;
        text-style: italic;
    }
    """


class SuccessScreen(ResultScreen):
    """
    Specialized result screen for successful operations.

    Uses success color for border.
    """

    CSS = ResultScreen.CSS + """
    #main-container {
        border: thick $success;
    }

    #title {
        color: $success;
    }
    """


class ErrorScreen(ResultScreen):
    """
    Specialized result screen for errors.

    Uses error color for border.
    """

    CSS = ResultScreen.CSS + """
    #main-container {
        border: thick $error;
    }

    #title {
        color: $error;
    }
    """
