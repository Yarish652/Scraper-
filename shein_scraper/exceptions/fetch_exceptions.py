"""
Exceptions related to the fetching process.
"""

from . import ScraperException

class FetchException(ScraperException):
    """Base exception for fetching errors."""
    pass

class RequestException(FetchException):
    """Raised when an HTTP request fails after all retries."""
    def __init__(self, url: str, message: str):
        self.url = url
        self.message = message
        super().__init__(f"Failed to fetch {url}: {message}")

class ThrottledException(FetchException):
    """Raised when the scraper is being throttled or blocked."""
    def __init__(self, url: str, status_code: int):
        self.url = url
        self.status_code = status_code
        super().__init__(f"Request for {url} was throttled with status {status_code}.")
