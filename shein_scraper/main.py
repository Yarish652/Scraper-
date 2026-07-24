"""
Main entry point for the SHEIN scraper application.

This script now follows the browser-assisted API flow for a single product.
"""

import json
import logging
import os
import sys
from pathlib import Path

from config.logging_config import setup_logging
from config.settings import settings
from scraper.extractor import ApiProductExtractor
from scraper.fetcher import PlaywrightFetcher
from storage.json_writer import JsonWriter


def main() -> None:
    """
    Runs a single, browser-assisted product scrape and saves the result to JSON.
    """
    setup_logging(log_level=settings.log_level)
    logging.info("Starting SHEIN scraper.")

    target_url = os.environ.get("SHEIN_TARGET_URL") or (sys.argv[1] if len(sys.argv) > 1 else str(settings.target_urls[0]))
    print("====================================")
    print("Target URL")
    print(target_url)
    print("====================================")

    fetcher = PlaywrightFetcher(timeout_seconds=settings.scraper.request_timeout)
    api_payload = fetcher.fetch(target_url)

    product = ApiProductExtractor.extract(api_payload, product_url=target_url)
    if product is None:
        raise RuntimeError("Failed to convert the SHEIN API payload into a valid Product model.")

    print("Product(")
    print(f"    product_id={product.product_id}")
    print(f"    title={product.name}")
    print(f"    sale_price={product.price}")
    print(f"    retail_price={product.retail_price}")
    print(f"    stock={product.stock}")
    print(f"    images={product.images}")
    print(f"    sizes={product.sizes}")
    print(")")

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "product.json").open("w", encoding="utf-8") as handle:
        json.dump(product.model_dump(), handle, indent=4, ensure_ascii=False)

    writer = JsonWriter(filename=settings.storage.output_filename)
    writer.write(product)
    writer.save()

    print("====================================")
    print("✓ Browser launched")
    print("✓ Product page opened")
    print("✓ API response captured")
    print("✓ Raw JSON saved")
    print("✓ Product extracted")
    print("✓ Product JSON saved")
    print("====================================")

    logging.info("SHEIN scraper finished.")


if __name__ == "__main__":
    Path("logs").mkdir(exist_ok=True)
    Path("outputs").mkdir(exist_ok=True)
    Path("debug").mkdir(exist_ok=True)
    main()
