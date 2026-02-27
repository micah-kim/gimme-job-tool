"""Auto-apply engine using Playwright for browser automation."""

import json
import logging
import os
from datetime import datetime

from openai import AsyncAzureOpenAI
from playwright.async_api import Page, async_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    ApplicationLog,
    ApplicationStatus,
    JobListing,
    JobStatus,
    TailoredResume,
    UserProfile,
)

logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "screenshots")


async def _answer_custom_question(client: AsyncAzureOpenAI, question: str, profile: UserProfile) -> str:
    """Use AI to answer a custom application question."""
    response = await client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=[
            {
                "role": "system",
                "content": "You are helping fill out a job application. Answer the question concisely and professionally based on the candidate's profile. If unsure, give a reasonable default answer.",
            },
            {
                "role": "user",
                "content": f"Candidate: {profile.first_name} {profile.last_name}, Email: {profile.email}\nPreferences: {profile.preferences}\n\nApplication question: {question}\n\nProvide a brief answer:",
            },
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


async def _fill_greenhouse_form(
    page: Page,
    profile: UserProfile,
    resume_path: str,
    cover_letter: str,
    ai_client: AsyncAzureOpenAI,
) -> None:
    """Fill out a Greenhouse application form."""
    # Standard fields
    name_selectors = [
        ("input#first_name", profile.first_name),
        ("input#last_name", profile.last_name),
        ("input#email", profile.email),
        ("input#phone", profile.phone),
    ]
    for selector, value in name_selectors:
        try:
            el = page.locator(selector)
            if await el.count() > 0 and value:
                await el.fill(value)
        except Exception:
            pass

    # Resume upload
    try:
        file_input = page.locator("input[type='file']").first
        if await file_input.count() > 0 and resume_path:
            await file_input.set_input_files(resume_path)
    except Exception as e:
        logger.warning(f"Could not upload resume: {e}")

    # Cover letter textarea
    try:
        cover_el = page.locator("textarea#cover_letter, textarea[name*='cover']").first
        if await cover_el.count() > 0 and cover_letter:
            await cover_el.fill(cover_letter)
    except Exception:
        pass

    # Handle custom questions — find labeled text inputs/textareas without known IDs
    try:
        custom_fields = await page.locator(
            "div.field:not(:has(#first_name)):not(:has(#last_name)):not(:has(#email)):not(:has(#phone)) textarea, "
            "div.field:not(:has(#first_name)):not(:has(#last_name)):not(:has(#email)):not(:has(#phone)) input[type='text']"
        ).all()
        for field in custom_fields:
            label_el = await field.evaluate(
                "el => el.closest('.field')?.querySelector('label')?.textContent"
            )
            if label_el:
                answer = await _answer_custom_question(ai_client, label_el, profile)
                await field.fill(answer)
    except Exception as e:
        logger.warning(f"Error handling custom fields: {e}")


async def _fill_ashby_form(
    page: Page,
    profile: UserProfile,
    resume_path: str,
    cover_letter: str,
    ai_client: AsyncAzureOpenAI,
) -> None:
    """Fill out an Ashby application form."""
    field_map = [
        ("input[name='_systemfield_name']", f"{profile.first_name} {profile.last_name}"),
        ("input[name='_systemfield_email']", profile.email),
        ("input[name='_systemfield_phone']", profile.phone),
    ]
    for selector, value in field_map:
        try:
            el = page.locator(selector)
            if await el.count() > 0 and value:
                await el.fill(value)
        except Exception:
            pass

    # Resume upload
    try:
        file_input = page.locator("input[type='file']").first
        if await file_input.count() > 0 and resume_path:
            await file_input.set_input_files(resume_path)
    except Exception as e:
        logger.warning(f"Could not upload resume: {e}")

    # LinkedIn URL
    try:
        linkedin_el = page.locator("input[name*='linkedin'], input[placeholder*='linkedin']").first
        if await linkedin_el.count() > 0 and profile.linkedin_url:
            await linkedin_el.fill(profile.linkedin_url)
    except Exception:
        pass


async def _fill_lever_form(
    page: Page,
    profile: UserProfile,
    resume_path: str,
    cover_letter: str,
    ai_client: AsyncAzureOpenAI,
) -> None:
    """Fill out a Lever application form."""
    # Lever uses a single "Full name" field
    field_map = [
        ("input[name='name']", f"{profile.first_name} {profile.last_name}"),
        ("input[name='email']", profile.email),
        ("input[name='phone']", profile.phone),
        ("input[name='org']", ""),  # Current company — filled if available
        ("input[name='urls[LinkedIn]']", profile.linkedin_url),
        ("input[name='urls[GitHub]']", ""),
        ("input[name='urls[Portfolio]']", ""),
        ("input[name='urls[Other]']", ""),
    ]
    for selector, value in field_map:
        try:
            el = page.locator(selector)
            if await el.count() > 0 and value:
                await el.fill(value)
        except Exception:
            pass

    # Resume upload
    try:
        file_input = page.locator("input[type='file'][name='resume']").first
        if await file_input.count() > 0 and resume_path:
            await file_input.set_input_files(resume_path)
    except Exception as e:
        logger.warning(f"Could not upload resume (Lever): {e}")

    # Cover letter / additional info textarea
    try:
        comments_el = page.locator("textarea[name='comments']").first
        if await comments_el.count() > 0 and cover_letter:
            await comments_el.fill(cover_letter)
    except Exception:
        pass

    # Handle custom questions (Lever uses div.custom-question containers)
    try:
        custom_questions = await page.locator(".custom-question").all()
        for q in custom_questions:
            label_text = await q.locator("label").first.text_content()
            if not label_text:
                continue
            text_input = q.locator("input[type='text'], textarea").first
            if await text_input.count() > 0:
                answer = await _answer_custom_question(ai_client, label_text.strip(), profile)
                await text_input.fill(answer)
    except Exception as e:
        logger.warning(f"Error handling Lever custom fields: {e}")


async def _fill_generic_form(
    page: Page,
    profile: UserProfile,
    resume_path: str,
    cover_letter: str,
    ai_client: AsyncAzureOpenAI,
) -> None:
    """Best-effort form fill for unknown ATS layouts."""
    # Try common field patterns
    patterns = [
        ("input[name*='first_name'], input[placeholder*='First']", profile.first_name),
        ("input[name*='last_name'], input[placeholder*='Last']", profile.last_name),
        ("input[name*='email'], input[type='email']", profile.email),
        ("input[name*='phone'], input[type='tel']", profile.phone),
    ]
    for selector, value in patterns:
        try:
            el = page.locator(selector).first
            if await el.count() > 0 and value:
                await el.fill(value)
        except Exception:
            pass

    # File upload
    try:
        file_input = page.locator("input[type='file']").first
        if await file_input.count() > 0 and resume_path:
            await file_input.set_input_files(resume_path)
    except Exception:
        pass


async def apply_to_job(db: AsyncSession, job: JobListing) -> ApplicationLog:
    """Apply to a single job using browser automation."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    # Get profile and tailored resume
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        raise ValueError("No user profile configured")

    result = await db.execute(
        select(TailoredResume).where(TailoredResume.job_id == job.id)
    )
    tailored = result.scalar_one_or_none()
    resume_path = tailored.resume_pdf_path if tailored else profile.base_resume_path
    cover_letter = tailored.cover_letter if tailored else ""

    ai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )

    app_log = ApplicationLog(job_id=job.id, status=ApplicationStatus.PENDING)
    db.add(app_log)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            await page.goto(job.url, wait_until="networkidle", timeout=30000)

            # Detect ATS type from URL and fill accordingly
            url_lower = job.url.lower()
            if "greenhouse" in url_lower or "boards.greenhouse.io" in url_lower:
                await _fill_greenhouse_form(page, profile, resume_path, cover_letter, ai_client)
            elif "ashby" in url_lower or "jobs.ashbyhq.com" in url_lower:
                await _fill_ashby_form(page, profile, resume_path, cover_letter, ai_client)
            elif "lever.co" in url_lower or "jobs.lever.co" in url_lower:
                await _fill_lever_form(page, profile, resume_path, cover_letter, ai_client)
            else:
                await _fill_generic_form(page, profile, resume_path, cover_letter, ai_client)

            # Submit
            if not settings.dry_run:
                submit_btn = page.locator(
                    "button[type='submit'], input[type='submit'], button:has-text('Submit'), button:has-text('Apply')"
                ).first
                if await submit_btn.count() > 0:
                    await submit_btn.click()
                    await page.wait_for_timeout(3000)

            # Screenshot
            ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"job_{job.id}_{ts}.png")
            await page.screenshot(path=screenshot_path, full_page=True)

            await browser.close()

        app_log.status = ApplicationStatus.SUBMITTED
        app_log.applied_at = datetime.utcnow()
        app_log.screenshot_path = screenshot_path
        job.status = JobStatus.APPLIED
        logger.info(f"{'[DRY RUN] ' if settings.dry_run else ''}Applied to job {job.id}: {job.title}")

    except Exception as e:
        app_log.status = ApplicationStatus.FAILED
        app_log.error_message = str(e)
        job.status = JobStatus.FAILED
        logger.error(f"Failed to apply to job {job.id}: {e}")

    await db.commit()
    return app_log


async def apply_to_matched_jobs(db: AsyncSession, max_applications: int | None = None) -> int:
    """Apply to all matched jobs with tailored resumes. Returns count of applications."""
    limit = max_applications or settings.max_applications_per_run

    result = await db.execute(
        select(JobListing)
        .where(JobListing.status == JobStatus.MATCHED)
        .join(TailoredResume)
        .outerjoin(ApplicationLog)
        .where(ApplicationLog.id.is_(None))
        .limit(limit)
    )
    jobs = result.scalars().all()
    if not jobs:
        logger.info("No matched jobs to apply to")
        return 0

    applied = 0
    for job in jobs:
        log = await apply_to_job(db, job)
        if log.status == ApplicationStatus.SUBMITTED:
            applied += 1

    logger.info(f"Applied to {applied}/{len(jobs)} jobs")
    return applied
