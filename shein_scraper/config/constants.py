"""
Global constants for the SHEIN scraper.

This file contains fixed values that are not expected to change at runtime.
"""

from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Directories for logs and outputs
LOGS_DIR = BASE_DIR / "logs"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Base URL for SHEIN US
BASE_URL = "https://us.shein.com"

# Internal API endpoint fragment used to retrieve realtime product detail payloads.
SHEIN_PRODUCT_DETAIL_API_FRAGMENT = "get_goods_detail_realtime_data"
