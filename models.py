from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProjectLead(BaseModel):
    is_relevant: bool
    project_name: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    project_type: Literal[
        "construction",
        "landscaping",
        "renovation",
        "infrastructure",
        "tender",
        "other",
        "unknown",
    ]
    stage: Literal[
        "initiative",
        "design",
        "tender",
        "construction",
        "completed",
        "unknown",
    ]
    customer: Optional[str] = None
    short_description: Optional[str] = None
    materials_demand: Literal["low", "medium", "high", "unknown"]
    priority: Literal["low", "medium", "high"]
    source_url: str
    publication_date: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

    class Config:
        extra = "ignore"


PROJECT_LEAD_FIELDS = [
    "is_relevant",
    "project_name",
    "region",
    "city",
    "project_type",
    "stage",
    "customer",
    "short_description",
    "materials_demand",
    "priority",
    "source_url",
    "publication_date",
    "confidence",
    "reason",
]
