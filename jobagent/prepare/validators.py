"""Fact validator: rejects any claim in a cover letter not grounded in profile.yaml."""

import re
from typing import Any


def _extract_years(text: str) -> list[str]:
    """Extract 4-digit year strings (2000–2029) from text."""
    return re.findall(r"\b(20\d{2})\b", text)


def _profile_years(profile: dict[str, Any]) -> set[str]:
    """Collect all years mentioned in education and experience blocks."""
    years: set[str] = set()
    for edu in profile.get("education", []):
        years.update(_extract_years(str(edu.get("years", ""))))
    for exp in profile.get("experience", []):
        years.update(_extract_years(str(exp.get("period", ""))))
    return years


def _all_known_skills(profile: dict[str, Any]) -> set[str]:
    """Return all skills (lowercase) from strong + familiar + learning."""
    skills_cfg = profile.get("skills", {})
    raw = (
        skills_cfg.get("strong", [])
        + skills_cfg.get("familiar", [])
        + skills_cfg.get("learning", [])
    )
    return {s.lower() for s in raw}


def _all_known_employers(profile: dict[str, Any]) -> set[str]:
    """Return all company names (lowercase) from experience."""
    return {str(e.get("company", "")).lower() for e in profile.get("experience", [])}


def _all_known_institutions(profile: dict[str, Any]) -> set[str]:
    """Return all institution names (lowercase) from education."""
    return {str(e.get("institution", "")).lower() for e in profile.get("education", [])}


def validate_letter(
    letter: str,
    profile: dict[str, Any],
    job: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check cover letter against profile facts.

    Args:
        letter: The generated cover letter text.
        profile: Parsed profile.yaml dict.
        job: Optional job dict; used to whitelist the target company name.

    Returns:
        A dict with keys:
            ok (bool): True if no hard errors found.
            errors (list[str]): Hard violations — fabricated facts that should block use.
            warnings (list[str]): Soft issues worth noting but not blocking.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Fabricated years (present in letter but not in profile)
    letter_years = set(_extract_years(letter))
    profile_years = _profile_years(profile)
    fake_years = letter_years - profile_years
    if fake_years:
        errors.append(f"Fabricated years not in profile: {sorted(fake_years)}")

    # 2. Suspicious "N years of experience" claims
    exp_matches = re.findall(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", letter, re.I)
    for claim in exp_matches:
        if int(claim) >= 3:
            errors.append(
                f"Inflated experience claim: '{claim}+ years' — profile shows internships only"
            )
        elif int(claim) >= 2:
            warnings.append(f"Borderline experience claim: '{claim} years' — verify this is accurate")

    # 3. Employer references not in profile
    known_employers = _all_known_employers(profile)
    all_skills = _all_known_skills(profile)
    # Whitelist the target company so "working at TestCorp" doesn't false-positive
    target_company = str(job.get("company", "")).lower() if job else ""
    if target_company:
        known_employers.add(target_company)

    # Match "at/with/for/joined CompanyName" where CompanyName is 1–3 capitalized words
    mentioned_at = re.findall(
        r"(?:^|(?<=\s))(?:at|with|for|joined)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})(?=[\s,.])",
        letter,
    )
    skip_words = {"the", "my", "our", "your", "this", "that", "a", "an", "we", "i"}
    connector_words = {"and", "or", "to", "in", "of", "for", "as", "on", "by"}
    for m in mentioned_at:
        m_clean = m.strip().lower()
        if not m_clean or m_clean in skip_words:
            continue
        # Skip if any word is a lowercase connector (phrase, not a company name)
        words = m.strip().split()
        if any(w.lower() in connector_words for w in words):
            continue
        # Skip if it's just a known skill name (e.g. "Python", "FastAPI")
        if m_clean in all_skills:
            continue
        if not any(m_clean in emp or emp in m_clean for emp in known_employers):
            errors.append(f"Employer reference not in profile: '{m.strip()}'")


    # 4. Institution references not in profile
    known_inst = _all_known_institutions(profile)
    inst_matches = re.findall(
        r"(?:studied|graduated|degree|bachelor|master|engineering)\s+(?:at|from)\s+([A-Z][A-Za-z\s,]{3,40}?)(?:\.|,)",
        letter,
        re.I,
    )
    for inst in inst_matches:
        inst_clean = inst.strip().lower()
        if inst_clean and not any(known in inst_clean or inst_clean in known for known in known_inst):
            errors.append(f"Institution reference not in profile: '{inst.strip()}'")

    # 5. Warn about very long letters (over-generation)
    word_count = len(letter.split())
    if word_count > 280:
        warnings.append(f"Letter is {word_count} words — may exceed requested max_words limit")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
