# JobAgent

A personal, local-first job-search automation tool designed for discovering junior/entry-level AI, ML, NLP, Python, and software engineering roles.

> **Status:** **Phase 3 (Discovery Pipeline)**, **Phase 4 (Deterministic Scoring & Shortlisting)**, **Phase 5 (Preparation & Approval)**, and **Phase 6 (Web UI)** are fully implemented and verified.

---

## Features

- **Remotive Fetcher (Phase 3)**: Fetches remote job postings using the Remotive API with configurable keywords.
- **SQLite Storage & Deduplication (Phase 3)**: Persists jobs to `~/jobagent/data/jobs.db` and skips duplicates based on unique `source_url`.
- **Deterministic Scoring & Shortlisting (Phase 4)**: Audits job postings against `config/profile.yaml` with a 0–100 rubric, filters deal breakers and seniority mismatches, and ranks actionable opportunities.
- **LLM Cover Letter Preparation & Validation (Phase 5)**: Local Ollama LLM drafts cover letters tailored to verified facts with strict validation against hallucinations.
- **Local Web UI (Phase 6)**: Modern React + Vite dashboard served by FastAPI, providing interactive job shortlists, real-time Ollama status, letter editing, and packet approval.
- **Rich Terminal Interface**: Complete CLI support with formatted summary tables and statistics via `rich`.

---

## Remotive API Rate-Limit Warning

Remotive terms specify a limit of approximately **4 requests per day** and no more than **2 requests per minute**.
- The default configuration in `config/sources.yaml` queries **2 keywords** (`python`, `machine learning`) with a 1-second delay between requests to strictly respect these boundaries.
- Do not increase the keyword list beyond 2–3 terms to avoid exceeding the daily limit.

---

## Phase 4 — Scoring & Shortlisting

Scoring is fully deterministic, transparent, and auditable without calling external APIs or LLMs. Results are stored in the SQLite `matches` table and can be re-run safely and idempotently (using `INSERT OR REPLACE`).

### Scoring Rubric (100 Points Max)

| Dimension | Max Points | Evaluation Rules |
| :--- | :--- | :--- |
| **Skill Overlap** | 40 pts | `40 * len(matched) / max(1, len(matched) + len(missing))` |
| **Role Family Match** | 20 pts | +20 if target role keyword in title, +10 if in description only, 0 otherwise |
| **Seniority Fit** | 10 pts | +10 for accepted entry/junior/intern levels, +5 for unknown, 0 for mid, -50 for senior/lead |
| **Location / Eligibility** | 10 pts | +10 if eligible in top priorities (Tunisia / EU remote), +7 if general remote, 0 if ineligible |
| **Language Fit** | 10 pts | +10 for English/none, +5 for French (intermediate profile), -30 / reject for German |
| **Recency** | 10 pts | +10 for <=14 days, +6 for <=45 days, +2 for older, +5 if unparseable |

### Hard Rejections (Score = 0, Verdict: `unsuitable`)
- Matched deal breaker (e.g. sales, unpaid, commission-only, strict 3+/5+ years requirement).
- Seniority mismatch (senior, lead, principal, staff, head, director).
- On-site outside Tunisia without visa.
- Unmet language requirements (German required, or French required with basic proficiency).

---

## Phase 5 — Application Preparation & Terminal Flow

```bash
# Prepare application and draft cover letter (if required)
python -m jobagent.cli prepare <id>

# Review packet in terminal, edit in $EDITOR, and approve
python -m jobagent.cli review <id>

# View prepared applications
python -m jobagent.cli applications
```

---

## Phase 6 — Web UI

### 1. What It Is
A local React + TypeScript dashboard built with Vite and served directly by FastAPI as static files. No cloud services, external UI frameworks, or auth providers.

### 2. One-Time Setup
```bash
cd ~/jobagent
source venv/bin/activate
pip install fastapi uvicorn
cd jobagent/web
npm install
npm run build
cd ~/jobagent
```

### 3. Daily Use
```bash
python -m jobagent.cli serve # open http://127.0.0.1:8000
```

### 4. Rebuilding the Frontend After Changes
```bash
cd jobagent/web && npm run build
```

### 5. Security Note
Binds strictly to `127.0.0.1:8000`. No remote access. No auth. Do **NOT** expose to the public internet.

### 6. CLI Compatibility
The CLI remains fully functional and independent — the Web UI is an optional interactive frontend on top of the same SQLite database and engine modules.
