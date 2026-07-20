"""
Pydantic models — the strict contract between frontend and backend.
Nothing enters or leaves a route without matching one of these shapes.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    SCRAPING = "scraping"
    ANALYZING = "analyzing"
    GENERATING_INSIGHTS = "generating_insights"
    COMPLETE = "complete"
    FAILED = "failed"


class AnalysisRequest(BaseModel):
    """Form fields accompanying the CV upload (multipart, not raw JSON)."""
    role_query: str = Field(..., min_length=2, max_length=120, examples=["Senior Data Scientist"])
    location: Optional[str] = Field(default=None, max_length=80, examples=["Bengaluru"])
    max_jobs: int = Field(default=40, ge=5, le=50)


class AnalysisJobCreated(BaseModel):
    job_id: str
    status: AnalysisStatus


class KeywordFrequency(BaseModel):
    keyword: str
    count: int
    percentage_of_jds: float = Field(..., description="% of scraped JDs mentioning this keyword")


class SkillGap(BaseModel):
    skill: str
    importance: str = Field(..., description="high | medium | low, as judged by the LLM")
    reason: str
    learning_path: List[str] = Field(default_factory=list, description="Ordered resources/steps")


class JobClusterSummary(BaseModel):
    cluster_label: str
    job_count: int
    representative_titles: List[str]


class AnalysisResult(BaseModel):
    job_id: str
    status: AnalysisStatus
    role_query: str
    jobs_scraped: int
    match_score: Optional[float] = Field(default=None, ge=0, le=100)
    top_keywords: List[KeywordFrequency] = Field(default_factory=list)
    job_clusters: List[JobClusterSummary] = Field(default_factory=list)
    skill_gaps: List[SkillGap] = Field(default_factory=list)
    error_message: Optional[str] = None


class ScrapedJob(BaseModel):
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    raw_description: str
    url: Optional[str] = None
