"""
Utilities for timing code execution.

Provides a simple context manager to measure and log the execution time
of a block of code.
"""

import logging
import time
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

@contextmanager
def time_block(label: str) -> Generator[None, None, None]:
    """
    A context manager to log the execution time of a code block.

    Args:
        label: A description of the code block being timed.
    
    Example:
        with time_block("Data processing"):
            process_data()
    """
    start_time = time.monotonic()
    try:
        yield
    finally:
        end_time = time.monotonic()
        duration = end_time - start_time
        logger.info("%s took %.4f seconds", label, duration)
