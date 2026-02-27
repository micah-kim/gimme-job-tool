"""API routes for job listings and companies."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Company, JobListing, JobScore
from app.schemas.schemas import CompanyCreate, CompanyOut, JobListingOut, JobScoreOut
from app.services.job_fetcher import fetch_all_jobs, fetch_jobs_for_company

router = APIRouter(prefix="/api", tags=["jobs"])


# ── Companies ──


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).order_by(Company.name))
    return result.scalars().all()


@router.post("/companies", response_model=CompanyOut)
async def add_company(data: CompanyCreate, db: AsyncSession = Depends(get_db)):
    company = Company(name=data.name, ats_type=data.ats_type, board_token=data.board_token)
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


@router.delete("/companies/{company_id}")
async def delete_company(company_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    await db.delete(company)
    await db.commit()
    return {"detail": "deleted"}


# ── Jobs ──


@router.get("/jobs", response_model=list[JobListingOut])
async def list_jobs(
    status: str | None = None,
    title: str | None = None,
    location: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(JobListing).order_by(JobListing.fetched_at.desc())
    if status:
        query = query.where(JobListing.status == status)
    if title:
        query = query.where(JobListing.title.ilike(f"%{title}%"))
    if location:
        query = query.where(JobListing.location.ilike(f"%{location}%"))
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/jobs/matched", response_model=list[JobListingOut])
async def list_matched_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(JobListing).where(JobListing.status == "matched").order_by(JobListing.fetched_at.desc())
    )
    return result.scalars().all()


@router.get("/jobs/{job_id}", response_model=JobListingOut)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobListing).where(JobListing.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/score", response_model=JobScoreOut | None)
async def get_job_score(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobScore).where(JobScore.job_id == job_id))
    return result.scalar_one_or_none()


# ── Fetch trigger ──


@router.post("/jobs/fetch")
async def trigger_fetch(db: AsyncSession = Depends(get_db)):
    count = await fetch_all_jobs(db)
    return {"jobs_fetched": count}
