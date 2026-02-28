"""API routes for Q&A bank and form scanning."""

import json
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import QAEntry, JobFormField
from app.schemas.schemas import QAEntryOut, QAAnswerRequest, ScanResult, UnmatchedQuestion
from app.services.form_scanner import scan_jobs, get_unanswered_questions, seed_qa_from_profile

router = APIRouter(prefix="/api/qa", tags=["qa"])


@router.get("", response_model=list[QAEntryOut])
async def list_qa_entries(
    unanswered_only: bool = False,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all Q&A bank entries with optional filters."""
    query = select(QAEntry).order_by(QAEntry.category, QAEntry.display_question)
    if unanswered_only:
        query = query.where(QAEntry.answer.is_(None))
    if category:
        query = query.where(QAEntry.category == category)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/answer")
async def answer_questions(req: QAAnswerRequest, db: AsyncSession = Depends(get_db)):
    """Batch answer multiple Q&A entries."""
    updated = 0
    for item in req.answers:
        qa_id = item.get("qa_id")
        answer = item.get("answer", "")
        if qa_id and answer:
            result = await db.execute(select(QAEntry).where(QAEntry.id == qa_id))
            qa = result.scalar_one_or_none()
            if qa:
                qa.answer = answer
                updated += 1
    await db.commit()
    return {"updated": updated}


@router.get("/unanswered", response_model=list[UnmatchedQuestion])
async def get_unanswered(
    job_ids: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get all unanswered questions, optionally filtered to specific jobs."""
    ids = [int(x) for x in job_ids.split(",")] if job_ids else None
    questions = await get_unanswered_questions(db, job_ids=ids)
    return questions


@router.post("/scan", response_model=ScanResult)
async def trigger_scan(
    job_ids: list[int] | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Scan job application forms to discover questions."""
    summary = await scan_jobs(db, job_ids=job_ids)
    return ScanResult(**summary)


@router.post("/seed")
async def seed_from_profile(db: AsyncSession = Depends(get_db)):
    """One-time seed of Q&A bank from existing profile application_answers."""
    count = await seed_qa_from_profile(db)
    return {"seeded": count}


@router.get("/scan-status")
async def scan_status(db: AsyncSession = Depends(get_db)):
    """Check if all eligible jobs are scanned and how many questions need answers."""
    from app.models.models import JobListing, JobStatus

    # Count eligible jobs
    eligible_result = await db.execute(
        select(func.count(JobListing.id)).where(
            JobListing.status.in_([JobStatus.NEW, JobStatus.MATCHED])
        )
    )
    total_eligible = eligible_result.scalar() or 0

    # Count scanned jobs (have at least one form field)
    scanned_result = await db.execute(
        select(func.count(func.distinct(JobFormField.job_id)))
    )
    total_scanned = scanned_result.scalar() or 0

    # Count unanswered questions
    unanswered_result = await db.execute(
        select(func.count(QAEntry.id)).where(QAEntry.answer.is_(None))
    )
    total_unanswered = unanswered_result.scalar() or 0

    # Count total Q&A entries
    total_qa_result = await db.execute(select(func.count(QAEntry.id)))
    total_qa = total_qa_result.scalar() or 0

    return {
        "eligible_jobs": total_eligible,
        "scanned_jobs": total_scanned,
        "total_questions": total_qa,
        "unanswered_questions": total_unanswered,
        "all_answered": total_unanswered == 0,
        "ready_to_apply": total_scanned > 0 and total_unanswered == 0,
    }
