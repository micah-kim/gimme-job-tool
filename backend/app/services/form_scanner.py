"""Form scanner — discovers all form fields from job applications without filling them."""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from openai import AzureOpenAI
from playwright.sync_api import sync_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    Company,
    JobFormField,
    JobListing,
    JobStatus,
    QAEntry,
    UserProfile,
)

logger = logging.getLogger(__name__)

# ── Category auto-tagging based on keywords ──
_CATEGORY_KEYWORDS = {
    "work_auth": ["authorized", "legally authorized", "sponsorship", "visa", "work permit", "employment eligibility"],
    "demographic": ["gender", "race", "ethnicity", "hispanic", "latino", "veteran", "disability", "lgbtq", "sexual orientation"],
    "education": ["school", "university", "degree", "field of study", "discipline", "graduation", "gpa"],
    "experience": ["years of experience", "current company", "current title", "current employer"],
    "compensation": ["salary", "compensation", "pay"],
    "logistics": ["relocate", "start date", "available", "location", "commute"],
    "legal": ["non-compete", "non-solicitation", "background check", "previously worked", "ever worked"],
    "online": ["website", "github", "portfolio", "linkedin", "url"],
    "misc": ["how did you hear", "referred", "referral", "over 18", "accommodation", "privacy"],
}


def _categorize_question(label_text: str) -> str:
    """Auto-categorize a question based on label keywords."""
    lower = label_text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "other"


def _normalize_question(label_text: str) -> str:
    """Normalize a question for deduplication."""
    import re
    text = label_text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)  # remove punctuation
    text = re.sub(r'\s+', ' ', text)  # collapse whitespace
    return text.strip()


# ── Label synonym mapping (same as auto_apply._LABEL_TO_ANSWER_KEY) ──
_SYNONYM_GROUPS = {
    "authorized_to_work": ["authorized", "legally authorized", "legal authorization", "work authorization"],
    "sponsorship_needed": ["sponsorship", "visa", "work permit"],
    "gender": ["gender"],
    "race_ethnicity": ["race", "ethnicity"],
    "hispanic_latino": ["hispanic", "latino"],
    "veteran_status": ["veteran"],
    "disability_status": ["disability"],
    "lgbtq": ["lgbtq"],
    "sexual_orientation": ["sexual orientation"],
    "school_name": ["school", "university", "college"],
    "degree": ["degree"],
    "field_of_study": ["field of study", "discipline", "major"],
    "graduation_year": ["graduation"],
    "years_of_experience": ["years of experience"],
    "how_did_you_hear": ["how did you hear"],
    "non_compete": ["non-compete", "non-solicitation"],
    "previously_worked_here": ["previously worked", "ever worked for", "have you ever worked"],
    "willing_to_relocate": ["relocate"],
    "over_18": ["over 18"],
    "requires_accommodation": ["accommodation"],
    "website_url": ["website"],
    "github_url": ["github"],
    "portfolio_url": ["portfolio"],
    "linkedin_url": ["linkedin"],
}


def _match_to_synonym_group(label_text: str) -> str | None:
    """Match a label to a synonym group key, or return None."""
    lower = label_text.lower()
    for group_key, keywords in _SYNONYM_GROUPS.items():
        if any(kw in lower for kw in keywords):
            return group_key
    return None


def _scan_greenhouse_form(page, apply_url: str) -> list[dict]:
    """Open a Greenhouse embed form and extract all custom fields."""
    fields = []
    try:
        page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        custom_fields = page.locator("#custom_fields > div.field").all()
        logger.info(f"Found {len(custom_fields)} custom fields on form")

        for field_div in custom_fields:
            try:
                label_el = field_div.locator("label").first
                if label_el.count() == 0:
                    continue
                label_text = label_el.inner_text().strip().replace("*", "").strip()
                label_first_line = label_text.split("\n")[0].strip()
                if not label_first_line:
                    continue

                # Check required
                is_required = (
                    field_div.locator("span.asterisk").count() > 0
                    or field_div.locator("[aria-required='true']").count() > 0
                )

                # Determine field type and extract options
                field_type = "text"
                options = []

                select_el = field_div.locator("select")
                if select_el.count() > 0:
                    field_type = "select"
                    options = select_el.first.evaluate("""el => {
                        return Array.from(el.options)
                            .filter(o => o.value !== '')
                            .map(o => [o.text.trim(), o.value]);
                    }""")
                elif field_div.locator("textarea").count() > 0:
                    field_type = "textarea"
                elif field_div.locator("input[type='checkbox']").count() > 0:
                    field_type = "checkbox"

                fields.append({
                    "label": label_first_line,
                    "field_type": field_type,
                    "options": options,
                    "is_required": is_required,
                })
            except Exception as e:
                logger.warning(f"Error extracting field: {e}")

    except Exception as e:
        logger.error(f"Error scanning form at {apply_url}: {e}")
        raise

    return fields


def _scan_lever_form(page, apply_url: str) -> list[dict]:
    """Open a Lever application form and extract all custom fields."""
    fields = []
    try:
        page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # Lever uses .application-question for ALL questions (standard + custom + EEO)
        # We skip standard fields (name, email, phone, resume, location, company, URLs)
        # and focus on custom-question and EEO fields
        SKIP_NAMES = {"name", "email", "phone", "location", "org", "resume",
                       "urls[LinkedIn]", "urls[GitHub]", "urls[Portfolio]"}

        questions = page.locator(".application-question.custom-question, .eeo-section .application-question").all()
        logger.info(f"Found {len(questions)} custom/EEO questions on Lever form")

        for q_div in questions:
            try:
                # Get the first label (the question label, not option labels)
                label_el = q_div.locator("> label, > .application-label").first
                if label_el.count() == 0:
                    # Try getting the first direct text label
                    label_el = q_div.locator("label").first
                if label_el.count() == 0:
                    continue

                label_text = label_el.inner_text().strip()
                # Clean: remove ✱ and extra whitespace
                label_text = label_text.replace("✱", "").replace("*", "").strip()
                label_first_line = label_text.split("\n")[0].strip()
                if not label_first_line or len(label_first_line) < 3:
                    continue

                # Check required: ✱ in original text or required attr on input
                original_text = label_el.inner_text()
                is_required = "✱" in original_text or q_div.locator("[required]").count() > 0

                # Determine field type and options
                field_type = "text"
                options = []

                select_el = q_div.locator("select")
                radio_els = q_div.locator("input[type='radio']")
                checkbox_els = q_div.locator("input[type='checkbox']")
                textarea_el = q_div.locator("textarea")
                text_el = q_div.locator("input[type='text']")

                if select_el.count() > 0:
                    field_type = "select"
                    options = select_el.first.evaluate("""el => {
                        return Array.from(el.options)
                            .filter(o => o.value !== '')
                            .map(o => [o.text.trim(), o.value]);
                    }""")
                elif radio_els.count() > 0:
                    field_type = "select"  # treat radio as select for Q&A purposes
                    # Extract radio option labels
                    option_labels = q_div.locator("li label, .radio-option label").all()
                    for opt_label in option_labels:
                        try:
                            opt_text = opt_label.inner_text().strip()
                            if opt_text:
                                options.append([opt_text, opt_text])
                        except Exception:
                            pass
                elif checkbox_els.count() > 1:
                    field_type = "checkbox"  # multi-select checkboxes
                    option_labels = q_div.locator("li label").all()
                    for opt_label in option_labels:
                        try:
                            opt_text = opt_label.inner_text().strip()
                            if opt_text:
                                options.append([opt_text, opt_text])
                        except Exception:
                            pass
                elif textarea_el.count() > 0:
                    field_type = "textarea"
                elif checkbox_els.count() == 1:
                    field_type = "checkbox"

                # Skip if this is a standard field we already handle
                input_el = q_div.locator("input, select, textarea").first
                if input_el.count() > 0:
                    input_name = input_el.evaluate("el => el.name") or ""
                    if input_name in SKIP_NAMES:
                        continue

                fields.append({
                    "label": label_first_line,
                    "field_type": field_type,
                    "options": options,
                    "is_required": is_required,
                })
            except Exception as e:
                logger.warning(f"Error extracting Lever field: {e}")

    except Exception as e:
        logger.error(f"Error scanning Lever form at {apply_url}: {e}")
        raise

    return fields


def _scan_job_form_sync(job_url: str, ats_type: str, board_token: str, external_id: str) -> list[dict]:
    """Scan a single job form in a sync Playwright context. Returns list of field dicts."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        try:
            if ats_type == "greenhouse":
                apply_url = f"https://boards.greenhouse.io/embed/job_app?for={board_token}&token={external_id}"
                logger.info(f"Scanning Greenhouse form: {apply_url}")
                fields = _scan_greenhouse_form(page, apply_url)
            elif ats_type == "lever":
                apply_url = job_url.rstrip('/') + '/apply'
                logger.info(f"Scanning Lever form: {apply_url}")
                fields = _scan_lever_form(page, apply_url)
            else:
                # Ashby or unknown — basic scan attempt
                page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                fields = []
                logger.warning(f"No scanner implemented for ATS type: {ats_type}")

            return fields
        except Exception as e:
            logger.error(f"Scan failed for {job_url}: {e}")
            return []
        finally:
            browser.close()


async def match_field_to_qa(
    db: AsyncSession, label_text: str, field_type: str, options_json: str,
) -> QAEntry | None:
    """Try to match a form field to an existing Q&A entry. Returns matched entry or None."""
    normalized = _normalize_question(label_text)

    # 1. Exact match on canonical_question
    result = await db.execute(
        select(QAEntry).where(QAEntry.canonical_question == normalized)
    )
    qa = result.scalar_one_or_none()
    if qa:
        return qa

    # 2. Synonym group match — find existing QA with same synonym group
    group_key = _match_to_synonym_group(label_text)
    if group_key:
        # Check if there's already a QA entry whose canonical matches any synonym in this group
        all_qa = (await db.execute(select(QAEntry))).scalars().all()
        for existing_qa in all_qa:
            existing_group = _match_to_synonym_group(existing_qa.display_question)
            if existing_group == group_key:
                return existing_qa

    return None


async def scan_jobs(
    db: AsyncSession, job_ids: list[int] | None = None,
) -> dict:
    """Scan form fields for eligible jobs. Returns scan summary."""
    import asyncio

    # Get eligible jobs (NEW or MATCHED status, not yet scanned)
    query = select(JobListing).join(Company)
    if job_ids:
        query = query.where(JobListing.id.in_(job_ids))
    else:
        query = query.where(JobListing.status.in_([JobStatus.NEW, JobStatus.MATCHED]))

    result = await db.execute(query)
    jobs = result.scalars().all()

    # Filter to jobs that haven't been scanned yet
    jobs_to_scan = []
    for job in jobs:
        existing = await db.execute(
            select(JobFormField).where(JobFormField.job_id == job.id).limit(1)
        )
        if existing.scalar_one_or_none() is None:
            jobs_to_scan.append(job)

    logger.info(f"Scanning {len(jobs_to_scan)} jobs (of {len(jobs)} eligible)")

    summary = {"jobs_scanned": 0, "total_fields": 0, "matched_fields": 0, "unmatched_fields": 0, "errors": []}

    # Get company data for board tokens
    company_cache = {}

    for job in jobs_to_scan:
        if job.company_id not in company_cache:
            co_result = await db.execute(select(Company).where(Company.id == job.company_id))
            company_cache[job.company_id] = co_result.scalar_one_or_none()

        company = company_cache[job.company_id]
        board_token = company.board_token if company else ""
        ats_type = company.ats_type.value.lower() if company and company.ats_type else "greenhouse"

        try:
            # Run Playwright scan in thread
            loop = asyncio.get_event_loop()
            fields = await loop.run_in_executor(
                None,
                _scan_job_form_sync,
                job.url,
                ats_type,
                board_token,
                job.external_id,
            )

            summary["jobs_scanned"] += 1

            for field_data in fields:
                options_json = json.dumps(field_data.get("options", []))

                # Try to match to existing QA
                qa_entry = await match_field_to_qa(
                    db, field_data["label"], field_data["field_type"], options_json,
                )

                # If no match, create a new QA entry (unanswered)
                if not qa_entry:
                    normalized = _normalize_question(field_data["label"])
                    qa_entry = QAEntry(
                        canonical_question=normalized,
                        display_question=field_data["label"],
                        field_type=field_data["field_type"],
                        answer=None,
                        category=_categorize_question(field_data["label"]),
                    )
                    db.add(qa_entry)
                    await db.flush()  # get the ID

                # Create job_form_field linking to qa_entry
                form_field = JobFormField(
                    job_id=job.id,
                    label_text=field_data["label"],
                    field_type=field_data["field_type"],
                    options_json=options_json,
                    is_required=field_data.get("is_required", False),
                    qa_entry_id=qa_entry.id,
                    scanned_at=datetime.utcnow(),
                )
                db.add(form_field)

                summary["total_fields"] += 1
                if qa_entry.answer:
                    summary["matched_fields"] += 1
                else:
                    summary["unmatched_fields"] += 1

            logger.info(f"Scanned job {job.id} ({job.title}): {len(fields)} fields found")

        except Exception as e:
            logger.error(f"Failed to scan job {job.id}: {e}")
            summary["errors"].append(f"Job {job.id}: {str(e)}")

    await db.commit()
    return summary


async def get_unanswered_questions(db: AsyncSession, job_ids: list[int] | None = None) -> list[dict]:
    """Get all Q&A entries that have no answer, with form options from the first matching field."""
    query = select(QAEntry).where(QAEntry.answer.is_(None))
    result = await db.execute(query)
    unanswered = result.scalars().all()

    questions = []
    for qa in unanswered:
        # Get the first form field for this QA to get options
        field_query = select(JobFormField).where(JobFormField.qa_entry_id == qa.id)
        if job_ids:
            field_query = field_query.where(JobFormField.job_id.in_(job_ids))
        field_result = await db.execute(field_query)
        fields = field_result.scalars().all()

        if not fields:
            continue

        options = json.loads(fields[0].options_json) if fields[0].options_json else []
        job_count = len(set(f.job_id for f in fields))

        questions.append({
            "qa_id": qa.id,
            "display_question": qa.display_question,
            "field_type": qa.field_type,
            "category": qa.category,
            "options": options,
            "job_count": job_count,
        })

    return questions


async def seed_qa_from_profile(db: AsyncSession) -> int:
    """Seed the Q&A bank from the user's existing profile application_answers. Returns count of entries created."""
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        return 0

    answers = json.loads(profile.application_answers) if profile.application_answers else {}
    count = 0

    # Map profile answer keys to display questions
    _KEY_TO_DISPLAY = {
        "authorized_to_work": "Are you legally authorized to work in the United States?",
        "sponsorship_needed": "Will you now or in the future require sponsorship for employment visa status?",
        "school_name": "School Name",
        "degree": "Degree",
        "field_of_study": "Field of Study / Discipline",
        "graduation_year": "Graduation Year",
        "years_of_experience": "Years of Experience",
        "current_company": "Current Company",
        "current_title": "Current Job Title",
        "desired_salary": "Desired Salary",
        "willing_to_relocate": "Are you willing to relocate?",
        "available_start_date": "Available Start Date",
        "website_url": "Website URL",
        "github_url": "GitHub URL",
        "portfolio_url": "Portfolio URL",
        "gender": "What is your gender?",
        "race_ethnicity": "How would you identify your race?",
        "hispanic_latino": "Are you Hispanic or Latino?",
        "veteran_status": "Are you a veteran?",
        "disability_status": "Do you have a disability?",
        "lgbtq": "Do you identify as LGBTQ+?",
        "sexual_orientation": "How would you describe your sexual orientation?",
        "over_18": "Are you over 18 years of age?",
        "how_did_you_hear": "How did you hear about this job?",
        "requires_accommodation": "Do you require any accommodations?",
        "non_compete": "Are you currently bound by a non-compete agreement?",
        "previously_worked_here": "Have you previously worked for this company?",
        "location_city": "Location (City)",
    }

    _KEY_TO_FIELD_TYPE = {
        "authorized_to_work": "select",
        "sponsorship_needed": "select",
        "gender": "select",
        "race_ethnicity": "select",
        "hispanic_latino": "select",
        "veteran_status": "select",
        "disability_status": "select",
        "lgbtq": "select",
        "sexual_orientation": "select",
        "willing_to_relocate": "select",
        "over_18": "select",
        "requires_accommodation": "select",
        "non_compete": "select",
        "previously_worked_here": "select",
    }

    for key, value in answers.items():
        if not value or key == "salary_currency":
            continue

        display = _KEY_TO_DISPLAY.get(key, key.replace("_", " ").title())
        normalized = _normalize_question(display)
        field_type = _KEY_TO_FIELD_TYPE.get(key, "text")
        category = _categorize_question(display)

        # Check if already exists
        existing = await db.execute(
            select(QAEntry).where(QAEntry.canonical_question == normalized)
        )
        if existing.scalar_one_or_none():
            continue

        qa = QAEntry(
            canonical_question=normalized,
            display_question=display,
            field_type=field_type,
            answer=value,
            category=category,
        )
        db.add(qa)
        count += 1

    await db.commit()
    logger.info(f"Seeded {count} Q&A entries from profile")
    return count
