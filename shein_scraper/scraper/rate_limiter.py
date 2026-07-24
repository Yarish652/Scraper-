"""
Provides rate limiting functionality for web requests.

This helps to avoid being blocked by the target server.
"""

import logging
import time
from functools import wraps
from typing import Callable

class RateLimiter:
    """
    A simple rate limiter.
    """
    def __init__(self, requests_per_minute: int):
        """
        Initializes the RateLimiter.

        Args:
            requests_per_minute: The maximum number of requests allowed per minute.
        """
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive.")
        self.interval = 60.0 / requests_per_minute
        self.last_call_time = 0

    def wait(self):
        """
        Waits if necessary to maintain the desired request rate.
        """
        elapsed_time = time.monotonic() - self.last_call_time
        wait_time = self.interval - elapsed_time
        if wait_time > 0:
            logging.debug(f"Rate limiting: waiting for {wait_time:.2f} seconds.")
            time.sleep(wait_time)
        self.last_call_time = time.monotonic()

def rate_limited(limiter: RateLimiter):
    """
    Decorator to apply rate limiting to a function.

    Args:
        limiter: An instance of the RateLimiter class.
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter.wait()
            return func(*args, **kwargs)
        return wrapper
    return decorator
