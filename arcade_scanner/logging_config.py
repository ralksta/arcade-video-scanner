"""
arcade_scanner.logging_config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Call ``setup_logging()`` once at application startup.  After that every module
can simply do ``logging.getLogger(__name__)`` to get a correctly configured
logger that writes to both the console and to a rotating log file.
"""

import logging
import logging.handlers
import os
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_dir: "str | Path | None" = None,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> None:
    """
    Configure the root logger with:

    * StreamHandler  → coloured console output
    * RotatingFileHandler → ``<log_dir>/arcade_scanner.log``

    Safe to call multiple times (idempotent – handlers are added only once).

    :param level:        Log level string (DEBUG / INFO / WARNING / ERROR).
    :param log_dir:      Directory for the log file.  Falls back to
                         ``~/.arcade-scanner/logs`` if not given.
    :param max_bytes:    Log file size limit before rotation (default 5 MB).
    :param backup_count: Number of rotated log files to keep (default 3).
    """
    root = logging.getLogger()

    # Idempotency guard – only attach handlers once
    if root.handlers:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(numeric_level)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s:%(lineno)d  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Console handler ---
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(numeric_level)
    root.addHandler(console)

    # --- Rotating file handler ---
    if log_dir is None:
        log_dir = Path.home() / ".arcade-scanner" / "logs"
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "arcade_scanner.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(numeric_level)
    root.addHandler(file_handler)

    logging.getLogger(__name__).debug(
        "Logging initialised → %s (level=%s)", log_file, level
    )
