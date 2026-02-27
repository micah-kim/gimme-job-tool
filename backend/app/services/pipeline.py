"""Pipeline orchestrator — runs the full fetch → analyze → tailor → apply pipeline."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemas import PipelineRunResult
from app.services.ai_analyzer import analyze_new_jobs
from app.services.auto_apply import apply_to_matched_jobs
from app.services.job_fetcher import fetch_all_jobs
from app.services.resume_tailor import tailor_resumes_for_matched_jobs

logger = logging.getLogger(__name__)


async def run_pipeline(
    db: AsyncSession,
    dry_run: bool | None = None,
    max_applications: int | None = None,
) -> PipelineRunResult:
    """Execute the full pipeline end-to-end."""
    from app.core.config import settings

    # Override dry_run if specified
    original_dry_run = settings.dry_run
    if dry_run is not None:
        settings.dry_run = dry_run

    result = PipelineRunResult()

    try:
        # Step 1: Fetch new jobs
        logger.info("Pipeline step 1/4: Fetching jobs...")
        result.jobs_fetched = await fetch_all_jobs(db)

        # Step 2: Analyze new jobs with AI
        logger.info("Pipeline step 2/4: Analyzing jobs...")
        result.jobs_analyzed = await analyze_new_jobs(db)

        # Step 3: Tailor resumes for matched jobs
        logger.info("Pipeline step 3/4: Tailoring resumes...")
        result.resumes_tailored = await tailor_resumes_for_matched_jobs(db)

        # Step 4: Apply to matched jobs
        logger.info("Pipeline step 4/4: Applying to jobs...")
        result.applications_submitted = await apply_to_matched_jobs(db, max_applications)

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        result.errors.append(str(e))
    finally:
        settings.dry_run = original_dry_run

    logger.info(
        f"Pipeline complete: {result.jobs_fetched} fetched, {result.jobs_analyzed} analyzed, "
        f"{result.resumes_tailored} tailored, {result.applications_submitted} applied"
    )
    return result
