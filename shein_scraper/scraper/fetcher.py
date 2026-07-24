"""
Responsible for fetching the product data from a SHEIN product page.

This module uses Playwright to open the product page in a real Chromium session and
capture the internal JSON API response that SHEIN returns for the product detail payload.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from config.constants import SHEIN_PRODUCT_DETAIL_API_FRAGMENT
from config.settings import settings

logger = logging.getLogger(__name__)
CHROME_CDP_URL = "http://127.0.0.1:9222"


class PlaywrightFetcher:
    """
    Launches a real Chromium session and captures the JSON payload from the internal
    SHEIN product detail API endpoint.
    """

    def __init__(self, timeout_seconds: int = 30, headless: bool = True) -> None:
        self.timeout_seconds = timeout_seconds
        self.headless = headless

    def fetch(self, url: str) -> dict[str, Any]:
        """
        Connects to the existing Chrome instance via CDP, finds the open SHEIN page,
        attaches response listeners, reloads once, and returns the product-detail JSON.

        Args:
            url: A SHEIN product page URL.

        Returns:
            The parsed product detail JSON dictionary.

        Raises:
            RuntimeError: If the browser-assisted API request fails or times out.
            ValueError: If the response body is not a JSON dictionary.
        """
        logger.info("Starting browser-assisted product fetch for %s", url)

        payload: dict[str, Any] | None = None
        debug_dir = Path("debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_file = debug_dir / "product_api_response.json"

        with sync_playwright() as playwright:
            print("Connected to Chrome")
            browser = playwright.chromium.connect_over_cdp(CHROME_CDP_URL)

            try:
                shein_page = None
                for context in browser.contexts:
                    for page in context.pages:
                        page_url = page.url.lower()
                        if "shein.com" in page_url:
                            shein_page = page
                            break
                    if shein_page is not None:
                        break

                if shein_page is None:
                    raise RuntimeError("Found no existing SHEIN page in the attached Chrome session.")

                print("Found existing SHEIN page")
                print(shein_page.url)

                matching_response: Any | None = None

                def log_response(response: Any) -> None:
                    response_url = response.url.lower()
                    if any(token in response_url for token in ("product", "goods", "detail", "realtime")):
                        print(response.url)
                    if SHEIN_PRODUCT_DETAIL_API_FRAGMENT in response.url:
                        nonlocal matching_response
                        matching_response = response

                shein_page.on("response", log_response)
                print("Network listeners attached")

                print("Reloading page")
                try:
                    shein_page.reload(wait_until="networkidle", timeout=self.timeout_seconds * 1000)
                except Exception as reload_exc:
                    print(f"Reload reached a non-idle state before the timeout: {reload_exc}")

                print("Waiting for product API...")
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if matching_response is not None:
                        break
                    shein_page.wait_for_timeout(250)

                if matching_response is None:
                    print("Product API not observed after reload.")
                    raise RuntimeError("Product API not observed after reload.")

                response = matching_response
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Expected the product detail endpoint to return a JSON object.")

                print("PRODUCT API FOUND")
                logger.info("Captured SHEIN product detail API response for %s", url)
                self._print_response_diagnostics(response, payload)

                with debug_file.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=4, ensure_ascii=False)
                logger.info("Saved raw API response to %s", debug_file)
            except Exception as exc:
                logger.exception("Failed to capture product detail API response from %s", url)
                raise RuntimeError(f"Unable to fetch product details for {url}: {exc}") from exc
            finally:
                browser.close()

        if payload is None:
            raise RuntimeError("No product detail API payload was captured.")

        print("Extraction starting...")
        return payload

    @staticmethod
    def _print_response_diagnostics(response: Any, payload: dict[str, Any]) -> None:
        """
        Prints a compact diagnostic summary of the captured API structure.
        """
        print("==================================================")
        print("Response URL")
        print(response.url)
        print("HTTP Status")
        print(response.status)
        print("Top-level JSON keys")
        print(list(payload.keys()))

        info = payload.get("info") if isinstance(payload.get("info"), dict) else None
        product_info = payload.get("productInfo") if isinstance(payload.get("productInfo"), dict) else None
        price_info = payload.get("priceInfo") if isinstance(payload.get("priceInfo"), dict) else None
        sale_attr = payload.get("saleAttr") if isinstance(payload.get("saleAttr"), dict) else None
        store_info = payload.get("storeInfo") if isinstance(payload.get("storeInfo"), dict) else None
        comment = payload.get("comment") if isinstance(payload.get("comment"), dict) else None

        print("info.keys()")
        print(list(info.keys()) if info is not None else "missing")
        print("productInfo.keys()")
        print(list(product_info.keys()) if product_info is not None else "missing")
        print("priceInfo.keys()")
        print(list(price_info.keys()) if price_info is not None else "missing")
        print("saleAttr.keys()")
        print(list(sale_attr.keys()) if sale_attr is not None else "missing")
        print("storeInfo.keys()")
        print(list(store_info.keys()) if store_info is not None else "missing")
        print("comment.keys()")
        print(list(comment.keys()) if comment is not None else "missing")
        print("==================================================")


class Fetcher(PlaywrightFetcher):
    """
    Backward-compatible fetcher alias that still exposes the original interface.
    """

    pass
