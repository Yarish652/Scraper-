"""
Exceptions related to the parsing process.
"""

from . import ScraperException

class ParseException(ScraperException):
    """Base exception for parsing errors."""
    pass

class HTMLParseException(ParseException):
    """Raised when HTML content cannot be parsed into a soup object."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Failed to parse HTML: {message}")

class SelectorNotFoundException(ParseException):
    """Raised when a required CSS selector is not found in the HTML."""
    def __init__(self, selector: str):
        self.selector = selector
        super().__init__(f"Selector not found: '{selector}'")
