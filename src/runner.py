import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make sibling folders importable without needing a package
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.append(str(CURRENT_DIR))

from clients.http_client import HttpClient  # noqa: E402
from outputs.json_exporter import JsonExporter  # noqa: E402
from parsers.listings_parser import parse_listings_page  # noqa: E402
from parsers.details_parser import enrich_with_details  # noqa: E402

@dataclass
class Listing:
    detailUrl: str
    title: Optional[str] = None
    description: Optional[str] = None
    askingPrice: Optional[float] = None
    cashFlow: Optional[float] = None
    status: Optional[str] = None
    imageUrl: Optional[str] = None
    fullDescription: Optional[str] = None
    grossIncome: Optional[float] = None
    yearEstablished: Optional[int] = None

def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def to_number(maybe_money: Optional[str]) -> Optional[float]:
    if not maybe_money:
        return None
    s = str(maybe_money)
    # Keep digits, dot, and comma; remove other tokens
    s = re.sub(r"[^\d,.\-]", "", s)
    # Handle comma as thousand sep (heuristic): if both comma and dot, drop commas
    if "," in s and "." in s:
        s = s.replace(",", "")
    else:
        # If only commas, treat as thousand separators
        s = s.replace(",", "")
    try:
        return float(s) if s not in ("", "-", "--") else None
    except ValueError:
        return None

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape WebsiteClosers listings into JSON."
    )
    parser.add_argument(
        "--inputs",
        default=str(CURRENT_DIR.parent / "data" / "inputs.sample.json"),
        help="Path to inputs JSON file.",
    )
    parser.add_argument(
        "--settings",
        default=str(CURRENT_DIR / "config" / "settings.example.json"),
        help="Path to settings JSON file.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    inputs_path = Path(args.inputs)
    settings_path = Path(args.settings)

    if not inputs_path.exists():
        logging.error("Inputs file not found: %s", inputs_path)
        sys.exit(2)
    if not settings_path.exists():
        logging.error("Settings file not found: %s", settings_path)
        sys.exit(2)

    inputs = load_json(inputs_path)
    settings = load_json(settings_path)

    base_url = settings.get("baseUrl", "https://www.websiteclosers.com")
    list_path = inputs.get("startPath") or settings.get("defaultStartPath", "/businesses-for-sale")
    start_url = inputs.get("startUrl") or f"{base_url.rstrip('/')}/{list_path.lstrip('/')}"
    max_pages = int(inputs.get("maxPages", settings.get("maxPagesDefault", 3)))
    delay = float(inputs.get("delaySeconds", settings.get("delaySecondsDefault", 1.5)))
    output_file = inputs.get("outputFile", "data/website-closers-listings.json")
    user_agent = settings.get("userAgent")
    proxies = inputs.get("proxies")  # e.g., {"http": "http://user:pass@host:port", "https": "http://user:pass@host:port"}

    http = HttpClient(user_agent=user_agent, proxies=proxies, timeout_seconds=30)
    exporter = JsonExporter(Path(output_file))

    all_items: List[Dict[str, Any]] = []
    next_url: Optional[str] = start_url

    for page_index in range(1, max_pages + 1):
        if not next_url:
            logging.info("No further pagination URL. Stopping at page %d.", page_index - 1)
            break

        logging.info("Fetching page %d: %s", page_index, next_url)
        html = http.get_text(next_url)

        items, pagination_next = parse_listings_page(html, base_url=base_url)
        logging.info("Parsed %d listing cards.", len(items))

        for item in items:
            listing = Listing(
                detailUrl=item.get("detailUrl"),
                title=item.get("title"),
                description=item.get("description"),
                askingPrice=to_number(item.get("askingPrice")),
                cashFlow=to_number(item.get("cashFlow")),
                status=item.get("status"),
                imageUrl=item.get("imageUrl"),
            )

            if listing.detailUrl:
                try:
                    enrich_with_details(http, listing)
                except Exception as e:
                    logging.warning("Detail enrichment failed for %s: %s", listing.detailUrl, e)

            all_items.append(asdict(listing))

            # Politeness delay between detail fetches
            time.sleep(max(0.2, delay / 5.0))

        if pagination_next:
            next_url = pagination_next
            logging.info("Next page detected: %s", next_url)
            time.sleep(delay)
        else:
            logging.info("No next page link found. Stopping.")
            break

    exporter.write(all_items)
    logging.info("Exported %d records to %s", len(all_items), output_file)

if __name__ == "__main__":
    main()