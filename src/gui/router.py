"""
Navigation Router for Biotite GUI.

Manages page navigation with a history stack, enabling Back navigation
and direct jumps to any page. Maps to QStackedWidget indices.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class Router:
    """
    Navigation controller backed by QStackedWidget + history stack.

    Each page is registered by name. navigate_to() pushes onto the
    history stack; go_back() pops and restores the previous page.
    """

    def __init__(self, main_window: MainWindow):
        self._window = main_window
        self._history: list[str] = []
        self._pages: dict[str, int] = {}  # name -> stacked widget index

    def register_page(self, name: str, index: int) -> None:
        """Register a page name to its QStackedWidget index."""
        self._pages[name] = index

    def navigate_to(self, name: str, **kwargs: Any) -> None:
        """
        Navigate to a named page, pushing current page onto history.

        Parameters
        ----------
        name : str
            Page name (must be registered)
        **kwargs
            Passed to the page's `on_enter(**kwargs)` method if it exists
        """
        if name not in self._pages:
            raise ValueError(f"Unknown page: {name!r}")

        # Push current page onto history stack
        current = self._window.stack.currentIndex()
        for page_name, idx in self._pages.items():
            if idx == current:
                self._history.append(page_name)
                break

        self._switch_to(name, **kwargs)

    def go_back(self) -> None:
        """Navigate to the previous page in history."""
        if not self._history:
            self.return_to_main_menu()
            return
        prev = self._history.pop()
        self._switch_to(prev)

    def return_to_main_menu(self) -> None:
        """Clear history and return to main menu."""
        self._history.clear()
        self._switch_to("main_menu")

    def _switch_to(self, name: str, **kwargs: Any) -> None:
        """Switch the stacked widget and notify the page."""
        idx = self._pages[name]
        self._window.stack.setCurrentIndex(idx)
        widget = self._window.stack.widget(idx)
        if hasattr(widget, "on_enter"):
            widget.on_enter(**kwargs)
        self._window.update_breadcrumb(name)
        self._window.update_sidebar_selection(name)

    @property
    def can_go_back(self) -> bool:
        return len(self._history) > 0

    @property
    def current_page(self) -> str | None:
        idx = self._window.stack.currentIndex()
        for name, i in self._pages.items():
            if i == idx:
                return name
        return None
