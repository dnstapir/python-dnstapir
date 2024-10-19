import logging
import logging.config

from dnstapir.logging import JsonFormatter  # noqa

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

LOGGING_CONFIG_JSON = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "class": "tapir.logging.JsonFormatter",
            "format": LOGGING_RECORD_CUSTOM_FORMAT,
        },
    },
    "handlers": {
        "json": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["json"], "level": "DEBUG"},
}


def test_logging():
    logger = logging.getLogger(__name__)
    logging_config = LOGGING_CONFIG_JSON
    logging.config.dictConfig(logging_config)
    logger.warning("Hello")
