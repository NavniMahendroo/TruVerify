from __future__ import annotations

from typing import Dict

import torch
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-mpnet-base-v2"
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def compute_match_score(verified_cv_text: str, job_description_text: str) -> Dict[str, float]:
    """Compute semantic match score between verified CV and JD using cosine similarity."""
    if not verified_cv_text.strip() or not job_description_text.strip():
        raise ValueError("Both verified CV text and job description text are required.")

    model = _get_model()
    embeddings = model.encode(
        [verified_cv_text, job_description_text],
        convert_to_tensor=True,
        normalize_embeddings=True,
    )

    similarity = torch.nn.functional.cosine_similarity(
        embeddings[0].unsqueeze(0),
        embeddings[1].unsqueeze(0),
        dim=1,
    ).item()

    # Convert from [-1, 1] to [0, 100]
    score = max(0.0, min(100.0, ((similarity + 1.0) / 2.0) * 100.0))
    return {
        "similarity_raw": float(similarity),
        "score_percent": round(float(score), 2),
    }
