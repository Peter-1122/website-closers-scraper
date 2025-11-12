import logging
from typing import Optional, Dict

import requests

class HttpClient:
    """
    Thin wrapper around requests with default headers, timeouts, and basic error handling.
    """

    def __init__(
        self,
        user_agent: Optional[str] = None,
        proxies: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 30,
    ):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.7",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Connection": "keep-alive",
                "User-Agent": user_agent
                or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
        )
        if proxies:
            self.session.proxies.update(proxies)
        self.timeout_seconds = timeout_seconds

    def get_text(self, url: str) -> str:
        try:
            resp = self.session.get(url, timeout=self.timeout_seconds)
            resp.raise_for_status()
            # Requests auto-detects encoding; fall back if missing
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        except requests.RequestException as e:
            logging.error("HTTP GET failed for %s: %s", url, e)
            raise