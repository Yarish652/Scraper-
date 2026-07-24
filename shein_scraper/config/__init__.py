"""
This package contains all application configuration.

By centralizing configuration, we can easily manage different environments
(development, testing, production) and settings.

Modules:
- settings: Main Pydantic-based settings management.
- logging_config: Configuration for the logging system.
- headers: Manages HTTP headers for requests.
- rate_limits: Defines the rate limiting settings.
"""
from .settings import settings

__all__ = ["settings"]
