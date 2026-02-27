"""Fetches job listings from Greenhouse and AshbyHQ public APIs."""

import logging
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ATSType, Company, JobListing, JobStatus

logger = logging.getLogger(__name__)

GREENHOUSE_BASE = "https://boards-api.greenhouse.io/v1/boards"
ASHBY_BASE = "https://api.ashbyhq.com/posting-api/job-board"


def _safe_parse_date(value) -> datetime | None:
    """Parse a date string into a datetime object, or return None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
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


async def fetch_jobs_for_company(db: AsyncSession, company: Company) -> int:
    """Fetch and store new jobs for a single company. Returns count of new jobs."""
    async with httpx.AsyncClient() as client:
        if company.ats_type == ATSType.GREENHOUSE:
            raw_jobs = await fetch_greenhouse_jobs(client, company.board_token)
        elif company.ats_type == ATSType.ASHBY:
            raw_jobs = await fetch_ashby_jobs(client, company.board_token)
        else:
            logger.warning(f"Unknown ATS type: {company.ats_type}")
            return 0

    # Dedup: get existing external IDs for this company
    result = await db.execute(
        select(JobListing.external_id).where(JobListing.company_id == company.id)
    )
    existing_ids = {row[0] for row in result.fetchall()}

    new_count = 0
    for job_data in raw_jobs:
        if job_data["external_id"] in existing_ids:
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
    logger.info(f"Fetched {new_count} new jobs from {company.name} ({company.ats_type.value})")
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
