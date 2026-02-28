"""Auto-apply engine using Playwright for browser automation."""

import asyncio
import json
import logging
import os
from datetime import datetime
from functools import partial

from openai import AzureOpenAI
from playwright.sync_api import Page as SyncPage, sync_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    ApplicationLog,
    ApplicationStatus,
    JobListing,
    JobStatus,
    UserProfile,
)

logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "screenshots")


def _answer_custom_question(client: AzureOpenAI, question: str, profile: UserProfile) -> str:
    """Use AI to answer a custom application question."""
    response = client.chat.completions.create(
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


def _fill_greenhouse_form(
    page: SyncPage, profile: UserProfile, resume_path: str, cover_letter: str, ai_client: AzureOpenAI,
) -> None:
    """Fill out a Greenhouse application form."""
    for selector, value in [
        ("input#first_name", profile.first_name),
        ("input#last_name", profile.last_name),
        ("input#email", profile.email),
        ("input#phone", profile.phone),
    ]:
        try:
            el = page.locator(selector)
            if el.count() > 0 and value:
                el.fill(value)
        except Exception:
            pass

    try:
        file_input = page.locator("input[type='file']").first
        if file_input.count() > 0 and resume_path:
            file_input.set_input_files(resume_path)
    except Exception as e:
        logger.warning(f"Could not upload resume: {e}")

    try:
        cover_el = page.locator("textarea#cover_letter, textarea[name*='cover']").first
        if cover_el.count() > 0 and cover_letter:
            cover_el.fill(cover_letter)
    except Exception:
        pass

    try:
        custom_fields = page.locator(
            "div.field:not(:has(#first_name)):not(:has(#last_name)):not(:has(#email)):not(:has(#phone)) textarea, "
            "div.field:not(:has(#first_name)):not(:has(#last_name)):not(:has(#email)):not(:has(#phone)) input[type='text']"
        ).all()
        for field in custom_fields:
            label_el = field.evaluate("el => el.closest('.field')?.querySelector('label')?.textContent")
            if label_el:
                answer = _answer_custom_question(ai_client, label_el, profile)
                field.fill(answer)
    except Exception as e:
        logger.warning(f"Error handling custom fields: {e}")


def _fill_ashby_form(
    page: SyncPage, profile: UserProfile, resume_path: str, cover_letter: str, ai_client: AzureOpenAI,
) -> None:
    """Fill out an Ashby application form."""
    for selector, value in [
        ("input[name='_systemfield_name']", f"{profile.first_name} {profile.last_name}"),
        ("input[name='_systemfield_email']", profile.email),
        ("input[name='_systemfield_phone']", profile.phone),
    ]:
        try:
            el = page.locator(selector)
            if el.count() > 0 and value:
                el.fill(value)
        except Exception:
            pass

    try:
        file_input = page.locator("input[type='file']").first
        if file_input.count() > 0 and resume_path:
            file_input.set_input_files(resume_path)
    except Exception as e:
        logger.warning(f"Could not upload resume: {e}")

    try:
        linkedin_el = page.locator("input[name*='linkedin'], input[placeholder*='linkedin']").first
        if linkedin_el.count() > 0 and profile.linkedin_url:
            linkedin_el.fill(profile.linkedin_url)
    except Exception:
        pass


def _fill_lever_form(
    page: SyncPage, profile: UserProfile, resume_path: str, cover_letter: str, ai_client: AzureOpenAI,
) -> None:
    """Fill out a Lever application form."""
    for selector, value in [
        ("input[name='name']", f"{profile.first_name} {profile.last_name}"),
        ("input[name='email']", profile.email),
        ("input[name='phone']", profile.phone),
        ("input[name='org']", ""),
        ("input[name='urls[LinkedIn]']", profile.linkedin_url),
        ("input[name='urls[GitHub]']", ""),
        ("input[name='urls[Portfolio]']", ""),
        ("input[name='urls[Other]']", ""),
    ]:
        try:
            el = page.locator(selector)
            if el.count() > 0 and value:
                el.fill(value)
        except Exception:
            pass

    try:
        file_input = page.locator("input[type='file'][name='resume']").first
        if file_input.count() > 0 and resume_path:
            file_input.set_input_files(resume_path)
    except Exception as e:
        logger.warning(f"Could not upload resume (Lever): {e}")

    try:
        comments_el = page.locator("textarea[name='comments']").first
        if comments_el.count() > 0 and cover_letter:
            comments_el.fill(cover_letter)
    except Exception:
        pass

    try:
        custom_questions = page.locator(".custom-question").all()
        for q in custom_questions:
            label_text = q.locator("label").first.text_content()
            if not label_text:
                continue
            text_input = q.locator("input[type='text'], textarea").first
            if text_input.count() > 0:
                answer = _answer_custom_question(ai_client, label_text.strip(), profile)
                text_input.fill(answer)
    except Exception as e:
        logger.warning(f"Error handling Lever custom fields: {e}")


def _fill_generic_form(
    page: SyncPage, profile: UserProfile, resume_path: str, cover_letter: str, ai_client: AzureOpenAI,
) -> None:
    """Best-effort form fill for unknown ATS layouts."""
    for selector, value in [
        ("input[name*='first_name'], input[placeholder*='First']", profile.first_name),
        ("input[name*='last_name'], input[placeholder*='Last']", profile.last_name),
        ("input[name*='email'], input[type='email']", profile.email),
        ("input[name*='phone'], input[type='tel']", profile.phone),
    ]:
        try:
            el = page.locator(selector).first
            if el.count() > 0 and value:
                el.fill(value)
        except Exception:
            pass

    try:
        file_input = page.locator("input[type='file']").first
        if file_input.count() > 0 and resume_path:
            file_input.set_input_files(resume_path)
    except Exception:
        pass


def _run_playwright_apply(job_url: str, profile_data: dict, resume_path: str, dry_run: bool, board_token: str = "") -> dict:
    """Run Playwright in a sync context (called from a thread). Returns result dict."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    ai_client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )

    # Reconstruct a simple profile-like object for form fillers
    class ProfileProxy:
        pass
    profile = ProfileProxy()
    for k, v in profile_data.items():
        setattr(profile, k, v)

    screenshot_path = ""
    with sync_playwright() as p:
        # Dry run: open visible browser so user can watch; live: headless
        browser = p.chromium.launch(headless=not dry_run)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        url_lower = job_url.lower()
        cover_letter = ""

        # For Greenhouse jobs with custom career pages, go directly to the hosted apply form
        if "gh_jid=" in url_lower or "greenhouse" in url_lower or board_token:
            # Extract job ID and try the standard Greenhouse application URL
            import re
            gh_match = re.search(r'gh_jid=(\d+)', job_url)
            if not gh_match:
                gh_match = re.search(r'/jobs/(\d+)', job_url)
            if not gh_match:
                gh_match = re.search(r'/positions/(\d+)', job_url)
            if gh_match:
                gh_job_id = gh_match.group(1)
                # Use the board_token passed from the company record
                if not board_token:
                    bm = re.search(r'boards\.greenhouse\.io/(\w+)', job_url)
                    board_token = bm.group(1) if bm else ""

                if board_token:
                    apply_url = f"https://boards.greenhouse.io/embed/job_app?for={board_token}&token={gh_job_id}"
                else:
                    apply_url = job_url
                logger.info(f"Greenhouse apply URL: {apply_url}")
                page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
                # Wait for form fields to render
                page.wait_for_timeout(3000)
            else:
                page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

            # If we landed on a listing page, try clicking "Apply" button
            apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply')")
            if apply_btn.count() > 0:
                try:
                    apply_btn.first.click()
                    page.wait_for_timeout(3000)
                except Exception:
                    pass

            _fill_greenhouse_form(page, profile, resume_path, cover_letter, ai_client)

        elif "ashby" in url_lower or "jobs.ashbyhq.com" in url_lower:
            page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            # Ashby: click Apply button to reveal the form
            apply_btn = page.locator("button:has-text('Apply'), a:has-text('Apply')")
            if apply_btn.count() > 0:
                try:
                    apply_btn.first.click()
                    page.wait_for_timeout(2000)
                except Exception:
                    pass
            _fill_ashby_form(page, profile, resume_path, cover_letter, ai_client)

        elif "lever.co" in url_lower or "jobs.lever.co" in url_lower:
            # Lever: navigate to /apply at the end of the URL
            apply_url = job_url.rstrip('/') + '/apply'
            page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            _fill_lever_form(page, profile, resume_path, cover_letter, ai_client)

        else:
            page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply')")
            if apply_btn.count() > 0:
                try:
                    apply_btn.first.click()
                    page.wait_for_timeout(3000)
                except Exception:
                    pass
            _fill_generic_form(page, profile, resume_path, cover_letter, ai_client)

        if not dry_run:
            submit_btn = page.locator(
                "button[type='submit'], input[type='submit'], button:has-text('Submit'), button:has-text('Apply')"
            ).first
            if submit_btn.count() > 0:
                submit_btn.click()
                page.wait_for_timeout(3000)

        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        screenshot_path = os.path.join(SCREENSHOTS_DIR, f"apply_{ts}.png")
        page.screenshot(path=screenshot_path, full_page=True)

        if dry_run:
            logger.info("Dry run: browser will stay open for 30 seconds for inspection...")
            page.wait_for_timeout(30000)

        browser.close()

    return {"screenshot_path": screenshot_path}


async def apply_to_job(db: AsyncSession, job: JobListing, dry_run: bool = False) -> ApplicationLog:
    """Apply to a single job using browser automation (runs Playwright in a thread)."""
    # Get profile
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        raise ValueError("No user profile configured")

    resume_path = profile.base_resume_path or ""

    # Serialize profile data for thread
    profile_data = {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "email": profile.email,
        "phone": profile.phone or "",
        "linkedin_url": profile.linkedin_url or "",
        "preferences": profile.preferences or "{}",
    }

    app_log = ApplicationLog(job_id=job.id, status=ApplicationStatus.PENDING)

    # Get the board token from the company for Greenhouse URL construction
    board_token = ""
    try:
        if job.company:
            board_token = job.company.board_token or ""
    except Exception:
        # Company not loaded; query it
        from app.models.models import Company
        company_result = await db.execute(select(Company).where(Company.id == job.company_id))
        company = company_result.scalar_one_or_none()
        if company:
            board_token = company.board_token or ""

    try:
        # Run Playwright in a separate thread to avoid Windows event loop issues
        loop = asyncio.get_event_loop()
        pw_result = await loop.run_in_executor(
            None,
            partial(_run_playwright_apply, job.url, profile_data, resume_path, dry_run, board_token),
        )

        app_log.screenshot_path = pw_result.get("screenshot_path", "")

        if dry_run:
            # Dry run: don't persist anything, don't change job status
            app_log.status = ApplicationStatus.SUBMITTED
            logger.info(f"[DRY RUN] Filled form for job {job.id}: {job.title}")
        else:
            # Live run: persist the log and update job status
            app_log.status = ApplicationStatus.SUBMITTED
            app_log.applied_at = datetime.utcnow()
            db.add(app_log)
            job.status = JobStatus.APPLIED
            await db.commit()
            logger.info(f"Applied to job {job.id}: {job.title}")

    except Exception as e:
        app_log.status = ApplicationStatus.FAILED
        app_log.error_message = str(e)
        if not dry_run:
            db.add(app_log)
            job.status = JobStatus.FAILED
            await db.commit()
        logger.error(f"Failed to apply to job {job.id}: {e}")

    return app_log


async def apply_to_all_jobs(
    db: AsyncSession, max_applications: int | None = None, dry_run: bool = False
) -> tuple[int, int, int]:
    """Apply to all eligible jobs (NEW or MATCHED, not already APPLIED/FAILED).
    Returns (submitted, failed, skipped) counts."""
    limit = max_applications or settings.max_applications_per_run

    from sqlalchemy.orm import selectinload

    # Get jobs that haven't been applied to or failed
    result = await db.execute(
        select(JobListing)
        .options(selectinload(JobListing.company))
        .where(JobListing.status.in_([JobStatus.NEW, JobStatus.MATCHED]))
        .order_by(JobListing.fetched_at.desc())
        .limit(limit)
    )
    jobs = result.scalars().all()
    if not jobs:
        logger.info("No eligible jobs to apply to")
        return 0, 0, 0

    submitted = 0
    failed = 0
    for job in jobs:
        log = await apply_to_job(db, job, dry_run=dry_run)
        if log.status == ApplicationStatus.SUBMITTED:
            submitted += 1
        else:
            failed += 1

    skipped_result = await db.execute(
        select(JobListing)
        .where(JobListing.status.in_([JobStatus.APPLIED, JobStatus.FAILED]))
    )
    skipped = len(skipped_result.scalars().all())

    logger.info(f"Applied to {submitted}/{len(jobs)} jobs, {failed} failed, {skipped} skipped")
    return submitted, failed, skipped
