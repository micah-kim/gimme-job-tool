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

    jobs = relationship("JobListing", back_populates="company")


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
    tailored_resume = relationship("TailoredResume", uselist=False, back_populates="job")
    application_log = relationship("ApplicationLog", uselist=False, back_populates="job")


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


class TailoredResume(Base):
    __tablename__ = "tailored_resume"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("job_listing.id"), nullable=False, unique=True)
    resume_content = Column(Text, default="")
    resume_pdf_path = Column(String, default="")
    cover_letter = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("JobListing", back_populates="tailored_resume")


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
