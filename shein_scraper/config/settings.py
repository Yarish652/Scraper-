"""
Centralized configuration settings for the SHEIN scraper.

This module uses Pydantic's BaseSettings to manage configuration, allowing
for validation and loading from environment variables or a .env file. It's
the single source of truth for all configurable parameters.
"""

from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

# Define the root directory of the project
# This assumes the script is in shein_scraper/config
ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT_DIR / "outputs"
LOGS_DIR = ROOT_DIR / "logs"
CACHE_DIR = ROOT_DIR / "cache"


class ScraperSettings(BaseModel):
    """Settings specific to the scraping process."""
    request_timeout: int = Field(15, description="Timeout for HTTP requests in seconds.")
    max_retries: int = Field(3, description="Maximum number of retries for a failed request.")
    retry_delay: int = Field(5, description="Delay between retries in seconds.")
    max_concurrent_requests: int = Field(5, description="Maximum number of concurrent requests for async fetching.")


class StorageSettings(BaseModel):
    """Settings for data storage."""
    storage_type: Literal["json", "csv", "sqlite"] = Field("json", description="The type of storage to use.")
    output_filename: str = Field("scraped_products", description="Base filename for output files (without extension).")
    sqlite_db_name: str = Field("shein_scraper.db", description="Name of the SQLite database file.")


class Settings(BaseSettings):
    """
    Main application settings class.
    
    It aggregates all other settings classes and provides global configurations.
    """
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Project metadata
    project_name: str = "SHEIN Scraper"
    base_url: HttpUrl = "https://us.shein.com"

    # Logging level
    log_level: str = Field("INFO", description="Logging level (e.g., DEBUG, INFO, WARNING).")
    
    # Target URLs to scrape
    target_urls: List[HttpUrl] = Field(
        default_factory=lambda: [
            "https://us.shein.com/some-product-url-1",
            "https://us.shein.com/some-product-url-2",
        ],
        description="A list of initial URLs to scrape."
    )

    # Sub-settings
    scraper: ScraperSettings = ScraperSettings()
    storage: StorageSettings = StorageSettings()

    # Feature flags
    enable_caching: bool = Field(True, description="Enable caching of fetched HTML pages.")
    enable_metrics: bool = Field(True, description="Enable tracking of scraping metrics.")


# Instantiate settings to be used throughout the application
settings = Settings()

# Create necessary directories on import
OUTPUTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
(CACHE_DIR / "html").mkdir(parents=True, exist_ok=True)
(CACHE_DIR / "json").mkdir(parents=True, exist_ok=True)
