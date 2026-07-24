import argparse
import csv
import json
import logging
import re
import random
import subprocess
import sys
import time
from ctypes import Structure, byref, c_size_t, sizeof, windll
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent
SHEIN_PROJECT_ROOT = PROJECT_ROOT / "shein_scraper"
if str(SHEIN_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(SHEIN_PROJECT_ROOT))

from config.constants import SHEIN_PRODUCT_DETAIL_API_FRAGMENT
from scraper.extractor import ApiProductExtractor

CDP_URL = "http://127.0.0.1:9222"
URLS_FILE = PROJECT_ROOT / "urls.txt"
PROCESSED_URLS_FILE = PROJECT_ROOT / "processed_urls.txt"
UNSUPPORTED_URLS_FILE = PROJECT_ROOT / "unsupported_urls.txt"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DEBUG_DIR = PROJECT_ROOT / "debug"
REPORTS_DIR = PROJECT_ROOT / "reports"

POLL_INTERVAL_SECONDS = 5
NAVIGATION_TIMEOUT_MS = 60_000
API_WAIT_SECONDS = 20
ANTIBOT_WAIT_SECONDS = 5
URL_ROUTING_DELAY_MIN_SECONDS = 2.0
URL_ROUTING_DELAY_MAX_SECONDS = 4.0
URL_ROUTING_BACKOFF_STEP_SECONDS = 1.5
URL_ROUTING_BACKOFF_MAX_SECONDS = 10.0
DEFAULT_MAX_PRODUCTS = 100
COLLECTION_WAIT_SECONDS = 20
RECOMMENDATION_ENQUEUE_LIMIT = 8
PRODUCT_LINK_PATTERN = re.compile(r"-p-\d+", re.IGNORECASE)
COLLECTION_URL_HINTS = ("trend", "landing", "search", "cat", "category", "collection", "browse")
RECOMMENDATION_SECTION_KEYWORDS = (
    "similar products",
    "you may also like",
    "related products",
    "recommended",
    "recommendations",
    "customers also bought",
    "customers also viewed",
    "you might also like",
)

DEBUG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class PROCESS_MEMORY_COUNTERS(Structure):
    _fields_ = [
        ("cb", c_size_t),
        ("PageFaultCount", c_size_t),
        ("PeakWorkingSetSize", c_size_t),
        ("WorkingSetSize", c_size_t),
        ("QuotaPeakPagedPoolUsage", c_size_t),
        ("QuotaPagedPoolUsage", c_size_t),
        ("QuotaPeakNonPagedPoolUsage", c_size_t),
        ("QuotaNonPagedPoolUsage", c_size_t),
        ("PagefileUsage", c_size_t),
        ("PeakPagefileUsage", c_size_t),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reliability experiment runner for SHEIN scraping")
    parser.add_argument("--force", action="store_true", help="Reprocess URLs even if already listed in processed_urls.txt")
    parser.add_argument("--max-products", type=int, default=DEFAULT_MAX_PRODUCTS, help="Number of products to attempt before stopping")
    return parser.parse_args()


def normalize_urls(lines: list[str]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for line in lines:
        url = line.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def load_urls() -> list[str]:
    if not URLS_FILE.exists():
        raise FileNotFoundError(f"Missing queue file: {URLS_FILE}")
    return normalize_urls(URLS_FILE.read_text(encoding="utf-8").splitlines())


def load_processed_urls() -> set[str]:
    if not PROCESSED_URLS_FILE.exists():
        PROCESSED_URLS_FILE.touch()
        return set()
    return set(normalize_urls(PROCESSED_URLS_FILE.read_text(encoding="utf-8").splitlines()))


def load_unsupported_urls() -> set[str]:
    if not UNSUPPORTED_URLS_FILE.exists():
        return set()

    urls: set[str] = set()
    for line in UNSUPPORTED_URLS_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        urls.add(normalize_url(line.split("\t", 1)[0]))
    return urls


def append_processed_url(url: str) -> None:
    with PROCESSED_URLS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{url}\n")


def append_unsupported_url(url: str, reason: str) -> None:
    with UNSUPPORTED_URLS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{url}\t{reason}\n")


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return cleaned or "product"


def normalize_url(value: str, base_url: str | None = None) -> str:
    raw_value = value.strip()
    if not raw_value:
        return ""

    absolute_url = urljoin(base_url or "https://us.shein.com/", raw_value)
    parsed = urlsplit(absolute_url)
    if not parsed.scheme or not parsed.netloc:
        return ""

    normalized = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), fragment="")
    path = normalized.path or "/"
    return urlunsplit((normalized.scheme, normalized.netloc, path, normalized.query, ""))


def is_shein_url(url: str) -> bool:
    return "shein.com" in urlsplit(url).netloc.lower()


def is_product_url(url: str) -> bool:
    return bool(PRODUCT_LINK_PATTERN.search(urlsplit(url).path))


def is_collection_url(url: str) -> bool:
    parsed = urlsplit(url)
    url_text = f"{parsed.path.lower()}?{parsed.query.lower()}"
    return any(token in url_text for token in COLLECTION_URL_HINTS) and not is_product_url(url)


def classify_url(url: str) -> tuple[str, str]:
    normalized_url = normalize_url(url)
    if not normalized_url:
        return "unsupported", "malformed URL"
    if not is_shein_url(normalized_url):
        return "unsupported", "non-SHEIN domain"
    if is_product_url(normalized_url):
        return "product", ""
    if is_collection_url(normalized_url):
        return "collection", ""
    return "unsupported", "unsupported SHEIN URL pattern"


def enqueue_url(queue: deque[str], queued_urls: set[str], seen_urls: set[str], url: str, *, force: bool = False) -> bool:
    normalized_url = normalize_url(url)
    if not normalized_url:
        return False
    if normalized_url in queued_urls or normalized_url in seen_urls:
        return False
    if not force and normalized_url in queued_urls:
        return False
    queue.append(normalized_url)
    queued_urls.add(normalized_url)
    return True


def route_delay_seconds(state: dict[str, Any]) -> float:
    base_delay = random.uniform(URL_ROUTING_DELAY_MIN_SECONDS, URL_ROUTING_DELAY_MAX_SECONDS)
    failure_streak = int(state.get("consecutive_failures", 0))
    if failure_streak <= 0:
        return base_delay
    backoff_delay = min(URL_ROUTING_DELAY_MAX_SECONDS + (failure_streak * URL_ROUTING_BACKOFF_STEP_SECONDS), URL_ROUTING_BACKOFF_MAX_SECONDS)
    return max(base_delay, backoff_delay)


def pause_before_next_url(state: dict[str, Any]) -> None:
    time.sleep(route_delay_seconds(state))


def refresh_queue_from_file(
    queue: deque[str],
    queued_urls: set[str],
    seen_urls: set[str],
    processed_urls: set[str],
    unsupported_urls: set[str],
    force: bool,
) -> int:
    new_items = 0
    for raw_url in load_urls():
        normalized_url = normalize_url(raw_url)
        if not normalized_url:
            continue
        if normalized_url in queued_urls or normalized_url in seen_urls or normalized_url in unsupported_urls:
            continue
        if not force and normalized_url in processed_urls:
            continue
        queue.append(normalized_url)
        queued_urls.add(normalized_url)
        new_items += 1
    return new_items


def format_seconds(value: float | None) -> str:
    return f"{value:.2f}s" if value is not None else "n/a"


def get_python_memory_mb() -> float | None:
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = sizeof(PROCESS_MEMORY_COUNTERS)
        handle = windll.kernel32.GetCurrentProcess()
        if not windll.psapi.GetProcessMemoryInfo(handle, byref(counters), counters.cb):
            return None
        return counters.WorkingSetSize / (1024 * 1024)
    except Exception:
        return None


def get_browser_memory_mb() -> float | None:
    try:
        command = "(Get-Process chrome -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            return None
        output = result.stdout.strip()
        if not output:
            return None
        working_set = float(output)
        return working_set / (1024 * 1024)
    except Exception:
        return None


def find_shein_page(browser: Any) -> Any:
    for context in browser.contexts:
        for page in context.pages:
            if "shein.com" in page.url.lower():
                return page
    raise RuntimeError("No existing SHEIN page was found in the connected browser session.")


def is_antibot_page(page: Any) -> bool:
    current_url = page.url.lower()
    return any(token in current_url for token in ("risk/challenge", "risk/action"))


def is_product_page_loaded(page: Any) -> bool:
    return is_shein_url(page.url) and is_product_url(page.url)


def save_raw_payload(product_number: int, payload: dict[str, Any]) -> Path:
    debug_path = DEBUG_DIR / f"product_{product_number:04d}.json"
    debug_path.write_text(json.dumps(payload, indent=4, ensure_ascii=False), encoding="utf-8")
    return debug_path


def save_product_output(product_number: int, product: Any) -> Path:
    product_id = sanitize_filename(str(product.product_id))
    output_path = OUTPUTS_DIR / f"product_{product_number:04d}_{product_id}.json"
    output_path.write_text(json.dumps(product.model_dump(), indent=4, ensure_ascii=False), encoding="utf-8")
    return output_path


def print_status(state: dict[str, Any]) -> None:
    average_navigation_time = state["total_navigation_time"] / state["processed_products"] if state["processed_products"] else None
    average_api_time = state["total_api_time"] / state["processed_products"] if state["processed_products"] else None
    average_extraction_time = state["total_extraction_time"] / state["processed_products"] if state["processed_products"] else None
    average_total_time = state["total_total_time"] / state["processed_products"] if state["processed_products"] else None

    print("STATUS")
    print(f"Products scraped: {state['products_scraped']}")
    print(f"Collection pages expanded: {state['collection_pages_expanded']}")
    print(f"Unsupported URLs: {state['unsupported_urls_count']}")
    print(f"Failed products: {state['failed_products']}")
    print(f"Queue size: {state['queue_size']}")
    print(f"Remaining URLs: {state['queue_size']}")
    print(f"Current product: {state['current_product']}")
    print(f"Success count: {state['products_scraped']}")
    print(f"Failure count: {state['failed_products']}")
    print(f"Average processing time: {format_seconds(average_total_time)}")
    print(f"Average navigation time: {format_seconds(average_navigation_time)}")
    print(f"Average API capture time: {format_seconds(average_api_time)}")
    print(f"Average extraction time: {format_seconds(average_extraction_time)}")
    print("=" * 60)


def print_resource_snapshot(browser: Any) -> None:
    browser_memory = get_browser_memory_mb()
    python_memory = get_python_memory_mb()
    open_tabs = sum(len(context.pages) for context in browser.contexts)
    browser_contexts = len(browser.contexts)

    print("RESOURCE SNAPSHOT")
    print(f"Browser memory usage: {format_seconds(browser_memory) if browser_memory is None else f'{browser_memory:.2f} MB'}")
    print(f"Python process memory usage: {format_seconds(python_memory) if python_memory is None else f'{python_memory:.2f} MB'}")
    print(f"Number of open tabs: {open_tabs}")
    print(f"Number of browser contexts: {browser_contexts}")
    print("=" * 60)


def save_antibot_artifacts(product_number: int, page: Any) -> tuple[Path, Path]:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = DEBUG_DIR / f"antibot_{product_number:04d}_{timestamp}.png"
    html_path = DEBUG_DIR / f"antibot_{product_number:04d}_{timestamp}.html"
    page.screenshot(path=str(screenshot_path), full_page=True)
    html_path.write_text(page.content(), encoding="utf-8")
    return screenshot_path, html_path


def wait_for_session_recovery(page: Any) -> None:
    while is_antibot_page(page):
        page.wait_for_timeout(ANTIBOT_WAIT_SECONDS * 1000)


def extract_visible_product_links(page: Any) -> list[str]:
    raw_links = page.locator("a[href]").evaluate_all(
        """elements => elements.map((element) => {
            const href = element.href || '';
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            const visible = style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
            return visible ? href : null;
        }).filter(Boolean)"""
    )

    product_links: list[str] = []
    seen_links: set[str] = set()
    for raw_link in raw_links:
        if not isinstance(raw_link, str):
            continue
        normalized_link = normalize_url(raw_link, page.url)
        if not normalized_link or not is_shein_url(normalized_link) or not is_product_url(normalized_link):
            continue
        if normalized_link in seen_links:
            continue
        seen_links.add(normalized_link)
        product_links.append(normalized_link)
    return product_links


def discover_recommendation_urls(page: Any) -> list[str]:
    raw_links = page.evaluate(
        """(keywords) => {
            const isVisible = (element) => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
            };

            const keywordSet = keywords.map((keyword) => keyword.toLowerCase());
            const containers = [];

            for (const element of Array.from(document.querySelectorAll('section,div,aside,main,ul'))) {
                if (!isVisible(element)) {
                    continue;
                }
                const text = (element.innerText || '').toLowerCase();
                if (keywordSet.some((keyword) => text.includes(keyword))) {
                    containers.push(element);
                }
            }

            const candidateLinks = [];
            for (const container of containers) {
                for (const anchor of Array.from(container.querySelectorAll('a[href]'))) {
                    if (!isVisible(anchor)) {
                        continue;
                    }
                    candidateLinks.push(anchor.href || '');
                }
            }

            return Array.from(new Set(candidateLinks.filter(Boolean)));
        }""",
        RECOMMENDATION_SECTION_KEYWORDS,
    )

    recommendation_links: list[str] = []
    seen_links: set[str] = set()
    for raw_link in raw_links:
        if not isinstance(raw_link, str):
            continue
        normalized_link = normalize_url(raw_link, page.url)
        if not normalized_link or not is_shein_url(normalized_link):
            continue
        if normalized_link in seen_links:
            continue
        seen_links.add(normalized_link)
        recommendation_links.append(normalized_link)
    return recommendation_links


def expand_collection_page(page: Any, url: str, product_queue: deque[str], queued_urls: set[str], seen_urls: set[str]) -> list[str]:
    attempts = 0
    while True:
        attempts += 1
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        except Exception as exc:
            if "net::ERR_ABORTED" in str(exc) and attempts < 2:
                page.wait_for_timeout(1000)
                continue
            raise
        deadline = time.monotonic() + COLLECTION_WAIT_SECONDS
        discovered_links: list[str] = []

        while time.monotonic() < deadline:
            if is_antibot_page(page):
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                screenshot_path, html_path = save_antibot_artifacts(0, page)
                print("ANTI-BOT DETECTED")
                print("Waiting for manual intervention...")
                print(f"Product number: collection:{url}")
                print(f"Current URL: {page.url}")
                print(f"Timestamp: {timestamp}")
                print(f"Screenshot: {screenshot_path}")
                print(f"HTML: {html_path}")
                wait_for_session_recovery(page)
                break

            discovered_links = extract_visible_product_links(page)
            if discovered_links:
                break
            page.wait_for_timeout(500)

        if discovered_links or not is_antibot_page(page):
            new_links: list[str] = []
            for link in discovered_links:
                if link in queued_urls or link in seen_urls:
                    continue
                product_queue.append(link)
                queued_urls.add(link)
                new_links.append(link)
            return new_links


def record_unsupported_url(url: str, reason: str, state: dict[str, Any], seen_urls: set[str]) -> None:
    append_unsupported_url(url, reason)
    state["unsupported_urls_count"] += 1
    state["seen_unsupported_urls"].add(url)
    seen_urls.add(url)
    print("UNSUPPORTED URL")
    print(url)
    print(f"Reason: {reason}")


def capture_product_payload(page: Any, url: str) -> tuple[dict[str, Any], float]:
    attempts = 0
    while True:
        attempts += 1
        matching_response: Any | None = None

        def on_response(response: Any) -> None:
            nonlocal matching_response
            if SHEIN_PRODUCT_DETAIL_API_FRAGMENT in response.url:
                matching_response = response

        page.on("response", on_response)
        capture_started = time.perf_counter()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)

            deadline = time.monotonic() + API_WAIT_SECONDS
            while time.monotonic() < deadline:
                if matching_response is not None:
                    payload = matching_response.json()
                    if not isinstance(payload, dict):
                        raise ValueError("Expected the product API response to be a JSON object.")
                    return payload, time.perf_counter() - capture_started

                if is_antibot_page(page):
                    raise RuntimeError("ANTI-BOT")

                page.wait_for_timeout(250)

            raise RuntimeError("Product API was not observed before the timeout.")
        except Exception as exc:
            if "net::ERR_ABORTED" in str(exc) and attempts < 2:
                page.wait_for_timeout(1000)
                continue
            if str(exc) == "ANTI-BOT":
                raise
            raise
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass


def write_reports(report_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    report_json_path = REPORTS_DIR / "run_report.json"
    report_csv_path = REPORTS_DIR / "run_report.csv"
    report_md_path = REPORTS_DIR / "run_report.md"

    payload = {
        "summary": summary,
        "products": report_rows,
    }
    report_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    fieldnames = [
        "Product #",
        "URL",
        "Status",
        "Product ID",
        "Navigation Time",
        "API Time",
        "Extraction Time",
        "Total Time",
        "API Captured",
        "Extraction Started",
        "Product Validated",
        "JSON Saved",
        "Validation Failed",
        "Failure Reason",
    ]
    with report_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report_rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    lines = ["# SHEIN Reliability Run Report", ""]
    lines.append("## Summary")
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Results")
    lines.append("| Product # | Status | Product ID | Navigation Time | API Time | Extraction Time | Total Time | Failure Reason |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in report_rows:
        lines.append(
            f"| {row.get('Product #', '')} | {row.get('Status', '')} | {row.get('Product ID', '')} | {row.get('Navigation Time', '')} | {row.get('API Time', '')} | {row.get('Extraction Time', '')} | {row.get('Total Time', '')} | {row.get('Failure Reason', '')} |"
        )
    report_md_path.write_text("\n".join(lines), encoding="utf-8")


def get_pending_urls(urls: list[str], processed_urls: set[str], attempted_urls: set[str], force: bool) -> list[str]:
    pending_urls: list[str] = []
    for url in urls:
        if url in attempted_urls:
            continue
        if not force and url in processed_urls:
            continue
        pending_urls.append(url)
    return pending_urls


def process_url(page: Any, product_number: int, url: str, state: dict[str, Any]) -> dict[str, Any]:
    report_row: dict[str, Any] = {
        "Product #": product_number,
        "URL": url,
        "Status": "FAILED",
        "Product ID": "",
        "Navigation Time": "",
        "API Time": "",
        "Extraction Time": "",
        "Total Time": "",
        "API Captured": False,
        "Extraction Started": False,
        "Product Validated": False,
        "JSON Saved": False,
        "Validation Failed": False,
        "Failure Reason": "",
    }

    state["current_product"] = url
    current_start = time.perf_counter()
    navigation_start = time.perf_counter()
    current_title = "n/a"

    try:
        api_payload, api_time = capture_product_payload(page, url)
        navigation_end = time.perf_counter()
        report_row["Navigation Time"] = f"{navigation_end - navigation_start:.2f}s"
        report_row["API Time"] = f"{api_time:.2f}s"
        report_row["API Captured"] = True

        extraction_start = time.perf_counter()
        report_row["Extraction Started"] = True
        product = ApiProductExtractor.extract(api_payload, product_url=url)
        extraction_end = time.perf_counter()
        extraction_time = extraction_end - extraction_start
        report_row["Extraction Time"] = f"{extraction_time:.2f}s"

        if product is None:
            report_row["Validation Failed"] = True
            raise RuntimeError("Product validation failed")

        report_row["Product Validated"] = True
        report_row["Product ID"] = str(product.product_id)

        output_path = save_product_output(product_number, product)
        report_row["JSON Saved"] = True
        report_row["Status"] = "SUCCESS"
        report_row["Failure Reason"] = ""

        total_time = time.perf_counter() - current_start
        report_row["Total Time"] = f"{total_time:.2f}s"

        state["products_scraped"] += 1
        state["processed_products"] += 1
        state["total_navigation_time"] += navigation_end - navigation_start
        state["total_api_time"] += api_time
        state["total_extraction_time"] += extraction_time
        state["total_total_time"] += total_time
        state["longest_api_wait"] = max(state["longest_api_wait"], api_time)
        state["consecutive_failures"] = 0

        resolved_url = page.url
        current_title = page.title()
        print(f"Current URL: {resolved_url}")
        print(f"Current page title: {current_title}")
        print("✓ Product ID")
        print(product.product_id)
        print("✓ Title")
        print(product.name)
        print("✓ Price")
        print(product.price)
        print("✓ Processing Time")
        print(f"{total_time:.2f}s")
        print(f"✓ JSON saved: {output_path}")
        return report_row
    except RuntimeError as exc:
        try:
            current_title = page.title()
        except Exception:
            current_title = "n/a"
        resolved_url = url

        if str(exc) == "ANTI-BOT" or is_antibot_page(page):
            state["anti_bot_events"] += 1
            state["consecutive_failures"] += 1
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            screenshot_path, html_path = save_antibot_artifacts(product_number, page)
            print("ANTI-BOT DETECTED")
            print("Waiting for manual intervention...")
            print(f"Product number: {product_number}")
            print(f"Current URL: {resolved_url}")
            print(f"Timestamp: {timestamp}")
            print(f"Screenshot: {screenshot_path}")
            print(f"HTML: {html_path}")
            wait_for_session_recovery(page)
            print("Session recovered. Continuing.")
            return process_url(page, product_number, url, state)

        navigation_end = time.perf_counter()
        report_row["Navigation Time"] = f"{navigation_end - navigation_start:.2f}s"
        report_row["API Time"] = report_row["API Time"] or "n/a"
        report_row["Extraction Time"] = report_row["Extraction Time"] or "n/a"
        report_row["Total Time"] = f"{time.perf_counter() - current_start:.2f}s"
        report_row["Failure Reason"] = str(exc)

        state["failed_products"] += 1
        state["processed_products"] += 1
        state["total_navigation_time"] += navigation_end - navigation_start
        state["consecutive_failures"] += 1

        print(f"Current URL: {resolved_url}")
        print(f"Current page title: {current_title}")
        print("✗ EXTRACTION FAILED")
        print(f"Reason: {exc}")
        logging.exception("Failed product #%s (%s)", product_number, url)
        return report_row
    except Exception as exc:
        navigation_end = time.perf_counter()
        try:
            current_title = page.title()
        except Exception:
            current_title = "n/a"
        resolved_url = url

        report_row["Navigation Time"] = f"{navigation_end - navigation_start:.2f}s"
        report_row["API Time"] = report_row["API Time"] or "n/a"
        report_row["Extraction Time"] = report_row["Extraction Time"] or "n/a"
        report_row["Total Time"] = f"{time.perf_counter() - current_start:.2f}s"
        report_row["Failure Reason"] = str(exc)

        state["failed_products"] += 1
        state["processed_products"] += 1
        state["total_navigation_time"] += navigation_end - navigation_start
        state["consecutive_failures"] += 1

        print(f"Current URL: {resolved_url}")
        print(f"Current page title: {current_title}")
        print("✗ EXTRACTION FAILED")
        print(f"Reason: {exc}")
        logging.exception("Failed product #%s (%s)", product_number, url)
        return report_row


def process_collection_url(page: Any, url: str, queue: deque[str], queued_urls: set[str], seen_urls: set[str], state: dict[str, Any]) -> list[str]:
    discovered_links = expand_collection_page(page, url, queue, queued_urls, seen_urls)
    state["collection_pages_expanded"] += 1
    state["processed_collections"] += 1
    print(f"Collection page expanded: {url}")
    print(f"Discovered product links: {len(discovered_links)}")
    return discovered_links


def build_summary(state: dict[str, Any], report_rows: list[dict[str, Any]], browser_restarts: int) -> dict[str, Any]:
    products_attempted = state["processed_products"]
    products_successful = state["products_scraped"]
    products_failed = state["failed_products"]
    success_rate = (products_successful / products_attempted * 100.0) if products_attempted else 0.0
    average_navigation_time = (state["total_navigation_time"] / products_attempted) if products_attempted else 0.0
    average_api_time = (state["total_api_time"] / products_attempted) if products_attempted else 0.0
    average_extraction_time = (state["total_extraction_time"] / products_attempted) if products_attempted else 0.0
    average_total_time = (state["total_total_time"] / products_attempted) if products_attempted else 0.0

    successful_rows = [row for row in report_rows if row.get("Status") == "SUCCESS" and row.get("Total Time") not in ("", "n/a")]
    fastest_product = min(successful_rows, key=lambda row: float(row["Total Time"].rstrip("s")), default=None)
    slowest_product = max(successful_rows, key=lambda row: float(row["Total Time"].rstrip("s")), default=None)
    longest_api_wait = max((float(row["API Time"].rstrip("s")) for row in report_rows if row["API Time"] not in ("", "n/a")), default=0.0)

    summary = {
        "Products Attempted": products_attempted,
        "Products Scraped": products_successful,
        "Products Successful": products_successful,
        "Products Failed": products_failed,
        "Success Rate": f"{success_rate:.2f}%",
        "Average Navigation Time": f"{average_navigation_time:.2f}s",
        "Average API Capture Time": f"{average_api_time:.2f}s",
        "Average Extraction Time": f"{average_extraction_time:.2f}s",
        "Fastest Product": fastest_product["Product #"] if fastest_product else "n/a",
        "Slowest Product": slowest_product["Product #"] if slowest_product else "n/a",
        "Longest API Wait": f"{longest_api_wait:.2f}s",
        "Average Total Time": f"{average_total_time:.2f}s",
        "Anti-bot Events": state["anti_bot_events"],
        "Browser Restarts": browser_restarts,
        "Collection Pages Expanded": state["collection_pages_expanded"],
        "Unsupported URLs": state["unsupported_urls_count"],
        "Failed Products": products_failed,
        "Queue Size": state["queue_size"],
        "Remaining URLs": state["queue_size"],
        "Recommendation": "RECOMMEND INVESTIGATION" if success_rate < 95.0 else "SCRAPER PASSED RELIABILITY TEST",
    }
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    print("\n========================================")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print("========================================")


def main() -> None:
    args = parse_args()
    processed_urls = load_processed_urls()
    unsupported_urls = load_unsupported_urls()
    seen_urls: set[str] = set(unsupported_urls) if args.force else set(processed_urls) | set(unsupported_urls)
    attempted_urls: set[str] = set()
    queue: deque[str] = deque()
    queued_urls: set[str] = set()

    state: dict[str, Any] = {
        "current_product": "-",
        "queue_size": 0,
        "products_scraped": 0,
        "failed_products": 0,
        "collection_pages_expanded": 0,
        "processed_collections": 0,
        "unsupported_urls_count": 0,
        "processed_products": 0,
        "total_navigation_time": 0.0,
        "total_api_time": 0.0,
        "total_extraction_time": 0.0,
        "total_total_time": 0.0,
        "anti_bot_events": 0,
        "consecutive_failures": 0,
        "seen_unsupported_urls": set(unsupported_urls),
        "longest_api_wait": 0.0,
    }
    browser_restarts = 0
    report_rows: list[dict[str, Any]] = []

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    if args.force:
        print("Force mode enabled.")

    refresh_queue_from_file(queue, queued_urls, seen_urls, set() if args.force else processed_urls, unsupported_urls, args.force)

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(CDP_URL)
        page = find_shein_page(browser)

        print("Connected to existing Chrome session")
        print("Reusing the existing authenticated SHEIN page")

        try:
            while queue and state["products_scraped"] < args.max_products:
                refresh_queue_from_file(queue, queued_urls, seen_urls, set() if args.force else processed_urls, unsupported_urls, args.force)
                state["queue_size"] = len(queue)
                print_status(state)

                if state["processed_products"] and state["processed_products"] % 10 == 0:
                    print_resource_snapshot(browser)

                if not queue:
                    continue

                url = queue.popleft()
                queued_urls.discard(url)
                state["queue_size"] = len(queue)

                seen_urls.add(url)

                url_type, reason = classify_url(url)

                if url_type == "unsupported":
                    record_unsupported_url(url, reason, state, seen_urls)
                    write_reports(report_rows, build_summary(state, report_rows, browser_restarts))
                    pause_before_next_url(state)
                    continue

                if url_type == "collection":
                    try:
                        discovered_links = process_collection_url(page, url, queue, queued_urls, seen_urls, state)
                        print(f"Queue size after expansion: {len(queue)}")
                        print(f"Remaining URLs: {len(queue)}")
                        append_processed_url(url)
                        processed_urls.add(url)
                    except Exception as exc:
                        state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
                        logging.exception("Failed to expand collection page %s", url)
                        print(f"Collection expansion failed: {exc}")
                    finally:
                        write_reports(report_rows, build_summary(state, report_rows, browser_restarts))
                        pause_before_next_url(state)
                    continue

                product_number = len(report_rows) + 1
                state["current_product"] = url
                row = process_url(page, product_number, url, state)
                report_rows.append(row)

                if row["Status"] == "SUCCESS":
                    append_processed_url(url)
                    processed_urls.add(url)

                    discovered_recommendations = discover_recommendation_urls(page)
                    for discovered_url in discovered_recommendations[:RECOMMENDATION_ENQUEUE_LIMIT]:
                        discovered_type, discovered_reason = classify_url(discovered_url)
                        if discovered_type == "unsupported":
                            if discovered_url not in seen_urls:
                                record_unsupported_url(discovered_url, discovered_reason, state, seen_urls)
                            continue
                        if discovered_url in seen_urls or discovered_url in queued_urls:
                            continue
                        enqueue_url(queue, queued_urls, seen_urls, discovered_url)

                write_reports(report_rows, build_summary(state, report_rows, browser_restarts))
                pause_before_next_url(state)
        finally:
            summary = build_summary(state, report_rows, browser_restarts)
            write_reports(report_rows, summary)
            print_summary(summary)
            browser.close()


if __name__ == "__main__":
    main()
