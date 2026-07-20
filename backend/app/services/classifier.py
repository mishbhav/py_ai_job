"""
Multi-label job classification into industry sub-domains.

Honesty note: a Keras Sequential network needs LABELED training data
(JD text -> sub-domain labels) to be meaningful. This project has none
yet, so this module ships two things:

  1. `build_keras_classifier()` — the actual model architecture,
     ready to `.fit()` once you have a labeled dataset (see the
     `train_from_labeled_csv` helper below for the expected format).
  2. `heuristic_cluster_jobs()` — a keyword-overlap fallback that
     produces real, usable JobClusterSummary output *today*, so the
     dashboard isn't blocked waiting on a training set. Swap the route
     in `api/routes.py` to call `classify_with_keras` once trained.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

import numpy as np

from app.models.schemas import JobClusterSummary, ScrapedJob

# --- Seed taxonomy for the heuristic fallback. Extend freely. ---
_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "Data Science / ML": ["machine", "learning", "model", "tensorflow", "pytorch", "pandas", "numpy", "regression", "dataset"],
    "Data Engineering": ["etl", "pipeline", "airflow", "spark", "kafka", "warehouse", "redshift", "bigquery"],
    "Backend Engineering": ["api", "django", "flask", "fastapi", "microservices", "backend", "rest", "graphql"],
    "Frontend Engineering": ["react", "vue", "angular", "frontend", "javascript", "typescript", "css", "ui"],
    "DevOps / Cloud": ["aws", "azure", "gcp", "kubernetes", "docker", "terraform", "cicd", "devops"],
    "Analytics / BI": ["tableau", "powerbi", "sql", "reporting", "dashboard", "analytics", "excel"],
}


def heuristic_cluster_jobs(jobs: List[ScrapedJob]) -> List[JobClusterSummary]:
    """Assigns each JD to the sub-domain with the highest keyword overlap."""
    clusters: Dict[str, List[str]] = defaultdict(list)

    for job in jobs:
        text_lower = job.raw_description.lower()
        scores = {
            domain: sum(text_lower.count(kw) for kw in keywords)
            for domain, keywords in _DOMAIN_KEYWORDS.items()
        }
        best_domain = max(scores, key=scores.get)
        if scores[best_domain] == 0:
            best_domain = "General / Unclassified"
        clusters[best_domain].append(job.title)

    return [
        JobClusterSummary(
            cluster_label=domain,
            job_count=len(titles),
            representative_titles=titles[:5],
        )
        for domain, titles in sorted(clusters.items(), key=lambda kv: -len(kv[1]))
    ]


def build_keras_classifier(input_dim: int, num_classes: int):
    """
    Sequential multi-label classifier (sigmoid output = independent
    per-class probabilities, since a JD can belong to multiple domains).

    Usage once you have labeled data:
        X = tfidf_vectorizer.fit_transform(jd_texts).toarray()
        y = multi_hot_label_matrix  # shape (n_samples, num_classes)
        model = build_keras_classifier(X.shape[1], y.shape[1])
        model.fit(X, y, epochs=20, batch_size=16, validation_split=0.2)
    """
    from tensorflow import keras
    from tensorflow.keras import layers

    model = keras.Sequential(
        [
            layers.Input(shape=(input_dim,)),
            layers.Dense(256, activation="relu"),
            layers.Dropout(0.3),
            layers.Dense(64, activation="relu"),
            layers.Dropout(0.2),
            layers.Dense(num_classes, activation="sigmoid"),
        ]
    )
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    return model


def classify_with_keras(model, tfidf_vector: np.ndarray, class_names: List[str], threshold: float = 0.5) -> List[str]:
    """Run inference with a *trained* Keras model; returns matched labels above threshold."""
    probs = model.predict(tfidf_vector, verbose=0)[0]
    return [class_names[i] for i, p in enumerate(probs) if p >= threshold]
