"""
LLM synthesis step: given the CV text and top market keywords/skills,
ask a model to identify concrete gaps and a learning path.

Three interchangeable backends, selected by settings.LLM_PROVIDER:

  * "huggingface_api"   — FREE. Hugging Face's serverless Inference API.
                          Needs only a free HF token (no billing info
                          required). Rate-limited but fine for personal use.
  * "local_transformers" — FREE and fully offline. Downloads an open-source
                          checkpoint once, then runs entirely on your
                          Codespace's CPU with no external calls or tokens.
                          Slower and lower-quality than the two API options,
                          but zero ongoing dependency on any external service.
  * "anthropic"         — paid, kept for anyone who wants Claude-quality output.

All three funnel through the same prompt + JSON-parsing logic, so routes.py
never needs to know which backend is active.
"""
from __future__ import annotations

import json
import logging
import re
from typing import List

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
    # Truncate CV defensively — keeps prompt size predictable regardless of CV length.
    # Local small models especially need a tight context budget.
    cv_excerpt = cv_text[:4000]
    return (
        f"Target role: {role_query}\n\n"
        f"Top market keywords from current job postings:\n{keyword_lines}\n\n"
        f"Candidate CV text:\n\"\"\"\n{cv_excerpt}\n\"\"\""
    )


def _extract_json_array(raw_text: str) -> list:
    """
    Open models rarely respect "JSON only" as reliably as Claude does — they
    often wrap the array in prose or markdown fences. This pulls out the
    first [...] block before parsing, so we tolerate a little chatter.
    """
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        raise LLMAnalysisError("No JSON array found in the model's response.")

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMAnalysisError(f"Model output wasn't valid JSON: {exc}") from exc


# --------------------------------------------------------------------------
# Backend 1: Hugging Face free serverless Inference API
# --------------------------------------------------------------------------
def _call_huggingface_api(system_prompt: str, user_prompt: str) -> str:
    if not settings.HF_API_TOKEN:
        raise LLMAnalysisError(
            "HF_API_TOKEN is not configured. Get a free token at "
            "https://huggingface.co/settings/tokens and set it as a "
            "Codespaces secret or in backend/.env."
        )

    from huggingface_hub import InferenceClient
    from huggingface_hub.errors import HfHubHTTPError

    client = InferenceClient(model=settings.HF_INFERENCE_MODEL, token=settings.HF_API_TOKEN)

    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=0.3,
        )
        return completion.choices[0].message.content
    except HfHubHTTPError as exc:
        raise LLMAnalysisError(
            f"Hugging Face Inference API request failed ({exc}). The model "
            f"'{settings.HF_INFERENCE_MODEL}' may be unavailable on the free "
            "tier right now — try another model in HF_INFERENCE_MODEL, e.g. "
            "'Qwen/Qwen2.5-7B-Instruct' or 'mistralai/Mistral-7B-Instruct-v0.3'."
        ) from exc


# --------------------------------------------------------------------------
# Backend 2: fully local/offline transformers model
# --------------------------------------------------------------------------
_local_pipeline_cache = {}


def _get_local_pipeline():
    """Lazily loads and caches the local model — downloaded once, reused after."""
    if settings.LOCAL_MODEL_ID in _local_pipeline_cache:
        return _local_pipeline_cache[settings.LOCAL_MODEL_ID]

    from transformers import pipeline

    logger.info("Loading local model '%s' (first call only, may take a while)...", settings.LOCAL_MODEL_ID)
    pipe = pipeline(
        "text-generation",
        model=settings.LOCAL_MODEL_ID,
        device_map="auto",  # falls back to CPU automatically if no GPU
    )
    _local_pipeline_cache[settings.LOCAL_MODEL_ID] = pipe
    return pipe


def _call_local_transformers(system_prompt: str, user_prompt: str) -> str:
    try:
        pipe = _get_local_pipeline()
    except Exception as exc:
        raise LLMAnalysisError(
            f"Failed to load local model '{settings.LOCAL_MODEL_ID}': {exc}. "
            "Make sure 'transformers' and 'torch' are installed "
            "(see backend/requirements.txt)."
        ) from exc

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        output = pipe(
            messages,
            max_new_tokens=settings.LLM_MAX_TOKENS,
            temperature=0.3,
            do_sample=True,
        )
        generated = output[0]["generated_text"]
        # transformers' chat pipeline returns the full message list; the
        # assistant's reply is the last entry.
        if isinstance(generated, list):
            return generated[-1]["content"]
        return str(generated)
    except Exception as exc:
        raise LLMAnalysisError(f"Local model inference failed: {exc}") from exc


# --------------------------------------------------------------------------
# Backend 3: Anthropic (optional, paid)
# --------------------------------------------------------------------------
def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    if not settings.ANTHROPIC_API_KEY:
        raise LLMAnalysisError("ANTHROPIC_API_KEY is not configured.")

    from anthropic import Anthropic, APIError, APIStatusError

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except APIStatusError as exc:
        raise LLMAnalysisError(f"Anthropic API returned an error: {exc.message}") from exc
    except APIError as exc:
        raise LLMAnalysisError(f"Anthropic API request failed: {exc}") from exc

    return "".join(block.text for block in response.content if block.type == "text")


_PROVIDERS = {
    "huggingface_api": _call_huggingface_api,
    "local_transformers": _call_local_transformers,
    "anthropic": _call_anthropic,
}


def generate_skill_gaps(
    cv_text: str,
    role_query: str,
    top_keywords: List[KeywordFrequency],
) -> List[SkillGap]:
    provider = settings.LLM_PROVIDER
    if provider not in _PROVIDERS:
        raise LLMAnalysisError(
            f"Unknown LLM_PROVIDER '{provider}'. Choose one of: {list(_PROVIDERS.keys())}"
        )

    user_prompt = _build_user_prompt(cv_text, role_query, top_keywords)
    raw_text = _PROVIDERS[provider](_SYSTEM_PROMPT, user_prompt)

    parsed = _extract_json_array(raw_text)

    try:
        return [SkillGap(**item) for item in parsed]
    except Exception as exc:
        raise LLMAnalysisError(f"Model output didn't match the expected schema: {exc}") from exc
