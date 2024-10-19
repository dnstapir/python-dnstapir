import logging
import logging.config

from dnstapir.logging import LOGGING_CONFIG_JSON


def test_logging():
    logger = logging.getLogger(__name__)
    logging_config = LOGGING_CONFIG_JSON
    logging.config.dictConfig(logging_config)
    logger.warning("Hello")
