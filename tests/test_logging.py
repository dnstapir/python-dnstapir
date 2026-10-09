import logging

import structlog

from dnstapir.logging import HANDLER_NAME, setup_logging


def test_logging():
    setup_logging(json_logs=False, log_level="INFO")
    logger = structlog.getLogger()
    logger.warning("Hello %s", "world", foo="bar")


def test_logging_twice():
    setup_logging(json_logs=False, log_level="INFO")
    setup_logging(json_logs=True, log_level="DEBUG")
    root_logger = logging.getLogger()
    handlers = [h for h in root_logger.handlers if h.get_name() == HANDLER_NAME]
    assert len(handlers) == 1
    assert root_logger.level == logging.DEBUG
