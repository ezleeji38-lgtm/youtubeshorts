"""SQLite + SQLAlchemy (단일 사용자 로컬 모드).

데이터 모델 계층:
    Playlist (15곡 묶음, 한 영상 회차)
      └─ Song × 15 (곡당 metadata + intro/highlight 구간)
            └─ Short × 2 (intro 클립 + highlight 클립)
"""

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from .config import settings

DB_PATH = settings.storage_path / "coolvibeply.db"

engine = create_engine(f"sqlite:///{DB_PATH}", future=True, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class Playlist(Base):
    """한 영상 회차 = 한 플레이리스트 (15곡 묶음)."""

    __tablename__ = "playlists"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    theme = Column(String)  # 자유 설명 (무드, 컨셉)
    created_at = Column(DateTime, default=datetime.utcnow)

    songs = relationship(
        "Song",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="Song.order_index",
    )


class Song(Base):
    """플레이리스트에 들어가는 곡 한 개 + intro/highlight 구간 정의."""

    __tablename__ = "songs"

    id = Column(String, primary_key=True)
    playlist_id = Column(String, ForeignKey("playlists.id"), nullable=False)
    order_index = Column(Integer, nullable=False)  # 1~15

    source_url = Column(String, nullable=False)
    artist = Column(String)
    title = Column(String)

    # 두 구간 — intro 와 highlight 클립용
    intro_start = Column(Float)
    intro_end = Column(Float)
    highlight_start = Column(Float)
    highlight_end = Column(Float)

    # 비주얼: 썸네일 또는 영상의 특정 프레임
    visual_source = Column(String)  # 'thumbnail' | 'frame'
    visual_frame_seconds = Column(Float)

    # 15곡 중 1곡만 True — 그 곡의 highlight가 YouTube Shorts에 업로드됨
    is_shorts_pick = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    playlist = relationship("Playlist", back_populates="songs")
    shorts = relationship("Short", back_populates="song", cascade="all, delete-orphan")


class Short(Base):
    """쇼츠 한 건 = 한 곡의 intro 또는 highlight 클립.

    song_id가 None이면 V0.1 ad-hoc 모드로 단일 클립을 만든 것.
    """

    __tablename__ = "shorts"

    id = Column(String, primary_key=True)
    song_id = Column(String, ForeignKey("songs.id"), nullable=True)

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

    song = relationship("Song", back_populates="shorts")


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
