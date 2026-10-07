# AI Keyword Research Tool

Flask web application that uses an AI API (Groq free tier by default) to generate keyword research ideas with estimated SEO metrics, plus advanced analysis tools.

## Features

- **Keyword research** — enter a seed keyword, get related keywords with estimated volume, difficulty, intent, and CPC
- **Filter & export** — filter by search intent, export results as CSV, one-click copy to clipboard
- **Save & manage** — rename, delete, and assign searches to named groups/folders
- **Compare** — view two searches side-by-side
- **Bulk import** — upload a CSV of seed keywords (capped to 5 per run due to free-tier rate limits)
- **AI Tools** (all powered by the free Groq tier):
  - Keyword Expansion — long-tail variations and question-based suggestions
  - Intent Classification — informational/commercial/transactional/navigational per keyword
  - Content Clustering — group keywords into topic clusters with content briefs
  - PPC & Budget Forecast — impressions, CTR, clicks, CPC, and monthly budget estimates
- **Async logging** — non-blocking via `QueueHandler`/`QueueListener`

## Requirements

- Python 3.11+
- A free **Groq** API key from https://console.groq.com/keys (no credit card required)

## Setup

```bash
cd keyword-research

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set GROQ_API_KEY
```

Run:

```bash
python app.py
# or
flask --app app run
```

Open http://localhost:5000

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `groq` | Backend provider: `groq` (free) or `openai` (paid) |
| `GROQ_API_KEY` | (required for groq) | Free Groq key |
| `AI_MODEL` | `openai/gpt-oss-120b` | Model used (must support JSON mode) |
| `AI_BASE_URL` | `https://api.groq.com/openai/v1` | API endpoint |
| `OPENAI_API_KEY` | (for openai) | OpenAI key (needs billing) |
| `SECRET_KEY` | dev-secret-key | Flask session secret |
| `MAX_KEYWORDS` | 20 | Max keywords per result list |
| `REQUEST_TIMEOUT` | 30 | API request timeout (seconds) |

## Tests

```bash
pytest
```

## Project Structure

```
keyword-research/
├── app.py                    # App factory
├── config.py                 # Configuration
├── models.py                 # SQLAlchemy models (Search, Keyword, Folder)
├── services/ai_researcher.py # AI integration + advanced tool prompts
├── routes/
│   ├── main.py               # Home, health
│   ├── research.py           # Research, results, export, AI tools
│   └── manage.py             # Folders, manage, compare, import
├── templates/                # Jinja2 templates
├── static/                   # CSS/JS
├── utils/logging_config.py   # Async logging
└── tests/                    # Pytest suite (27 tests)
```

## Notes

- **Free-tier limits**: Groq free plan allows ~30 requests/minute. Bulk import is capped at 5 seed keywords per run to stay within this.
- **Real search volume**: volumes/difficulty/CPC are AI *estimates*, not live Google/Semrush data. Accurate volume and competitor/gap analysis require paid third-party APIs.
