"""Pydantic schemas for request validation."""
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class ProcessCreate(BaseModel):
    template_key: str
    name: str = Field(min_length=3, max_length=200)
    owner: str = Field(min_length=3, max_length=120)
    description: str = ""
    start_date: date | None = None


class SubmissionUpdate(BaseModel):
    fields: dict[str, Any]
