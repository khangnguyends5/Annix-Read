"""FastAPI app — browse, search, generate, translate, audio, exports."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # read .env into the process before anything else runs

from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from . import models, ai, exports
from .db import init_db, get_db, DATA_DIR
from .catalog import SUPPORTED_LANGUAGES, LANG_NAME

BASE_DIR     = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR   = BASE_DIR / "static"

app = FastAPI(title="Annix Read", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@app.on_event("startup")
def _startup():
    init_db()


# ─── Pages ───────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Book)
    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(
            models.Book.title.ilike(pattern),
            models.Book.author.ilike(pattern),
            models.Book.genre.ilike(pattern),
        ))
    books = query.order_by(models.Book.title).all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"books": books, "q": q or "",
         "total": db.query(models.Book).count()},
    )


@app.get("/book/{book_id}", response_class=HTMLResponse)
def book_page(
    book_id: int,
    request: Request,
    auto: int = 0,
    db: Session = Depends(get_db),
):
    book = db.get(models.Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    summary = db.query(models.Summary).filter_by(book_id=book_id).one_or_none()
    return templates.TemplateResponse(
        request,
        "book.html",
        {
            "book": book,
            "summary": summary,
            "languages": SUPPORTED_LANGUAGES,
            "auto_generate": bool(auto) and summary is None,
        },
    )


@app.post("/book/new")
def book_new(
    title:  str = Form(...),
    author: str = Form(...),
    year:   Optional[int] = Form(None),
    genre:  Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """User-submitted book. Adds it to the catalog and redirects to the
    detail page, which auto-triggers summary generation."""
    title  = title.strip()
    author = author.strip()
    if not title or not author:
        raise HTTPException(400, "Title and author are required.")

    # Dedupe — case-insensitive match on (title, author).
    existing = (
        db.query(models.Book)
          .filter(func.lower(models.Book.title)  == title.lower())
          .filter(func.lower(models.Book.author) == author.lower())
          .one_or_none()
    )
    if existing:
        return RedirectResponse(
            url=f"/book/{existing.id}", status_code=303,
        )

    book = models.Book(
        title=title,
        author=author,
        year=year,
        genre=(genre or "").strip() or None,
        description=None,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return RedirectResponse(url=f"/book/{book.id}?auto=1", status_code=303)


# ─── API: summaries + translations ──────────────────────────────────────────
@app.post("/api/books/{book_id}/summary")
def api_generate_summary(book_id: int, db: Session = Depends(get_db)):
    book = db.get(models.Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    cached = db.query(models.Summary).filter_by(book_id=book_id).one_or_none()
    if cached:
        return {"cached": True, "content": cached.content,
                "word_count": cached.word_count}

    try:
        content = ai.generate_summary(book.title, book.author, book.year)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Summary generation failed: {e}")

    word_count = len(content.split())
    cached = models.Summary(book_id=book_id, content=content, word_count=word_count)
    db.add(cached)
    db.commit()
    return {"cached": False, "content": content, "word_count": word_count}


@app.get("/api/books/{book_id}/translation")
def api_get_translation(book_id: int, lang: str, db: Session = Depends(get_db)):
    if lang not in LANG_NAME:
        raise HTTPException(400, f"Unsupported language: {lang}")
    if lang == "en":
        s = db.query(models.Summary).filter_by(book_id=book_id).one_or_none()
        if not s:
            raise HTTPException(404, "Summary not yet generated")
        return {"lang": "en", "content": s.content}

    t = db.query(models.Translation).filter_by(
        book_id=book_id, language=lang).one_or_none()
    if not t:
        raise HTTPException(404, "Translation not yet generated")
    return {"lang": lang, "content": t.content}


@app.post("/api/books/{book_id}/translation")
def api_generate_translation(book_id: int, lang: str, db: Session = Depends(get_db)):
    if lang not in LANG_NAME:
        raise HTTPException(400, f"Unsupported language: {lang}")
    book = db.get(models.Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    if lang == "en":
        s = db.query(models.Summary).filter_by(book_id=book_id).one_or_none()
        if not s:
            raise HTTPException(400, "Generate the English summary first")
        return {"cached": True, "lang": "en", "content": s.content}

    cached = db.query(models.Translation).filter_by(
        book_id=book_id, language=lang).one_or_none()
    if cached:
        return {"cached": True, "lang": lang, "content": cached.content}

    summary = db.query(models.Summary).filter_by(book_id=book_id).one_or_none()
    if not summary:
        raise HTTPException(400, "Generate the English summary first")

    try:
        translated = ai.translate(summary.content, LANG_NAME[lang])
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Translation failed: {e}")

    cached = models.Translation(book_id=book_id, language=lang, content=translated)
    db.add(cached)
    db.commit()
    return {"cached": False, "lang": lang, "content": translated}


# ─── API: audio + exports ────────────────────────────────────────────────────
def _get_summary_text(db: Session, book_id: int, lang: str) -> tuple[models.Book, str]:
    book = db.get(models.Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    if lang == "en":
        s = db.query(models.Summary).filter_by(book_id=book_id).one_or_none()
        if not s:
            raise HTTPException(400, "Generate the summary first")
        return book, s.content
    t = db.query(models.Translation).filter_by(
        book_id=book_id, language=lang).one_or_none()
    if not t:
        raise HTTPException(400, f"Generate the {LANG_NAME.get(lang, lang)} "
                                  "translation first")
    return book, t.content


@app.get("/api/books/{book_id}/audio")
def api_audio(book_id: int, lang: str = "en", db: Session = Depends(get_db)):
    if lang not in LANG_NAME:
        raise HTTPException(400, f"Unsupported language: {lang}")
    book, text = _get_summary_text(db, book_id, lang)
    try:
        path = exports.generate_audio(book_id, book.title, lang, text)
    except Exception as e:
        raise HTTPException(500, f"TTS failed: {e}")
    # Cache the path (idempotent — same file is overwritten with same content).
    existing = db.query(models.AudioFile).filter_by(
        book_id=book_id, language=lang).one_or_none()
    if not existing:
        db.add(models.AudioFile(book_id=book_id, language=lang,
                                file_path=str(path)))
        db.commit()
    return FileResponse(path, media_type="audio/mpeg",
                        filename=path.name)


@app.get("/api/books/{book_id}/export.pdf")
def api_pdf(book_id: int, lang: str = "en", db: Session = Depends(get_db)):
    if lang not in LANG_NAME:
        raise HTTPException(400, f"Unsupported language: {lang}")
    book, text = _get_summary_text(db, book_id, lang)
    path = exports.generate_pdf(book_id, book.title, book.author, lang, text)
    return FileResponse(path, media_type="application/pdf",
                        filename=path.name)


@app.get("/api/books/{book_id}/export.epub")
def api_epub(book_id: int, lang: str = "en", db: Session = Depends(get_db)):
    if lang not in LANG_NAME:
        raise HTTPException(400, f"Unsupported language: {lang}")
    book, text = _get_summary_text(db, book_id, lang)
    path = exports.generate_epub(book_id, book.title, book.author, lang, text)
    return FileResponse(path, media_type="application/epub+zip",
                        filename=path.name)


# ─── Health ──────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "anthropic_key_configured": bool(
            os.getenv("ANTHROPIC_API_KEY")
            and not os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-your")
        ),
    }
