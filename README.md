# Media Monitoring MVP

Local Python app for monitoring Russian-language news and web pages about construction, renovation, landscaping, infrastructure, tenders, and development projects.

It includes:

- FastAPI web UI with a Russian region/city dropdown
- existing CLI pipeline in `main.py`
- web search, article fetching, OpenAI relevance analysis, and deduplication
- SQLite storage in `data/app.db`
- per-run Excel and JSON exports in `outputs/`
- rejected item tracking for noisy or failed results

## Requirements

- Python 3.10+
- OpenAI API key

## Install

```bash
pip install -r requirements.txt
```

## Environment

Create `.env` from the example:

```bash
cp .env.example .env
```

Set your key:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
MAX_RESULTS_PER_QUERY=5
MAX_ARTICLE_CHARS=12000
OUTPUT_DIR=outputs
```

## Run Web App

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Use it by selecting a region, clicking `Run Monitoring`, then viewing or downloading the results.

Routes:

- `GET /`
- `POST /run`
- `GET /results/{run_id}`
- `GET /download/{run_id}/excel`
- `GET /download/{run_id}/json`

## Run CLI

```bash
python main.py
```

The CLI keeps writing:

- `outputs/leads.json`
- `outputs/leads.csv`
- `outputs/rejected.json`

## Web Outputs

Each web run writes:

- SQLite database: `data/app.db`
- Excel export: `outputs/{region_key}_run_{run_id}_leads.xlsx`
- JSON export: `outputs/{region_key}_run_{run_id}_leads.json`

The results page shows:

- region and city
- total search results
- fetched articles
- AI analyzed
- rejected count
- duplicates removed
- final leads count
- lead table with source links

## Notes

- One failed query, URL, or AI analysis does not stop the whole run.
- Russian text is saved as UTF-8 in JSON and SQLite.
- The app is local and intentionally simple; Telegram and CRM features are not included.
