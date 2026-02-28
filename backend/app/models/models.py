import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ATSType(str, enum.Enum):
    GREENHOUSE = "greenhouse"
    ASHBY = "ashby"
    LEVER = "lever"


class JobStatus(str, enum.Enum):
    NEW = "new"
    MATCHED = "matched"
    REJECTED = "rejected"
    APPLIED = "applied"
    FAILED = "failed"


class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FAILED = "failed"
    ERROR = "error"


class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, default="")
    linkedin_url = Column(String, default="")
    base_resume_path = Column(String, default="")
    # JSON string: {"titles": [...], "locations": [...], "min_yoe": 0, "max_yoe": 10, "keywords": [...], "deal_breakers": [...]}
    preferences = Column(Text, default="{}")
    # JSON string for pre-filled application answers (EEO, education, work auth, etc.)
    application_answers = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    ats_type = Column(Enum(ATSType), nullable=False)
    board_token = Column(String, nullable=False, unique=True)
    last_scraped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("JobListing", back_populates="company", cascade="all, delete-orphan")


class JobListing(Base):
    __tablename__ = "job_listing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    external_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    location = Column(String, default="")
    department = Column(String, default="")
    description_html = Column(Text, default="")
    description_text = Column(Text, default="")
    url = Column(String, default="")
    compensation = Column(String, default="")
    posted_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(JobStatus), default=JobStatus.NEW)

    company = relationship("Company", back_populates="jobs")
    score = relationship("JobScore", uselist=False, back_populates="job")
    application_log = relationship("ApplicationLog", uselist=False, back_populates="job")
    form_fields = relationship("JobFormField", back_populates="job", cascade="all, delete-orphan")


class JobScore(Base):
    __tablename__ = "job_score"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("job_listing.id"), nullable=False, unique=True)
    relevance_score = Column(Float, default=0.0)
    reasoning = Column(Text, default="")
    matched_criteria = Column(Text, default="[]")  # JSON
    flagged_dealbreakers = Column(Text, default="[]")  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("JobListing", back_populates="score")


class ApplicationLog(Base):
    __tablename__ = "application_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("job_listing.id"), nullable=False, unique=True)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.PENDING)
    applied_at = Column(DateTime, nullable=True)
    error_message = Column(Text, default="")
    screenshot_path = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("JobListing", back_populates="application_log")


class QAEntry(Base):
    """Canonical Q&A bank — one entry per unique question across all applications."""
    __tablename__ = "qa_entry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_question = Column(Text, nullable=False, unique=True)
    display_question = Column(Text, nullable=False)
    field_type = Column(String, nullable=False)  # select / text / textarea / checkbox
    answer = Column(Text, nullable=True)
    category = Column(String, default="other")  # demographic, work_auth, education, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    form_fields = relationship("JobFormField", back_populates="qa_entry")


class JobFormField(Base):
    """Per-job form field discovered during scanning."""
    __tablename__ = "job_form_field"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("job_listing.id"), nullable=False)
    label_text = Column(Text, nullable=False)
    field_type = Column(String, nullable=False)  # select / text / textarea / checkbox
    options_json = Column(Text, default="[]")  # JSON: [[text, value], ...]
    is_required = Column(Boolean, default=False)
    qa_entry_id = Column(Integer, ForeignKey("qa_entry.id"), nullable=True)
    scanned_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("JobListing", back_populates="form_fields")
    qa_entry = relationship("QAEntry", back_populates="form_fields")
