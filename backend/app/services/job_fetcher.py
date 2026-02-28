"""Fetches job listings from Greenhouse, AshbyHQ, and Lever public APIs."""

import json
import logging
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ATSType, Company, JobListing, JobStatus, UserProfile

logger = logging.getLogger(__name__)

GREENHOUSE_BASE = "https://boards-api.greenhouse.io/v1/boards"
ASHBY_BASE = "https://api.ashbyhq.com/posting-api/job-board"
LEVER_BASE = "https://api.lever.co/v0/postings"


def _safe_parse_date(value) -> datetime | None:
    """Parse a date string or Unix timestamp (ms) into a datetime object, or return None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    # Handle Unix timestamps in milliseconds (Lever uses these)
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(value / 1000 if value > 1e12 else value)
        except (ValueError, OSError):
            return None
    try:
        return parse_date(str(value))
    except (ValueError, TypeError):
        return None


async def fetch_greenhouse_jobs(client: httpx.AsyncClient, token: str) -> list[dict]:
    """Fetch all jobs from a Greenhouse board."""
    url = f"{GREENHOUSE_BASE}/{token}/jobs?content=true"
    resp = await client.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    jobs = data.get("jobs", [])
    results = []
    for j in jobs:
        desc_html = j.get("content", "")
        desc_text = BeautifulSoup(desc_html, "html.parser").get_text(separator="\n").strip()
        loc = j.get("location", {})
        loc_name = loc.get("name", "") if isinstance(loc, dict) else str(loc)
        departments = j.get("departments", [])
        dept_name = departments[0]["name"] if departments else ""
        results.append(
            {
                "external_id": str(j["id"]),
                "title": j.get("title", ""),
                "location": loc_name,
                "department": dept_name,
                "description_html": desc_html,
                "description_text": desc_text,
                "url": j.get("absolute_url", ""),
                "compensation": "",
                "posted_at": _safe_parse_date(j.get("updated_at")),
            }
        )
    return results


async def fetch_ashby_jobs(client: httpx.AsyncClient, token: str) -> list[dict]:
    """Fetch all jobs from an AshbyHQ board."""
    url = f"{ASHBY_BASE}/{token}?includeCompensation=true"
    resp = await client.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    jobs = data.get("jobs", [])
    results = []
    for j in jobs:
        desc_html = j.get("descriptionHtml", "") or j.get("content", "")
        desc_text = BeautifulSoup(desc_html, "html.parser").get_text(separator="\n").strip()
        comp = j.get("compensation", {})
        comp_str = ""
        if comp:
            comp_str = f"{comp.get('compensationTierSummary', '')}"
        loc = j.get("location", "") or ""
        if isinstance(loc, dict):
            loc = loc.get("name", "")
        results.append(
            {
                "external_id": str(j["id"]),
                "title": j.get("title", ""),
                "location": loc,
                "department": j.get("department", ""),
                "description_html": desc_html,
                "description_text": desc_text,
                "url": j.get("jobUrl", j.get("hostedUrl", "")),
                "compensation": comp_str,
                "posted_at": _safe_parse_date(j.get("publishedAt")),
            }
        )
    return results


async def fetch_lever_jobs(client: httpx.AsyncClient, token: str) -> list[dict]:
    """Fetch all jobs from a Lever postings board."""
    url = f"{LEVER_BASE}/{token}"
    resp = await client.get(url, timeout=30)
    resp.raise_for_status()
    jobs = resp.json()  # Lever returns a JSON array directly
    if not isinstance(jobs, list):
        logger.warning(f"Lever returned non-list response for {token}: {type(jobs)}")
        return []
    results = []
    for j in jobs:
        desc_html = j.get("descriptionPlain", "") or j.get("description", "")
        desc_html_raw = j.get("description", "")
        desc_text = BeautifulSoup(desc_html_raw, "html.parser").get_text(separator="\n").strip() if desc_html_raw else desc_html
        categories = j.get("categories", {})
        loc = categories.get("location", "") or ""
        team = categories.get("team", "") or ""
        commitment = categories.get("commitment", "") or ""
        results.append(
            {
                "external_id": str(j["id"]),
                "title": j.get("text", ""),
                "location": loc,
                "department": team,
                "description_html": desc_html_raw,
                "description_text": desc_text,
                "url": j.get("hostedUrl", j.get("applyUrl", "")),
                "compensation": commitment,
                "posted_at": _safe_parse_date(j.get("createdAt")),
            }
        )
    return results


async def _get_filter_criteria(db: AsyncSession) -> tuple[list[str], list[str]]:
    """Load target titles and excluded titles from user profile preferences (all lowercased)."""
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile or not profile.preferences:
        return [], []
    try:
        prefs = json.loads(profile.preferences) if isinstance(profile.preferences, str) else profile.preferences

        def _parse_list(val):
            if isinstance(val, str):
                return [t.strip().lower() for t in val.split(",") if t.strip()]
            return [t.lower() for t in (val or [])]

        return _parse_list(prefs.get("titles", [])), _parse_list(prefs.get("excluded_titles", []))
    except (json.JSONDecodeError, AttributeError):
        return [], []


# Non-US location indicators to filter out
_NON_US_INDICATORS = [
    "canada", "ontario", "british columbia", "toronto", "vancouver", "montreal", "quebec", "alberta", "calgary",
    "united kingdom", "uk", "london", "england", "ireland", "dublin",
    "germany", "berlin", "munich", "france", "paris", "netherlands", "amsterdam",
    "spain", "madrid", "barcelona", "italy", "rome", "milan",
    "australia", "sydney", "melbourne", "singapore", "japan", "tokyo",
    "india", "bangalore", "bengaluru", "mumbai", "hyderabad", "gurugram", "gurgaon", "delhi", "pune", "chennai",
    "china", "beijing", "shanghai", "brazil", "são paulo", "sao paulo",
    "korea", "seoul", "israel", "tel aviv",
    "mexico", "argentina", "buenos aires", "colombia", "bogota",
    "sweden", "stockholm", "norway", "oslo", "denmark", "copenhagen", "finland", "helsinki",
    "poland", "warsaw", "czech", "prague", "switzerland", "zurich",
    "portugal", "lisbon", "austria", "vienna",
]


def _is_us_location(location: str) -> bool:
    """Return True if the location appears to be in the US or is Remote (no specific non-US country)."""
    if not location:
        return True  # No location info, assume eligible
    loc_lower = location.lower().strip()
    # Explicit US indicators
    if any(us in loc_lower for us in ["united states", "usa", "u.s.", "remote - usa", "remote, us"]):
        return True
    # "Remote" or "Anywhere" without a specific non-US country
    if "remote" in loc_lower or "anywhere" in loc_lower:
        return not any(non_us in loc_lower for non_us in _NON_US_INDICATORS)
    # Check for non-US indicators
    if any(non_us in loc_lower for non_us in _NON_US_INDICATORS):
        return False
    return True  # Default: keep if unclear


def _matches_filters(job_title: str, job_location: str, target_titles: list[str], excluded_titles: list[str]) -> bool:
    """Check if a job passes all filters (case-insensitive)."""
    job_lower = job_title.lower()

    # Must match at least one target title (if any configured)
    if target_titles and not any(target in job_lower for target in target_titles):
        return False

    # Must not match any excluded title
    if excluded_titles and any(excl in job_lower for excl in excluded_titles):
        return False

    # Must be a US-based location
    if not _is_us_location(job_location):
        return False

    return True


async def fetch_jobs_for_company(db: AsyncSession, company: Company) -> int:
    """Fetch and store new jobs for a single company. Returns count of new jobs."""
    async with httpx.AsyncClient() as client:
        if company.ats_type == ATSType.GREENHOUSE:
            raw_jobs = await fetch_greenhouse_jobs(client, company.board_token)
        elif company.ats_type == ATSType.ASHBY:
            raw_jobs = await fetch_ashby_jobs(client, company.board_token)
        elif company.ats_type == ATSType.LEVER:
            raw_jobs = await fetch_lever_jobs(client, company.board_token)
        else:
            logger.warning(f"Unknown ATS type: {company.ats_type}")
            return 0

    # Dedup: get existing external IDs for this company
    result = await db.execute(
        select(JobListing.external_id).where(JobListing.company_id == company.id)
    )
    existing_ids = {row[0] for row in result.fetchall()}

    # Load filter criteria from profile
    target_titles, excluded_titles = await _get_filter_criteria(db)

    new_count = 0
    skipped = 0
    for job_data in raw_jobs:
        if job_data["external_id"] in existing_ids:
            continue
        if not _matches_filters(job_data["title"], job_data["location"], target_titles, excluded_titles):
            skipped += 1
            continue
        listing = JobListing(
            company_id=company.id,
            external_id=job_data["external_id"],
            title=job_data["title"],
            location=job_data["location"],
            department=job_data["department"],
            description_html=job_data["description_html"],
            description_text=job_data["description_text"],
            url=job_data["url"],
            compensation=job_data.get("compensation", ""),
            posted_at=job_data.get("posted_at"),
            fetched_at=datetime.utcnow(),
            status=JobStatus.NEW,
        )
        db.add(listing)
        new_count += 1

    company.last_scraped_at = datetime.utcnow()
    await db.commit()
    logger.info(f"Fetched {new_count} new jobs from {company.name} ({company.ats_type.value}), skipped {skipped} non-matching titles")
    return new_count


async def fetch_all_jobs(db: AsyncSession) -> int:
    """Fetch jobs from all tracked companies. Returns total new jobs."""
    result = await db.execute(select(Company))
    companies = result.scalars().all()
    total = 0
    for company in companies:
        try:
            count = await fetch_jobs_for_company(db, company)
            total += count
        except Exception as e:
            logger.error(f"Error fetching jobs for {company.name}: {e}")
    return total
