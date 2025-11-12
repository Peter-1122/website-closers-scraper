import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

def _text(el) -> str:
    return el.get_text(strip=True) if el else ""

def _first_attr(el, name: str) -> Optional[str]:
    if not el:
        return None
    return el.get(name)

def _find_money_in_text(text: str) -> Optional[str]:
    """
    Heuristics to find money-like tokens in a string: $1,234,567.89
    """
    m = re.search(r"\$?\s*[0-9][\d,]*(?:\.\d{1,2})?", text.replace("\xa0", " "))
    return m.group(0) if m else None

def parse_listings_page(html: str, base_url: str) -> Tuple[List[Dict], Optional[str]]:
    """
    Parse a WebsiteClosers listings/index page to extract card data and pagination.
    Returns (items, next_page_url).
    Each item minimally contains a 'detailUrl'; other fields are best-effort.
    """
    soup = BeautifulSoup(html, "lxml")

    items: List[Dict] = []

    # Attempt 1: Generic card selector used by many themes
    cards = soup.select("article, div.card, div.listing, div.loop-item, li")
    if not cards:
        # Fallback to common containers
        cards = soup.find_all(["article", "div", "li"])

    for el in cards:
        # Try to find a link to detail page
        a = el.find("a", href=True)
        href = a["href"] if a else None
        if not href:
            # Skip elements without links
            continue

        detail_url = urljoin(base_url, href)

        title = _text(el.find(["h2", "h3", "h4"])) or _text(a)
        # Short description often stored in p/summary fields
        description = _text(el.find("p"))

        # Attempt to capture asking price and cash flow within the card
        text_blob = el.get_text(" ", strip=True)
        asking = None
        cashflow = None
        status = None

        # Look for keywords near numbers
        ask_match = re.search(r"(asking[\s:]*|price[\s:]*)(\$?\s*[\d,]+(?:\.\d{1,2})?)", text_blob, flags=re.I)
        cf_match = re.search(r"(cash\s*flow[\s:]*)(\$?\s*[\d,]+(?:\.\d{1,2})?)", text_blob, flags=re.I)
        status_match = re.search(r"(status|availability)[:\s]*([A-Za-z]+)", text_blob, flags=re.I)

        if ask_match:
            asking = ask_match.group(2)
        else:
            asking = _find_money_in_text(text_blob)

        if cf_match:
            cashflow = cf_match.group(2)

        if status_match:
            status = status_match.group(2)

        img = el.find("img")
        img_url = _first_attr(img, "data-src") or _first_attr(img, "src")

        item = {
            "detailUrl": detail_url,
            "title": title or None,
            "description": description or None,
            "askingPrice": asking,
            "cashFlow": cashflow,
            "status": status,
            "imageUrl": urljoin(base_url, img_url) if img_url else None,
        }
        # Avoid duplicates if the page has nested elements
        if item["detailUrl"] and item["detailUrl"] not in {it["detailUrl"] for it in items}:
            items.append(item)

    # Pagination: look for "Next" rel or text
    next_link = soup.find("a", attrs={"rel": "next"}) or soup.find("a", string=re.compile(r"next", re.I))
    next_url = urljoin(base_url, next_link["href"]) if next_link and next_link.has_attr("href") else None

    return items, next_url