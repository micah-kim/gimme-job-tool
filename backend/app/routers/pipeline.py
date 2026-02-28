"""API routes for pipeline execution and application logs."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import ApplicationLog, JobListing
from app.schemas.schemas import (
    ApplicationLogOut,
    PipelineRunRequest,
    PipelineRunResult,
)
from app.services.auto_apply import apply_to_job, apply_to_all_jobs
from app.services.pipeline import run_pipeline

router = APIRouter(prefix="/api", tags=["pipeline"])


# ── Pipeline ──


@router.post("/pipeline/run", response_model=PipelineRunResult)
async def trigger_pipeline(req: PipelineRunRequest | None = None, db: AsyncSession = Depends(get_db)):
    """Run the full pipeline: fetch → apply."""
    dry_run = req.dry_run if req else None
    max_apps = req.max_applications if req else None
    return await run_pipeline(db, dry_run=dry_run, max_applications=max_apps)


@router.post("/jobs/{job_id}/apply")
async def trigger_apply_single(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobListing).where(JobListing.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return {"error": "Job not found"}
    log = await apply_to_job(db, job)
    return {"status": log.status.value, "error": log.error_message}


@router.post("/apply/run")
async def trigger_apply_all(max_applications: int | None = None, db: AsyncSession = Depends(get_db)):
    submitted, failed, skipped = await apply_to_all_jobs(db, max_applications)
    return {"applications_submitted": submitted, "applications_failed": failed, "applications_skipped": skipped}


# ── Application Logs ──


@router.get("/applications")
async def list_applications(db: AsyncSession = Depends(get_db)):
    """List all application logs with job title, company, and URL."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(ApplicationLog)
        .options(selectinload(ApplicationLog.job).selectinload(JobListing.company))
        .order_by(ApplicationLog.created_at.desc())
    )
    logs = result.scalars().all()
    out = []
    for log in logs:
        entry = {
            "id": log.id,
            "job_id": log.job_id,
            "status": log.status.value if log.status else "unknown",
            "applied_at": log.applied_at.isoformat() if log.applied_at else None,
            "error_message": log.error_message or "",
            "screenshot_path": log.screenshot_path or "",
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "job_title": log.job.title if log.job else "Unknown",
            "company_name": log.job.company.name if log.job and log.job.company else "Unknown",
            "job_url": log.job.url if log.job else "",
        }
        out.append(entry)
    return out
