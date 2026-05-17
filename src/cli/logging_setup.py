"""Logging configuration for the biotite CLI.

Wires a single RichHandler to the root logger so library code that uses
`logging.getLogger(__name__)` produces nicely formatted diagnostics on
stderr, gated by the user's `--verbose` flag.
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler


_MANAGED_FLAG = "_biotite_managed"

_QUIET_THIRD_PARTY = (
    "matplotlib",
    "matplotlib.font_manager",
    "PIL",
    "numba",
    "asyncio",
)


def configure_logging(verbose: bool) -> None:
    """Install (or replace) the biotite RichHandler on the root logger.

    `verbose=False` -> root level WARNING.
    `verbose=True`  -> root level INFO.

    Idempotent: removes any previously installed biotite-managed handler
    so repeated calls (e.g. from Typer's global callback) don't stack.
    """
    root = logging.getLogger()

    for handler in list(root.handlers):
        if getattr(handler, _MANAGED_FLAG, False):
            root.removeHandler(handler)

    handler = RichHandler(
        console=Console(stderr=True),
        show_time=False,
        show_path=False,
        markup=False,
        rich_tracebacks=True,
    )
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    setattr(handler, _MANAGED_FLAG, True)
    root.addHandler(handler)

    root.setLevel(logging.INFO if verbose else logging.WARNING)

    for name in _QUIET_THIRD_PARTY:
        logging.getLogger(name).setLevel(logging.WARNING)
