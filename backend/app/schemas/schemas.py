from datetime import datetime

from pydantic import BaseModel


# ── User Profile ──


class UserPreferences(BaseModel):
    titles: list[str] = []
    excluded_titles: list[str] = []
    locations: list[str] = []
    min_yoe: int = 0
    max_yoe: int = 99
    keywords: list[str] = []
    deal_breakers: list[str] = []


class ApplicationAnswers(BaseModel):
    # Work authorization
    authorized_to_work: str = ""  # "Yes" / "No"
    sponsorship_needed: str = ""  # "Yes" / "No"
    # Education
    school_name: str = ""
    degree: str = ""  # "Bachelor's", "Master's", "PhD", "Associate's", "High School", etc.
    field_of_study: str = ""
    graduation_year: str = ""
    # Work details
    years_of_experience: str = ""
    current_company: str = ""
    current_title: str = ""
    desired_salary: str = ""
    salary_currency: str = "USD"
    willing_to_relocate: str = ""  # "Yes" / "No"
    available_start_date: str = ""
    # Online presence
    website_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""
    # EEO / Demographics (voluntary self-identification)
    gender: str = ""  # "Male", "Female", "Decline To Self Identify"
    race_ethnicity: str = ""  # "Decline To Self Identify", "Asian", "White", etc.
    hispanic_latino: str = ""  # "Yes", "No", "Decline To Self Identify"
    veteran_status: str = ""  # "I am not a protected veteran", "Decline to Self Identify"
    disability_status: str = ""  # "No", "Yes", "I do not want to answer"
    lgbtq: str = ""  # "Decline to state", "Yes", "No"
    sexual_orientation: str = ""  # "Decline to state"
    # Misc common questions
    over_18: str = ""  # "Yes" / "No"
    how_did_you_hear: str = ""
    requires_accommodation: str = ""  # "Yes" / "No"
    # Additional common required questions
    non_compete: str = ""  # "Yes" / "No" — non-compete/non-solicitation agreements
    previously_worked_here: str = ""  # "Yes" / "No" — have you worked at this company before
    location_city: str = ""  # preferred city for the Location (City) field


class UserProfileCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    linkedin_url: str = ""
    preferences: UserPreferences = UserPreferences()
    application_answers: ApplicationAnswers = ApplicationAnswers()


class UserProfileOut(UserProfileCreate):
    id: int
    base_resume_path: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Company ──


class CompanyCreate(BaseModel):
    name: str
    ats_type: str  # "greenhouse" or "ashby"
    board_token: str


class CompanyOut(CompanyCreate):
    id: int
    last_scraped_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Job Listing ──


class JobListingOut(BaseModel):
    id: int
    company_id: int
    external_id: str
    title: str
    location: str
    department: str
    description_text: str
    url: str
    compensation: str
    posted_at: datetime | None
    fetched_at: datetime
    status: str

    model_config = {"from_attributes": True}


# ── Job Score ──


class JobScoreOut(BaseModel):
    id: int
    job_id: int
    relevance_score: float
    reasoning: str
    matched_criteria: str
    flagged_dealbreakers: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Application Log ──


class ApplicationLogOut(BaseModel):
    id: int
    job_id: int
    status: str
    applied_at: datetime | None
    error_message: str
    screenshot_path: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Pipeline ──


class PipelineRunRequest(BaseModel):
    dry_run: bool | None = None
    max_applications: int | None = None


class PipelineRunResult(BaseModel):
    dry_run: bool = False
    jobs_fetched: int = 0
    jobs_scanned: int = 0
    questions_found: int = 0
    questions_unanswered: int = 0
    needs_review: bool = False
    forms_filled: int = 0
    applications_failed: int = 0
    applications_skipped: int = 0
    errors: list[str] = []


# ── Q&A Bank ──


class QAEntryOut(BaseModel):
    id: int
    canonical_question: str
    display_question: str
    field_type: str
    answer: str | None = None
    category: str = "other"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QAAnswerRequest(BaseModel):
    """Batch answer multiple Q&A entries."""
    answers: list[dict]  # [{"qa_id": 1, "answer": "Yes"}, ...]


class JobFormFieldOut(BaseModel):
    id: int
    job_id: int
    label_text: str
    field_type: str
    options_json: str = "[]"
    is_required: bool = False
    qa_entry_id: int | None = None
    scanned_at: datetime

    model_config = {"from_attributes": True}


class ScanResult(BaseModel):
    jobs_scanned: int = 0
    total_fields: int = 0
    matched_fields: int = 0
    unmatched_fields: int = 0
    errors: list[str] = []


class UnmatchedQuestion(BaseModel):
    """An unanswered Q&A entry with associated form options."""
    qa_id: int
    display_question: str
    field_type: str
    category: str
    options: list[list[str]] = []  # [[text, value], ...] from first job that has this Q
    job_count: int = 1  # how many jobs ask this question
