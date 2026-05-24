"""Export generators — audio (MP3), PDF, EPUB.

All output files live under data/exports and data/audio (gitignored).
Filenames are deterministic so we can serve them as static cached assets.
"""
from __future__ import annotations

import re
from pathlib import Path
from io import BytesIO

from gtts import gTTS
from fpdf import FPDF
from ebooklib import epub

from .db import DATA_DIR

EXPORT_DIR = DATA_DIR / "exports"
AUDIO_DIR  = DATA_DIR / "audio"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ─── Filename helpers ────────────────────────────────────────────────────────
def _slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60] or "untitled"


def _stem(book_id: int, title: str, lang: str) -> str:
    return f"{book_id:04d}-{_slug(title)}-{lang}"


# ─── Audio (gTTS) ────────────────────────────────────────────────────────────
# gTTS uses its own language codes; map ours to theirs where they differ.
_GTTS_LANG = {
    "zh-CN": "zh-CN",  # gTTS accepts both lowercase and uppercase
}

def _gtts_lang(code: str) -> str:
    return _GTTS_LANG.get(code, code.lower())


def generate_audio(book_id: int, title: str, lang: str, text: str) -> Path:
    """Synthesize MP3 from the (possibly translated) summary. Returns file path.

    Strips Markdown so the narration doesn't read out "pound pound heading".
    """
    out = AUDIO_DIR / f"{_stem(book_id, title, lang)}.mp3"
    if out.exists():
        return out

    clean = _strip_markdown(text)
    tts = gTTS(text=clean, lang=_gtts_lang(lang))
    tts.save(str(out))
    return out


def _strip_markdown(text: str) -> str:
    """Cheap Markdown → plain text for TTS narration."""
    # headings
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    # bold / italic
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"__(.+?)__",     r"\1", text)
    text = re.sub(r"_(.+?)_",       r"\1", text)
    # inline code / links
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # list markers
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.M)
    return text.strip()


# ─── PDF (fpdf2) ─────────────────────────────────────────────────────────────
class _SummaryPDF(FPDF):
    def __init__(self, title: str, author: str):
        super().__init__()
        self._book_title  = title
        self._book_author = author

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, _ascii_safe(f"Annix Read - {self._book_title}"), align="L")
        self.ln(12)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def generate_pdf(book_id: int, title: str, author: str, lang: str, text: str) -> Path:
    """Render the summary as a paginated PDF. Returns file path."""
    out = EXPORT_DIR / f"{_stem(book_id, title, lang)}.pdf"
    if out.exists():
        return out

    pdf = _SummaryPDF(title=title, author=author)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Title block
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(20, 20, 20)
    pdf.multi_cell(0, 10, _ascii_safe(title))
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, _ascii_safe(f"by {author}"))
    pdf.ln(12)

    # Body — render Markdown headings as bold, paragraphs as flowing text.
    pdf.set_text_color(0, 0, 0)
    for block in _markdown_blocks(text):
        if block["type"] == "heading":
            pdf.set_font("Helvetica", "B", 14)
            pdf.ln(3)
            pdf.multi_cell(0, 7, _ascii_safe(block["text"]))
            pdf.ln(1)
        elif block["type"] == "paragraph":
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, _ascii_safe(block["text"]))
            pdf.ln(2)
        elif block["type"] == "list":
            pdf.set_font("Helvetica", "", 11)
            for item in block["items"]:
                # fpdf2's multi_cell leaves x at the right edge of the
                # rendered content — reset before adding the indent for the
                # next bullet, otherwise cell(6) pushes past the right margin.
                pdf.set_x(pdf.l_margin)
                pdf.cell(6)
                pdf.multi_cell(0, 6, _ascii_safe(f"* {item}"))
            pdf.ln(2)

    pdf.output(str(out))
    return out


def _ascii_safe(text: str) -> str:
    """fpdf2's built-in Helvetica is Latin-1 only; non-Latin scripts (CJK,
    Arabic, Hindi, ...) would crash. Drop unsupported chars silently rather
    than insert U+FFFD (which fpdf2 also can't render). EPUB and audio paths
    preserve full Unicode."""
    # Normalise common Unicode punctuation that has Latin-1 equivalents.
    replacements = {
        "—": "-",  "–": "-",   # em / en dashes
        "‘": "'",  "’": "'",   # curly single quotes
        "“": '"',  "”": '"',   # curly double quotes
        "…": "...",                  # ellipsis
        " ": " ",                    # non-breaking space
        "•": "*",                    # bullet
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


def _markdown_blocks(text: str) -> list[dict]:
    """Very small Markdown parser — splits text into headings / paragraphs /
    list blocks. Good enough for the PDF; the EPUB uses a richer renderer."""
    blocks: list[dict] = []
    paragraph_buf: list[str] = []
    list_buf: list[str] = []

    def flush_paragraph():
        if paragraph_buf:
            blocks.append({"type": "paragraph",
                           "text": " ".join(paragraph_buf).strip()})
            paragraph_buf.clear()

    def flush_list():
        if list_buf:
            blocks.append({"type": "list", "items": list_buf.copy()})
            list_buf.clear()

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            flush_paragraph()
            flush_list()
            continue
        m_heading = re.match(r"^#{1,6}\s+(.*)", line)
        m_list    = re.match(r"^\s*[-*+]\s+(.*)", line) \
                    or re.match(r"^\s*\d+\.\s+(.*)", line)
        if m_heading:
            flush_paragraph()
            flush_list()
            blocks.append({"type": "heading", "text": m_heading.group(1)})
        elif m_list:
            flush_paragraph()
            list_buf.append(m_list.group(1))
        else:
            flush_list()
            paragraph_buf.append(line)
    flush_paragraph()
    flush_list()
    return blocks


# ─── EPUB (ebooklib) ─────────────────────────────────────────────────────────
def generate_epub(book_id: int, title: str, author: str, lang: str, text: str) -> Path:
    """Build a single-chapter EPUB. Returns file path."""
    out = EXPORT_DIR / f"{_stem(book_id, title, lang)}.epub"
    if out.exists():
        return out

    book = epub.EpubBook()
    book.set_identifier(f"annix-read-{book_id}-{lang}")
    book.set_title(f"Summary of {title}")
    book.set_language(lang.split("-")[0])  # epub wants short codes
    book.add_author(author)

    chapter = epub.EpubHtml(
        title="Summary",
        file_name="summary.xhtml",
        lang=lang.split("-")[0],
    )
    chapter.content = _markdown_to_html(text, title=title, author=author)

    book.add_item(chapter)
    book.toc = (chapter,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    style = """
        body  { font-family: Georgia, 'Times New Roman', serif;
                line-height: 1.55; padding: 1em; }
        h1    { font-size: 1.8em; margin-bottom: 0; }
        .by   { color: #666; font-style: italic; margin: 0 0 1.5em 0; }
        h2    { margin-top: 1.5em; border-bottom: 1px solid #ddd;
                padding-bottom: 0.2em; }
        p     { margin: 0.7em 0; }
        li    { margin: 0.3em 0; }
    """
    css = epub.EpubItem(uid="style", file_name="style.css",
                        media_type="text/css", content=style)
    book.add_item(css)
    chapter.add_item(css)

    book.spine = ["nav", chapter]
    epub.write_epub(str(out), book)
    return out


def _markdown_to_html(text: str, title: str, author: str) -> str:
    """Convert our simple Markdown subset to HTML for the EPUB chapter."""
    parts = [f"<h1>{_html_escape(title)}</h1>",
             f"<p class='by'>by {_html_escape(author)}</p>"]
    for block in _markdown_blocks(text):
        if block["type"] == "heading":
            parts.append(f"<h2>{_html_escape(block['text'])}</h2>")
        elif block["type"] == "paragraph":
            parts.append(f"<p>{_inline_md_to_html(block['text'])}</p>")
        elif block["type"] == "list":
            items = "".join(f"<li>{_inline_md_to_html(i)}</li>"
                            for i in block["items"])
            parts.append(f"<ul>{items}</ul>")
    return "<html><body>" + "\n".join(parts) + "</body></html>"


def _inline_md_to_html(text: str) -> str:
    text = _html_escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*",     r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_",       r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`",     r"<code>\1</code>", text)
    return text


def _html_escape(text: str) -> str:
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
