"""
Logging Configuration
====================

Centralized logging setup using loguru.
Provides structured JSON logging for production and colorful logging for development.
"""

import sys
import logging
from loguru import logger
from backend.config.settings import settings

class InterceptHandler(logging.Handler):
    """
    Redirect standard logging to Loguru.
    """
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

def setup_logging():
    """
    Configure logging based on environment.
    """
    # Remove default handlers
    logging.root.handlers = []
    
    # Configure Loguru
    logger.remove()
    
    if settings.ENV == "production":
        # JSON logs for production (Datadog/Splunk friendly)
        logger.add(
            sys.stderr,
            format="{message}",
            serialize=True,
            level="INFO",
            backtrace=False,
            diagnose=False,
        )
    else:
        # Pretty logs for development
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="DEBUG",
            colorize=True
        )

    # Intercept standard library logs (e.g. uvicorn, sqlalchemy)
    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    for _log in ["uvicorn", "uvicorn.error", "fastapi", "sqlalchemy"]:
        _logger = logging.getLogger(_log)
        _logger.handlers = [InterceptHandler()]

# Export simplified logger for use in app
log = logger
