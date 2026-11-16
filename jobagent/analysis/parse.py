"""Deterministic parsing of job postings against candidate profile."""

from pathlib import Path
import re
from typing import Any
import yaml

# Canonical skill detection patterns
SKILL_PATTERNS: dict[str, str] = {
    "Python": r"\bpython\b", "PyTorch": r"\bpytorch\b", "HuggingFace": r"\b(huggingface|hugging\s+face)\b",
    "scikit-learn": r"\b(scikit[\s-]learn|sklearn)\b", "NLP": r"\b(nlp|natural\s+language\s+processing)\b",
    "Transformers": r"\btransformers?\b", "FastAPI": r"\bfastapi\b", "Flask": r"\bflask\b",
    "Docker": r"\bdocker\b", "SQL": r"\bsql\b", "MySQL": r"\bmysql\b", "PostgreSQL": r"\b(postgresql|postgres)\b",
    "MongoDB": r"\b(mongodb|mongo)\b", "Angular": r"\bangular\b", "ASP.NET Core": r"\b(asp\.net\s*core|asp\.net|\.net\s*core)\b",
    "Node.js": r"\b(node\.js|nodejs|node)\b", "Flutter": r"\bflutter\b", "Git": r"\bgit\b", "Linux": r"\blinux\b",
    "Pandas": r"\bpandas\b", "NumPy": r"\bnumpy\b", "REST APIs": r"\b(rest\s+api[s]?|restful)\b",
    "RAG": r"\b(rag|retrieval[\s-]augmented)\b", "Ollama": r"\bollama\b", "TensorFlow": r"\btensorflow\b",
    "XGBoost": r"\bxgboost\b", "Prophet": r"\bprophet\b", "SARIMA": r"\bsarima\b", "ChromaDB": r"\b(chromadb|chroma)\b",
    "YOLO": r"\byolo\b", "Java": r"\bjava\b(?!script)", "C++": r"\bc\+\+", "C#": r"\bc\#|\bc-sharp\b",
    "TypeScript": r"\b(typescript|ts)\b", "React": r"\breact(\.js|js)?\b", "React Native": r"\breact\s+native\b",
    "Firebase": r"\bfirebase\b", "Postman": r"\bpostman\b", "Swagger": r"\bswagger\b", "JWT": r"\bjwt\b",
    "SQL Server": r"\b(sql\s+server|mssql)\b", "spaCy": r"\bspacy\b", "fastText": r"\bfasttext\b",
    "LangChain": r"\blangchain\b", "Kubernetes": r"\b(kubernetes|k8s)\b", "Rust": r"\brust\b",
    "Go": r"\b(golang|go\s+lang(uage)?)\b|\bGo\b(?=[,\s/])", "AWS": r"\b(aws|amazon\s+web\s+services)\b",
    "GCP": r"\b(gcp|google\s+cloud)\b", "Azure": r"\bazure\b", "Ruby on Rails": r"\b(rails|ruby\s+on\s+rails)\b",
    "Ruby": r"\bruby\b", "Kafka": r"\bkafka\b", "Spark": r"\b(apache\s+spark|spark)\b", "Redis": r"\bredis\b",
    "GraphQL": r"\bgraphql\b", "PHP": r"\bphp\b", "Swift": r"\bswift\b", "Kotlin": r"\bkotlin\b",
    "Terraform": r"\bterraform\b",
}


def load_profile() -> dict[str, Any]:
    """Read and return candidate profile from config/profile.yaml."""
    profile_path = Path(__file__).resolve().parents[2] / "config" / "profile.yaml"
    if not profile_path.exists():
        return {}
    with open(profile_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def extract_seniority(title: str, description: str) -> str:
    """Classify seniority level into internship, junior, mid, senior, lead, or unknown."""
    t_lower = title.lower()
    if re.search(r"\b(intern|internship|stage|stagiaire)\b", t_lower):
        return "internship"
    if re.search(r"\b(lead|tech lead|team lead)\b", t_lower):
        return "lead"
    if re.search(r"\b(senior|sr\.?|principal|staff|head of|head|director|manager)\b", t_lower):
        return "senior"
    if re.search(r"\b(junior|entry[\s-]level|entry|graduate|d[ée]butant)\b", t_lower):
        return "junior"
    if re.search(r"\b(mid[\s-]level|mid)\b", t_lower):
        return "mid"

    d_clean = re.sub(r"https?://\S+", " ", description)
    d_clean = re.sub(r"<[^>]+>", " ", d_clean).lower()
    if re.search(r"\b(internship|intern|stage|stagiaire)\b", d_clean):
        return "internship"
    if re.search(r"\b(graduate|entry[\s-]level|junior|d[ée]butant|0-2\s*years?|1\+?\s*years?)\b", d_clean):
        return "junior"
    if re.search(r"\b(senior|sr\.?|lead|principal|head of|director|8\+\s*years?|5\+\s*years?|staff\s+(?:engineer|developer|scientist))\b", d_clean):
        return "senior"
    if re.search(r"\b(mid[\s-]level|3\+\s*years?|4\+\s*years?)\b", d_clean):
        return "mid"
    return "unknown"


def extract_required_skills(description: str, profile: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return tuple of (matched_skills, missing_skills) detected in description."""
    text = re.sub(r"https?://\S+", " ", description)
    text = re.sub(r"<[^>]+>", " ", text)
    skills_sec = profile.get("skills", {})
    known_skills = set(skills_sec.get("strong", []) + skills_sec.get("familiar", []))
    known_lower = {s.lower(): s for s in known_skills}

    matched: list[str] = []
    missing: list[str] = []

    for skill_name, pattern in SKILL_PATTERNS.items():
        flags = re.IGNORECASE if not ("Go" in skill_name and "\\bGo\\b" in pattern) else 0
        if re.search(pattern, text, flags):
            if skill_name.lower() in known_lower:
                matched.append(known_lower[skill_name.lower()])
            else:
                missing.append(skill_name)

    return sorted(list(dict.fromkeys(matched))), sorted(list(dict.fromkeys(missing)))


def extract_language_requirements(description: str) -> dict[str, bool]:
    """Extract required languages from job description."""
    text = description.lower()
    return {
        "requires_french": bool(re.search(
            r"\b(fluent french|french required|french mandatory|french speaking|"
            r"ma[îi]trise du fran[çc]ais|fran[çc]ais courant|fran[çc]ais exig[ée]|parlant fran[çc]ais)\b",
            text,
        )),
        "requires_english": bool(re.search(
            r"\b(fluent english|english required|english mandatory|english speaking|"
            r"anglais courant|anglais exig[ée])\b",
            text,
        )),
        "requires_german": bool(re.search(
            r"\b(fluent german|german required|german mandatory|deutschkenntnisse|"
            r"deutsch flie[ßs]end|german speaking)\b",
            text,
        )),
    }


def extract_location_eligibility(location: str, description: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Evaluate candidate eligibility based on job location and residency terms."""
    loc = (location or "").lower()
    desc = (description or "").lower()
    eu_visa = profile.get("eligibility", {}).get("eu_visa_route", False)

    if "tunisia" in loc or "tunisie" in loc:
        return {"eligible": True, "reason": "Tunisia / Local"}
    if any(k in loc for k in ["worldwide", "anywhere", "global"]):
        return {"eligible": True, "reason": "Worldwide remote"}
    if any(k in loc for k in ["europe", "eu", "emea"]):
        is_remote = "remote" in loc or "remote" in desc or True
        if eu_visa or is_remote:
            return {"eligible": True, "reason": "Europe/EMEA remote"}
    is_remote = "remote" in loc or "remote" in desc
    if not is_remote and any(c in loc for c in ["germany", "usa", "uk", "france", "canada"]):
        return {"eligible": False, "reason": "On-site outside Tunisia without visa"}
    if is_remote:
        return {"eligible": True, "reason": "Remote position"}
    return {"eligible": False, "reason": "unclear - manual review"}


def detect_deal_breakers(title: str, description: str, profile: dict[str, Any]) -> list[str]:
    """Identify deal breaker phrases in job title and description."""
    clean_desc = re.sub(r"https?://\S+", " ", description)
    clean_desc = re.sub(r"<[^>]+>", " ", clean_desc)
    text = f"{title} {clean_desc}".lower()
    matched: list[str] = []
    for db in profile.get("deal_breakers", []):
        db_clean = db.strip().lower()
        if db_clean == "sales" and re.search(r"\bsales\b", text):
            matched.append(db)
        elif db_clean == "commission-only" and ("commission-only" in text or "commission only" in text):
            matched.append(db)
        elif db_clean == "unpaid" and re.search(r"\bunpaid\b", text):
            matched.append(db)
        elif db_clean in ("requires 3+ years experience", "requires 5+ years experience"):
            years = "5" if "5" in db_clean else "3"
            if re.search(rf"\b({years}\+\s*years?|{years}\s*years?\s+of\s+experience)\b", text):
                matched.append(db)
        elif db_clean in text:
            matched.append(db)
    return list(dict.fromkeys(matched))


def parse_job(job: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Orchestrate deterministic parsing of a single job record."""
    title = str(job.get("title") or "")
    desc = str(job.get("description") or "")
    loc = str(job.get("location") or "")

    return {
        "seniority": extract_seniority(title, desc),
        "matched_skills": extract_required_skills(desc, profile)[0],
        "missing_skills": extract_required_skills(desc, profile)[1],
        "language_requirements": extract_language_requirements(desc),
        "location_eligibility": extract_location_eligibility(loc, desc, profile),
        "deal_breakers": detect_deal_breakers(title, desc, profile),
    }
