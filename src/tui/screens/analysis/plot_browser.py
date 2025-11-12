"""
PlotBrowserScreen - Browse and view existing plots from figs/ directory.

This screen provides a two-pane interface for navigating the plot directory
structure and viewing individual plots with metadata.
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime
import logging

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DirectoryTree
from textual.containers import Container, Horizontal
from textual.binding import Binding

from src.tui.widgets import MatplotlibImageWidget

logger = logging.getLogger(__name__)


class PlotBrowserScreen(Screen):
    """
    Screen to browse and view plots from the figs/ directory.

    Provides a two-pane interface:
    - Left pane: Directory tree for navigation
    - Right pane: Plot display and metadata

    Features:
    - Navigate directory tree with arrow keys
    - Select PNG files to display in viewer
    - Show file metadata (path, size, modified date)
    - Keyboard shortcuts for quick navigation
    """

    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        Binding("q", "quit_app", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("o", "open_external", "Open in Viewer"),
    ]

    CSS = """
    PlotBrowserScreen {
        background: $surface;
    }

    #browser-container {
        width: 100%;
        height: 100%;
    }

    #tree-panel {
        width: 30%;
        height: 100%;
        border-right: solid $primary;
        padding: 1;
    }

    #plot-tree {
        width: 100%;
        height: 100%;
    }

    #viewer-panel {
        width: 70%;
        height: 100%;
        padding: 1;
    }

    #plot-display-container {
        width: 100%;
        height: 70%;
        border: solid $accent;
        margin-bottom: 1;
    }

    #plot-display {
        width: 100%;
        height: 100%;
    }

    #metadata-panel {
        width: 100%;
        height: 30%;
        border: solid $accent;
        padding: 1;
        background: $panel;
    }

    #metadata-text {
        width: 100%;
        padding: 1;
    }

    .info-label {
        color: $text-muted;
        text-style: italic;
    }

    .no-plots-message {
        width: 100%;
        height: 100%;
        text-align: center;
        padding: 4;
        color: $text-muted;
    }
    """

    def __init__(self, figs_dir: Path | None = None, **kwargs):
        """
        Initialize the plot browser screen.

        Args:
            figs_dir: Root directory for plots (defaults to "figs/")
            **kwargs: Additional screen arguments
        """
        super().__init__(**kwargs)
        self.figs_dir = figs_dir or Path("figs")
        self.current_plot_path: Path | None = None
        self._processing_file_selection = False  # Flag to prevent accidental go_back during file selection

        logger.info(f"Initializing PlotBrowserScreen with figs_dir: {self.figs_dir}")

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header(show_clock=True)

        # Check if figs directory exists
        if not self.figs_dir.exists():
            with Container():
                yield Static(
                    f"📊 No plots directory found\n\n"
                    f"Expected directory: {self.figs_dir.absolute()}\n\n"
                    f"Generate some plots first!",
                    classes="no-plots-message"
                )
            yield Footer()
            return

        # Two-pane layout
        with Horizontal(id="browser-container"):
            # Left pane: Directory tree
            with Container(id="tree-panel"):
                yield DirectoryTree(
                    str(self.figs_dir),
                    id="plot-tree"
                )

            # Right pane: Plot viewer and metadata
            with Container(id="viewer-panel"):
                # Plot display area (use Container instead of ScrollableContainer to avoid conflicts)
                with Container(id="plot-display-container"):
                    yield MatplotlibImageWidget(
                        image_path=None,
                        show_filename=True,
                        id="plot-display"
                    )

                # Metadata panel
                with Container(id="metadata-panel"):
                    yield Static(
                        self._get_welcome_message(),
                        id="metadata-text"
                    )

        yield Footer()

    def _get_welcome_message(self) -> str:
        """Get welcome message for metadata panel."""
        return """
📊 Plot Browser

Select a PNG file from the directory tree to view it here.

Navigation:
  ↑↓    - Navigate tree
  →     - Expand folder
  ←     - Collapse folder
  Enter - Select file/folder

Actions:
  o     - Open selected plot in external viewer
  r     - Refresh directory tree
  Esc   - Return to main menu
  q     - Quit application
        """.strip()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """
        Handle file selection from directory tree.

        Args:
            event: File selection event
        """
        try:
            self._processing_file_selection = True
            path = Path(event.path)

            # Only handle PNG files
            if path.suffix.lower() != '.png':
                logger.debug(f"Ignoring non-PNG file: {path}")
                self._processing_file_selection = False
                return

            logger.info(f"File selected: {path}")

            # Update current plot path
            self.current_plot_path = path

            # Update image widget
            try:
                image_widget = self.query_one("#plot-display", MatplotlibImageWidget)
                logger.debug(f"Found image widget, updating to: {path}")
                image_widget.update_image(str(path))
                logger.debug(f"Image widget updated successfully")
            except Exception as e:
                logger.error(f"Error updating image widget: {e}", exc_info=True)
                self.notify(f"Error loading image: {e}", severity="error", timeout=5)
                self._processing_file_selection = False
                return

            # Update metadata
            self._update_metadata(path)
            logger.debug(f"Metadata updated successfully")

            # Use call_after_refresh to ensure the Image widget finishes mounting before clearing flag
            def clear_flag():
                logger.debug("Clearing processing flag after refresh")
                self._processing_file_selection = False

            self.call_after_refresh(clear_flag)

        except Exception as e:
            logger.error(f"Unexpected error in file selection handler: {e}", exc_info=True)
            self.notify(f"Unexpected error: {e}", severity="error", timeout=5)
            self._processing_file_selection = False

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """
        Handle directory selection from tree.

        Args:
            event: Directory selection event
        """
        path = Path(event.path)
        logger.debug(f"Directory selected: {path}")

    def _update_metadata(self, path: Path) -> None:
        """
        Update metadata panel with file information.

        Args:
            path: Path to the file
        """
        try:
            # Get file statistics
            stat = path.stat()
            size_mb = stat.st_size / (1024 * 1024)
            modified = datetime.fromtimestamp(stat.st_mtime)

            # Get image dimensions if possible
            dimensions = self._get_image_dimensions(path)
            dimensions_str = f"\n📐 Dimensions: {dimensions}" if dimensions else ""

            # Format metadata text
            metadata_text = f"""
📁 File Information

File: {path.name}
Size: {size_mb:.2f} MB
Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}
Path: {path.parent}{dimensions_str}
            """.strip()

            # Update metadata display
            metadata_widget = self.query_one("#metadata-text", Static)
            metadata_widget.update(metadata_text)

        except Exception as e:
            logger.error(f"Error updating metadata: {e}")
            error_text = f"❌ Error reading file metadata: {e}"
            try:
                metadata_widget = self.query_one("#metadata-text", Static)
                metadata_widget.update(error_text)
            except Exception:
                pass

    def _get_image_dimensions(self, path: Path) -> str | None:
        """
        Get image dimensions from PNG file.

        Args:
            path: Path to image file

        Returns:
            Dimensions string like "1920x1080" or None if error
        """
        try:
            from PIL import Image
            with Image.open(path) as img:
                return f"{img.width}x{img.height}"
        except ImportError:
            logger.debug("PIL not available for image dimension reading")
            return None
        except Exception as e:
            logger.debug(f"Error reading image dimensions: {e}")
            return None

    def action_go_back(self) -> None:
        """Go back to previous screen (Escape key)."""
        if self._processing_file_selection:
            logger.warning("Ignoring go_back action during file selection processing")
            return
        logger.info("Going back from plot browser")
        self.app.pop_screen()

    def action_quit_app(self) -> None:
        """Quit the application (q key)."""
        logger.info("Quitting application from plot browser")
        self.app.exit()

    def action_refresh(self) -> None:
        """Refresh the directory tree (r key)."""
        logger.info("Refreshing plot browser")
        try:
            tree = self.query_one("#plot-tree", DirectoryTree)
            tree.reload()
            self.notify("Directory tree refreshed", severity="information", timeout=2)
        except Exception as e:
            logger.error(f"Error refreshing tree: {e}")
            self.notify(f"Error refreshing: {e}", severity="error", timeout=3)

    def action_open_external(self) -> None:
        """Open the currently selected plot in external image viewer (o key)."""
        if not self.current_plot_path:
            self.notify("No plot selected", severity="warning", timeout=2)
            return

        try:
            import subprocess
            import platform

            # Get the appropriate open command for the OS
            if platform.system() == "Darwin":  # macOS
                cmd = ["open", str(self.current_plot_path)]
            elif platform.system() == "Linux":
                cmd = ["xdg-open", str(self.current_plot_path)]
            else:  # Windows
                cmd = ["start", str(self.current_plot_path)]

            logger.info(f"Opening plot in external viewer: {self.current_plot_path}")
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.notify(f"Opening {self.current_plot_path.name}", severity="information", timeout=2)

        except Exception as e:
            logger.error(f"Error opening plot in external viewer: {e}", exc_info=True)
            self.notify(f"Error opening plot: {e}", severity="error", timeout=5)
