"""Configuration settings for the Zero-Click Job Alert Pipeline."""

import os
import re
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
SEEN_JOBS_FILE = BASE_DIR / "seen_jobs.json"


def load_env_file(filepath: Path = ENV_FILE) -> None:
    """Lightweight .env loader using standard library to avoid external dependencies."""
    if not filepath.exists():
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        print(f"[Config] Warning: Failed to load .env file: {e}")


# Auto-load local .env if present
load_env_file()

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Target Job Roles (Case-insensitive substring match)
DEFAULT_TARGET_ROLES = [
    "data scientist",
    "senior data analyst",
    "analytics engineer",
    "decision scientist",
    "machine learning engineer",
    "ai engineer",
    "quantitative analyst",
]

_custom_roles = os.getenv("TARGET_ROLES")
if _custom_roles:
    TARGET_ROLES = [r.strip().lower() for r in _custom_roles.split(",") if r.strip()]
else:
    TARGET_ROLES = DEFAULT_TARGET_ROLES

# Hard Visa Exclusion Patterns (Regex matching across job descriptions)
EXCLUSION_PATTERNS = [
    r"will not sponsor",
    r"no visa sponsorship",
    r"without sponsorship",
    r"sponsorship is not available",
    r"sponsorship is not provided",
    r"not eligible for visa sponsorship",
    r"must be a us citizen or permanent resident",
    r"us citizen or green card only",
    r"unable to sponsor",
    r"no sponsorship now or in the future",
    r"does not offer sponsorship",
    r"not offering visa sponsorship",
    r"not offering sponsorship",
    r"opt[/\s-]cpt not accepted",
    r"no cpt[/\s-]opt",
    r"require permanent us work authorization",
    r"must have unrestricted work authorization",
    r"security clearance required",
    r"active secret clearance",
]

# Max notifications sent per run (to prevent mobile notification floods)
MAX_ALERTS_PER_RUN = int(os.getenv("MAX_ALERTS_PER_RUN", "10"))

# Max history retention in seen_jobs.json (prevents unbounded cache growth)
MAX_SEEN_CACHE_SIZE = 1000

# Location Filtering Settings (Strictly US Eligible)
# Set US_ONLY=true to enforce roles where US residents are eligible
US_ONLY = os.getenv("US_ONLY", "true").lower() in ("true", "1", "yes")
ALLOW_WORLDWIDE = os.getenv("ALLOW_WORLDWIDE", "true").lower() in ("true", "1", "yes")

# Explicit US match patterns
US_LOCATION_PATTERNS = [
    r"\bus\b",
    r"\busa\b",
    r"united states",
    r"north america",
    r"americas",
    r"remote\s*[-–—:]*\s*(?:us|usa|united states)",
    r"remote\s*\((?:us|usa|united states)\)",
]

# Explicit foreign non-US locations (rejected if US is not explicitly listed)
NON_US_LOCATION_PATTERNS = [
    r"\bspain\b",
    r"\beurope\b",
    r"\bemea\b",
    r"\buk\b",
    r"united kingdom",
    r"\bgermany\b",
    r"\bfrance\b",
    r"\bpoland\b",
    r"\bnetherlands\b",
    r"\bireland\b",
    r"\bindia\b",
    r"\bbrazil\b",
    r"\blatam\b",
    r"\bapac\b",
    r"\baustralia\b",
    r"\bnew zealand\b",
    r"\bsingapore\b",
    r"\bphilippines\b",
    r"\bsweden\b",
    r"\bswitzerland\b",
    r"\bitaly\b",
    r"\bportugal\b",
    r"\bromania\b",
    r"\bafrica\b",
    r"\bmiddle east\b",
]

# Public Job APIs and Feeds (restricting to USA / Remote feeds)
JOB_FEEDS = [
    {
        "name": "Remotive Remote Data",
        "url": "https://remotive.com/api/remote-jobs?category=data&limit=50",
        "type": "remotive",
    },
    {
        "name": "Jobicy USA Remote Data",
        "url": "https://jobicy.com/api/v2/remote-jobs?count=50&geo=usa&tag=data",
        "type": "jobicy",
    },
]

