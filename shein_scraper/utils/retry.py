"""
A generic retry decorator for handling transient errors.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Type

from exceptions import ScraperException

logger = logging.getLogger(__name__)

def retry(
    max_retries: int,
    delay: int,
    retryable_exceptions: tuple[Type[Exception], ...] = (ScraperException,)
):
    """
    A decorator to retry a function call on specific, retryable exceptions.

    Args:
        max_retries: The maximum number of retries.
        delay: The delay in seconds between retries.
        retryable_exceptions: A tuple of exception types that should trigger a retry.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, max_retries + 2):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    if attempt > max_retries:
                        logger.error(
                            "Function %s failed after %d retries. Error: %s",
                            func.__name__, max_retries, e
                        )
                        raise  # Re-raise the exception after all retries are exhausted
                    
                    logger.warning(
                        "Function %s failed with a retryable error. Retrying in %ds... (Attempt %d/%d). Error: %s",
                        func.__name__, delay, attempt, max_retries, e
                    )
                    time.sleep(delay)
        return wrapper
    return decorator
