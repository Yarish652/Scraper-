# SHEIN Scraper

A browser-assisted SHEIN product scraper that extracts internal SHEIN product JSON payloads using Playwright and maps them into a validated product model.

This repository currently supports:

- `shein_scraper/main.py`: a single-product entrypoint that attaches to a remote Chrome session and extracts one product from the SHEIN product detail API.
- `multi_product_test.py`: a queue-driven multi-product experiment runner that loads seed URLs from `urls.txt`, persists processed URLs to `processed_urls.txt`, discovers additional product and collection links, and generates run reports in `reports/`.

## What works today

- Browser-assisted product extraction via `PlaywrightFetcher`.
- Internal SHEIN product API payload capture over CDP.
- Mapping of the captured JSON into the `Product` model.
- Writing extracted products to JSON output files.
- A stateful queue experiment runner with URL deduplication, collection expansion, recommendation discovery, and retry/backoff delay logic.

## Repository layout

- `shein_scraper/main.py`: single-product scraper entrypoint.
- `multi_product_test.py`: multi-product queue runner for experimentation.
- `shein_scraper/scraper/fetcher.py`: Playwright-based browser fetcher.
- `shein_scraper/scraper/extractor.py`: maps the SHEIN JSON payload into `Product`.
- `shein_scraper/storage/json_writer.py`: writes product data to `outputs/`.
- `shein_scraper/models/product.py`: Pydantic product model.
- `shein_scraper/config/settings.py`: centralized Pydantic settings.
- `shein_scraper/config/constants.py`: fixed project constants and internal endpoint fragments.
- `urls.txt`: seed URLs for the multi-product runner.
- `processed_urls.txt`: persisted list of successfully processed URLs.
- `unsupported_urls.txt`: logs unsupported or malformed URLs.
- `debug/`: raw debug captures, API payloads, anti-bot artifacts.
- `outputs/`: extracted product JSON output files.
- `reports/`: generated reports from `multi_product_test.py` runs.

## Quick start

### 1. Prepare the environment

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r shein_scraper/requirements.txt
```

### 2. Start Chrome with remote debugging

```powershell
& 'C:\Program Files\Google\Chrome\Application\chrome.exe' --remote-debugging-port=9222 --user-data-dir='C:\ChromeDebug'
```

### 3. Single-product run

```bash
python shein_scraper/main.py <product_url>
```

If no URL is passed, `main.py` falls back to `SHEIN_TARGET_URL` environment variable or the first URL configured in `shein_scraper/config/settings.py`.

### 4. Multi-product experiment run

```bash
python multi_product_test.py --max-products 20
```

The runner reads `urls.txt`, skips already processed URLs in `processed_urls.txt`, and logs unsupported URLs to `unsupported_urls.txt`.

## How it works

1. `multi_product_test.py` loads the initial seed URL queue from `urls.txt`.
2. Each URL is normalized and classified as a product or collection URL.
3. Product URLs are fetched by attaching to an existing Chrome remote debugging session and capturing SHEIN's internal `get_goods_detail_realtime_data` API response.
4. The JSON payload is converted into a validated `Product` model.
5. Extracted products are written to `outputs/` and reported in `reports/`.
6. Collection pages and recommendation sections are scanned for new product URLs and enqueued for later processing.
7. The runner uses delay/backoff pacing to reduce anti-bot pressure and avoid rapid re-routing.

## Scaling to 10,000 products

To scale this scraper from experiments to 10,000 products, the key focus is stateful orchestration, parallelism, and anti-bot resilience.

### 1. Persist state and deduplicate aggressively

- Keep a durable source-of-truth for processed URLs and seen URLs.
- Store queued URLs in a database or queue service instead of only text files.
- Partition work across workers by URL shard, product category, or recommendation graph.

### 2. Run many workers safely

- Use a browser pool or multiple remote CDP Chrome instances.
- Keep concurrency low per browser (2-4 concurrent pages) to reduce anti-bot risk.
- Prefer a retry policy with exponential backoff and jitter rather than constant rapid retries.

### 3. Use a distributed job queue

- Move from `urls.txt`/`processed_urls.txt` to a shared queue or database table.
- Mark jobs as claimed and completed so workers can restart without duplicate processing.
- Capture metadata for each run (worker id, attempt count, status, timing).

### 4. Extract data efficiently

- Continue using browser-assisted API capture instead of brittle HTML scraping.
- Persist raw JSON payloads to debug storage only when failures occur.
- Save extracted products in batched files, CSV, or a database.

### 5. Harden anti-bot handling

- Add page-level detection for challenge pages and wait for manual resolution only when needed.
- Rotate user agents and use persistent browser profiles / cookies for session continuity.
- Introduce longer delays after failed attempts and after collection/recommendation navigation.

### 6. Monitor progress and failures

- Generate structured run reports for success/failure counts, queue growth, and error ratios.
- Persist diagnostics for blocked pages, unsupported URL patterns, and payload validation issues.
- Use `debug/` for artifacts but keep production storage separate from normal outputs.

## Next improvements

- Replace text-queue persistence with SQLite/Postgres or an external task queue.
- Add metrics collection and worker health reporting.
- Add retryable error classification for better failure recovery.
- Add explicit collection page discovery that extracts product links cleanly from category pages.
- Add a root-level `README.md` and `.gitignore` if the repository should be formalized further.

## Notes

- The current implementation assumes Chrome is already running with `--remote-debugging-port=9222`.
- `multi_product_test.py` is the primary script for multi-product experiments; `shein_scraper/main.py` is the single-product entrypoint.
- Keep `urls.txt`, `processed_urls.txt`, and `unsupported_urls.txt` under version control only if they are part of the experiment state; these files are the active queue state.
