"""Fetch + parse a target page. Kept dependency-light on purpose."""
import hashlib
import os
import re

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; personal-monitor/1.0)"

# ── Resume-derived skill keywords (used for relevance scoring) ──────────────
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
    # Data Engineering
    "data pipeline", "etl", "data engineering",
    # General SDE
    "software engineer", "software developer", "sde",
    "backend", "full stack", "fullstack",
}

# Minimum number of resume skill keywords a job must match to pass the filter
MIN_SKILL_MATCH = 2

SENIOR_PATTERNS = [
    " sde ii", " sde-ii", " sde 2", " sde-2", "sde 3", "sde-3", "sde iii", "sde-iii",
    "senior", "sr.", "sr ", "lead", "principal", "staff", "architect", "manager",
    "director", "head of", " ii", " iii", " - ii", " - iii", " 2 ", " 3 ", " 4 ",
    "2+ years", "3+ years", "4+ years", "5+ years", "6+ years",
    "7+ years", "8+ years", "10+ years",
]

# Patterns that match high experience requirements in descriptions
EXP_YEAR_PATTERN = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)", re.IGNORECASE)


def fetch_page(url: str, timeout: int = 15) -> str:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def extract_items(html: str, selector: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [el.get_text(strip=True) for el in soup.select(selector)]


def is_fresher_job(title: str) -> bool:
    """Returns True if the title does NOT contain senior/experienced patterns."""
    t = " " + title.lower().replace(",", " ").replace("-", " ") + " "
    for p in SENIOR_PATTERNS:
        if p in t:
            return False
    return True


def _extract_experience_years(text: str) -> int | None:
    """Extract minimum years of experience from text. Returns None if not found."""
    matches = EXP_YEAR_PATTERN.findall(text)
    if matches:
        return min(int(m) for m in matches)
    return None


def _count_skill_matches(text: str) -> int:
    """Count how many resume-skill keywords appear in the text."""
    text_lower = text.lower()
    count = 0
    for skill in RESUME_SKILLS:
        if skill in text_lower:
            count += 1
    return count


def is_resume_match(title: str, description: str = "") -> bool:
    """Check if a job matches the resume profile.
    
    Three-gate filter:
    1. Title must not contain senior patterns (is_fresher_job)
    2. If description mentions experience years, must be ≤ 2
    3. Title + description must match at least MIN_SKILL_MATCH resume skills
    """
    # Gate 1: Title-level senior filter
    if not is_fresher_job(title):
        return False

    combined = f"{title} {description}"

    # Gate 2: Experience-years filter (from description if available)
    if description:
        exp_years = _extract_experience_years(description)
        if exp_years is not None and exp_years > 2:
            return False

    # Gate 3: Skill relevance
    skill_hits = _count_skill_matches(combined)
    if skill_hits < MIN_SKILL_MATCH:
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
            desc = j.get("description_short", "") or j.get("basic_qualifications", "")
            if fresher_only and not is_resume_match(title, desc):
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
                desc = j.get("job_description", "")
                if fresher_only and not is_resume_match(title, desc):
                    continue
                company = j.get("employer_name", "")
                city = j.get("job_city", "")
                country = j.get("job_country", "")
                loc = f"{city}, {country}".strip(", ")
                link = j.get("job_apply_link", "")
                date = str(j.get("job_posted_at_datetime_utc", ""))[:10]
                remote = " 🏠 Remote" if j.get("job_is_remote", False) else ""
                items.append(f"{company}: {title} | {loc}{remote} | Date: {date} | Apply: {link}")
        return items

    elif "item_key" in target:
        key = target["item_key"]
        return [str(item) for item in data.get(key, [])]

    return []


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
