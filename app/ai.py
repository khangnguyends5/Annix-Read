"""Claude API integration — summary generation and translation.

Uses claude-opus-4-7 with adaptive thinking and prompt caching on the
stable system prompts (so a high-volume catalog gets cache hits).

Streaming is used for both calls — book summaries can run several thousand
tokens and a stream avoids any HTTP-timeout risk on large responses.
"""
from __future__ import annotations

import os
import anthropic

MODEL = "claude-opus-4-7"

# Big enough that summaries never truncate; we stream so the wall-clock is fine.
MAX_TOKENS_SUMMARY     = 8_000
MAX_TOKENS_TRANSLATION = 16_000


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


def _client() -> anthropic.Anthropic:
    """Construct the client. Errors if no API key is set."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key or key.startswith("sk-ant-your"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and "
            "fill in your key from https://console.anthropic.com/"
        )
    return anthropic.Anthropic(api_key=key)


def generate_summary(title: str, author: str, year: int | None = None) -> str:
    """Generate a Markdown summary of the named book. Blocks until complete."""
    client = _client()

    book_ref = f'"{title}" by {author}'
    if year:
        book_ref += f" ({year})"

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS_SUMMARY,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": _SUMMARY_SYSTEM,
            # The system prompt is identical across every summary request, so
            # mark it cacheable. Note: cache only activates once the prefix
            # exceeds the model's minimum (~4096 tokens on Opus 4.7); our
            # prompt is short, so this is a no-op today but costs nothing.
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"Summarize the book {book_ref}.",
        }],
    ) as stream:
        final = stream.get_final_message()

    parts = [b.text for b in final.content if b.type == "text"]
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("Claude returned no text. stop_reason="
                           f"{final.stop_reason}")
    return text


def translate(text: str, target_language_name: str) -> str:
    """Translate Markdown text into the named target language."""
    client = _client()

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS_TRANSLATION,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": _TRANSLATION_SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": (
                f"Target language: {target_language_name}\n\n"
                f"Text to translate:\n\n{text}"
            ),
        }],
    ) as stream:
        final = stream.get_final_message()

    parts = [b.text for b in final.content if b.type == "text"]
    out = "".join(parts).strip()
    if not out:
        raise RuntimeError("Claude returned no text. stop_reason="
                           f"{final.stop_reason}")
    return out
