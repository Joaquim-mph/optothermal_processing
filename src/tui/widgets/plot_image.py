"""
MatplotlibImageWidget - Display matplotlib plots in Textual TUI.

This widget handles displaying static matplotlib PNG images within a Textual
application, with support for kitty terminal graphics protocol.
"""

from __future__ import annotations
from pathlib import Path
import logging
import os

from textual.widget import Widget
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.widgets import Static

logger = logging.getLogger(__name__)


class MatplotlibImageWidget(Widget):
    """
    Widget to display matplotlib plots as images in terminals with graphics support.

    Supports:
    - Kitty graphics protocol (via textual-image)
    - Fallback to file path display for unsupported terminals

    Attributes:
        image_path: Path to the PNG image file to display
        show_filename: Whether to show the filename below the image
    """

    image_path: reactive[str | None] = reactive(None)
    show_filename: reactive[bool] = reactive(True)

    DEFAULT_CSS = """
    MatplotlibImageWidget {
        width: 100%;
        height: auto;
        border: solid $primary;
        padding: 1;
        background: $surface;
    }

    MatplotlibImageWidget > Image {
        width: 100%;
        height: auto;
    }

    MatplotlibImageWidget .filename {
        width: 100%;
        text-align: center;
        color: $text-muted;
        padding-top: 1;
    }

    MatplotlibImageWidget .error {
        width: 100%;
        height: 100%;
        text-align: center;
        color: $error;
        padding: 2;
    }

    MatplotlibImageWidget .placeholder {
        width: 100%;
        height: 100%;
        text-align: center;
        color: $text-muted;
        padding: 2;
    }
    """

    def __init__(
        self,
        image_path: str | None = None,
        show_filename: bool = True,
        **kwargs
    ):
        """
        Initialize the matplotlib image widget.

        Args:
            image_path: Path to the PNG image to display
            show_filename: Whether to show filename below image
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.image_path = image_path
        self.show_filename = show_filename
        self._has_graphics_support = self._check_graphics_support()

    def _check_graphics_support(self) -> bool:
        """
        Check if the terminal supports graphics protocol.

        Returns:
            True if kitty graphics protocol is available

        Note:
            Kitty graphics is disabled by default due to previous terminal freeze issues
            with large images. Now fixed with automatic resizing (1920x1080 max, 2MB limit).

            To enable, set environment variable:
                export ENABLE_KITTY_GRAPHICS=1
        """
        # DISABLED: Textual's Static widget buffers escape sequences causing freeze
        # Issue: Even with image resizing, Textual can't handle raw escape codes
        # The terminal works (tested with direct echo), but Textual buffering breaks it
        #
        # TODO: Need alternative approach:
        #   - Write directly to terminal bypassing Textual (risky)
        #   - Use subprocess to call kitty icat (external)
        #   - Wait for textual-image library fix

        logger.debug("Graphics support: Kitty graphics disabled (Textual rendering issue)")
        return False

    def compose(self) -> ComposeResult:
        """Compose the widget's child components."""
        if not self.image_path:
            yield self._render_placeholder()
            return

        path = Path(self.image_path)
        if not path.exists():
            yield self._render_error(f"Image not found: {path}")
            return

        if self._has_graphics_support:
            yield self._render_image_kitty(path)
        else:
            yield self._render_image_fallback(path)

    def _render_image_kitty(self, path: Path) -> Widget:
        """
        Render image using kitty graphics protocol.

        Args:
            path: Path to the image file

        Returns:
            Static widget with kitty graphics escape sequences
        """
        try:
            from src.tui.widgets.kitty_image import KittyImageView

            logger.info(f"Rendering image with kitty graphics protocol: {path}")

            # Create kitty image view
            kitty_view = KittyImageView(
                image_path=path,
                max_width=None,  # Auto-size to container
                max_height=None
            )

            # Wrap in Static widget to display the Rich renderable
            # Static handles the Rich console protocol automatically
            static = Static(kitty_view)
            static.can_focus = False  # Prevent focus issues

            logger.debug(f"Successfully created kitty graphics view for: {path}")
            return static

        except Exception as e:
            logger.error(f"Error rendering image with kitty graphics: {e}", exc_info=True)
            # Fall back to info display if kitty graphics fail
            return self._render_image_fallback(path)

    def _render_image_fallback(self, path: Path) -> Widget:
        """
        Render fallback display for terminals without graphics support.

        Args:
            path: Path to the image file

        Returns:
            Static widget with image information
        """
        size_mb = path.stat().st_size / (1024 * 1024)

        # Get image dimensions
        dimensions_str = ""
        try:
            from PIL import Image
            with Image.open(path) as img:
                dimensions_str = f"\n📐 Dimensions: {img.width} × {img.height} px"
        except Exception as e:
            logger.debug(f"Could not read image dimensions: {e}")

        # Get file modification time
        from datetime import datetime
        mod_time = datetime.fromtimestamp(path.stat().st_mtime)
        mod_time_str = mod_time.strftime('%Y-%m-%d %H:%M:%S')

        # Check if we're in kitty but have it disabled
        term = os.environ.get('TERM', '')
        in_kitty = 'kitty' in term.lower()

        if in_kitty:
            enable_note = """
⚠️  Inline graphics not yet supported in TUI.

   Kitty terminal detected, but Textual framework
   buffering causes rendering issues. Your terminal
   DOES support graphics (tested with direct echo).

   For now, press 'o' to open plots externally.

   Working on solution...
"""
        else:
            enable_note = """
⚠️  Inline graphics require kitty terminal.
   Install: https://sw.kovidgoyal.net/kitty/
"""

        text = f"""
📊 Plot Preview

📁 {path.name}
📦 Size: {size_mb:.2f} MB{dimensions_str}
📅 Modified: {mod_time_str}
📂 Location: {path.parent.name}/

──────────────────────────────────────

💡 Tip: Press 'o' to open in external viewer
{enable_note}
        """.strip()

        return Static(text, classes="placeholder")

    def _render_placeholder(self) -> Widget:
        """Render placeholder when no image is set."""
        return Static(
            "No plot image loaded\n📊",
            classes="placeholder"
        )

    def _render_error(self, error_msg: str) -> Widget:
        """
        Render error message.

        Args:
            error_msg: Error message to display

        Returns:
            Static widget with error message
        """
        return Static(f"❌ {error_msg}", classes="error")

    def update_image(self, new_path: str) -> None:
        """
        Update the displayed image.

        Args:
            new_path: Path to new image file
        """
        logger.info(f"Updating plot image to: {new_path}")
        try:
            self.image_path = new_path
            logger.debug(f"Triggering recompose for new image: {new_path}")
            self.refresh(recompose=True)
            logger.debug(f"Recompose completed for: {new_path}")
        except Exception as e:
            logger.error(f"Error during image update: {e}", exc_info=True)
            raise

    def watch_image_path(self, old_path: str | None, new_path: str | None) -> None:
        """
        React to image_path changes.

        Args:
            old_path: Previous image path
            new_path: New image path
        """
        if old_path != new_path:
            logger.debug(f"Image path changed from {old_path} to {new_path}")
            self.refresh(recompose=True)
