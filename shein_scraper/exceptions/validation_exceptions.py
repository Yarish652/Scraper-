"""
Exceptions related to the data validation process.
"""

from . import ScraperException

class ValidationException(ScraperException):
    """Base exception for validation errors."""
    pass

class DataValidationException(ValidationException):
    """
    Raised when extracted data fails Pydantic model validation.
    
    This helps distinguish between a scraping error (e.g., wrong selector)
    and an unexpected data format.
    """
    def __init__(self, model_name: str, errors: str):
        self.model_name = model_name
        self.errors = errors
        super().__init__(f"Validation failed for {model_name}: {errors}")
