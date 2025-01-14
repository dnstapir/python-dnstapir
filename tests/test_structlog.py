import structlog

from dnstapir.structlog import setup_logging


def test_logging():
    setup_logging(json_logs=False, log_level="INFO")
    logger = structlog.getLogger()
    logger.warning("Hello %s", "world", foo="bar")
