"""Deterministic scoring engine for matching jobs against candidate profile."""

from datetime import datetime, timezone
import re
from typing import Any


def parse_posted_days(posted_at: str | None) -> float | None:
    """Calculate the number of days elapsed since the job was posted."""
    if not posted_at:
        return None
    try:
        clean = posted_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
    except Exception:
        return None


def generate_reasons(parsed: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    """Generate concise, human-readable rationale strings for score and verdict."""
    reasons: list[str] = []
    if parsed.get("deal_breakers"):
        reasons.append(f"Deal breaker: {', '.join(parsed['deal_breakers'])}")

    matched, missing = parsed.get("matched_skills", []), parsed.get("missing_skills", [])
    if matched:
        suffix = f" (+{len(matched) - 4} more)" if len(matched) > 4 else ""
        reasons.append(f"Matches: {', '.join(matched[:4])}{suffix}")
    if missing:
        reasons.append(f"Missing: {', '.join(missing[:3])}")

    sen = parsed.get("seniority", "unknown")
    if sen in ("internship", "junior"):
        reasons.append(f"{sen.capitalize()}-level — good fit")
    elif sen in ("senior", "lead"):
        reasons.append(f"Seniority mismatch ({sen})")

    loc_info = parsed.get("location_eligibility", {})
    reasons.append(f"Location: {loc_info.get('reason', 'eligible')}" if loc_info.get("eligible") else f"Location ineligible: {loc_info.get('reason', 'unclear')}")

    lang = parsed.get("language_requirements", {})
    if lang.get("requires_german"):
        reasons.append("German required — candidate has none")
    elif lang.get("requires_french"):
        reasons.append("French required — candidate is intermediate")

    return [f"{r[:120]}..." if len(r) > 120 else r for r in reasons]


def score_job(job: dict[str, Any], parsed: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Calculate deterministic 0-100 fit score and return verdict with explanations."""
    flags: list[str] = []
    hard_reject_reasons: list[str] = []

    # 1. Skill overlap (40 pts) - Universal 1x, core strong 2x, familiar 1x
    matched, missing = parsed.get("matched_skills", []), parsed.get("missing_skills", [])
    strong_lower = {s.lower() for s in profile.get("skills", {}).get("strong", [])}
    universal_lower = {s.lower() for s in profile.get("skill_weights", {}).get("universal", [])}
    weighted_matched = sum(2.0 if (m.lower() in strong_lower and m.lower() not in universal_lower) else 1.0 for m in matched)
    weighted_total = weighted_matched + float(len(missing))
    skill_pts = 40.0 * (weighted_matched / max(1.0, weighted_total))

    # 2. Role family match (20 pts) — tiered
    roles_cfg = profile.get("target_roles", {})
    primary = [r.lower() for r in roles_cfg.get("primary", [])] if isinstance(roles_cfg, dict) else []
    secondary = [r.lower() for r in roles_cfg.get("secondary", [])] if isinstance(roles_cfg, dict) else []
    title_lower = (job.get("title") or "").lower()
    desc_clean = re.sub(r"<[^>]+>", " ", job.get("description") or "").lower()

    if any(r in title_lower for r in primary):
        role_pts, role_tier = 20.0, "primary"
    elif any(r in title_lower for r in secondary):
        role_pts, role_tier = 14.0, "secondary"
    elif any(r in desc_clean for r in primary):
        role_pts, role_tier = 10.0, "primary_desc"
    elif any(r in desc_clean for r in secondary):
        role_pts, role_tier = 6.0, "secondary_desc"
    else:
        role_pts, role_tier = 0.0, "none"

    # Downweight annotation/training-data roles
    downweight_keywords = profile.get("role_quality", {}).get("downweight_titles", [])
    if any(kw.lower() in title_lower for kw in downweight_keywords):
        role_pts = min(role_pts, 6.0)
        flags.append("possible_annotation_role")

    # 3. Seniority fit (10 pts)
    sen = parsed.get("seniority", "unknown")
    accept_sen = profile.get("seniority", {}).get("accept", [])
    if sen in accept_sen:
        sen_pts = 10.0
    elif sen == "unknown":
        sen_pts = 5.0
    elif sen == "mid":
        sen_pts = 0.0
    else:
        sen_pts = -50.0
        hard_reject_reasons.append(f"Seniority is {sen}")

    # 4. Location eligibility (10 pts)
    loc_elig = parsed.get("location_eligibility", {})
    job_loc = (job.get("location") or "").lower()
    if loc_elig.get("eligible", False):
        loc_pts = 10.0 if any(p in job_loc for p in ["tunisia", "eu timezone", "europe"]) else 7.0
    else:
        loc_pts = 0.0
        flags.append("location_ineligible")
        if "on-site" in job_loc or not ("remote" in job_loc or "remote" in desc_clean):
            hard_reject_reasons.append("On-site outside Tunisia without visa")

    # 5. Language fit (10 pts)
    langs = parsed.get("language_requirements", {})
    user_french = profile.get("languages", {}).get("french", "intermediate")
    if langs.get("requires_german"):
        lang_pts = -30.0
        hard_reject_reasons.append("Requires German")
    elif langs.get("requires_french"):
        lang_pts = 5.0 if user_french in ("intermediate", "advanced", "native") else 0.0
        if user_french not in ("intermediate", "advanced", "native"):
            hard_reject_reasons.append("French required but candidate is below intermediate")
    else:
        lang_pts = 10.0

    # 6. Recency (10 pts)
    days = parse_posted_days(job.get("posted_at"))
    recency_pts = 5.0 if days is None else (10.0 if days <= 14 else (6.0 if days <= 45 else 2.0))

    deal_breakers = parsed.get("deal_breakers", [])
    if deal_breakers:
        hard_reject_reasons.append(f"Deal breaker matched: {', '.join(deal_breakers)}")

    raw_score = skill_pts + role_pts + sen_pts + loc_pts + lang_pts + recency_pts

    if hard_reject_reasons:
        score = 0
        verdict = "unsuitable"
    else:
        score = max(0, min(100, int(round(raw_score))))
        verdict = "high_priority" if score >= 70 else ("worth_reviewing" if score >= 40 else "unsuitable")

    reasons = generate_reasons(parsed, profile)
    for hr in hard_reject_reasons:
        if hr not in reasons:
            reasons.insert(0, hr)

    # Gate A: Zero role match cannot be high_priority
    if role_pts == 0.0 and verdict == "high_priority":
        verdict = "worth_reviewing"
        reasons.append("Role family mismatch — not a target role")

    # Gate B: Secondary-only + weak skills cannot be high_priority
    if role_tier in ("secondary", "secondary_desc") and skill_pts < 30.0 and verdict == "high_priority":
        verdict = "worth_reviewing"
        reasons.append("Generic software role — verify ML/AI focus before applying")

    # Gate C: Possible annotation roles never high_priority
    if "possible_annotation_role" in flags and verdict == "high_priority":
        verdict = "worth_reviewing"
        reasons.append("⚠️ Likely annotation/training-data role — verify before applying")

    # Guard against suspiciously high skill coverage in laundry-list descriptions
    total_skills = len(matched) + len(missing)
    if total_skills > 0 and (len(matched) / total_skills) > 0.85 and len(matched) >= 5:
        reasons.append("Skill match unusually high — review manually")
        if verdict == "high_priority":
            verdict = "worth_reviewing"

    return {
        "score": score,
        "reasons": reasons,
        "missing": missing,
        "eligibility_flags": flags,
        "verdict": verdict,
        "parsed": parsed,
    }
