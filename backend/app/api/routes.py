"""
API routes.

Design: the CV upload endpoint returns immediately with a job_id after
kicking off a BackgroundTask; the frontend polls GET /analysis/{job_id}
for status/results. This avoids holding an HTTP connection open through
a 30-90s scrape+ML+LLM pipeline.

In-memory `_JOBS` dict is intentionally simple for a single-developer
Codespaces project. For multi-user/production use, swap it for Redis
or a database table — the route logic itself won't need to change.
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.models.schemas import (
    AnalysisJobCreated,
    AnalysisResult,
    AnalysisStatus,
)
from app.services import nlp_analysis
from app.services.classifier import heuristic_cluster_jobs
from app.services.llm_gap_analysis import LLMAnalysisError, generate_skill_gaps
from app.services.pdf_parser import CVParsingError, extract_text_from_pdf, validate_pdf_size
from app.services.scraper import ScrapeError, load_manual_jd_texts, scrape_naukri_jobs

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api", tags=["analysis"])

# job_id -> AnalysisResult. Swap for Redis/DB for multi-user deployments.
_JOBS: Dict[str, AnalysisResult] = {}


async def _run_pipeline(
    job_id: str,
    cv_text: str,
    role_query: str,
    location: Optional[str],
    max_jobs: int,
    manual_jd_texts: Optional[List[str]],
) -> None:
    result = _JOBS[job_id]
    try:
        # --- 1. Extraction ---
        result.status = AnalysisStatus.SCRAPING
        if manual_jd_texts:
            jobs = load_manual_jd_texts(manual_jd_texts)
        else:
            jobs = await scrape_naukri_jobs(role_query, location, max_jobs)
        result.jobs_scraped = len(jobs)

        # --- 2 & 3. Analysis + ML scoring ---
        result.status = AnalysisStatus.ANALYZING
        jd_raw_texts = [j.raw_description for j in jobs]
        cleaned_cv, cleaned_jds = nlp_analysis.prepare_corpus(cv_text, jd_raw_texts)

        result.top_keywords = nlp_analysis.extract_top_keywords(cleaned_jds)
        result.match_score = nlp_analysis.compute_match_score(cv_text, jd_raw_texts)
        result.job_clusters = heuristic_cluster_jobs(jobs)

        # --- 4. LLM gap synthesis ---
        result.status = AnalysisStatus.GENERATING_INSIGHTS
        try:
            result.skill_gaps = generate_skill_gaps(cv_text, role_query, result.top_keywords)
        except LLMAnalysisError as exc:
            # Don't fail the whole analysis if only the LLM step breaks —
            # the match score + keywords are still valuable on their own.
            logger.warning("LLM gap analysis failed for job %s: %s", job_id, exc)
            result.error_message = f"Gap analysis unavailable: {exc}"

        result.status = AnalysisStatus.COMPLETE

    except ScrapeError as exc:
        result.status = AnalysisStatus.FAILED
        result.error_message = str(exc)
    except Exception as exc:  # last-resort guard so a bug never leaves a job stuck "pending"
        logger.exception("Unexpected pipeline failure for job %s", job_id)
        result.status = AnalysisStatus.FAILED
        result.error_message = f"Unexpected error: {exc}"


@router.post("/analysis", response_model=AnalysisJobCreated)
async def create_analysis(
    background_tasks: BackgroundTasks,
    role_query: str = Form(..., min_length=2, max_length=120),
    location: Optional[str] = Form(default=None),
    max_jobs: int = Form(default=40),
    cv_file: UploadFile = File(...),
) -> AnalysisJobCreated:
    if cv_file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="CV must be a PDF file.")

    file_bytes = await cv_file.read()

    try:
        validate_pdf_size(file_bytes, settings.MAX_CV_SIZE_MB)
        cv_text = extract_text_from_pdf(file_bytes)
    except CVParsingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job_id = str(uuid.uuid4())
    _JOBS[job_id] = AnalysisResult(
        job_id=job_id,
        status=AnalysisStatus.PENDING,
        role_query=role_query,
        jobs_scraped=0,
    )

    background_tasks.add_task(
        _run_pipeline, job_id, cv_text, role_query, location, max_jobs, None
    )

    return AnalysisJobCreated(job_id=job_id, status=AnalysisStatus.PENDING)


@router.post("/analysis/manual", response_model=AnalysisJobCreated)
async def create_analysis_from_manual_jds(
    background_tasks: BackgroundTasks,
    role_query: str = Form(..., min_length=2, max_length=120),
    jd_texts: List[str] = Form(..., description="One form field per pasted JD"),
    cv_file: UploadFile = File(...),
) -> AnalysisJobCreated:
    """
    Fallback path when live scraping is blocked (captcha, login wall, etc):
    the user pastes JD text bodies directly and the rest of the pipeline
    (keyword extraction, match scoring, clustering, LLM gaps) runs the same.
    """
    file_bytes = await cv_file.read()
    try:
        validate_pdf_size(file_bytes, settings.MAX_CV_SIZE_MB)
        cv_text = extract_text_from_pdf(file_bytes)
    except CVParsingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job_id = str(uuid.uuid4())
    _JOBS[job_id] = AnalysisResult(
        job_id=job_id, status=AnalysisStatus.PENDING, role_query=role_query, jobs_scraped=0
    )
    background_tasks.add_task(
        _run_pipeline, job_id, cv_text, role_query, None, len(jd_texts), jd_texts
    )
    return AnalysisJobCreated(job_id=job_id, status=AnalysisStatus.PENDING)


@router.get("/analysis/{job_id}", response_model=AnalysisResult)
async def get_analysis(job_id: str) -> AnalysisResult:
    result = _JOBS.get(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No analysis job found with that ID.")
    return result
