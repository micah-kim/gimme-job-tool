from datetime import datetime

from pydantic import BaseModel


# ── User Profile ──


class UserPreferences(BaseModel):
    titles: list[str] = []
    locations: list[str] = []
    min_yoe: int = 0
    max_yoe: int = 99
    keywords: list[str] = []
    deal_breakers: list[str] = []


class UserProfileCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    linkedin_url: str = ""
    preferences: UserPreferences = UserPreferences()


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


# ── Tailored Resume ──


class TailoredResumeOut(BaseModel):
    id: int
    job_id: int
    resume_content: str
    resume_pdf_path: str
    cover_letter: str
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
    jobs_analyzed: int = 0
    jobs_matched: int = 0
    resumes_tailored: int = 0
    applications_submitted: int = 0
    applications_failed: int = 0
    errors: list[str] = []
