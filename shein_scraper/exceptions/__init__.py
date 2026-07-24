"""
This package defines custom application-specific exceptions.

Using custom exceptions allows for more specific and cleaner error handling
throughout the application, as opposed to relying on generic exceptions.
This makes the code more readable and easier to debug.
"""

class ScraperException(Exception):
    """Base exception class for this application."""
    pass
