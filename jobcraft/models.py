"""Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Profile(BaseModel):
    """User profile — source of truth for all generations."""

    name: str
    title: str = ""
    location: str = ""
    contact: dict[str, str] = Field(default_factory=dict)
    experiences: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    skills: dict[str, list[str]] = Field(default_factory=dict)
    certifications: list[str] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    languages: list[dict[str, str]] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    career_goals: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class Job(BaseModel):
    """A scraped job offer."""

    id: int = 0
    url: str
    title: str = ""
    company: str = ""
    location: str = ""
    contract_type: str = ""
    salary: str = ""
    text: str = ""
    added_at: datetime = Field(default_factory=datetime.now)
    score: int | None = None
    analysis: dict[str, Any] | None = None
    documents: dict[str, str] | None = None


class Analysis(BaseModel):
    """LLM analysis of a job vs profile."""

    score: int
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    ats_keywords: list[str] = Field(default_factory=list)
    narrative_angle: str = ""
    recommendation: str = ""


class Documents(BaseModel):
    """Generated CV + cover letter."""

    cv_html: str = ""
    cover_html: str = ""
    instructions_history: list[str] = Field(default_factory=list)
