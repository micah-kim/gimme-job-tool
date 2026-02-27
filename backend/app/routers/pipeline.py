"""API routes for pipeline execution and application logs."""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import ApplicationLog, JobListing, TailoredResume
from app.schemas.schemas import (
    ApplicationLogOut,
    PipelineRunRequest,
    PipelineRunResult,
    TailoredResumeOut,
)
from app.services.ai_analyzer import analyze_new_jobs
from app.services.auto_apply import apply_to_job, apply_to_matched_jobs
from app.services.pipeline import run_pipeline
from app.services.resume_tailor import tailor_resumes_for_matched_jobs

router = APIRouter(prefix="/api", tags=["pipeline"])


# ── Pipeline ──


@router.post("/pipeline/run", response_model=PipelineRunResult)
async def trigger_pipeline(req: PipelineRunRequest | None = None, db: AsyncSession = Depends(get_db)):
    """Run the full pipeline: fetch → analyze → tailor → apply."""
    dry_run = req.dry_run if req else None
    max_apps = req.max_applications if req else None
    return await run_pipeline(db, dry_run=dry_run, max_applications=max_apps)


@router.post("/jobs/analyze")
async def trigger_analysis(db: AsyncSession = Depends(get_db)):
    count = await analyze_new_jobs(db)
    return {"jobs_analyzed": count}


@router.post("/jobs/tailor")
async def trigger_tailoring(db: AsyncSession = Depends(get_db)):
    count = await tailor_resumes_for_matched_jobs(db)
    return {"resumes_tailored": count}


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
    count = await apply_to_matched_jobs(db, max_applications)
    return {"applications_submitted": count}


# ── Application Logs ──


@router.get("/applications", response_model=list[ApplicationLogOut])
async def list_applications(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApplicationLog).order_by(ApplicationLog.created_at.desc()))
    return result.scalars().all()


# ── Tailored Resumes ──


@router.get("/jobs/{job_id}/resume", response_model=TailoredResumeOut | None)
async def get_tailored_resume(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TailoredResume).where(TailoredResume.job_id == job_id))
    return result.scalar_one_or_none()
