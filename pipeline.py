"""Zero-Click Daily Cloud Job Pipeline

Fetches career feeds / public ATS APIs, applies hard visa exclusions & role filters,
deduplicates against previously seen job IDs, and pushes directly to your phone via Telegram.
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure UTF-8 output encoding for emojis across Windows and Linux terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Import local configuration
try:
    from config import (
        ALLOW_WORLDWIDE,
        EXCLUSION_PATTERNS,
        JOB_FEEDS,
        MAX_ALERTS_PER_RUN,
        MAX_SEEN_CACHE_SIZE,
        NON_US_LOCATION_PATTERNS,
        SEEN_JOBS_FILE,
        TARGET_ROLES,
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        US_LOCATION_PATTERNS,
        US_ONLY,
    )
except ImportError:
    from job_pipeline.config import (  # type: ignore
        ALLOW_WORLDWIDE,
        EXCLUSION_PATTERNS,
        JOB_FEEDS,
        MAX_ALERTS_PER_RUN,
        MAX_SEEN_CACHE_SIZE,
        NON_US_LOCATION_PATTERNS,
        SEEN_JOBS_FILE,
        TARGET_ROLES,
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        US_LOCATION_PATTERNS,
        US_ONLY,
    )


# ---------------------------------------------------------------------------
# Filtering Functions
# ---------------------------------------------------------------------------


def clean_html_tags(text: str) -> str:
    """Strip HTML tags and unescape entities for clean regex filtering."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(clean)


def check_sponsorship_disqualification(text: str) -> Tuple[bool, Optional[str]]:
    """Returns (True, matched_pattern) if the text explicitly excludes visa sponsorship."""
    if not text:
        return False, None
    clean_text = clean_html_tags(text)
    for pattern in EXCLUSION_PATTERNS:
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            return True, match.group(0)
    return False, None


def match_target_role(title: str) -> bool:
    """Checks whether the job title matches any target role keywords."""
    if not title:
        return False
    title_lower = title.lower()
    return any(role in title_lower for role in TARGET_ROLES)


def is_location_eligible(location: str) -> Tuple[bool, str]:
    """Validates whether the job location is eligible for a US applicant.
    Strictly disqualifies roles restricted to non-US locations (e.g. Spain, UK, Europe, EMEA).
    """
    if not location:
        return not US_ONLY, "No location specified"

    clean_loc = location.strip().lower()

    # 1. If explicit US pattern matches, it's eligible
    for pat in US_LOCATION_PATTERNS:
        if re.search(pat, clean_loc, re.IGNORECASE):
            return True, "US Eligible"

    # 2. If explicit foreign / non-US pattern matches without US, disqualify!
    for pat in NON_US_LOCATION_PATTERNS:
        match = re.search(pat, clean_loc, re.IGNORECASE)
        if match:
            return False, f"Restricted to {match.group(0).upper()} (Non-US)"

    # 3. Check for Worldwide / Anywhere
    if any(k in clean_loc for k in ("worldwide", "anywhere", "global")):
        if ALLOW_WORLDWIDE:
            return True, "Worldwide Remote"
        return False, "Worldwide not enabled"

    # 4. If US_ONLY is active and not explicitly matched as US or Worldwide, exclude
    if US_ONLY:
        return False, f"Location '{location}' not verified for US"

    return True, "Default Eligible"


def generate_job_id(company: str, title: str, apply_url: str, explicit_id: Optional[str] = None) -> str:
    """Generates a stable, unique ID for a job posting."""
    if explicit_id:
        return str(explicit_id).strip()
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{apply_url.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Deduplication Store (SQLite / JSON)
# ---------------------------------------------------------------------------


def load_seen_jobs(file_path: Path = SEEN_JOBS_FILE) -> Dict[str, Any]:
    """Loads previously seen job records to prevent duplicate mobile alerts."""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        print(f"[Deduplication] Warning: Could not read {file_path}: {e}")
    return {}


def save_seen_jobs(seen_jobs: Dict[str, Any], file_path: Path = SEEN_JOBS_FILE) -> None:
    """Saves seen jobs and trims cache size to prevent unbounded file growth."""
    try:
        # Keep only the newest entries if cache exceeds max size
        if len(seen_jobs) > MAX_SEEN_CACHE_SIZE:
            sorted_items = sorted(
                seen_jobs.items(),
                key=lambda item: item[1].get("seen_at", ""),
                reverse=True,
            )
            seen_jobs = dict(sorted_items[:MAX_SEEN_CACHE_SIZE])

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(seen_jobs, f, indent=2, ensure_ascii=False)
        print(f"[Deduplication] Cached {len(seen_jobs)} seen job IDs in {file_path.name}.")
    except Exception as e:
        print(f"[Deduplication] Error writing {file_path}: {e}")


# ---------------------------------------------------------------------------
# Feed Fetchers
# ---------------------------------------------------------------------------


def fetch_url(url: str, timeout: int = 15) -> Optional[bytes]:
    """Fetches raw content with standard browser user-agent and timeout."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        print(f"[Fetcher] Failed to fetch {url}: {e}")
        return None


def parse_remotive_jobs(payload_bytes: bytes) -> List[Dict[str, Any]]:
    """Parses jobs from Remotive API response."""
    jobs_out = []
    try:
        data = json.loads(payload_bytes.decode("utf-8"))
        for item in data.get("jobs", []):
            jobs_out.append({
                "id": str(item.get("id", "")),
                "title": item.get("title", "").strip(),
                "company": item.get("company_name", "").strip(),
                "apply_url": item.get("url", "").strip(),
                "description": item.get("description", ""),
                "location": item.get("candidate_required_location", "Remote"),
                "source": "Remotive",
            })
    except Exception as e:
        print(f"[Fetcher] Remotive parse error: {e}")
    return jobs_out


def parse_jobicy_jobs(payload_bytes: bytes) -> List[Dict[str, Any]]:
    """Parses jobs from Jobicy public API response."""
    jobs_out = []
    try:
        data = json.loads(payload_bytes.decode("utf-8"))
        for item in data.get("jobs", []):
            jobs_out.append({
                "id": str(item.get("id", "")),
                "title": item.get("jobTitle", "").strip(),
                "company": item.get("companyName", "").strip(),
                "apply_url": item.get("url", "").strip(),
                "description": item.get("jobDescription", ""),
                "location": item.get("jobGeo", "Remote"),
                "source": "Jobicy",
            })
    except Exception as e:
        print(f"[Fetcher] Jobicy parse error: {e}")
    return jobs_out


def fetch_all_jobs() -> List[Dict[str, Any]]:
    """Fetches and aggregates jobs across all configured feeds."""
    aggregated: List[Dict[str, Any]] = []

    for feed in JOB_FEEDS:
        print(f"[Fetcher] Querying {feed['name']}...")
        content = fetch_url(feed["url"])
        if not content:
            continue

        if feed["type"] == "remotive":
            parsed = parse_remotive_jobs(content)
        elif feed["type"] == "jobicy":
            parsed = parse_jobicy_jobs(content)
        else:
            parsed = []

        print(f"[Fetcher] Retrieved {len(parsed)} raw jobs from {feed['name']}.")
        aggregated.extend(parsed)

    return aggregated


# ---------------------------------------------------------------------------
# Telegram Delivery (Mobile Interface)
# ---------------------------------------------------------------------------


def escape_html(text: str) -> str:
    """Escapes HTML special characters for safe Telegram HTML parsing."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def send_telegram_message(bot_token: str, chat_id: str, html_text: str) -> bool:
    """Pushes a notification directly to the user's phone via Telegram Bot API."""
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        print(f"[Telegram] HTTP Error {e.code}: {error_body}")
        return False
    except Exception as e:
        print(f"[Telegram] Failed to push Telegram alert: {e}")
        return False


def build_telegram_digest(jobs: List[Dict[str, Any]]) -> List[str]:
    """Builds clean Telegram mobile message chunks with 1-click links (max 4000 chars each)."""
    header = (
        f"🎯 <b>Daily Job Alert ({len(jobs)} New Roles)</b>\n"
        f"<i>Verified Sponsorship &amp; Role Match</i>\n\n"
    )

    chunks: List[str] = []
    current_chunk = header

    for idx, j in enumerate(jobs, 1):
        company = escape_html(j["company"] or "Unknown Company")
        title = escape_html(j["title"])
        location = escape_html(j.get("location") or "Remote")
        apply_url = j["apply_url"]

        entry = (
            f"<b>{idx}. {company}</b> — {title}\n"
            f"📍 {location}\n"
            f'👉 <a href="{apply_url}"><b>Tap to 1-Click Apply</b></a>\n\n'
        )

        if len(current_chunk) + len(entry) > 3800:
            chunks.append(current_chunk)
            current_chunk = entry
        else:
            current_chunk += entry

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# ---------------------------------------------------------------------------
# Core Orchestration Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    dry_run: bool = False,
    force: bool = False,
    max_alerts: int = MAX_ALERTS_PER_RUN,
) -> List[Dict[str, Any]]:
    """Runs the complete ingestion, filter, deduplication, and notification flow."""
    print("=" * 60)
    print(f"🚀 Starting Zero-Click Job Pipeline at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Target Roles: {', '.join(TARGET_ROLES)}")
    print("=" * 60)

    # 1. Load seen cache
    seen_jobs = {} if force else load_seen_jobs()
    print(f"[Deduplication] Loaded {len(seen_jobs)} previously alerted jobs.")

    # 2. Fetch raw feeds
    raw_jobs = fetch_all_jobs()
    if not raw_jobs:
        print("[Pipeline] No jobs retrieved from any feed today. Exiting.")
        return []

    print(f"[Pipeline] Processing {len(raw_jobs)} total raw jobs against filters...")

    # 3. Apply Filters & Deduplication
    qualified_jobs: List[Dict[str, Any]] = []
    role_match_count = 0
    location_excluded_count = 0
    visa_excluded_count = 0
    duplicate_count = 0

    now_iso = datetime.now(timezone.utc).isoformat()

    for job in raw_jobs:
        title = job.get("title", "")
        company = job.get("company", "")
        desc = job.get("description", "")
        apply_url = job.get("apply_url", "")
        location = job.get("location", "")
        raw_id = job.get("id")

        # Step A: Target Role Match
        if not match_target_role(title):
            continue
        role_match_count += 1

        # Step B: Location Verification (US Applicants Only)
        loc_ok, loc_reason = is_location_eligible(location)
        if not loc_ok:
            location_excluded_count += 1
            continue

        # Step C: Visa Exclusion Disqualification
        excluded, pattern = check_sponsorship_disqualification(desc)
        if excluded:
            visa_excluded_count += 1
            continue

        # Step D: Deduplication Check
        job_id = generate_job_id(company, title, apply_url, raw_id)
        if job_id in seen_jobs and not force:
            duplicate_count += 1
            continue

        # Validated New Qualified Role
        job["stable_id"] = job_id
        job["seen_at"] = now_iso
        qualified_jobs.append(job)

    print("\n📊 Filter Summary:")
    print(f"   • Matching Target Roles: {role_match_count}")
    print(f"   • Excluded (Non-US Location): {location_excluded_count}")
    print(f"   • Excluded (Visa / No Sponsorship): {visa_excluded_count}")
    print(f"   • Deduplicated (Already Seen): {duplicate_count}")
    print(f"   • New Qualified Roles: {len(qualified_jobs)}")

    if not qualified_jobs:
        print("\n✨ Clean inbox: No new matching roles today. Enjoy your day!")
        return []

    # Limit to top N daily alerts to avoid mobile clutter
    selected_jobs = qualified_jobs[:max_alerts]
    print(f"\n📦 Preparing mobile alert batch: {len(selected_jobs)} roles (Max cap: {max_alerts}).")

    # 4. Build Telegram Digest
    message_chunks = build_telegram_digest(selected_jobs)

    # 5. Push to Phone or Console
    has_telegram = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

    if dry_run or not has_telegram:
        print("\n" + "=" * 30 + " TELEGRAM PREVIEW " + "=" * 30)
        if not has_telegram:
            print("⚠️ Notice: TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID are not set.")
            print("Displaying formatted alert digest below:\n")
        for idx, chunk in enumerate(message_chunks, 1):
            print(f"--- Chunk {idx} ---")
            print(clean_html_tags(chunk))
        print("=" * 78)
    else:
        print(f"[Telegram] Sending {len(message_chunks)} message chunk(s) to Chat ID: {TELEGRAM_CHAT_ID}...")
        for chunk in message_chunks:
            ok = send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, chunk)
            if ok:
                print("✅ Telegram notification pushed successfully!")
            else:
                print("❌ Failed to push Telegram message.")
            time.sleep(1)  # Respect Telegram rate limits

    # 6. Update seen cache (only if not dry run)
    if not dry_run:
        for j in selected_jobs:
            seen_jobs[j["stable_id"]] = {
                "title": j["title"],
                "company": j["company"],
                "apply_url": j["apply_url"],
                "seen_at": j["seen_at"],
            }
        save_seen_jobs(seen_jobs)

    return selected_jobs


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Zero-Click Daily Cloud Job Alert Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Print preview to console without sending or caching")
    parser.add_argument("--force", action="store_true", help="Ignore seen cache and evaluate all retrieved jobs")
    parser.add_argument("--max", type=int, default=MAX_ALERTS_PER_RUN, help="Maximum number of alerts to push")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test ping to Telegram to verify credentials")

    args = parser.parse_args()

    if args.test_telegram:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("❌ Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env or environment.")
            sys.exit(1)
        test_msg = (
            "🔔 <b>Zero-Click Job Pipeline Test Alert</b>\n\n"
            "Your Telegram Bot connection is working perfectly! You will receive daily 8:00 AM CST alerts here.\n\n"
            '👉 <a href="https://github.com"><b>Test 1-Click Link</b></a>'
        )
        print("Sending test message to Telegram...")
        success = send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, test_msg)
        if success:
            print("🎉 Success! Check your Telegram app.")
        else:
            print("❌ Delivery failed. Double check your Bot Token and Chat ID.")
        sys.exit(0 if success else 1)

    run_pipeline(dry_run=args.dry_run, force=args.force, max_alerts=args.max)


if __name__ == "__main__":
    main()
