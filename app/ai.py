"""AI backend with three free fallbacks.

Provider priority (auto-detected from environment):

    1. Claude    — set ANTHROPIC_API_KEY (premium, ~$0.10 per book)
    2. Gemini    — set GOOGLE_API_KEY    (free tier, 1500 requests/day)
    3. Ollama    — install Ollama + ENABLE_OLLAMA=1 (100% offline, no key)

If none are configured, raises a friendly RuntimeError that the API
surfaces as a 503 and the UI surfaces as a banner.

For an educational project where you don't want any API at all, run
`python -m app.precache` once with any provider configured — it generates
summaries for the 60 seeded books and stores them in the DB. After that
the seeded catalog works for unlimited visits with no key needed.
"""
from __future__ import annotations

import logging
import os
from typing import Callable

log = logging.getLogger(__name__)


# ─── Prompts (shared across providers) ───────────────────────────────────────
_SUMMARY_SYSTEM = """You are a senior literary critic and editor writing for an
audience that wants the substance of a book in roughly ten minutes of reading.

Write a comprehensive summary of the book the user names. Cover:

1. **The core thesis or premise** — what the book is fundamentally about.
2. **Structure** — how the argument or story is organised.
3. **Key ideas, frameworks, or plot beats** — the substance, in order.
4. **Memorable examples or scenes** — concrete moments that illustrate the ideas.
5. **What the reader takes away** — the practical lessons or emotional weight.
6. **Honest critique** — what the book gets right, where it stumbles, who it's for.

Aim for 800–1200 words. Use clear Markdown headings (##) for sections and
short paragraphs. Be specific and concrete — quote phrases, name characters,
cite mechanisms. Avoid filler and avoid breathless praise; the reader wants
to know the book, not be sold on it. Do not refuse to summarise on the grounds
that you "cannot reproduce the text" — summarising a book is fair use and
exactly the task here."""

_TRANSLATION_SYSTEM = """You are a professional literary translator. Translate
the user's text into the target language they specify. Preserve the structure
exactly — keep Markdown headings, paragraph breaks, and emphasis. Translate
idioms and metaphors for sense, not word-for-word. Return only the translated
text; do not add commentary, do not include the original, do not wrap in
quotation marks."""


# ─── Provider detection ──────────────────────────────────────────────────────
def _claude_available() -> bool:
    k = os.getenv("ANTHROPIC_API_KEY", "")
    return bool(k) and not k.startswith("sk-ant-your")


def _gemini_available() -> bool:
    k = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
    return bool(k) and not k.startswith("your-")


def _ollama_available() -> bool:
    """Considered available when the user has explicitly enabled it.
    We don't ping the server here — the actual call will surface a
    connection error if Ollama isn't running."""
    return os.getenv("ENABLE_OLLAMA", "").lower() in ("1", "true", "yes")


def active_provider() -> str:
    """Returns the name of the provider that will be used, or 'none'."""
    if _claude_available():
        return "claude"
    if _gemini_available():
        return "gemini"
    if _ollama_available():
        return "ollama"
    return "none"


# ─── Public API ──────────────────────────────────────────────────────────────
def generate_summary(title: str, author: str, year: int | None = None) -> str:
    """Generate a Markdown summary of the named book."""
    book_ref = f'"{title}" by {author}'
    if year:
        book_ref += f" ({year})"
    user_msg = f"Summarize the book {book_ref}."
    return _dispatch(_SUMMARY_SYSTEM, user_msg, max_tokens=8_000)


def translate(text: str, target_language_name: str) -> str:
    """Translate Markdown text into the named target language."""
    user_msg = (
        f"Target language: {target_language_name}\n\n"
        f"Text to translate:\n\n{text}"
    )
    return _dispatch(_TRANSLATION_SYSTEM, user_msg, max_tokens=16_000)


def _dispatch(system: str, user_msg: str, max_tokens: int) -> str:
    """Pick the highest-priority configured provider and run."""
    provider = active_provider()
    log.info("AI dispatch: provider=%s tokens=%d", provider, max_tokens)
    handlers: dict[str, Callable[[str, str, int], str]] = {
        "claude": _run_claude,
        "gemini": _run_gemini,
        "ollama": _run_ollama,
    }
    if provider == "none":
        raise RuntimeError(
            "No AI provider configured. Choose one of three free options:\n"
            "  • Gemini (free tier): get a free key at "
            "https://aistudio.google.com/app/apikey, set GOOGLE_API_KEY in .env\n"
            "  • Ollama (offline, no key): install from https://ollama.ai, "
            "run `ollama pull llama3.1`, set ENABLE_OLLAMA=1 in .env\n"
            "  • Claude (best quality, paid): set ANTHROPIC_API_KEY in .env\n"
            "Or run `python -m app.precache` once on a machine that has one "
            "of the above and ship the resulting DB."
        )
    return handlers[provider](system, user_msg, max_tokens)


# ─── Claude implementation ───────────────────────────────────────────────────
_CLAUDE_MODEL = "claude-opus-4-7"


def _run_claude(system: str, user_msg: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    with client.messages.stream(
        model=_CLAUDE_MODEL,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        final = stream.get_final_message()
    text = "".join(b.text for b in final.content if b.type == "text").strip()
    if not text:
        raise RuntimeError(f"Claude returned no text. stop_reason={final.stop_reason}")
    return text


# ─── Gemini implementation ───────────────────────────────────────────────────
_GEMINI_MODEL = "gemini-2.0-flash"


def _run_gemini(system: str, user_msg: str, max_tokens: int) -> str:
    try:
        import google.generativeai as genai
    except ImportError as e:                                                  # pragma: no cover
        raise RuntimeError(
            "google-generativeai not installed. Run: pip install google-generativeai"
        ) from e

    key = os.getenv("GOOGLE_API_KEY") or os.environ["GEMINI_API_KEY"]
    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        model_name=_GEMINI_MODEL,
        system_instruction=system,
    )
    resp = model.generate_content(
        user_msg,
        generation_config={
            "max_output_tokens": max_tokens,
            "temperature": 0.7,
        },
    )
    text = (resp.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned no text.")
    return text


# ─── Ollama implementation ───────────────────────────────────────────────────
_OLLAMA_DEFAULT_MODEL = "llama3.1"


def _run_ollama(system: str, user_msg: str, max_tokens: int) -> str:
    import requests
    host  = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", _OLLAMA_DEFAULT_MODEL)
    try:
        r = requests.post(
            f"{host}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user_msg},
                ],
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.7},
            },
            timeout=300,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(
            f"Ollama call failed ({e}). Is Ollama running? "
            f"Try: `ollama serve` in another terminal, then "
            f"`ollama pull {model}` if you haven't already."
        ) from e
    data = r.json()
    text = (data.get("message", {}).get("content", "") or "").strip()
    if not text:
        raise RuntimeError(f"Ollama returned no text. Response: {data}")
    return text
