"""AI-powered job analysis — scores jobs against user preferences using Azure OpenAI."""

import json
import logging

from openai import AsyncAzureOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import JobListing, JobScore, JobStatus, UserProfile

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a job matching assistant. Given a job description and a candidate's preferences, 
evaluate how well the job matches. Return a JSON object with:
- "relevance_score": integer 0-100
- "reasoning": brief explanation (2-3 sentences)
- "matched_criteria": list of criteria the job matches
- "flagged_dealbreakers": list of any deal-breakers found

Be strict: if the job clearly doesn't match the candidate's target titles, location, or experience level, 
score it low. If deal-breakers are present, score below 30."""


def _build_user_prompt(job: JobListing, preferences: dict) -> str:
    return f"""## Candidate Preferences
- Target titles: {preferences.get('titles', [])}
- Preferred locations: {preferences.get('locations', [])}
- Years of experience range: {preferences.get('min_yoe', 0)}-{preferences.get('max_yoe', 99)}
- Keywords to match: {preferences.get('keywords', [])}
- Deal-breakers (reject if found): {preferences.get('deal_breakers', [])}

## Job Details
- Title: {job.title}
- Location: {job.location}
- Department: {job.department}
- Compensation: {job.compensation}

## Job Description
{job.description_text[:4000]}

Evaluate this job against the candidate's preferences. Return ONLY valid JSON."""


async def analyze_job(
    client: AsyncAzureOpenAI, job: JobListing, preferences: dict
) -> dict:
    """Score a single job against user preferences."""
    response = await client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(job, preferences)},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return json.loads(content)


async def analyze_new_jobs(db: AsyncSession) -> int:
    """Analyze all jobs with status=NEW. Returns count of analyzed jobs."""
    # Get user profile/preferences
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        logger.warning("No user profile found — skipping analysis")
        return 0

    preferences = json.loads(profile.preferences) if isinstance(profile.preferences, str) else profile.preferences

    # Get unanalyzed jobs
    result = await db.execute(select(JobListing).where(JobListing.status == JobStatus.NEW))
    jobs = result.scalars().all()
    if not jobs:
        logger.info("No new jobs to analyze")
        return 0

    client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )

    analyzed = 0
    for job in jobs:
        try:
            result_data = await analyze_job(client, job, preferences)
            score = result_data.get("relevance_score", 0)

            job_score = JobScore(
                job_id=job.id,
                relevance_score=score,
                reasoning=result_data.get("reasoning", ""),
                matched_criteria=json.dumps(result_data.get("matched_criteria", [])),
                flagged_dealbreakers=json.dumps(result_data.get("flagged_dealbreakers", [])),
            )
            db.add(job_score)

            job.status = (
                JobStatus.MATCHED if score >= settings.min_relevance_score else JobStatus.REJECTED
            )
            analyzed += 1
        except Exception as e:
            logger.error(f"Error analyzing job {job.id} ({job.title}): {e}")

    await db.commit()
    logger.info(f"Analyzed {analyzed} jobs, {sum(1 for j in jobs if j.status == JobStatus.MATCHED)} matched")
    return analyzed
