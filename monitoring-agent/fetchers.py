"""Fetch + parse a target page with strict multi-layer filtering.

Guarantees:
1. NO jobs requiring 3+ years or ranges like 4-12 years of experience.
2. NO jobs requiring Green Card, US Citizenship, Security Clearance, or local native residency outside India.
3. NO Data Analyst / Business Analyst roles.
4. Abroad jobs MUST be Remote or provide international visa sponsorship.
"""
import hashlib
import os
import re
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; personal-monitor/1.0)"

# ── 1. RESUME CORE SKILLS (Used to verify profile relevance) ───────────────
RESUME_SKILLS = {
    # Core languages
    "python", "sql", "swift", "javascript", "js",
    # AI/ML & GenAI
    "machine learning", "ml", "deep learning", "ai", "artificial intelligence",
    "genai", "generative ai", "llm", "large language model",
    "rag", "retrieval augmented generation",
    "nlp", "natural language processing",
    "reinforcement learning", "rl",
    "transformers", "huggingface", "langchain", "langsmith", "langgraph",
    "groq", "llama", "openai", "gpt",
    "fine-tuning", "finetuning", "grpo",
    "prompt engineering", "prompting",
    # Data & Backend
    "fastapi", "flask", "django", "rest api", "api",
    "postgresql", "postgres", "redis", "supabase",
    "chromadb", "vector database", "vector db",
    "docker", "kubernetes", "k8s",
    # Cloud
    "aws", "amazon web services", "route53", "eks", "alb", "rds", "s3",
    "gcp", "google cloud", "azure",
    # Frontend
    "vite", "react", "next.js", "nextjs",
    "figma",
    # Mobile
    "swiftui", "ios", "mvvm", "xcode",
    # Tools
    "git", "github", "ci/cd", "cicd",
    # General SDE
    "software engineer", "software developer", "sde",
    "backend", "full stack", "fullstack",
}

# ── 2. EXCLUDED TITLE KEYWORDS (Strictly rejected) ──────────────────────────
EXCLUDED_TITLE_KEYWORDS = [
    # Analysts (Strict user command: "dont give me data analyst roles")
    "data analyst", "business analyst", "bi analyst", "analyst", "analytics",
    "business intelligence", "bi developer", "data analytics", "operations analyst",
    "financial analyst", "systems analyst", "system analyst", "qa analyst",
    # Senior / Experienced roles
    "senior", "sr.", "sr ", "lead", "principal", "staff", "architect",
    "manager", "director", "head of", "vp ", "vice president",
    "sde ii", "sde-ii", "sde 2", "sde-2", "sde 3", "sde-3", "sde iii", "sde-iii", "sde iv",
    "swe ii", "swe 2", "swe iii", "swe 3", "se ii", "se 2", "se iii",
    "level 2", "level 3", "level ii", "level iii", "mid-level", "mid level", "intermediate",
    # Non-relevant tech / non-engineering
    "sales", "recruiter", "marketing", "accountant", "hr ", "human resources", "support specialist",
]

# ── 3. EXCLUDED RESIDENCY / CITIZENSHIP / CLEARANCE PHRASES ────────────────
EXCLUDE_RESIDENCY_KEYWORDS = [
    # US / foreign citizenship & green card
    "green card", "permanent resident", "us citizen", "u.s. citizen", "united states citizen",
    "citizenship required", "citizen only", "citizens only", "must be a citizen", "us citizens only",
    "u.s. citizens only", "australian citizen", "uk citizen", "canadian citizen", "eu citizen",
    # Security clearances
    "security clearance", "secret clearance", "top secret", "ts/sci", "dod clearance", "active clearance",
    "public trust clearance", "polygraph",
    # Locals only / No visa sponsorship
    "locals only", "local candidates only", "local applicants only",
    "no visa sponsorship", "unable to sponsor", "will not sponsor", "cannot sponsor",
    "not offering sponsorship", "no sponsorship", "without sponsorship", "without visa sponsorship",
    "without employer sponsorship", "without need for sponsorship",
    "authorized to work in the us without", "authorized to work in the u.s. without",
    "legally authorized to work in the us without", "legally authorized to work in the united states without",
    "authorized to work in the us indefinitely without",
    "right to work in the uk", "right to work in australia", "right to work in canada", "right to work in the eu",
]

# ── 4. EXPERIENCE REGEX PATTERNS ───────────────────────────────────────────
# Experience ranges like "4-12 years", "3-5 years", "4 to 8 yrs"
EXP_RANGE_PATTERN = re.compile(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)", re.IGNORECASE)

# Mentions of 3+ years: "3+ years", "4 years of exp", "5+ yrs experience", "10+ years"
HIGH_EXP_PATTERN = re.compile(
    r"\b([3-9]|\d{2,})\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp|relevant|hands-on|industry|software|development|programming)?\b",
    re.IGNORECASE,
)

# Minimum experience requirement: "minimum 3 years", "min 4 yrs", "at least 3 years"
MIN_EXP_PATTERN = re.compile(
    r"(?:minimum|min|at least)\s*([3-9]|\d{2,})\+?\s*(?:years?|yrs?)",
    re.IGNORECASE,
)


def fetch_page(url: str, timeout: int = 15) -> str:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def extract_items(html: str, selector: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [el.get_text(strip=True) for el in soup.select(selector)]


def is_title_allowed(title: str) -> bool:
    """Rejects analyst roles, senior roles, managers, and multi-year levels."""
    t = f" {title.lower().replace(',', ' ').replace('-', ' ')} "
    for kw in EXCLUDED_TITLE_KEYWORDS:
        if kw in t:
            return False
    return True


def has_clearance_or_residency_restriction(text: str) -> bool:
    """Returns True if the text requires Green Card, US Citizenship, Clearance, or locals only."""
    t = text.lower()
    for kw in EXCLUDE_RESIDENCY_KEYWORDS:
        if kw in t:
            return True
    return False


def is_experience_excessive(description: str, req_exp_dict: Optional[Dict[str, Any]] = None) -> bool:
    """Returns True if experience requirement > 2 years (e.g., 3+, 4-12 years)."""
    # 1. Check API structured experience if available (e.g. from JSearch)
    if req_exp_dict and isinstance(req_exp_dict, dict):
        months = req_exp_dict.get("required_experience_in_months")
        if months is not None and isinstance(months, (int, float)) and months > 24:
            return True

    if not description:
        return False

    # 2. Check for experience ranges like "4-12 years", "3-5 years"
    for m in EXP_RANGE_PATTERN.finditer(description):
        try:
            low = int(m.group(1))
            high = int(m.group(2))
            if low > 2 or high >= 4:
                return True
        except (ValueError, IndexError):
            pass

    # 3. Check for minimum requirements: "minimum 3 years", "at least 4 yrs"
    if MIN_EXP_PATTERN.search(description):
        return True

    # 4. Check for high experience patterns: "3+ years", "5 years experience", "10+ yrs"
    if HIGH_EXP_PATTERN.search(description):
        return True

    return False


def is_location_eligible(
    country: Optional[str],
    is_remote: bool,
    location_str: str,
    description: str,
) -> bool:
    """Ensures jobs are either in India, 100% remote, or offer genuine international visa sponsorship."""
    country_upper = (country or "").strip().upper()
    loc_lower = (location_str or "").lower()
    desc_lower = (description or "").lower()

    # 1. India jobs are always eligible (onsite or remote)
    if country_upper == "IN" or "india" in loc_lower or "bengaluru" in loc_lower or "pune" in loc_lower or "hyderabad" in loc_lower or "noida" in loc_lower or "gurgaon" in loc_lower or "delhi" in loc_lower or "chennai" in loc_lower:
        return True

    # 2. Remote jobs are eligible regardless of company headquarters
    if is_remote or "remote" in loc_lower or "work from home" in loc_lower or "anywhere" in loc_lower:
        return True

    # 3. If onsite/hybrid in a foreign country: only eligible if international visa sponsorship is offered
    sponsorship_signals = [
        "visa sponsorship", "sponsor visa", "relocation assistance",
        "relocation package", "international applicants welcome", "willing to relocate",
    ]
    if any(sig in desc_lower for sig in sponsorship_signals):
        return True

    # Otherwise, it's a foreign onsite job requiring native residency/citizenship -> reject
    return False


def count_skill_matches(text: str) -> int:
    """Counts how many resume-skill keywords appear in the job text."""
    text_lower = text.lower()
    return sum(1 for skill in RESUME_SKILLS if skill in text_lower)


def is_job_suitable(
    title: str,
    description: str = "",
    country: Optional[str] = None,
    is_remote: bool = False,
    location_str: str = "",
    req_exp_dict: Optional[Dict[str, Any]] = None,
) -> bool:
    """Comprehensive multi-gate suitability check matching Prakhar's profile:
    
    1. Title Filter: No analysts, seniors, managers, leads, SDE II+.
    2. Residency/Clearance Filter: No Green Card, US Citizen, Clearance, locals only.
    3. Location Filter: Must be in India, Remote, or have visa sponsorship.
    4. Experience Filter: No 3+ years or 4-12 years experience.
    5. Skill Relevance Filter: Must match at least 2 relevant technical skills.
    """
    # Gate 1: Title
    if not is_title_allowed(title):
        return False

    combined_text = f"{title} {location_str} {description}"

    # Gate 2: Residency, Citizenship, Clearance restrictions
    if has_clearance_or_residency_restriction(combined_text):
        return False

    # Gate 3: Location eligibility
    if not is_location_eligible(country, is_remote, location_str, description):
        return False

    # Gate 4: Experience ceiling (0-2 years max)
    if is_experience_excessive(description, req_exp_dict):
        return False

    # Gate 5: Technical skill match (at least 2 skills)
    if count_skill_matches(combined_text) < 2:
        return False

    return True


def fetch_json_items(target: dict) -> list[str]:
    url = os.path.expandvars(target["url"])
    headers = {"User-Agent": USER_AGENT}
    if "headers" in target:
        for k, v in target["headers"].items():
            headers[k] = os.path.expandvars(str(v))

    timeout = target.get("timeout", 30)
    resp = requests.get(url, timeout=timeout, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    fresher_only = target.get("fresher_only", True)
    extractor = target.get("extractor")

    if extractor == "amazon_jobs":
        items = []
        for j in data.get("jobs", []):
            title = j.get("title", "Unknown Role")
            desc = j.get("description_short", "") or j.get("basic_qualifications", "")
            loc = j.get("location", "Unknown Location")
            country = "IN" if "India" in loc else ""
            is_remote = "virtual" in loc.lower() or "remote" in loc.lower()

            if fresher_only and not is_job_suitable(
                title=title,
                description=desc,
                country=country,
                is_remote=is_remote,
                location_str=loc,
            ):
                continue

            date = j.get("posted_date", "")
            job_path = j.get("job_path", "")
            link = f"https://www.amazon.jobs{job_path}" if job_path else ""
            remote_tag = " 🏠 Remote" if is_remote else ""
            items.append(f"{title} | {loc}{remote_tag} | Posted: {date} | Link: {link}")
        return items

    elif extractor == "jsearch":
        items = []
        raw_data = data.get("data", [])
        job_list = raw_data.get("jobs", []) if isinstance(raw_data, dict) else raw_data
        for j in job_list:
            if isinstance(j, dict):
                title = j.get("job_title", "Unknown Role")
                desc = j.get("job_description", "")
                company = j.get("employer_name", "Unknown Company")
                city = j.get("job_city", "")
                country = j.get("job_country", "")
                loc = f"{city}, {country}".strip(", ")
                is_remote = bool(j.get("job_is_remote", False))
                req_exp = j.get("job_required_experience")

                if fresher_only and not is_job_suitable(
                    title=title,
                    description=desc,
                    country=country,
                    is_remote=is_remote,
                    location_str=loc,
                    req_exp_dict=req_exp,
                ):
                    continue

                link = j.get("job_apply_link", "")
                date = str(j.get("job_posted_at_datetime_utc", ""))[:10]
                remote_tag = " 🏠 Remote" if is_remote else ""
                items.append(f"{company}: {title} | {loc}{remote_tag} | Date: {date} | Apply: {link}")
        return items

    elif "item_key" in target:
        key = target["item_key"]
        return [str(item) for item in data.get(key, [])]

    return []


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
