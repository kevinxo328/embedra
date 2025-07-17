import json
import logging
import logging.handlers
import os
from datetime import datetime, timedelta, timezone
from typing import Literal

import colorlog


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "level": record.levelname,
            "message": (
                record.msg
                if isinstance(record.msg, dict)
                else {"content": str(record.msg)}
            ),
            "file": getattr(record, "filename", "unknown"),
            "module": getattr(record, "module", "unknown"),
        }
        return json.dumps(log_entry, ensure_ascii=False)


class RelativePathFormatter(colorlog.ColoredFormatter):
    """
    Formatter that converts absolute file paths to relative paths.
    """

    def __init__(
        self,
        fmt=None,
        datefmt=None,
        style: Literal["%", "{", "$"] = "%",
        project_root=None,
    ):
        super().__init__(fmt, datefmt, style)
        self.project_root = project_root or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

    def format(self, record):
        try:
            record.relpath = os.path.relpath(record.pathname, self.project_root)
        except ValueError:
            record.relpath = record.pathname  # fallback to absolute
        return super().format(record)


logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers.clear()  # Clear existing handlers to avoid duplicates

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

# Stream handler for console output, with string formatting
stream_handler = logging.StreamHandler()
stream_formatter = RelativePathFormatter(
    fmt="%(log_color)s%(levelname)s%(reset)-10s[%(name)s][%(asctime)s]: %(message)s [%(relpath)s:%(lineno)d]",
    datefmt=DATE_FORMAT,
)
stream_handler.setFormatter(stream_formatter)

# Time Rotating File Handler for file output, with JSON formatting
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
os.makedirs(log_dir, exist_ok=True)  # Create log directory if it doesn't exist
print(log_dir)
log_file = os.path.join(log_dir, "app.log")
file_handler = logging.handlers.TimedRotatingFileHandler(
    log_file, when="midnight", interval=1, backupCount=30, encoding="utf-8", utc=True
)
file_handler.setFormatter(JSONFormatter(datefmt=DATE_FORMAT))


logger.addHandler(stream_handler)
logger.addHandler(file_handler)
