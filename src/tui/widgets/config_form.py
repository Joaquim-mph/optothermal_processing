"""
Reusable Configuration Form Widget.

Provides a styled form container for configuration screens.
"""

from __future__ import annotations
from typing import Dict, Any

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, Input, Select, RadioButton, RadioSet, Label


class ConfigForm(Container):
    """Reusable configuration form container."""

    DEFAULT_CSS = """
    ConfigForm {
        height: auto;
        layout: vertical;
    }

    .form-section {
        margin-bottom: 1;
    }

    .section-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .form-row {
        height: 3;
        margin-bottom: 0;
    }

    .form-label {
        width: 20;
        padding-top: 1;
        color: $text;
    }

    .form-input {
        width: 1fr;
    }

    .form-help {
        width: 25;
        padding-top: 1;
        color: $text-muted;
        text-style: dim;
    }

    RadioSet {
        height: auto;
        margin-bottom: 1;
    }

    RadioButton {
        margin: 0 2 0 0;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.form_values: Dict[str, Any] = {}

    def get_values(self) -> Dict[str, Any]:
        """Get all form values."""
        return self.form_values.copy()

    def set_value(self, key: str, value: Any) -> None:
        """Set a form value."""
        self.form_values[key] = value
