import logging

from dnstapir.logging import configure_json_logging


def test_logging():
    configure_json_logging()
    logger = logging.getLogger(__name__)
    logger.warning("Hello world")
