import json
import logging
import logging.handlers
import os
from datetime import datetime, timedelta, timezone
from typing import Literal, Union

import colorlog

from utils.request_context import RequestContext


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
        # If the record has a request_id attribute, include it in the log entry
        request_id = getattr(record, "request_id", None)
        if request_id is not None:
            log_entry["request_id"] = request_id

        # If the record has a seq_no attribute, include it in the log entry
        seq_no = getattr(record, "seq_no", None)
        if seq_no is not None:
            log_entry["seq_no"] = seq_no
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
        # Show request ID in the log record if available
        request_id = getattr(record, "request_id", None)
        if request_id:
            record.console_request_id = f"[{str(request_id)[:8]}]"
        else:
            record.console_request_id = ""

        # Show sequence number in the log record if available
        seq_no = getattr(record, "seq_no", None)
        if seq_no is not None:
            record.console_seq_no = f"[{seq_no}]"
        else:
            record.console_seq_no = ""
        return super().format(record)


DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def initialize_logger(
    context: RequestContext,
    name: Union[str, None] = None,
    level: Union[str, int] = "INFO",
) -> logging.Logger:

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()  # Clear existing handlers to avoid duplicates

    # Stream handler for console output, with string formatting
    stream_handler = logging.StreamHandler()
    stream_formatter = RelativePathFormatter(
        fmt="%(log_color)s%(levelname)s%(reset)-10s[%(name)s]%(console_request_id)s %(console_seq_no)s[%(asctime)s]: %(message)s [%(relpath)s:%(lineno)d]",
        datefmt=DATE_FORMAT,
    )
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)

    # Time Rotating File Handler for file output, with JSON formatting
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
    os.makedirs(log_dir, exist_ok=True)  # Create log directory if it doesn't exist
    log_file = os.path.join(log_dir, "app.log")
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    file_handler.setFormatter(JSONFormatter(datefmt=DATE_FORMAT))
    logger.addHandler(file_handler)

    # Set the log record factory to include request ID and sequence number
    # This allows us to access these attributes in the log records
    # and use them in the logging middleware for better traceability
    old_factory = logging.getLogRecordFactory()

    def new_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = context.get_request_id()
        record.seq_no = context.next_seq_no()

        return record

    logging.setLogRecordFactory(new_factory)

    return logger
