"""곡 단위 CRUD + shorts_pick 마킹 API.

shorts_pick: 한 플레이리스트(15곡) 안에서 단 한 곡만 True가 되어야 하므로,
PATCH로 is_shorts_pick=True를 켤 때 같은 플레이리스트의 다른 곡들은 자동 해제.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import Short, Song, session_scope

router = APIRouter()


class SongPatch(BaseModel):
    artist: str | None = None
    title: str | None = None
    intro_start: float | None = Field(None, ge=0)
    intro_end: float | None = Field(None, ge=0)
    highlight_start: float | None = Field(None, ge=0)
    highlight_end: float | None = Field(None, ge=0)
    visual_source: str | None = Field(None, pattern="^(thumbnail|frame)$")
    visual_frame_seconds: float | None = None
    is_shorts_pick: bool | None = None


def _short_dict(s: Short) -> dict:
    return {
        "id": s.id,
        "short_type": s.short_type,
        "status": s.status,
        "progress_percent": s.progress_percent,
        "output_path": s.output_path,
        "duration_seconds": s.duration_seconds,
    }


def _song_dict_full(song: Song) -> dict:
    return {
        "id": song.id,
        "playlist_id": song.playlist_id,
        "order_index": song.order_index,
        "source_url": song.source_url,
        "artist": song.artist,
        "title": song.title,
        "intro_start": song.intro_start,
        "intro_end": song.intro_end,
        "highlight_start": song.highlight_start,
        "highlight_end": song.highlight_end,
        "visual_source": song.visual_source,
        "visual_frame_seconds": song.visual_frame_seconds,
        "is_shorts_pick": song.is_shorts_pick,
        "created_at": song.created_at.isoformat() if song.created_at else None,
        "shorts": [_short_dict(sh) for sh in song.shorts],
    }


@router.get("/{song_id}")
def get_song(song_id: str):
    with session_scope() as s:
        song = s.query(Song).filter(Song.id == song_id).one_or_none()
        if not song:
            raise HTTPException(404, "곡을 찾을 수 없습니다.")
        return _song_dict_full(song)


@router.patch("/{song_id}")
def patch_song(song_id: str, payload: SongPatch):
    updates = payload.model_dump(exclude_unset=True)
    with session_scope() as s:
        song = s.query(Song).filter(Song.id == song_id).one_or_none()
        if not song:
            raise HTTPException(404, "곡을 찾을 수 없습니다.")

        # is_shorts_pick=True로 켜면 같은 플레이리스트 내 다른 곡들은 해제
        if updates.get("is_shorts_pick") is True:
            s.query(Song).filter(
                Song.playlist_id == song.playlist_id,
                Song.id != song_id,
            ).update({"is_shorts_pick": False})

        if updates.get("visual_source") == "frame" and (
            updates.get("visual_frame_seconds", song.visual_frame_seconds) is None
        ):
            raise HTTPException(400, "frame 비주얼은 visual_frame_seconds가 필요합니다.")

        for key, value in updates.items():
            setattr(song, key, value)
        s.flush()
        return _song_dict_full(song)


@router.delete("/{song_id}")
def delete_song(song_id: str):
    with session_scope() as s:
        song = s.query(Song).filter(Song.id == song_id).one_or_none()
        if not song:
            raise HTTPException(404, "곡을 찾을 수 없습니다.")
        s.delete(song)
        return {"deleted": song_id}
