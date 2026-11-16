"""Cover letter generation via local Ollama LLM with profile-grounded prompting."""

import re
from pathlib import Path
from typing import Any

import yaml

from jobagent.prepare import llm as llm_client
from jobagent.prepare.validators import validate_letter

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "cv.yaml"
_PROFILE_PATH = Path(__file__).resolve().parents[2] / "config" / "profile.yaml"


def load_cv_config() -> dict[str, Any]:
    """Load cover letter generation settings from config/cv.yaml."""
    if not _CONFIG_PATH.exists():
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_profile() -> dict[str, Any]:
    """Load candidate profile from config/profile.yaml."""
    if not _PROFILE_PATH.exists():
        return {}
    with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def cover_letter_requested(description: str, cfg: dict[str, Any]) -> bool:
    """Return True if the job description explicitly asks for a cover letter.

    Checks for any of the required_phrases from config/cv.yaml (case-insensitive).
    """
    phrases = cfg.get("cover_letter", {}).get("required_phrases", [])
    desc_lower = description.lower()
    return any(p.lower() in desc_lower for p in phrases)


def _build_prompt(job: dict[str, Any], profile: dict[str, Any], max_words: int) -> str:
    """Build a strict, fact-anchored prompt for Qwen to generate a cover letter."""
    name = profile.get("identity", {}).get("name", "the candidate")
    location = profile.get("identity", {}).get("location", "")
    education = profile.get("education", [])
    experience = profile.get("experience", [])
    strong = profile.get("skills", {}).get("strong", [])[:8]

    edu_summary = "; ".join(
        f"{e.get('degree')} at {e.get('institution')} ({e.get('years')})"
        for e in education
    )
    exp_summary = "; ".join(
        f"{e.get('title')} at {e.get('company')} ({e.get('period')})"
        for e in experience
    )

    title = job.get("title", "")
    company = job.get("company", "")
    desc_clean = re.sub(r"<[^>]+>", " ", job.get("description") or "")[:800]

    return f"""You are writing a professional cover letter for {name} applying to "{title}" at {company}.

STRICT RULES — follow all:
1. Exactly 3 paragraphs. No bullet points. No headers.
2. Total length: under {max_words} words.
3. Only use facts from VERIFIED FACTS. Do NOT invent dates, degrees, companies, or skills.
4. Do not claim experience beyond internships. Never write "3+ years" or "5+ years".
5. Opening salutation: "Dear Hiring Team," only. No closing signature.
6. Write in English, formal but natural.

VERIFIED FACTS about {name}:
- Education: {edu_summary}
- Work experience: {exp_summary}
- Location: {location}
- Core skills: {', '.join(strong)}

JOB CONTEXT (tailor paragraph 2 to this):
Role: {title} at {company}
Description excerpt: {desc_clean}

PARAGRAPH STRUCTURE:
1. Opening: who I am, degree/specialization, why this role excites me.
2. Middle: 2–3 skills or project experiences from VERIFIED FACTS that match the job.
3. Closing: enthusiasm for the mission, invite to discuss further.

Write the 3-paragraph letter now (no headers, no signature block):"""


def generate(job: dict[str, Any], profile: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Generate and validate a cover letter for a given job.

    Args:
        job: Job row dict (title, company, description, …).
        profile: Parsed profile.yaml dict.
        cfg: Parsed cv.yaml dict.

    Returns:
        Dict with keys: letter (str), status (str), violations (list[str]), warnings (list[str]).
        status is one of: 'generated', 'generated_with_warnings', 'validation_failed'.
    """
    max_words = cfg.get("cover_letter", {}).get("max_words", 220)
    prompt = _build_prompt(job, profile, max_words)

    # First attempt
    letter = llm_client.call(prompt, cfg)
    result = validate_letter(letter, profile, job)

    # One retry with stricter instruction if hard errors found
    if not result["ok"]:
        strict_prefix = (
            "IMPORTANT: Your previous draft contained factual errors. "
            "Do NOT invent companies, dates, or years absent from VERIFIED FACTS. "
            "Do NOT claim more than internship-level experience.\n\n"
        )
        letter = llm_client.call(strict_prefix + prompt, cfg)
        result = validate_letter(letter, profile, job)

    if not result["ok"]:
        status = "validation_failed"
    elif result["warnings"]:
        status = "generated_with_warnings"
    else:
        status = "generated"

    return {
        "letter": letter,
        "status": status,
        "violations": result["errors"],
        "warnings": result["warnings"],
    }
