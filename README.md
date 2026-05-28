# Annix Read

AI-powered book summaries. The essence of any book, in 10 minutes — with read, listen, translate, and export to PDF or EPUB.

**100% free for educational use.** Pick any of three AI backends:

| Backend | Cost | Setup | Quality |
|---|---|---|---|
| **Gemini Flash** | Free (1500 requests/day) | 5-min signup, no credit card | Very good ⭐ recommended |
| **Ollama** | Free, no key | Install Ollama + 5GB model | Decent (offline + private) |
| **Claude Opus** | ~$0.10 / book | Anthropic account | Best |

…plus **gTTS** for audio (free, no key) and a tiny FastAPI + SQLite stack.

## Features

- **Generate summaries on demand.** Pick a book from the catalog, click *Generate*, get a structured 800–1200-word Markdown summary covering thesis, key ideas, memorable examples, takeaways, and an honest critique.
- **18 languages.** Translate any generated summary; cached per (book, language) pair so it only ever runs once.
- **Audio narration.** Listen to the summary in any supported language. MP3 files are cached on disk.
- **Downloadable.** Export PDF or EPUB in any supported language.
- **Catalog seeded with 60 classics** across 13 genres — fiction, philosophy, business, science, psychology, history, sci-fi, biography, and more.
- **Request any book.** Don't see it? Type a title + author on the homepage and the AI generates a fresh summary. New books are added to the catalog and the summary is cached.
- **Pre-cache the whole catalog.** Run `python -m app.precache` once with any AI provider configured and every seeded book's summary lands in the DB. Ship the resulting `data/annix_read.db` and every visitor gets instant summaries with **no API key required, ever**.
- **Cached summaries / translations / audio** survive restarts via SQLite.

## Quickstart

### 1. Install dependencies

```powershell
cd C:\Users\khang\annix_read
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure one AI backend (pick one — first two are free)

```powershell
copy .env.example .env
notepad .env       # uncomment ONE of GOOGLE_API_KEY / ENABLE_OLLAMA / ANTHROPIC_API_KEY
```

**Easiest (free):** get a Gemini key at <https://aistudio.google.com/app/apikey>, no credit card. Paste as `GOOGLE_API_KEY` in `.env`.

**Truly offline (free, no key):** install [Ollama](https://ollama.ai/download), run `ollama pull llama3.1`, set `ENABLE_OLLAMA=1` in `.env`.

### 3. Run

```powershell
python run.py
```

Open <http://127.0.0.1:8000> and click any book — the summary auto-generates on first visit.

### 4. (Optional) Pre-cache the catalog for zero-API hosting

If you want to deploy this and have visitors use it with no API key at all:

```powershell
# On a machine that has one of the AI backends configured:
python -m app.precache

# Then ship data\annix_read.db with your deployment. Done.
```

Add `--audio --pdf --epub` to also pre-render those for every book (slower, more disk).

## Architecture

```
annix_read/
├── app/
│   ├── main.py           # FastAPI routes (pages + API)
│   ├── ai.py             # Claude integration — summary + translation
│   ├── exports.py        # gTTS audio + fpdf2 PDF + ebooklib EPUB
│   ├── db.py             # SQLAlchemy engine + session factory + init_db
│   ├── models.py         # Book / Summary / Translation / AudioFile
│   ├── catalog.py        # Seed list + supported languages
│   ├── templates/        # Jinja2 (base / index / book)
│   └── static/           # style.css + app.js
├── data/                 # SQLite + generated MP3 / PDF / EPUB (gitignored)
├── requirements.txt
├── run.py                # uvicorn entrypoint
└── .env.example
```

### Data flow

1. **Browse** → SQLite query of the catalog.
2. **Click a book** → server-rendered detail page. If the summary already exists in DB, it's shown immediately.
3. **Generate summary** → POST `/api/books/{id}/summary` → calls Claude with prompt caching on the stable system prompt → result stored in `summaries` table.
4. **Change language** → POST `/api/books/{id}/translation?lang=es` → Claude translates the cached English summary → stored in `translations`.
5. **Listen / PDF / EPUB** → reads the appropriate cached text and emits the file (also cached on disk).

## API reference

| Method | Path                                              | Purpose                          |
|--------|---------------------------------------------------|----------------------------------|
| GET    | `/`                                               | Browse catalog (optional `?q=…`) |
| POST   | `/book/new`                                       | Add a user-requested book (title/author form) |
| GET    | `/book/{id}`                                      | Book detail page (`?auto=1` auto-triggers generation) |
| POST   | `/api/books/{id}/summary`                         | Generate the English summary     |
| GET    | `/api/books/{id}/translation?lang=es`             | Fetch cached translation         |
| POST   | `/api/books/{id}/translation?lang=es`             | Generate translation             |
| GET    | `/api/books/{id}/audio?lang=es`                   | MP3 narration                    |
| GET    | `/api/books/{id}/export.pdf?lang=es`              | PDF download                     |
| GET    | `/api/books/{id}/export.epub?lang=es`             | EPUB download                    |
| GET    | `/api/health`                                     | Health + API-key status          |

## Customisation

- **Add more books.** Append entries to `SEED_BOOKS` in `app/catalog.py`, delete `data/annix_read.db`, restart.
- **Add a language.** Append to `SUPPORTED_LANGUAGES` in `app/catalog.py` (use a gTTS-compatible code).
- **Tune summaries.** Edit `_SUMMARY_SYSTEM` in `app/ai.py`. The system prompt is cacheable — keep it stable for cache hits.
- **Swap the model.** `MODEL = "claude-opus-4-7"` at the top of `app/ai.py`. For higher throughput, try `claude-sonnet-4-6`.

## Deploy to Render (free)

A `render.yaml` blueprint is included. After pushing this repo to GitHub:

1. Sign in at <https://dashboard.render.com>
2. **New → Blueprint** → pick this repo
3. Render reads `render.yaml` and asks for the `ANTHROPIC_API_KEY` env var
4. First deploy takes ~3–5 minutes; you get a public `https://annix-read-<hash>.onrender.com` URL

Free-tier notes:
- The service sleeps after 15 minutes of inactivity (~30s cold start when it wakes).
- The filesystem is ephemeral — SQLite + cached audio/PDF/EPUB reset on each redeploy. Summaries regenerate on demand and are re-cached. For permanent storage attach a persistent disk (paid) or migrate to Postgres.

## What this is not

- **Not a copy of the book.** Summaries are AI-generated literary analysis — fair use under most jurisdictions, but check yours before commercial deployment.
- **Not production-hardened.** SQLite + a single uvicorn worker is fine for development and small deployments. For real traffic: Postgres + multiple workers + a CDN for audio/PDF, plus per-IP rate limits on the generation endpoints (each one costs Claude credits).
- **Not free to run.** Each summary call hits the Anthropic API. Use prompt caching, generate once per book, and cache aggressively in the DB (we already do).

## License

MIT.
