"""
TUI Logging Configuration.

Sets up file logging for the TUI to capture all processing events, errors, and warnings.
"""

from __future__ import annotations
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler


def setup_tui_logging(log_dir: Path | str = "logs") -> Path:
    """
    Set up logging for the TUI application.

    Creates a rotating log file that captures all TUI events, errors, and processing steps.

    Parameters
    ----------
    log_dir : Path or str
        Directory for log files (default: "logs")

    Returns
    -------
    Path
        Path to the current log file

    Notes
    -----
    - Creates rotating log files (max 10 MB, keeps 5 backups)
    - Log format: timestamp | level | module | message
    - Captures all logging from 'src.tui' and 'src.derived' modules
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create log filename with date
    log_file = log_dir / f"tui_{datetime.now().strftime('%Y%m%d')}.log"

    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create rotating file handler (10 MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Configure root logger for TUI modules
    tui_logger = logging.getLogger('src.tui')
    tui_logger.setLevel(logging.DEBUG)
    tui_logger.addHandler(file_handler)

    # Also capture derived metrics pipeline logs
    derived_logger = logging.getLogger('src.derived')
    derived_logger.setLevel(logging.DEBUG)
    derived_logger.addHandler(file_handler)

    # Log startup
    tui_logger.info("=" * 80)
    tui_logger.info("TUI Session Started")
    tui_logger.info("=" * 80)

    return log_file


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a TUI module.

    Parameters
    ----------
    name : str
        Module name (e.g., 'src.tui.screens.processing.process_loading')

    Returns
    -------
    logging.Logger
        Configured logger instance
    """
    return logging.getLogger(name)


def read_recent_logs(log_dir: Path | str = "logs", max_lines: int = 500) -> list[str]:
    """
    Read recent log entries from the current log file.

    Parameters
    ----------
    log_dir : Path or str
        Directory containing log files (default: "logs")
    max_lines : int
        Maximum number of lines to return (default: 500)

    Returns
    -------
    list[str]
        List of log lines (most recent last)
    """
    log_dir = Path(log_dir)

    # Find today's log file
    log_file = log_dir / f"tui_{datetime.now().strftime('%Y%m%d')}.log"

    if not log_file.exists():
        return ["No log file found for today."]

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Return last max_lines
            return lines[-max_lines:] if len(lines) > max_lines else lines
    except Exception as e:
        return [f"Error reading log file: {e}"]


def get_log_file_path(log_dir: Path | str = "logs") -> Path:
    """
    Get the path to the current log file.

    Parameters
    ----------
    log_dir : Path or str
        Directory containing log files (default: "logs")

    Returns
    -------
    Path
        Path to today's log file
    """
    log_dir = Path(log_dir)
    return log_dir / f"tui_{datetime.now().strftime('%Y%m%d')}.log"
