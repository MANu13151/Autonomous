"""Fetch + parse a target page. Kept dependency-light on purpose."""
import hashlib
import os

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


SENIOR_PATTERNS = [
    " sde ii", " sde-ii", " sde 2", " sde-2", "sde 3", "sde-3", "sde iii", "sde-iii",
    "senior", "sr.", "sr ", "lead", "principal", "staff", "architect", "manager",
    "director", "head of", " ii", " iii", " - ii", " - iii", " 2 ", " 3 ", " 4 ",
    "2+ years", "3+ years", "4+ years", "5+ years", "6+ years"
]


def is_fresher_job(title: str) -> bool:
    t = " " + title.lower().replace(",", " ").replace("-", " ") + " "
    for p in SENIOR_PATTERNS:
        if p in t:
            return False
    return True


def fetch_json_items(target: dict) -> list[str]:
    url = os.path.expandvars(target["url"])
    headers = {"User-Agent": USER_AGENT}
    if "headers" in target:
        for k, v in target["headers"].items():
            headers[k] = os.path.expandvars(str(v))

    timeout = target.get("timeout", 25)
    resp = requests.get(url, timeout=timeout, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    fresher_only = target.get("fresher_only", True)

    extractor = target.get("extractor")
    if extractor == "amazon_jobs":
        items = []
        for j in data.get("jobs", []):
            title = j.get("title", "Unknown Role")
            if fresher_only and not is_fresher_job(title):
                continue
            loc = j.get("location", "Unknown Location")
            date = j.get("posted_date", "")
            job_path = j.get("job_path", "")
            link = f"https://www.amazon.jobs{job_path}" if job_path else ""
            items.append(f"{title} | {loc} | Posted: {date} | Link: {link}")
        return items

    elif extractor == "jsearch":
        items = []
        raw_data = data.get("data", [])
        job_list = raw_data.get("jobs", []) if isinstance(raw_data, dict) else raw_data
        for j in job_list:
            if isinstance(j, dict):
                title = j.get("job_title", "Unknown Role")
                if fresher_only and not is_fresher_job(title):
                    continue
                company = j.get("employer_name", "")
                city = j.get("job_city", "")
                country = j.get("job_country", "")
                loc = f"{city}, {country}".strip(", ")
                link = j.get("job_apply_link", "")
                date = str(j.get("job_posted_at_datetime_utc", ""))[:10]
                items.append(f"{company}: {title} | {loc} | Date: {date} | Apply: {link}")
        return items

    elif "item_key" in target:
        key = target["item_key"]
        return [str(item) for item in data.get(key, [])]

    return []


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

