"""ORM models — Book + cached Summary/Translation/Audio."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from .db import Base


class Book(Base):
    __tablename__ = "books"

    id          = Column(Integer, primary_key=True)
    title       = Column(String(255), nullable=False, index=True)
    author      = Column(String(255), nullable=False, index=True)
    year        = Column(Integer)
    genre       = Column(String(64))
    description = Column(Text)        # short blurb shown on cards

    summaries    = relationship("Summary",    back_populates="book", cascade="all, delete-orphan")
    translations = relationship("Translation", back_populates="book", cascade="all, delete-orphan")
    audio_files  = relationship("AudioFile",   back_populates="book", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Book {self.id} {self.title!r} by {self.author!r}>"


class Summary(Base):
    """Cached English summary for a book."""
    __tablename__ = "summaries"

    id         = Column(Integer, primary_key=True)
    book_id    = Column(Integer, ForeignKey("books.id"), nullable=False, unique=True)
    content    = Column(Text, nullable=False)
    word_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    book = relationship("Book", back_populates="summaries")


class Translation(Base):
    """Cached translation of a summary into a target language."""
    __tablename__ = "translations"

    id          = Column(Integer, primary_key=True)
    book_id     = Column(Integer, ForeignKey("books.id"), nullable=False)
    language    = Column(String(8), nullable=False)   # ISO code: "es", "fr", "zh-cn", ...
    content     = Column(Text, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    book = relationship("Book", back_populates="translations")

    __table_args__ = (
        UniqueConstraint("book_id", "language", name="uq_translation_book_lang"),
        Index("ix_translation_book_lang", "book_id", "language"),
    )


class AudioFile(Base):
    """Cached audio file for a summary in a given language."""
    __tablename__ = "audio_files"

    id         = Column(Integer, primary_key=True)
    book_id    = Column(Integer, ForeignKey("books.id"), nullable=False)
    language   = Column(String(8), nullable=False)
    file_path  = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    book = relationship("Book", back_populates="audio_files")

    __table_args__ = (
        UniqueConstraint("book_id", "language", name="uq_audio_book_lang"),
    )
