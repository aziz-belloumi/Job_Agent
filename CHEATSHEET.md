# JobAgent — Daily Cheat Sheet

## Every morning (5 min)
cd ~/jobagent && source venv/bin/activate
python -m jobagent.cli discover
python -m jobagent.cli score
python -m jobagent.cli shortlist

## When you find a job worth applying to
python -m jobagent.cli prepare <id>
python -m jobagent.cli review <id>
# Then open the job URL in your browser and submit manually.

## Useful queries
# See the job URL for a given ID:
sqlite3 data/jobs.db "SELECT title, company, source_url FROM jobs WHERE id=<id>;"

# See full reasons for a job:
sqlite3 data/jobs.db "SELECT reasons_json FROM matches WHERE job_id=<id>;"

## Limits
- Remotive updates jobs once per day (24h delay). Don't run discover more than 2–3 times/day.
- The generated cover letter is a DRAFT. Edit it for 3–8 minutes before sending.
- The validator blocks fabricated facts. If it blocks a real fact, add it to config/profile.yaml.
