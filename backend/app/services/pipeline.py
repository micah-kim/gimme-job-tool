"""Pipeline orchestrator — runs the full fetch → scan → apply pipeline."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemas import PipelineRunResult, ScanResult
from app.services.auto_apply import apply_to_all_jobs
from app.services.form_scanner import scan_jobs, get_unanswered_questions, seed_qa_from_profile
from app.services.job_fetcher import fetch_all_jobs

logger = logging.getLogger(__name__)


async def run_pipeline(
    db: AsyncSession,
    dry_run: bool | None = None,
    max_applications: int | None = None,
) -> PipelineRunResult:
    """Execute the full pipeline: fetch jobs → scan forms → apply (if all questions answered)."""
    from app.core.config import settings

    original_dry_run = settings.dry_run
    if dry_run is not None:
        settings.dry_run = dry_run

    result = PipelineRunResult(dry_run=settings.dry_run)

    try:
        # Step 1: Fetch new jobs from all tracked companies
        logger.info("Pipeline step 1/3: Fetching jobs...")
        result.jobs_fetched = await fetch_all_jobs(db)

        # Step 2: Scan forms to discover questions
        logger.info("Pipeline step 2/3: Scanning forms...")
        # Seed Q&A bank from profile if this is the first time
        await seed_qa_from_profile(db)
        scan_summary = await scan_jobs(db)
        result.jobs_scanned = scan_summary.get("jobs_scanned", 0)
        result.questions_found = scan_summary.get("total_fields", 0)
        result.questions_unanswered = scan_summary.get("unmatched_fields", 0)

        # Step 3: Apply — only if all questions have answers
        unanswered = await get_unanswered_questions(db)
        if unanswered:
            logger.info(f"Pipeline paused: {len(unanswered)} questions need answers before applying")
            result.needs_review = True
        else:
            logger.info("Pipeline step 3/3: Applying to jobs...")
            submitted, failed, skipped = await apply_to_all_jobs(db, max_applications, dry_run=settings.dry_run)
            result.forms_filled = submitted
            result.applications_failed = failed
            result.applications_skipped = skipped
            result.needs_review = False

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        result.errors.append(str(e))
    finally:
        settings.dry_run = original_dry_run

    logger.info(
        f"Pipeline complete: {result.jobs_fetched} fetched, {result.jobs_scanned} scanned, "
        f"{result.forms_filled} filled, {result.applications_failed} failed, "
        f"{result.applications_skipped} skipped"
    )
    return result
