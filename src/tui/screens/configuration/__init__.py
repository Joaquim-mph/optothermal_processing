"""
Configuration screens - Parameter setting and confirmation.

Provides screens for configuring plot parameters and confirming actions before execution.
"""

# v2.x configuration screens
from src.tui.screens.configuration.its_config import ITSConfigScreen
from src.tui.screens.configuration.ivg_config import IVgConfigScreen
from src.tui.screens.configuration.transconductance_config import TransconductanceConfigScreen

# v3.0 measurement plot configuration screens
from src.tui.screens.configuration.vvg_config import VVgConfigScreen
from src.tui.screens.configuration.vt_config import VtConfigScreen

# v3.0 derived metric plot configuration screens (requires enriched histories)
from src.tui.screens.configuration.cnp_config import CNPConfigScreen
from src.tui.screens.configuration.photoresponse_config import PhotoresponseConfigScreen

# Shared screens
from src.tui.screens.configuration.preview_screen import PreviewScreen
from src.tui.screens.configuration.process_confirmation import ProcessConfirmationScreen

__all__ = [
    # v2.x screens
    "ITSConfigScreen",
    "IVgConfigScreen",
    "TransconductanceConfigScreen",

    # v3.0 measurement plot screens
    "VVgConfigScreen",
    "VtConfigScreen",

    # v3.0 derived metric plot screens
    "CNPConfigScreen",
    "PhotoresponseConfigScreen",

    # Shared screens
    "PreviewScreen",
    "ProcessConfirmationScreen",
]
