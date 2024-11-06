import logging.config
from datetime import datetime
from typing import Any

from jsonformatter import JsonFormatter as _JsonFormatter

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"

LOGGING_RECORD_CUSTOM_FORMAT = {
    "time": "asctime",
    # "Created": "created",
    # "RelativeCreated": "relativeCreated",
    "name": "name",
    # "Levelno": "levelno",
    "levelname": "levelname",
    "process": "process",
    "thread": "thread",
    # "threadName": "threadName",
    # "Pathname": "pathname",
    # "Filename": "filename",
    # "Module": "module",
    # "Lineno": "lineno",
    # "FuncName": "funcName",
    "message": "message",
}

LOGGING_CONFIG_JSON: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "class": "dnstapir.logging.JsonFormatter",
            "format": LOGGING_RECORD_CUSTOM_FORMAT,
        },
    },
    "handlers": {
        "json": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["json"], "level": "DEBUG"},
}


class JsonFormatter(_JsonFormatter):
    def formatTime(self, record, datefmt=None) -> str:
        dt = datetime.fromtimestamp(record.created).astimezone()
        return dt.strftime(TIMESTAMP_FORMAT)


def configure_json_logging() -> dict[str, Any]:
    """Configure JSON logging and return configuration dictionary"""
    logging.config.dictConfig(LOGGING_CONFIG_JSON)
    return LOGGING_CONFIG_JSON
