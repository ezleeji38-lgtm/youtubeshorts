"""SQLite + SQLAlchemy (단일 사용자 로컬 모드)."""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

DB_PATH = settings.storage_path / "coolvibeply.db"

engine = create_engine(f"sqlite:///{DB_PATH}", future=True, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class Short(Base):
    """쇼츠 한 건 = 한 행. 곡 한 곡의 intro 또는 highlight 클립."""

    __tablename__ = "shorts"

    id = Column(String, primary_key=True)
    source_url = Column(String, nullable=False)
    song_title = Column(String)
    short_type = Column(String, nullable=False)  # 'intro' | 'highlight'
    start_seconds = Column(Float, nullable=False)
    end_seconds = Column(Float, nullable=False)
    visual_source = Column(String, nullable=False)  # 'thumbnail' | 'frame'
    visual_frame_seconds = Column(Float)

    status = Column(String, nullable=False, default="queued")
    progress_percent = Column(Integer, default=0)
    error_message = Column(String)

    output_path = Column(String)
    duration_seconds = Column(Float)
    english_lyrics = Column(JSON)
    korean_lyrics = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


def init_db() -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
