"""
LLM synthesis step: given the CV text and top market keywords/skills,
ask a foundational model to identify concrete gaps and a learning path.

Uses the Anthropic API by default. Swap `_call_llm` for an OpenAI or
Hugging Face Inference Endpoint client if you prefer — the rest of the
pipeline (prompt construction, JSON parsing, Pydantic validation)
stays the same.
"""
from __future__ import annotations

import json
import logging
from typing import List

from anthropic import Anthropic, APIError, APIStatusError

from app.core.config import get_settings
from app.models.schemas import KeywordFrequency, SkillGap

logger = logging.getLogger(__name__)
settings = get_settings()

_SYSTEM_PROMPT = """You are a career analyst. You will be given a candidate's CV text and \
a list of the most in-demand keywords/skills found across current job postings for their \
target role. Identify the skills the market demands that are MISSING or WEAK in the CV.

Respond with ONLY a JSON array (no prose, no markdown fences) of objects shaped exactly as:
[
  {
    "skill": "string",
    "importance": "high" | "medium" | "low",
    "reason": "one sentence on why this matters for the target role",
    "learning_path": ["ordered", "list", "of", "concrete", "learning", "steps"]
  }
]
Return at most 8 items, ordered by importance descending. Do not invent skills that \
aren't plausibly relevant to the target role and market keywords given."""


class LLMAnalysisError(Exception):
    """Raised when the LLM call fails or returns unparseable output."""


def _build_user_prompt(cv_text: str, role_query: str, top_keywords: List[KeywordFrequency]) -> str:
    keyword_lines = "\n".join(
        f"- {kw.keyword} (appears in {kw.percentage_of_jds}% of postings)" for kw in top_keywords
    )
    # Truncate CV defensively — keeps token usage predictable regardless of CV length.
    cv_excerpt = cv_text[:6000]
    return (
        f"Target role: {role_query}\n\n"
        f"Top market keywords from current job postings:\n{keyword_lines}\n\n"
        f"Candidate CV text:\n\"\"\"\n{cv_excerpt}\n\"\"\""
    )


def generate_skill_gaps(
    cv_text: str,
    role_query: str,
    top_keywords: List[KeywordFrequency],
) -> List[SkillGap]:
    if not settings.ANTHROPIC_API_KEY:
        raise LLMAnalysisError(
            "ANTHROPIC_API_KEY is not configured. Set it as a Codespaces secret "
            "or in backend/.env before calling the gap-analysis endpoint."
        )

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    user_prompt = _build_user_prompt(cv_text, role_query, top_keywords)

    try:
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except APIStatusError as exc:
        raise LLMAnalysisError(f"Anthropic API returned an error: {exc.message}") from exc
    except APIError as exc:
        raise LLMAnalysisError(f"Anthropic API request failed: {exc}") from exc

    raw_text = "".join(block.text for block in response.content if block.type == "text").strip()
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned non-JSON output: %s", raw_text[:500])
        raise LLMAnalysisError("The model's response could not be parsed as JSON.") from exc

    try:
        return [SkillGap(**item) for item in parsed]
    except Exception as exc:
        raise LLMAnalysisError(f"LLM output didn't match the expected schema: {exc}") from exc
