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
    """Create tables and seed the catalog if empty."""
    from . import models  # noqa: F401 — register models with Base
    Base.metadata.create_all(bind=engine)

    from .catalog import SEED_BOOKS
    db = SessionLocal()
    try:
        if db.query(models.Book).count() == 0:
            for entry in SEED_BOOKS:
                db.add(models.Book(**entry))
            db.commit()
    finally:
        db.close()
