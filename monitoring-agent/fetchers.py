"""Fetch + parse a target page. Kept dependency-light on purpose."""
import hashlib

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; personal-monitor/1.0)"


def fetch_page(url: str, timeout: int = 15) -> str:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def extract_items(html: str, selector: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [el.get_text(strip=True) for el in soup.select(selector)]


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
