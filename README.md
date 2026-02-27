# Gimme Job Tool

Automated job application agent that discovers, analyzes, and applies to jobs for you.

## Architecture

```
React Dashboard → FastAPI Backend → SQLite
                      ↓
        ┌─────────────┼─────────────┐
   Job Fetcher   AI Analyzer   Auto-Apply
  (Greenhouse)   (Azure GPT)  (Playwright)
    (Ashby)
```

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env        # Edit with your Azure OpenAI keys
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### API Docs

Once running, visit: `http://localhost:8000/docs`

## Usage

1. **Set up profile** — `POST /api/profile` with your name, email, preferences
2. **Upload resume** — `POST /api/profile/resume`
3. **Add companies** — `POST /api/companies` (with Greenhouse/Ashby board tokens)
4. **Run pipeline** — `POST /api/pipeline/run` (fetches → analyzes → tailors → applies)

## Configuration (.env)

| Variable | Description |
|---|---|
| `AZURE_OPENAI_API_KEY` | Your Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name (e.g., gpt-4o) |
| `MAX_APPLICATIONS_PER_RUN` | Cap on applications per pipeline run |
| `MIN_RELEVANCE_SCORE` | Minimum AI score (0-100) to match a job |
| `DRY_RUN` | Set to `true` to fill forms without submitting |
