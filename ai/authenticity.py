from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List

import spacy
from spacy.language import Language
from spacy.pipeline import EntityRuler


_nlp: Language | None = None

STRATEGIC_CATALOG: dict[str, dict[str, object]] = {
    "Institutions": {
        "entity_label": "INSTITUTION",
        "phrase_patterns": [
            "NSUT",
            "IIT",
            "NIT",
            "BITS",
            "IIIT",
            "Stanford",
            "MIT",
            "Carnegie Mellon",
            "Harvard",
            "Oxford",
            "Cambridge",
            "University",
            "Institute of Technology",
        ],
        "regex_patterns": [r"\b[A-Z][A-Za-z&\-. ]+ University\b", r"\b[A-Z][A-Za-z&\-. ]+ Institute of Technology\b"],
        "roles": {"engineering", "research", "consulting", "finance"},
        "hit_weight": 20.0,
        "cap": 40.0,
    },
    "Certifications": {
        "entity_label": "CERTIFICATION",
        "phrase_patterns": [
            "NVIDIA",
            "JPMorgan",
            "AWS",
            "Google Cloud",
            "Azure",
            "Oracle Certified",
            "Coursera",
            "Udacity",
            "DeepLearning.AI",
            "CFA",
            "FRM",
            "Scrum",
            "Kubernetes",
        ],
        "regex_patterns": [r"\b(certified|certification|certificate)\b"],
        "roles": {"engineering", "finance", "product", "consulting"},
        "hit_weight": 16.0,
        "cap": 32.0,
    },
    "Competitive Achievements": {
        "entity_label": "COMPETITION",
        "phrase_patterns": [
            "hackathon",
            "finalist",
            "winner",
            "runner up",
            "top 10",
            "top 50",
            "kaggle",
            "icpc",
        ],
        "regex_patterns": [r"\b(finalist|winner|runner\s*up|top\s*\d+)\b", r"\bhackathon\b"],
        "roles": {"engineering", "research", "product"},
        "hit_weight": 14.0,
        "cap": 28.0,
    },
    "Leadership Signals": {
        "entity_label": "LEADERSHIP",
        "phrase_patterns": [
            "team lead",
            "led",
            "mentored",
            "president",
            "head",
            "captain",
            "founded",
            "co-founded",
        ],
        "regex_patterns": [r"\b(led|managed|mentored|founded|co-founded|captain|president)\b"],
        "roles": {"product", "consulting", "finance", "engineering"},
        "hit_weight": 12.0,
        "cap": 24.0,
    },
    "Research/Publications": {
        "entity_label": "RESEARCH",
        "phrase_patterns": [
            "publication",
            "published",
            "paper",
            "arxiv",
            "ieee",
            "acm",
        ],
        "regex_patterns": [r"\b(published|publication|paper|journal|conference|arxiv|ieee|acm)\b"],
        "roles": {"research", "engineering"},
        "hit_weight": 14.0,
        "cap": 24.0,
    },
}

ROLE_TRACK_KEYWORDS: dict[str, list[str]] = {
    "engineering": ["engineer", "developer", "backend", "frontend", "full stack", "software", "platform", "api"],
    "research": ["research", "scientist", "ml", "ai", "nlp", "llm", "data science", "model"],
    "product": ["product", "pm", "roadmap", "growth", "user experience"],
    "finance": ["investment", "quant", "trading", "risk", "financial", "equity", "banking"],
    "consulting": ["consulting", "strategy", "analyst", "case", "advisory", "client"],
}


def _extract_years(text: str) -> List[int]:
    return [int(match.group(0)) for match in re.finditer(r"\b(19|20)\d{2}\b", text)]


def _get_nlp() -> Language:
    global _nlp
    if _nlp is not None:
        return _nlp

    nlp = spacy.blank("en")
    ruler = nlp.add_pipe("entity_ruler")
    assert isinstance(ruler, EntityRuler)

    patterns = []
    for config in STRATEGIC_CATALOG.values():
        label = str(config["entity_label"])
        for phrase in config["phrase_patterns"]:
            patterns.append({"label": label, "pattern": phrase})

    ruler.add_patterns(patterns)
    _nlp = nlp
    return _nlp


def _infer_role_tracks(job_description: str) -> set[str]:
    lowered = job_description.lower()
    tracks: set[str] = set()
    for track, keywords in ROLE_TRACK_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            tracks.add(track)
    return tracks or {"engineering"}


def _extract_strategic_signals(cv_text: str, job_description: str) -> dict[str, object]:
    doc = _get_nlp()(cv_text)
    role_tracks = _infer_role_tracks(job_description)
    raw: dict[str, set[str]] = {category: set() for category in STRATEGIC_CATALOG}
    label_to_category = {str(cfg["entity_label"]): category for category, cfg in STRATEGIC_CATALOG.items()}

    for ent in doc.ents:
        normalized = ent.text.strip()
        category = label_to_category.get(ent.label_)
        if category and normalized:
            raw[category].add(normalized)

    for category, cfg in STRATEGIC_CATALOG.items():
        for pattern in cfg["regex_patterns"]:
            for match in re.finditer(pattern, cv_text, flags=re.IGNORECASE):
                token = match.group(0).strip()
                if token:
                    raw[category].add(token)

    relevant_categories = [
        category
        for category, cfg in STRATEGIC_CATALOG.items()
        if set(cfg["roles"]) & role_tracks
    ]
    if not relevant_categories:
        relevant_categories = list(STRATEGIC_CATALOG.keys())

    score_total = 0.0
    max_total = 0.0
    strategic_signals: list[dict[str, object]] = []

    for category in relevant_categories:
        cfg = STRATEGIC_CATALOG[category]
        hit_weight = float(cfg["hit_weight"])
        cap = float(cfg["cap"])
        max_total += cap

        items = sorted(raw[category])
        component = min(cap, hit_weight * len(items))
        score_total += component

        if items:
            strategic_signals.append({"label": category, "items": items})

    component_score = (score_total / max_total) * 100.0 if max_total > 0 else 0.0

    return {
        "role_tracks": sorted(role_tracks),
        "component_score": round(component_score, 2),
        "signals": strategic_signals,
        "entities": {k: sorted(v) for k, v in raw.items()},
    }


def _has_contact_signals(text: str) -> bool:
    has_email = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text) is not None
    has_phone = re.search(r"\b(?:\+?\d[\d\s\-()]{8,}\d)\b", text) is not None
    return has_email and has_phone


def _section_present(text: str, names: List[str]) -> bool:
    lowered = text.lower()
    return any(name.lower() in lowered for name in names)


def _count_project_signals(text: str) -> int:
    patterns = [
        r"\btech\s*:\s*",
        r"\bgithub\b",
        r"\bbuilt\b",
        r"\bdeveloped\b",
        r"\bimplemented\b",
        r"\bdeployed\b",
        r"\bapi\b",
        r"\bfastapi\b",
        r"\breact\b",
        r"\bpytorch\b",
        r"\blangchain\b",
    ]
    return sum(1 for p in patterns if re.search(p, text, flags=re.IGNORECASE))


def analyze_resume(
    cv_text: str,
    job_description: str,
    is_blockchain_verified: bool,
    fit_data: Dict[str, object] | None = None,
) -> Dict[str, object]:
    """Generalized executive recruiter authenticity review.

    Weight model:
    - Verified Credentials: 40%
    - Core Competency: 40%
    - Institutional/Strategic Signal: 20%
    """
    now_year = datetime.now(timezone.utc).year
    checks: List[Dict[str, str]] = []
    red_flags = 0

    fit_payload = fit_data or {}
    core_competency = float(fit_payload.get("core_competency_score", 0.0))

    if is_blockchain_verified:
        verified_component = 100.0
        checks.append(
            {
                "name": "Verified Credentials",
                "status": "pass",
                "details": "High Credibility: SHA-256 credential hash is validated against blockchain eSeal.",
            }
        )
    else:
        verified_component = 25.0
        red_flags += 1
        checks.append(
            {
                "name": "Verified Credentials",
                "status": "warning",
                "details": "Credential is not backed by blockchain eSeal. Marked as unverified.",
            }
        )

    years = _extract_years(cv_text)
    is_internship = bool(re.search(r"\b(intern|internship|trainee)\b", job_description, flags=re.IGNORECASE))
    if years:
        future_years = [y for y in years if y > now_year + 1]
        very_old_years = [y for y in years if y < 1980]
        ideal_grad_years = [y for y in future_years if now_year + 2 <= y <= now_year + 3]

        if is_internship and ideal_grad_years:
            checks.append(
                {
                    "name": "Year Consistency",
                    "status": "pass",
                    "details": f"Ideal Candidate: Internship role aligns with upcoming graduation year(s): {sorted(set(ideal_grad_years))}.",
                }
            )
        elif future_years:
            red_flags += 1
            checks.append(
                {
                    "name": "Year Consistency",
                    "status": "warning",
                    "details": f"Future years found: {sorted(set(future_years))}",
                }
            )
        elif very_old_years:
            red_flags += 1
            checks.append(
                {
                    "name": "Year Consistency",
                    "status": "warning",
                    "details": f"Unusual old years found: {sorted(set(very_old_years))}",
                }
            )
        else:
            checks.append(
                {
                    "name": "Year Consistency",
                    "status": "pass",
                    "details": "Timeline years look plausible.",
                }
            )
    else:
        red_flags += 1
        checks.append(
            {
                "name": "Year Consistency",
                "status": "warning",
                "details": "No education/experience years detected.",
            }
        )

    if _has_contact_signals(cv_text):
        checks.append(
            {
                "name": "Contact Completeness",
                "status": "pass",
                "details": "Email and phone-like signals detected.",
            }
        )
    else:
        checks.append(
            {
                "name": "Contact Completeness",
                "status": "warning",
                "details": "Email or phone signals are missing.",
            }
        )

    has_education = _section_present(cv_text, ["education", "b.tech", "bachelor", "degree", "university"])
    has_experience = _section_present(cv_text, ["experience", "intern", "internship", "work"])
    has_projects = _section_present(cv_text, ["projects", "project"])

    if has_education and has_experience:
        checks.append(
            {
                "name": "Core Sections",
                "status": "pass",
                "details": "Education and experience sections are present.",
            }
        )
    else:
        red_flags += 1
        checks.append(
            {
                "name": "Core Sections",
                "status": "warning",
                "details": "Education or experience section is weak/missing.",
            }
        )

    project_signal_count = _count_project_signals(cv_text)
    if has_projects and project_signal_count >= 3:
        checks.append(
            {
                "name": "Project Evidence",
                "status": "pass",
                "details": "Projects include technical/actionable details.",
            }
        )
    elif has_projects:
        checks.append(
            {
                "name": "Project Evidence",
                "status": "warning",
                "details": "Projects present but with limited technical depth.",
            }
        )
    else:
        checks.append(
            {
                "name": "Project Evidence",
                "status": "warning",
                "details": "No project section detected.",
            }
        )

    strategic = _extract_strategic_signals(cv_text=cv_text, job_description=job_description)
    institutional_component = float(strategic["component_score"])
    strategic_signals = strategic["signals"]

    if institutional_component > 0:
        checks.append(
            {
                "name": "Institutional/Strategic Signal",
                "status": "pass",
                "details": f"Role-aware strategic evidence detected across {len(strategic_signals)} category/categories.",
            }
        )
    else:
        checks.append(
            {
                "name": "Institutional/Strategic Signal",
                "status": "warning",
                "details": "No clear institution, hackathon ranking, or strategic certification signals found.",
            }
        )

    all_caps_ratio = 0.0
    letters = re.findall(r"[A-Za-z]", cv_text)
    if letters:
        upper = sum(1 for c in letters if c.isupper())
        all_caps_ratio = upper / len(letters)
    if all_caps_ratio > 0.6:
        red_flags += 1
        checks.append(
            {
                "name": "Formatting Quality",
                "status": "warning",
                "details": "Text appears overly uppercase/noisy.",
            }
        )
    else:
        checks.append(
            {
                "name": "Formatting Quality",
                "status": "pass",
                "details": "Formatting looks readable for parsing.",
            }
        )

    weighted_score = (verified_component * 0.40) + (core_competency * 0.40) + (institutional_component * 0.20)

    # Primary gatekeeper behavior: unverified resumes are capped as medium-credibility at best.
    if not is_blockchain_verified:
        weighted_score = min(weighted_score, 69.0)

    score = max(0.0, min(100.0, weighted_score))

    is_qualified = core_competency >= 65.0
    if is_qualified and is_blockchain_verified:
        candidate_label = "Qualified and Verified"
    elif is_qualified:
        candidate_label = "Qualified but Unverified"
    else:
        candidate_label = "Not Yet Qualified"

    if score >= 80:
        risk = "low"
        summary = "High credibility profile with strong competency evidence. Key milestones are backed by the blockchain ledger."
    elif score >= 60:
        risk = "medium"
        if is_blockchain_verified:
            summary = "Credible and blockchain-backed profile, but some competency or signal gaps remain."
        else:
            summary = "Qualified indicators detected, but key milestones are not backed by the blockchain ledger."
    else:
        risk = "high"
        if is_blockchain_verified:
            summary = "Profile is verified on-chain but professional evidence is currently below top-tier hiring threshold."
        else:
            summary = "Multiple credibility gaps detected and milestones are not blockchain-verified; requires manual verification."

    return {
        "score_percent": round(score, 2),
        "risk_level": risk,
        "summary": summary,
        "red_flag_count": red_flags,
        "candidate_classification": candidate_label,
        "verified_credentials_status": "High Credibility" if is_blockchain_verified else "Unverified Credential",
        "weighted_dimensions": {
            "verified_credentials_40": round(verified_component, 2),
            "core_competency_40": round(core_competency, 2),
            "institutional_signal_20": round(institutional_component, 2),
        },
        "role_tracks": strategic["role_tracks"],
        "strategic_signals": strategic_signals,
        "strategic_entities": strategic["entities"],
        "checks": checks,
    }


def analyze_resume_authenticity(cv_text: str) -> Dict[str, object]:
    """Backward-compatible wrapper for legacy calls without JD/verification context."""
    return analyze_resume(
        cv_text=cv_text,
        job_description="",
        is_blockchain_verified=False,
        fit_data=None,
    )
