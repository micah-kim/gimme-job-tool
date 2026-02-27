"""API routes for user profile and preferences."""

import json
import os
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import UserProfile
from app.schemas.schemas import UserPreferences, UserProfileCreate, UserProfileOut

router = APIRouter(prefix="/api/profile", tags=["profile"])

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")


@router.get("", response_model=UserProfileOut | None)
async def get_profile(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if profile:
        # Parse preferences JSON for the response
        prefs = json.loads(profile.preferences) if isinstance(profile.preferences, str) else {}
        profile.preferences = prefs
    return profile


@router.post("", response_model=UserProfileOut)
async def create_or_update_profile(data: UserProfileCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()

    prefs_json = data.preferences.model_dump_json() if data.preferences else "{}"

    if profile:
        profile.first_name = data.first_name
        profile.last_name = data.last_name
        profile.email = data.email
        profile.phone = data.phone
        profile.linkedin_url = data.linkedin_url
        profile.preferences = prefs_json
    else:
        profile = UserProfile(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            linkedin_url=data.linkedin_url,
            preferences=prefs_json,
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    profile.preferences = json.loads(profile.preferences) if isinstance(profile.preferences, str) else {}
    return profile


@router.put("/preferences", response_model=UserProfileOut)
async def update_preferences(prefs: UserPreferences, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Create a profile first")

    profile.preferences = prefs.model_dump_json()
    await db.commit()
    await db.refresh(profile)
    profile.preferences = json.loads(profile.preferences)
    return profile


@router.post("/resume")
async def upload_resume(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Create a profile first")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    filepath = os.path.join(UPLOADS_DIR, file.filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    profile.base_resume_path = filepath
    await db.commit()
    return {"filename": file.filename, "path": filepath}
