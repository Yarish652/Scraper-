"""
This package contains the core scraping logic.

Each module has a single responsibility in the scraping pipeline.

Modules:
- fetcher.py: Fetches the HTML content of a given URL.
- parser.py: Parses the raw HTML.
- extractor.py: Extracts structured data from the parsed HTML.
- validator.py: Validates the extracted data.
- scheduler.py: Manages and coordinates the scraping tasks.
- rate_limiter.py: Controls the rate of outgoing requests.
"""
