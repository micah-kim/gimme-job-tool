"""Pipeline orchestrator — runs the full fetch → apply pipeline."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemas import PipelineRunResult
from app.services.auto_apply import apply_to_all_jobs
from app.services.job_fetcher import fetch_all_jobs

logger = logging.getLogger(__name__)


async def run_pipeline(
    db: AsyncSession,
    dry_run: bool | None = None,
    max_applications: int | None = None,
) -> PipelineRunResult:
    """Execute the full pipeline: fetch jobs → apply to eligible ones."""
    from app.core.config import settings

    original_dry_run = settings.dry_run
    if dry_run is not None:
        settings.dry_run = dry_run

    result = PipelineRunResult(dry_run=settings.dry_run)

    try:
        # Step 1: Fetch new jobs from all tracked companies
        logger.info("Pipeline step 1/2: Fetching jobs...")
        result.jobs_fetched = await fetch_all_jobs(db)

        # Step 2: Apply to all eligible jobs (skips APPLIED/FAILED)
        logger.info("Pipeline step 2/2: Applying to jobs...")
        submitted, failed, skipped = await apply_to_all_jobs(db, max_applications, dry_run=settings.dry_run)
        result.forms_filled = submitted
        result.applications_failed = failed
        result.applications_skipped = skipped

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        result.errors.append(str(e))
    finally:
        settings.dry_run = original_dry_run

    logger.info(
        f"Pipeline complete: {result.jobs_fetched} fetched, {result.forms_filled} filled, "
        f"{result.applications_failed} failed, {result.applications_skipped} skipped"
    )
    return result
