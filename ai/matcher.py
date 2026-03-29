from __future__ import annotations

import re
from typing import Dict

import torch
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-mpnet-base-v2"
_model: SentenceTransformer | None = None

NOISE_SECTION_HEADERS = {
    "hobbies",
    "interests",
    "extracurricular",
    "extracurriculars",
    "activities",
    "volunteering",
}

NOISE_INLINE_MARKERS = tuple(f"{header}:" for header in NOISE_SECTION_HEADERS)

PROFESSIONAL_SECTION_HEADERS = {
    "experience",
    "work experience",
    "education",
    "projects",
    "skills",
    "certifications",
    "achievements",
    "publications",
}

HARD_SKILL_KEYWORDS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "c",
    "solidity",
    "fastapi",
    "django",
    "flask",
    "react",
    "node",
    "pytorch",
    "tensorflow",
    "langchain",
    "rag",
    "nlp",
    "llm",
    "sql",
    "nosql",
    "postgresql",
    "mongodb",
    "web3",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "redis",
    "git",
}

CULTURE_SIGNAL_KEYWORDS = {
    "leadership",
    "collaboration",
    "teamwork",
    "mentorship",
    "community",
    "volunteer",
    "sports",
    "music",
    "design",
    "public speaking",
}


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "general"
    sections[current] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        normalized = re.sub(r"[^a-z\s]", "", line.lower()).strip()
        heading_candidate = normalized
        remainder = ""

        if ":" in line:
            head, tail = line.split(":", 1)
            heading_candidate = re.sub(r"[^a-z\s]", "", head.lower()).strip()
            remainder = tail.strip()

        if heading_candidate in PROFESSIONAL_SECTION_HEADERS or heading_candidate in NOISE_SECTION_HEADERS:
            current = heading_candidate
            sections.setdefault(current, [])
            if remainder:
                sections[current].append(remainder)
            continue

        sections.setdefault(current, []).append(line)

    return {key: "\n".join(value).strip() for key, value in sections.items() if value}


def _professional_text_from_sections(sections: dict[str, str], fallback_text: str) -> str:
    picked = [text for name, text in sections.items() if name in PROFESSIONAL_SECTION_HEADERS or name == "general"]
    cleaned_lines: list[str] = []
    for part in picked:
        for line in part.splitlines():
            stripped = line.strip()
            lowered = stripped.lower()
            if lowered.startswith(NOISE_INLINE_MARKERS):
                continue
            cleaned_lines.append(stripped)

    merged = "\n".join(line for line in cleaned_lines if line).strip()
    return merged or fallback_text


def _noise_text_from_sections(sections: dict[str, str]) -> str:
    picked = [text for name, text in sections.items() if name in NOISE_SECTION_HEADERS]
    inline_noise: list[str] = []
    general = sections.get("general", "")
    for line in general.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(NOISE_INLINE_MARKERS):
            inline_noise.append(stripped)

    combined = "\n".join([part for part in picked if part] + inline_noise).strip()
    return combined


def _extract_hard_skills(text: str) -> list[str]:
    lowered = text.lower()
    found = [skill for skill in HARD_SKILL_KEYWORDS if re.search(rf"\b{re.escape(skill)}\b", lowered)]
    return sorted(set(found))


def _extract_projects(text: str) -> list[str]:
    lines = [line.strip("-• ") for line in text.splitlines() if line.strip()]
    project_lines = [
        line
        for line in lines
        if re.search(r"\b(project|built|developed|implemented|deployed|designed)\b", line, flags=re.IGNORECASE)
    ]
    return project_lines[:8]


def _culture_fit_bonus(noise_text: str) -> float:
    if not noise_text:
        return 0.0
    lowered = noise_text.lower()
    hits = sum(1 for token in CULTURE_SIGNAL_KEYWORDS if token in lowered)
    # Bonus only; never negative and capped to avoid overpowering technical fit.
    return float(min(8.0, hits * 1.5))


def _semantic_similarity(a: str, b: str) -> float:
    model = _get_model()
    embeddings = model.encode(
        [a, b],
        convert_to_tensor=True,
        normalize_embeddings=True,
    )
    return float(
        torch.nn.functional.cosine_similarity(
            embeddings[0].unsqueeze(0),
            embeddings[1].unsqueeze(0),
            dim=1,
        ).item()
    )


def score_fit(verified_cv_text: str, job_description_text: str) -> Dict[str, object]:
    """Generalized executive-recruiter fit scoring with noise suppression.

    - Uses professional sections for primary fit scoring.
    - Treats hobbies/extracurriculars only as an additive culture bonus.
    - Uses PyTorch cosine similarity for semantic fit.
    """
    if not verified_cv_text.strip() or not job_description_text.strip():
        raise ValueError("Both verified CV text and job description text are required.")

    sections = _extract_sections(verified_cv_text)
    professional_text = _professional_text_from_sections(sections, verified_cv_text)
    noise_text = _noise_text_from_sections(sections)

    cv_skills = _extract_hard_skills(professional_text)
    jd_skills = _extract_hard_skills(job_description_text)
    projects = _extract_projects(professional_text)

    semantic_similarity = _semantic_similarity(professional_text, job_description_text)
    semantic_score = max(0.0, min(100.0, ((semantic_similarity + 1.0) / 2.0) * 100.0))

    skill_similarity = 0.0
    if cv_skills and jd_skills:
        skill_similarity = _semantic_similarity(" ".join(cv_skills), " ".join(jd_skills))
    skill_score = max(0.0, min(100.0, ((skill_similarity + 1.0) / 2.0) * 100.0))

    project_boost = min(10.0, len(projects) * 1.8)
    # Core competency prioritizes JD alignment and demonstrable output.
    core_competency = min(100.0, (semantic_score * 0.68) + (skill_score * 0.22) + project_boost)

    culture_bonus = _culture_fit_bonus(noise_text)
    # Guarantee culture fit cannot decrease technical/professional fit.
    final_score = min(100.0, max(core_competency, core_competency + culture_bonus))

    return {
        "similarity_raw": round(float(semantic_similarity), 6),
        "score_percent": round(float(final_score), 2),
        "core_competency_score": round(float(core_competency), 2),
        "culture_fit_bonus": round(float(culture_bonus), 2),
        "hard_skills": cv_skills,
        "jd_hard_skills": jd_skills,
        "project_evidence": projects,
        "noise_suppressed": True,
    }


def compute_match_score(verified_cv_text: str, job_description_text: str) -> Dict[str, float]:
    """Backward-compatible alias for legacy callers."""
    result = score_fit(verified_cv_text, job_description_text)
    return {
        "similarity_raw": float(result["similarity_raw"]),
        "score_percent": float(result["score_percent"]),
    }
