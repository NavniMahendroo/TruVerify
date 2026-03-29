from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List


def _extract_years(text: str) -> List[int]:
    return [int(match.group(0)) for match in re.finditer(r"\b(19|20)\d{2}\b", text)]


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


def analyze_resume_authenticity(cv_text: str) -> Dict[str, object]:
    """Heuristic authenticity and consistency checks for resume content.

    This is a plausibility score, not legal proof. It flags red/green signals and
    year consistency while preserving explainability for users.
    """
    now_year = datetime.now(timezone.utc).year
    checks: List[Dict[str, str]] = []

    score = 50.0
    red_flags = 0

    years = _extract_years(cv_text)
    if years:
        future_years = [y for y in years if y > now_year + 1]
        very_old_years = [y for y in years if y < 1980]
        if future_years:
            red_flags += 1
            score -= 18
            checks.append(
                {
                    "name": "Year Consistency",
                    "status": "warning",
                    "details": f"Future years found: {sorted(set(future_years))}",
                }
            )
        elif very_old_years:
            red_flags += 1
            score -= 8
            checks.append(
                {
                    "name": "Year Consistency",
                    "status": "warning",
                    "details": f"Unusual old years found: {sorted(set(very_old_years))}",
                }
            )
        else:
            score += 8
            checks.append(
                {
                    "name": "Year Consistency",
                    "status": "pass",
                    "details": "Timeline years look plausible.",
                }
            )
    else:
        red_flags += 1
        score -= 10
        checks.append(
            {
                "name": "Year Consistency",
                "status": "warning",
                "details": "No education/experience years detected.",
            }
        )

    if _has_contact_signals(cv_text):
        score += 6
        checks.append(
            {
                "name": "Contact Completeness",
                "status": "pass",
                "details": "Email and phone-like signals detected.",
            }
        )
    else:
        score -= 6
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
        score += 8
        checks.append(
            {
                "name": "Core Sections",
                "status": "pass",
                "details": "Education and experience sections are present.",
            }
        )
    else:
        red_flags += 1
        score -= 8
        checks.append(
            {
                "name": "Core Sections",
                "status": "warning",
                "details": "Education or experience section is weak/missing.",
            }
        )

    project_signal_count = _count_project_signals(cv_text)
    if has_projects and project_signal_count >= 3:
        score += 12
        checks.append(
            {
                "name": "Project Evidence",
                "status": "pass",
                "details": "Projects include technical/actionable details.",
            }
        )
    elif has_projects:
        score += 2
        checks.append(
            {
                "name": "Project Evidence",
                "status": "warning",
                "details": "Projects present but with limited technical depth.",
            }
        )
    else:
        score -= 6
        checks.append(
            {
                "name": "Project Evidence",
                "status": "warning",
                "details": "No project section detected.",
            }
        )

    all_caps_ratio = 0.0
    letters = re.findall(r"[A-Za-z]", cv_text)
    if letters:
        upper = sum(1 for c in letters if c.isupper())
        all_caps_ratio = upper / len(letters)
    if all_caps_ratio > 0.6:
        red_flags += 1
        score -= 7
        checks.append(
            {
                "name": "Formatting Quality",
                "status": "warning",
                "details": "Text appears overly uppercase/noisy.",
            }
        )
    else:
        score += 4
        checks.append(
            {
                "name": "Formatting Quality",
                "status": "pass",
                "details": "Formatting looks readable for parsing.",
            }
        )

    score = max(0.0, min(100.0, score))

    if score >= 80:
        risk = "low"
        summary = "Strong authenticity signals with consistent timeline and concrete evidence."
    elif score >= 60:
        risk = "medium"
        summary = "Mostly plausible resume with some gaps or weak evidence areas."
    else:
        risk = "high"
        summary = "Multiple credibility gaps detected; requires manual verification."

    return {
        "score_percent": round(score, 2),
        "risk_level": risk,
        "summary": summary,
        "red_flag_count": red_flags,
        "checks": checks,
    }
