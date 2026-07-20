"""
Core NLP/ML analysis:
  1. Text cleaning (strip HTML/punctuation/stopwords)
  2. Pandas-based keyword frequency aggregation across scraped JDs
  3. TF-IDF + cosine similarity match score between CV and aggregated JD corpus
"""
from __future__ import annotations

import re
from collections import Counter
from typing import List, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import get_settings
from app.models.schemas import KeywordFrequency

settings = get_settings()

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_NON_ALPHA_RE = re.compile(r"[^a-zA-Z\s\+\#\.]")  # keep + and # for "C++", "C#"; . for "Node.js"
_WHITESPACE_RE = re.compile(r"\s+")

# A pragmatic stopword list (avoids an nltk download dependency at import time).
_STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are aren't as at be because been
    before being below between both but by can't cannot could couldn't did didn't do does
    doesn't doing don't down during each few for from further had hadn't has hasn't have
    haven't having he he'd he'll he's her here here's hers herself him himself his how
    how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most
    mustn't my myself no nor not of off on once only or other ought our ours ourselves out
    over own same shan't she she'd she'll she's should shouldn't so some such than that
    that's the their theirs them themselves then there there's these they they'd they'll
    they're they've this those through to too under until up very was wasn't we we'd we'll
    we're we've were weren't what what's when when's where where's which while who who's
    whom why why's with won't would wouldn't you you'd you'll you're you've your yours
    yourself yourselves job description role responsibilities requirements experience
    years strong good knowledge working ability skills team company using
    """.split()
)


def clean_text(raw: str) -> str:
    """Strip HTML tags, punctuation (keeping tech-relevant symbols), and stopwords."""
    text = _HTML_TAG_RE.sub(" ", raw)
    text = text.lower()
    text = _NON_ALPHA_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()

    tokens = [t for t in text.split(" ") if t and t not in _STOPWORDS and len(t) > 1]
    return " ".join(tokens)


def extract_top_keywords(cleaned_jds: List[str], top_n: int | None = None) -> List[KeywordFrequency]:
    """
    Aggregate token frequency across all cleaned JDs using pandas, returning
    the top N keywords and the % of JDs each one appears in (a better
    "market demand" signal than raw count alone).
    """
    top_n = top_n or settings.TOP_KEYWORDS_COUNT
    if not cleaned_jds:
        return []

    total_docs = len(cleaned_jds)
    doc_token_sets = [set(jd.split()) for jd in cleaned_jds]

    all_tokens: List[str] = []
    for jd in cleaned_jds:
        all_tokens.extend(jd.split())

    freq = Counter(all_tokens)
    df = pd.DataFrame(freq.items(), columns=["keyword", "count"]).sort_values(
        "count", ascending=False
    )

    df["percentage_of_jds"] = df["keyword"].apply(
        lambda kw: round(100 * sum(kw in doc for doc in doc_token_sets) / total_docs, 1)
    )

    top = df.head(top_n)
    return [
        KeywordFrequency(keyword=row.keyword, count=int(row.count), percentage_of_jds=row.percentage_of_jds)
        for row in top.itertuples()
    ]


def compute_match_score(cv_text: str, jd_texts: List[str]) -> float:
    """
    Vectorize the CV against the aggregated JD corpus with TF-IDF and score
    similarity via cosine distance. Returns a 0-100 match percentage.
    """
    if not jd_texts:
        raise ValueError("Cannot compute a match score with zero job descriptions.")

    cleaned_cv = clean_text(cv_text)
    cleaned_jds = [clean_text(jd) for jd in jd_texts]

    # Corpus = [CV, aggregated_all_jds, jd_1, jd_2, ...] — we score the CV
    # against the *aggregated* JD text so one very long JD can't dominate.
    aggregated_jd_text = " ".join(cleaned_jds)
    corpus = [cleaned_cv, aggregated_jd_text]

    vectorizer = TfidfVectorizer(max_features=settings.TFIDF_MAX_FEATURES, ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(corpus)

    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    return round(float(similarity) * 100, 1)


def prepare_corpus(cv_raw: str, jd_raws: List[str]) -> Tuple[str, List[str]]:
    """Convenience wrapper: clean CV + JDs once, reuse for scoring and keywords."""
    cleaned_cv = clean_text(cv_raw)
    cleaned_jds = [clean_text(jd) for jd in jd_raws]
    return cleaned_cv, cleaned_jds
