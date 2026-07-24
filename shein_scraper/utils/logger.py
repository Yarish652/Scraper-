"""
Provides a simple, consistent way to get a logger instance.
"""
import logging

def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance for the given name.

    This should be called after setup_logging() has been run.

    Args:
        name: The name of the logger, typically __name__.

    Returns:
        A configured logger instance.
    """
    return logging.getLogger(name)
