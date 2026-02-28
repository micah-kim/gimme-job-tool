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


def _answer_custom_question(client: AzureOpenAI, question: str, profile_data: dict, options: list[str] | None = None) -> str:
    """Use AI to answer a custom application question. If options provided, pick the best one."""
    answers = profile_data.get("application_answers", {})
    if options:
        prompt = (
            f"Candidate: {profile_data.get('first_name', '')} {profile_data.get('last_name', '')}, "
            f"Email: {profile_data.get('email', '')}\n"
            f"Profile answers: {json.dumps(answers)}\n\n"
            f"Application question: {question}\n"
            f"Available options: {options}\n\n"
            f"Pick the single best option from the list above. Reply with ONLY the exact option text, nothing else."
        )
    else:
        prompt = (
            f"Candidate: {profile_data.get('first_name', '')} {profile_data.get('last_name', '')}, "
            f"Email: {profile_data.get('email', '')}\n"
            f"Profile answers: {json.dumps(answers)}\n\n"
            f"Application question: {question}\n\n"
            f"Provide a brief, professional answer:"
        )
    try:
        response = client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=[
                {
                    "role": "system",
                    "content": "You are helping fill out a job application. Answer concisely based on the candidate's profile. If picking from options, reply with ONLY the exact option text.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"AI answer failed for '{question}': {e}")
        return ""


# Maps label keywords to profile application_answers keys
_LABEL_TO_ANSWER_KEY = {
    "authorized": "authorized_to_work",
    "legally authorized": "authorized_to_work",
    "sponsorship": "sponsorship_needed",
    "how did you hear": "how_did_you_hear",
    "non-compete": "non_compete",
    "non-solicitation": "non_compete",
    "previously worked": "previously_worked_here",
    "ever worked for": "previously_worked_here",
    "have you ever worked": "previously_worked_here",
    "gender": "gender",
    "race": "race_ethnicity",
    "ethnicity": "race_ethnicity",
    "veteran": "veteran_status",
    "disability": "disability_status",
    "over 18": "over_18",
    "relocate": "willing_to_relocate",
    "accommodation": "requires_accommodation",
    "school": "school_name",
    "university": "school_name",
    "degree": "degree",
    "field of study": "field_of_study",
    "discipline": "field_of_study",
    "graduation": "graduation_year",
    "years of experience": "years_of_experience",
    "salary": "desired_salary",
    "website": "website_url",
    "github": "github_url",
    "portfolio": "portfolio_url",
    "linkedin": "linkedin_url",
}


def _match_label_to_answer(label_text: str, profile_data: dict) -> str | None:
    """Try to match a form field label to a profile answer value."""
    label_lower = label_text.lower().strip()
    answers = profile_data.get("application_answers", {})

    # Special: privacy policy → always acknowledge
    if "privacy" in label_lower and ("acknowledge" in label_lower or "policy" in label_lower):
        return "__ACKNOWLEDGE__"

    for keyword, answer_key in _LABEL_TO_ANSWER_KEY.items():
        if keyword in label_lower:
            # Check application_answers first
            if answer_key in answers and answers[answer_key]:
                return answers[answer_key]
            # Check top-level profile fields (e.g. linkedin_url)
            val = profile_data.get(answer_key, "")
            if val:
                return val
            return None
    return None


def _best_option_match(answer: str, options: list[str]) -> str | None:
    """Find the best matching option for a profile answer. Returns option value or None."""
    if not answer or not options:
        return None
    answer_lower = answer.lower().strip()

    # Exact match
    for opt_text, opt_value in options:
        if answer_lower == opt_text.lower().strip():
            return opt_value

    # Substring match (answer contained in option or vice versa)
    for opt_text, opt_value in options:
        opt_lower = opt_text.lower().strip()
        if answer_lower in opt_lower or opt_lower in answer_lower:
            return opt_value

    # Keyword match for Yes/No answers
    if answer_lower in ("yes", "no"):
        for opt_text, opt_value in options:
            opt_lower = opt_text.lower().strip()
            if answer_lower == "yes" and opt_lower.startswith("yes"):
                return opt_value
            if answer_lower == "no" and opt_lower.startswith("no"):
                return opt_value

    return None


def _fill_greenhouse_form(
    page: SyncPage, profile_data: dict, resume_path: str, ai_client: AzureOpenAI,
) -> None:
    """Fill out a Greenhouse application form — field-aware, required-only."""

    # Phase 1: Standard fields
    for selector, value in [
        ("input#first_name", profile_data.get("first_name", "")),
        ("input#last_name", profile_data.get("last_name", "")),
        ("input#email", profile_data.get("email", "")),
        ("input#phone", profile_data.get("phone", "")),
    ]:
        try:
            el = page.locator(selector)
            if el.count() > 0 and value:
                el.fill(value)
        except Exception:
            pass

    # Location (City) autocomplete
    try:
        answers = profile_data.get("application_answers", {})
        location_city = answers.get("location_city", "") or profile_data.get("job_location", "")
        if location_city:
            loc_input = page.locator("#location_autocomplete_root input[type='text'], input[name*='location'], input[placeholder*='city' i], input[placeholder*='location' i]").first
            if loc_input.count() > 0:
                loc_input.fill(location_city)
                page.wait_for_timeout(1500)
                # Select first autocomplete suggestion if dropdown appeared
                suggestion = page.locator(".pac-item, .autocomplete-suggestion, [role='option'], .location-autocomplete__option, ul.suggestions li, .pelias-results li").first
                if suggestion.count() > 0:
                    suggestion.click()
                    page.wait_for_timeout(500)
    except Exception as e:
        logger.warning(f"Could not fill location: {e}")

    # Resume upload
    try:
        file_input = page.locator("input[type='file']").first
        if file_input.count() > 0 and resume_path:
            file_input.set_input_files(resume_path)
            page.wait_for_timeout(1000)
    except Exception as e:
        logger.warning(f"Could not upload resume: {e}")

    # Phase 2: Custom fields — iterate each div.field in #custom_fields
    try:
        custom_fields = page.locator("#custom_fields > div.field").all()
        logger.info(f"Found {len(custom_fields)} custom fields on Greenhouse form")

        for field_div in custom_fields:
            try:
                _process_greenhouse_custom_field(field_div, profile_data, ai_client, page)
            except Exception as e:
                logger.warning(f"Error processing custom field: {e}")
    except Exception as e:
        logger.warning(f"Error iterating custom fields: {e}")


def _process_greenhouse_custom_field(
    field_div, profile_data: dict, ai_client: AzureOpenAI, page: SyncPage,
) -> None:
    """Process a single custom field div in a Greenhouse form."""
    # Extract label text
    label_el = field_div.locator("label").first
    if label_el.count() == 0:
        return
    label_text = label_el.inner_text().strip()
    # Clean label: remove asterisk markers and extra whitespace
    label_text = label_text.replace("*", "").strip()
    # Get first line only (labels can have long descriptions)
    label_first_line = label_text.split("\n")[0].strip()

    # Determine if required
    is_required = False
    asterisk = field_div.locator("span.asterisk")
    if asterisk.count() > 0:
        is_required = True

    # Also check aria-required on inputs/selects inside
    req_els = field_div.locator("[aria-required='true']")
    if req_els.count() > 0:
        is_required = True

    if not is_required:
        logger.debug(f"Skipping non-required field: {label_first_line}")
        return

    logger.info(f"Processing required field: {label_first_line}")

    # Determine field type
    select_el = field_div.locator("select")
    text_input = field_div.locator("input[type='text']")
    textarea = field_div.locator("textarea")
    checkbox = field_div.locator("input[type='checkbox']")

    # Match label to profile answer
    profile_answer = _match_label_to_answer(label_first_line, profile_data)

    if select_el.count() > 0:
        _fill_greenhouse_select(select_el.first, label_first_line, profile_answer, profile_data, ai_client)
    elif text_input.count() > 0:
        _fill_greenhouse_text(text_input.first, label_first_line, profile_answer, profile_data, ai_client)
    elif textarea.count() > 0:
        _fill_greenhouse_text(textarea.first, label_first_line, profile_answer, profile_data, ai_client)
    elif checkbox.count() > 0 and profile_answer == "__ACKNOWLEDGE__":
        try:
            if not checkbox.first.is_checked():
                checkbox.first.check()
        except Exception:
            pass


def _fill_greenhouse_select(
    select_el, label_text: str, profile_answer: str | None, profile_data: dict, ai_client: AzureOpenAI,
) -> None:
    """Fill a required select/dropdown field on a Greenhouse form."""
    # Get all options with their values
    options = select_el.evaluate("""el => {
        return Array.from(el.options)
            .filter(o => o.value !== '')
            .map(o => [o.text.trim(), o.value]);
    }""")

    if not options:
        return

    selected_value = None

    # Special: privacy policy — always pick the acknowledgment option
    if profile_answer == "__ACKNOWLEDGE__":
        selected_value = options[0][1] if options else None
    elif profile_answer:
        selected_value = _best_option_match(profile_answer, options)

    # AI fallback if no profile match
    if not selected_value:
        option_texts = [o[0] for o in options]
        ai_answer = _answer_custom_question(ai_client, label_text, profile_data, option_texts)
        if ai_answer:
            # Try to match AI answer to actual option
            for opt_text, opt_value in options:
                if ai_answer.strip().lower() == opt_text.strip().lower():
                    selected_value = opt_value
                    break
            if not selected_value:
                # Fuzzy match
                for opt_text, opt_value in options:
                    if ai_answer.strip().lower() in opt_text.strip().lower() or opt_text.strip().lower() in ai_answer.strip().lower():
                        selected_value = opt_value
                        break
            if not selected_value and options:
                # Last resort: pick first non-empty option
                selected_value = options[0][1]

    if selected_value:
        try:
            select_el.select_option(value=selected_value)
            logger.info(f"Selected '{selected_value}' for field: {label_text[:50]}")
        except Exception as e:
            logger.warning(f"Could not select option for '{label_text[:50]}': {e}")


def _fill_greenhouse_text(
    input_el, label_text: str, profile_answer: str | None, profile_data: dict, ai_client: AzureOpenAI,
) -> None:
    """Fill a required text input/textarea field on a Greenhouse form."""
    answer = profile_answer if profile_answer and profile_answer != "__ACKNOWLEDGE__" else None

    if not answer:
        answer = _answer_custom_question(ai_client, label_text, profile_data)

    if answer:
        try:
            input_el.fill(answer)
            logger.info(f"Filled text '{answer[:30]}...' for field: {label_text[:50]}")
        except Exception as e:
            logger.warning(f"Could not fill text for '{label_text[:50]}': {e}")


def _fill_ashby_form(
    page: SyncPage, profile_data: dict, resume_path: str, ai_client: AzureOpenAI,
) -> None:
    """Fill out an Ashby application form."""
    for selector, value in [
        ("input[name='_systemfield_name']", f"{profile_data.get('first_name', '')} {profile_data.get('last_name', '')}"),
        ("input[name='_systemfield_email']", profile_data.get("email", "")),
        ("input[name='_systemfield_phone']", profile_data.get("phone", "")),
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
        if linkedin_el.count() > 0 and profile_data.get("linkedin_url"):
            linkedin_el.fill(profile_data["linkedin_url"])
    except Exception:
        pass


def _fill_lever_form(
    page: SyncPage, profile_data: dict, resume_path: str, ai_client: AzureOpenAI,
) -> None:
    """Fill out a Lever application form."""
    for selector, value in [
        ("input[name='name']", f"{profile_data.get('first_name', '')} {profile_data.get('last_name', '')}"),
        ("input[name='email']", profile_data.get("email", "")),
        ("input[name='phone']", profile_data.get("phone", "")),
        ("input[name='urls[LinkedIn]']", profile_data.get("linkedin_url", "")),
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


def _fill_generic_form(
    page: SyncPage, profile_data: dict, resume_path: str, ai_client: AzureOpenAI,
) -> None:
    """Best-effort form fill for unknown ATS layouts."""
    for selector, value in [
        ("input[name*='first_name'], input[placeholder*='First']", profile_data.get("first_name", "")),
        ("input[name*='last_name'], input[placeholder*='Last']", profile_data.get("last_name", "")),
        ("input[name*='email'], input[type='email']", profile_data.get("email", "")),
        ("input[name*='phone'], input[type='tel']", profile_data.get("phone", "")),
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
    import re
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    ai_client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )

    screenshot_path = ""
    submit_result = {"success": False, "error": ""}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not dry_run)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        url_lower = job_url.lower()

        # For Greenhouse jobs
        if "gh_jid=" in url_lower or "greenhouse" in url_lower or board_token:
            gh_match = re.search(r'gh_jid=(\d+)', job_url)
            if not gh_match:
                gh_match = re.search(r'/jobs/(\d+)', job_url)
            if not gh_match:
                gh_match = re.search(r'/positions/(\d+)', job_url)
            if gh_match:
                gh_job_id = gh_match.group(1)
                if not board_token:
                    bm = re.search(r'boards\.greenhouse\.io/(\w+)', job_url)
                    board_token = bm.group(1) if bm else ""
                if board_token:
                    apply_url = f"https://boards.greenhouse.io/embed/job_app?for={board_token}&token={gh_job_id}"
                else:
                    apply_url = job_url
                logger.info(f"Greenhouse apply URL: {apply_url}")
                page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
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

            _fill_greenhouse_form(page, profile_data, resume_path, ai_client)

        elif "ashby" in url_lower or "jobs.ashbyhq.com" in url_lower:
            page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            apply_btn = page.locator("button:has-text('Apply'), a:has-text('Apply')")
            if apply_btn.count() > 0:
                try:
                    apply_btn.first.click()
                    page.wait_for_timeout(2000)
                except Exception:
                    pass
            _fill_ashby_form(page, profile_data, resume_path, ai_client)

        elif "lever.co" in url_lower or "jobs.lever.co" in url_lower:
            apply_url = job_url.rstrip('/') + '/apply'
            page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            _fill_lever_form(page, profile_data, resume_path, ai_client)

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
            _fill_generic_form(page, profile_data, resume_path, ai_client)

        # Take pre-submit screenshot
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        screenshot_path = os.path.join(SCREENSHOTS_DIR, f"apply_{ts}.png")
        page.screenshot(path=screenshot_path, full_page=True)

        if not dry_run:
            submit_result = _submit_and_verify(page)
            post_ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            post_screenshot = os.path.join(SCREENSHOTS_DIR, f"apply_{post_ts}_result.png")
            page.screenshot(path=post_screenshot, full_page=True)
            screenshot_path = post_screenshot

        if dry_run:
            logger.info("Dry run: browser will stay open for 30 seconds for inspection...")
            page.wait_for_timeout(30000)

        browser.close()

    return {"screenshot_path": screenshot_path, "submit_result": submit_result}


def _submit_and_verify(page: SyncPage) -> dict:
    """Click submit and verify the submission went through."""
    submit_btn = page.locator(
        "input[type='submit'], button[type='submit'], button:has-text('Submit Application'), button:has-text('Submit')"
    ).first
    if submit_btn.count() == 0:
        return {"success": False, "error": "No submit button found on the page"}

    try:
        submit_btn.click()
    except Exception as e:
        return {"success": False, "error": f"Could not click submit: {e}"}

    page.wait_for_timeout(5000)

    page_text = page.inner_text("body").lower()
    success_indicators = [
        "thank", "thanks for your submission", "application received",
        "application has been submitted", "successfully submitted",
        "we have received your application", "confirmation",
    ]
    for indicator in success_indicators:
        if indicator in page_text:
            logger.info(f"Submission verified: found '{indicator}' on page")
            return {"success": True, "error": ""}

    # Check for error indicators
    error_elements = page.locator(".error, .field-error, .validation-error, [class*='error'], .field_with_errors").all()
    error_texts = []
    for err_el in error_elements[:5]:
        try:
            text = err_el.inner_text().strip()
            if text and len(text) < 200:
                error_texts.append(text)
        except Exception:
            pass

    if error_texts:
        error_msg = "; ".join(error_texts)
        logger.warning(f"Submission had errors: {error_msg}")
        return {"success": False, "error": f"Form validation errors: {error_msg}"}

    required_errors = page.locator("[aria-invalid='true'], .required-error, input:invalid").all()
    if required_errors:
        return {"success": False, "error": f"Required fields not filled: {len(required_errors)} field(s) still invalid"}

    current_url = page.url.lower()
    if "thank" in current_url or "confirm" in current_url or "success" in current_url:
        return {"success": True, "error": ""}

    return {"success": False, "error": "Could not verify submission — no success or error indicators found"}


async def apply_to_job(db: AsyncSession, job: JobListing, dry_run: bool = False) -> ApplicationLog:
    """Apply to a single job using browser automation (runs Playwright in a thread)."""
    # Get profile
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        raise ValueError("No user profile configured")

    resume_path = profile.base_resume_path or ""

    # Serialize profile data for thread
    answers = {}
    if profile.application_answers:
        try:
            answers = json.loads(profile.application_answers) if isinstance(profile.application_answers, str) else profile.application_answers
        except Exception:
            answers = {}

    profile_data = {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "email": profile.email,
        "phone": profile.phone or "",
        "linkedin_url": profile.linkedin_url or "",
        "preferences": profile.preferences or "{}",
        "application_answers": answers,
        "job_location": job.location or "",
    }

    # Check for existing application log (from a previous failed attempt)
    existing_log_result = await db.execute(
        select(ApplicationLog).where(ApplicationLog.job_id == job.id)
    )
    app_log = existing_log_result.scalar_one_or_none()
    if app_log:
        app_log.status = ApplicationStatus.PENDING
        app_log.error_message = ""
    else:
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
        submit_result = pw_result.get("submit_result", {"success": False, "error": ""})

        if dry_run:
            # Dry run: don't persist anything, don't change job status
            app_log.status = ApplicationStatus.SUBMITTED
            logger.info(f"[DRY RUN] Filled form for job {job.id}: {job.title}")
        else:
            # Live run: check if submission was verified
            if submit_result.get("success"):
                app_log.status = ApplicationStatus.SUBMITTED
                app_log.applied_at = datetime.utcnow()
                app_log.error_message = ""
                if not app_log.id:
                    db.add(app_log)
                job.status = JobStatus.APPLIED
                await db.commit()
                logger.info(f"Successfully applied to job {job.id}: {job.title}")
            else:
                error_msg = submit_result.get("error", "Unknown submission error")
                app_log.status = ApplicationStatus.FAILED
                app_log.error_message = error_msg
                if not app_log.id:
                    db.add(app_log)
                job.status = JobStatus.FAILED
                await db.commit()
                logger.warning(f"Submission failed for job {job.id}: {error_msg}")

    except Exception as e:
        app_log.status = ApplicationStatus.FAILED
        app_log.error_message = str(e)
        if not dry_run:
            if not app_log.id:
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
