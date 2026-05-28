"""Database setup — SQLAlchemy + SQLite."""
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "annix_read.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session, closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create tables and seed the catalog. Idempotent — books that already
    exist (matched on lowercase title+author) are skipped, so adding new
    entries to SEED_BOOKS just adds them on next startup without wiping
    existing summaries / translations / audio.
    """
    from sqlalchemy import func
    from . import models  # noqa: F401 — register models with Base
    Base.metadata.create_all(bind=engine)

    from .catalog import SEED_BOOKS
    db = SessionLocal()
    try:
        # Build a set of lowercase (title, author) pairs already in the DB.
        existing = {
            (t.lower(), a.lower())
            for t, a in db.query(models.Book.title, models.Book.author).all()
        }
        added = 0
        for entry in SEED_BOOKS:
            key = (entry["title"].lower(), entry["author"].lower())
            if key in existing:
                continue
            db.add(models.Book(**entry))
            added += 1
        if added:
            db.commit()
            # Note: avoid touching logging here; init_db runs at FastAPI startup.
    finally:
        db.close()
