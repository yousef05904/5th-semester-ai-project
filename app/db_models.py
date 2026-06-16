from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class MonitoringRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    region_key: str = Field(index=True)
    region_name: str
    city: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    total_search_results: int = 0
    fetched_articles: int = 0
    ai_analyzed: int = 0
    relevant_before_dedup: int = 0
    rejected_count: int = 0
    duplicates_removed: int = 0
    final_leads_count: int = 0
    excel_path: Optional[str] = None
    json_path: Optional[str] = None


class ProjectLeadDB(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="monitoringrun.id", index=True)
    project_name: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    project_type: Optional[str] = None
    stage: Optional[str] = None
    customer: Optional[str] = None
    short_description: Optional[str] = None
    materials_demand: Optional[str] = None
    priority: Optional[str] = None
    source_url: str
    publication_date: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RejectedItemDB(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="monitoringrun.id", index=True)
    title: Optional[str] = None
    source_url: Optional[str] = None
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
