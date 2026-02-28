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
    gender: str = ""  # "Male", "Female", "Non-binary", "Prefer not to say"
    race_ethnicity: str = ""  # "White", "Black or African American", "Asian", "Hispanic or Latino", "Native American or Alaska Native", "Native Hawaiian or Other Pacific Islander", "Two or More Races", "Prefer not to say"
    veteran_status: str = ""  # "I am a veteran", "I am not a veteran", "Prefer not to say"
    disability_status: str = ""  # "Yes, I have a disability", "No, I do not have a disability", "Prefer not to say"
    # Misc common questions
    over_18: str = ""  # "Yes" / "No"
    how_did_you_hear: str = ""
    requires_accommodation: str = ""  # "Yes" / "No"


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
    jobs_fetched: int = 0
    applications_submitted: int = 0
    applications_failed: int = 0
    applications_skipped: int = 0
    errors: list[str] = []
