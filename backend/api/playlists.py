"""플레이리스트 CRUD + 곡 추가 API."""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import Playlist, Song, session_scope

router = APIRouter()


# ── Pydantic ────────────────────────────────────────────────
class PlaylistCreate(BaseModel):
    title: str
    theme: str | None = None


class SongCreate(BaseModel):
    source_url: str
    artist: str | None = None
    title: str | None = None
    order_index: int = Field(..., ge=1)

    intro_start: float | None = Field(None, ge=0)
    intro_end: float | None = Field(None, ge=0)
    highlight_start: float | None = Field(None, ge=0)
    highlight_end: float | None = Field(None, ge=0)

    visual_source: str | None = Field(None, pattern="^(thumbnail|frame)$")
    visual_frame_seconds: float | None = None


# ── 직렬화 ──────────────────────────────────────────────────
def _song_dict(s: Song) -> dict:
    return {
        "id": s.id,
        "playlist_id": s.playlist_id,
        "order_index": s.order_index,
        "source_url": s.source_url,
        "artist": s.artist,
        "title": s.title,
        "intro_start": s.intro_start,
        "intro_end": s.intro_end,
        "highlight_start": s.highlight_start,
        "highlight_end": s.highlight_end,
        "visual_source": s.visual_source,
        "visual_frame_seconds": s.visual_frame_seconds,
        "is_shorts_pick": s.is_shorts_pick,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _playlist_dict(p: Playlist, include_songs: bool = True) -> dict:
    out = {
        "id": p.id,
        "title": p.title,
        "theme": p.theme,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "song_count": len(p.songs),
    }
    if include_songs:
        out["songs"] = [_song_dict(s) for s in p.songs]
    return out


# ── Routes ──────────────────────────────────────────────────
@router.post("/")
def create_playlist(payload: PlaylistCreate):
    pid = str(uuid.uuid4())
    with session_scope() as s:
        p = Playlist(id=pid, title=payload.title, theme=payload.theme)
        s.add(p)
        s.flush()
        return _playlist_dict(p, include_songs=False)


@router.get("/")
def list_playlists():
    with session_scope() as s:
        rows = s.query(Playlist).order_by(Playlist.created_at.desc()).all()
        return [_playlist_dict(p, include_songs=False) for p in rows]


@router.get("/{playlist_id}")
def get_playlist(playlist_id: str):
    with session_scope() as s:
        p = s.query(Playlist).filter(Playlist.id == playlist_id).one_or_none()
        if not p:
            raise HTTPException(404, "플레이리스트를 찾을 수 없습니다.")
        return _playlist_dict(p)


@router.post("/{playlist_id}/songs")
def add_song(playlist_id: str, payload: SongCreate):
    with session_scope() as s:
        p = s.query(Playlist).filter(Playlist.id == playlist_id).one_or_none()
        if not p:
            raise HTTPException(404, "플레이리스트를 찾을 수 없습니다.")
        if len(p.songs) >= 15:
            raise HTTPException(400, "한 플레이리스트는 최대 15곡까지입니다.")
        # 같은 order_index 충돌 방지
        if any(existing.order_index == payload.order_index for existing in p.songs):
            raise HTTPException(409, f"order_index={payload.order_index}는 이미 사용 중입니다.")
        if payload.visual_source == "frame" and payload.visual_frame_seconds is None:
            raise HTTPException(400, "frame 비주얼은 visual_frame_seconds가 필요합니다.")

        song = Song(
            id=str(uuid.uuid4()),
            playlist_id=playlist_id,
            order_index=payload.order_index,
            source_url=payload.source_url,
            artist=payload.artist,
            title=payload.title,
            intro_start=payload.intro_start,
            intro_end=payload.intro_end,
            highlight_start=payload.highlight_start,
            highlight_end=payload.highlight_end,
            visual_source=payload.visual_source,
            visual_frame_seconds=payload.visual_frame_seconds,
            is_shorts_pick=False,
        )
        s.add(song)
        s.flush()
        return _song_dict(song)
