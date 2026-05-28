"""Pre-generate and cache summaries for every book that doesn't have one.

The point: once you run this on any machine with any AI provider configured,
the resulting DB has all 60 seeded summaries baked in. You can then ship the
DB and the catalog works for unlimited users with **no API key required**.

Usage:

    # With Gemini (free tier — generous):
    GOOGLE_API_KEY=... python -m app.precache

    # With Ollama (offline, no key):
    ENABLE_OLLAMA=1 python -m app.precache

    # With Claude (best quality):
    ANTHROPIC_API_KEY=sk-ant-... python -m app.precache

    # Limit to N books per run (cost control):
    python -m app.precache --limit 10

    # Translate every cached summary into one language too:
    python -m app.precache --translate es

    # Generate audio + PDF + EPUB for every cached summary (slower, more disk):
    python -m app.precache --audio --pdf --epub --lang en
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Ensure imports work when this is run as `python -m app.precache` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app import models, ai, exports                                            # noqa: E402
from app.db import SessionLocal, init_db                                       # noqa: E402
from app.catalog import LANG_NAME                                              # noqa: E402

log = logging.getLogger(__name__)


def precache(
    limit: int | None = None,
    translate_to: list[str] | None = None,
    do_audio: bool = False,
    do_pdf: bool = False,
    do_epub: bool = False,
    audio_lang: str = "en",
    sleep_s: float = 0.5,
) -> dict:
    """Walk every book in the catalog, generating + caching anything missing."""
    init_db()
    db = SessionLocal()
    stats = {
        "books_total":         0,
        "summaries_existing":  0,
        "summaries_generated": 0,
        "summaries_failed":    0,
        "translations":        0,
        "audio_files":         0,
        "pdf_files":           0,
        "epub_files":          0,
        "provider":            ai.active_provider(),
    }

    if stats["provider"] == "none":
        print("ERROR: no AI provider configured. See `python -m app.precache --help`.")
        return stats

    print(f"Pre-cache starting — provider: {stats['provider']}")
    print(f"  translations: {translate_to or 'none'}")
    print(f"  exports:      audio={do_audio} pdf={do_pdf} epub={do_epub} lang={audio_lang}")

    try:
        books = db.query(models.Book).order_by(models.Book.id).all()
        if limit:
            books = books[:limit]
        stats["books_total"] = len(books)

        for i, book in enumerate(books, 1):
            tag = f"[{i:3d}/{len(books)}] {book.title[:40]:40s} by {book.author[:25]:25s}"

            # ── Summary ─────────────────────────────────────────────────────
            existing = db.query(models.Summary).filter_by(book_id=book.id).one_or_none()
            if existing:
                stats["summaries_existing"] += 1
                summary_text = existing.content
                print(f"  {tag}  cached")
            else:
                try:
                    t0 = time.time()
                    summary_text = ai.generate_summary(book.title, book.author, book.year)
                    dt = time.time() - t0
                    word_count = len(summary_text.split())
                    db.add(models.Summary(
                        book_id=book.id,
                        content=summary_text,
                        word_count=word_count,
                    ))
                    db.commit()
                    stats["summaries_generated"] += 1
                    print(f"  {tag}  generated {word_count}w in {dt:4.1f}s")
                except Exception as e:                                         # noqa: BLE001
                    stats["summaries_failed"] += 1
                    print(f"  {tag}  FAILED: {type(e).__name__}: {e}")
                    continue

            # ── Translations ────────────────────────────────────────────────
            for lang in translate_to or []:
                if lang == "en":
                    continue
                if lang not in LANG_NAME:
                    print(f"      ⚠ skip unknown language {lang}")
                    continue
                if db.query(models.Translation).filter_by(
                        book_id=book.id, language=lang).one_or_none():
                    continue
                try:
                    t = ai.translate(summary_text, LANG_NAME[lang])
                    db.add(models.Translation(book_id=book.id, language=lang, content=t))
                    db.commit()
                    stats["translations"] += 1
                    print(f"      + translation [{lang}] {len(t.split())}w")
                except Exception as e:                                         # noqa: BLE001
                    print(f"      ⚠ translation [{lang}] failed: {e}")

            # ── Audio / PDF / EPUB ──────────────────────────────────────────
            if any([do_audio, do_pdf, do_epub]):
                # Source text in the chosen language.
                if audio_lang == "en":
                    text_for_export = summary_text
                else:
                    t = db.query(models.Translation).filter_by(
                        book_id=book.id, language=audio_lang).one_or_none()
                    if not t:
                        print(f"      ⚠ skip exports — no {audio_lang} translation")
                        continue
                    text_for_export = t.content

                if do_audio:
                    try:
                        exports.generate_audio(book.id, book.title, audio_lang, text_for_export)
                        stats["audio_files"] += 1
                        print("      + audio")
                    except Exception as e:                                     # noqa: BLE001
                        print(f"      ⚠ audio failed: {e}")

                if do_pdf:
                    try:
                        exports.generate_pdf(book.id, book.title, book.author,
                                             audio_lang, text_for_export)
                        stats["pdf_files"] += 1
                        print("      + pdf")
                    except Exception as e:                                     # noqa: BLE001
                        print(f"      ⚠ pdf failed: {e}")

                if do_epub:
                    try:
                        exports.generate_epub(book.id, book.title, book.author,
                                              audio_lang, text_for_export)
                        stats["epub_files"] += 1
                        print("      + epub")
                    except Exception as e:                                     # noqa: BLE001
                        print(f"      ⚠ epub failed: {e}")

            if sleep_s > 0:
                time.sleep(sleep_s)
    finally:
        db.close()

    print()
    print("Pre-cache complete:")
    for k, v in stats.items():
        print(f"  {k:22s} {v}")
    return stats


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limit", type=int, default=None,
                   help="Stop after this many books (default: all).")
    p.add_argument("--translate", action="append", default=[],
                   metavar="LANG",
                   help="Also cache translations into this language. Repeatable.")
    p.add_argument("--audio", action="store_true",
                   help="Generate gTTS audio for every book in --lang.")
    p.add_argument("--pdf", action="store_true",
                   help="Generate PDF for every book in --lang.")
    p.add_argument("--epub", action="store_true",
                   help="Generate EPUB for every book in --lang.")
    p.add_argument("--lang", default="en",
                   help="Language for --audio / --pdf / --epub (default en).")
    p.add_argument("--sleep", type=float, default=0.5,
                   help="Seconds between API calls (rate-limit politeness).")
    p.add_argument("-v", "--verbose", action="store_true")

    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    stats = precache(
        limit=args.limit,
        translate_to=args.translate,
        do_audio=args.audio,
        do_pdf=args.pdf,
        do_epub=args.epub,
        audio_lang=args.lang,
        sleep_s=args.sleep,
    )
    return 0 if stats["summaries_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
