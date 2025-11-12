"""
Kitty Graphics Protocol Renderer for Textual.

Uses Rich Segment system (inspired by textual_imageview pattern) to inject
kitty graphics escape sequences without event propagation issues.
"""

import base64
import io
import logging
from pathlib import Path
from typing import Optional

from PIL import Image
from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment
from rich.style import Style

logger = logging.getLogger(__name__)


class KittyImageView:
    """
    Renders an image using kitty graphics protocol via Rich segments.

    This uses the proven pattern from textual_imageview but outputs kitty
    graphics escape sequences instead of halfcell characters.

    Args:
        image_path: Path to the image file to display
        max_width: Maximum width in terminal columns (None = auto)
        max_height: Maximum height in terminal rows (None = auto)
    """

    # Maximum dimensions to prevent terminal freeze
    MAX_WIDTH_PX = 1920
    MAX_HEIGHT_PX = 1080
    MAX_FILE_SIZE_MB = 2.0

    def __init__(
        self,
        image_path: str | Path,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
    ):
        self.image_path = Path(image_path)
        self.max_width = max_width
        self.max_height = max_height
        self._image: Optional[Image.Image] = None
        self._encoded_data: Optional[str] = None
        self._was_resized = False

        # Load and prepare image
        self._load_image()

    def _load_image(self) -> None:
        """Load and prepare the image for display with safe resizing."""
        try:
            # Check file size first
            file_size_mb = self.image_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB * 10:  # 20MB limit for source file
                raise RuntimeError(
                    f"Image file too large: {file_size_mb:.1f}MB (max {self.MAX_FILE_SIZE_MB * 10}MB)"
                )

            self._image = Image.open(self.image_path)

            # Convert to RGB if needed (kitty requires RGB or RGBA)
            if self._image.mode not in ('RGB', 'RGBA'):
                self._image = self._image.convert('RGB')

            # CRITICAL: Resize image to safe dimensions to prevent terminal freeze
            original_size = self._image.size
            if (self._image.width > self.MAX_WIDTH_PX or
                self._image.height > self.MAX_HEIGHT_PX):

                # Calculate aspect-preserving resize
                ratio = min(
                    self.MAX_WIDTH_PX / self._image.width,
                    self.MAX_HEIGHT_PX / self._image.height
                )
                new_size = (
                    int(self._image.width * ratio),
                    int(self._image.height * ratio)
                )

                self._image = self._image.resize(new_size, Image.Resampling.LANCZOS)
                self._was_resized = True

                logger.info(f"Resized image from {original_size} to {new_size} for safe display")

            # Encode as PNG with compression
            buffer = io.BytesIO()
            self._image.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)

            png_data = buffer.read()
            png_size_mb = len(png_data) / (1024 * 1024)

            # Safety check: ensure encoded size is reasonable
            if png_size_mb > self.MAX_FILE_SIZE_MB:
                raise RuntimeError(
                    f"Encoded image too large: {png_size_mb:.1f}MB (max {self.MAX_FILE_SIZE_MB}MB)"
                )

            self._encoded_data = base64.standard_b64encode(png_data).decode('ascii')
            logger.info(f"Encoded image: {len(self._encoded_data)} bytes base64 "
                       f"({png_size_mb:.2f}MB PNG, resized={self._was_resized})")

        except Exception as e:
            raise RuntimeError(f"Failed to load image {self.image_path}: {e}")

    def _generate_kitty_escape_sequence(self, width_cols: int, height_rows: int) -> str:
        """
        Generate kitty graphics escape sequence using direct transmission.

        Kitty protocol format:
        \x1b_G<control_data>;<base64_payload>\x1b\\

        Control data keys:
            f=100 - Format: PNG
            a=T   - Action: Transmit and display (single step)
            t=d   - Transmission: Direct (not file, not temp file)

        For large images, we use chunked transmission (m=1/m=0).

        Args:
            width_cols: Desired width in terminal columns (unused for now)
            height_rows: Desired height in terminal rows (unused for now)

        Returns:
            Escape sequence string
        """
        if not self._encoded_data:
            return ""

        # For small images (< 4KB), use direct single-chunk transmission
        if len(self._encoded_data) < 4096:
            return f"\x1b_Gf=100,a=T,t=d;{self._encoded_data}\x1b\\"

        # For larger images, use chunked transmission
        chunk_size = 4096
        sequences = []

        for i in range(0, len(self._encoded_data), chunk_size):
            chunk = self._encoded_data[i:i+chunk_size]
            is_first = (i == 0)
            is_last = (i + chunk_size >= len(self._encoded_data))

            if is_first:
                # First chunk: include all control data
                seq = f"\x1b_Gf=100,a=T,t=d,m=1;{chunk}\x1b\\"
            elif is_last:
                # Last chunk: signal end of transmission
                seq = f"\x1b_Gm=0;{chunk}\x1b\\"
            else:
                # Middle chunks: continue transmission
                seq = f"\x1b_Gm=1;{chunk}\x1b\\"

            sequences.append(seq)

        return "".join(sequences)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """
        Render the image using kitty graphics protocol.

        This method is called by Rich/Textual to render the content.
        Returns Segment objects containing the escape sequences.
        """
        if not self._image or not self._encoded_data:
            yield Segment("Error: Image not loaded\n", Style(color="red"))
            return

        # Get terminal dimensions
        width_cols = self.max_width or options.max_width
        height_rows = self.max_height or (options.height if options.height else 20)

        # Generate kitty escape sequence
        escape_seq = self._generate_kitty_escape_sequence(width_cols, height_rows)

        # Calculate how many rows the image will occupy
        # Kitty graphics don't use character cells directly, but we need to
        # reserve space so Textual knows the widget height
        img_width, img_height = self._image.size

        # Estimate rows needed (rough approximation)
        # Kitty uses pixels, but we need to tell Textual about cell rows
        estimated_rows = min(height_rows, img_height // 20)  # ~20 pixels per row

        # Yield the escape sequence as a single segment
        yield Segment(escape_seq, Style.null())

        # Yield newlines to reserve vertical space
        for _ in range(max(1, estimated_rows)):
            yield Segment("\n", Style.null())

        # Add image info below
        size_mb = self.image_path.stat().st_size / (1024 * 1024)
        info = f"📊 {self.image_path.name} ({img_width}×{img_height}px, {size_mb:.2f}MB)"
        yield Segment(info, Style(color="cyan", dim=True))
        yield Segment("\n", Style.null())
