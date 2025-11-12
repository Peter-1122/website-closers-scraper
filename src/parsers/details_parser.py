import re
from typing import Optional

from bs4 import BeautifulSoup

from clients.http_client import HttpClient
from .listings_parser import _text  # reuse helper

def _money_to_float_str(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    # Extract first money-like number
    m = re.search(r"\$?\s*[0-9][\d,]*(?:\.\d{1,2})?", text.replace("\xa0", " "))
    return m.group(0) if m else None

def _extract_year(text: str) -> Optional[int]:
    # Find a plausible year between 1900 and 2100
    m = re.search(r"\b(19\d{2}|20\d{2}|2100)\b", text)
    if not m:
        return None
    try:
        year = int(m.group(1))
        if 1900 <= year <= 2100:
            return year
    except ValueError:
        return None
    return None

def enrich_with_details(http: HttpClient, listing) -> None:
    """
    Fetch listing.detailUrl and extract:
      - fullDescription (long text)
      - grossIncome (if present)
      - yearEstablished (if present)
      The function mutates the listing dataclass.
    """
    if not getattr(listing, "detailUrl", None):
        return

    html = http.get_text(listing.detailUrl)
    soup = BeautifulSoup(html, "lxml")

    # Strategy:
    # 1) The full description often lives in a content div or article
    # 2) Financial metrics may appear in labeled rows/definition lists/tables

    # Full description
    content = soup.select_one("article") or soup.select_one("div.entry-content") or soup.select_one("section")
    if not content:
        # Fallback to the largest text container
        candidates = sorted(soup.find_all(["div", "section", "article"], recursive=True),
                            key=lambda x: len(x.get_text(strip=True)), reverse=True)
        content = candidates[0] if candidates else None
    full_desc = None
    if content:
        # Remove scripts/styles
        for bad in content.find_all(["script", "style"]):
            bad.decompose()
        # Compress whitespace but preserve line breaks roughly
        full_desc = re.sub(r"\n{3,}", "\n\n", content.get_text("\n", strip=True))

    # Financials scanning
    page_text = soup.get_text("\n", strip=True)

    # Gross Income
    gi = None
    for label in [r"gross\s*income", r"revenue", r"sales"]:
        m = re.search(label + r"[^$]*?(\$?\s*[\d,]+(?:\.\d{1,2})?)", page_text, flags=re.I)
        if m:
            gi = _money_to_float_str(m.group(1))
            break

    # Year Established
    ye = None
    for label in [r"year\s*established", r"founded", r"established"]:
        m = re.search(label + r".{0,40}?(\b(19\d{2}|20\d{2}|2100)\b)", page_text, flags=re.I)
        if m:
            ye = m.group(1)
            break
    if not ye:
        ye = _extract_year(page_text)

    # Set on listing (runner will convert numbers)
    listing.fullDescription = full_desc or None
    listing.grossIncome = None
    listing.yearEstablished = None

    if gi:
        # runner converts commas; here keep raw money-like string
        listing.grossIncome = float(re.sub(r"[^\d.]", "", gi.replace(",", ""))) if gi else None

    if ye:
        try:
            listing.yearEstablished = int(ye)
        except Exception:
            listing.yearEstablished = None