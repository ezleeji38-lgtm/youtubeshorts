"""쇼츠 작업 생성·조회 API (단일 사용자 로컬)."""

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..db import Short, session_scope
from ..workers.tasks import run_short_pipeline

router = APIRouter()


class ShortCreate(BaseModel):
    source_url: str
    song_title: str | None = None
    short_type: str = Field(..., pattern="^(intro|highlight)$")
    start_seconds: float = Field(..., ge=0)
    end_seconds: float = Field(..., gt=0)
    visual_source: str = Field(..., pattern="^(thumbnail|frame)$")
    visual_frame_seconds: float | None = None


def _to_dict(s: Short) -> dict:
    return {
        "id": s.id,
        "source_url": s.source_url,
        "song_title": s.song_title,
        "short_type": s.short_type,
        "start_seconds": s.start_seconds,
        "end_seconds": s.end_seconds,
        "visual_source": s.visual_source,
        "visual_frame_seconds": s.visual_frame_seconds,
        "status": s.status,
        "progress_percent": s.progress_percent,
        "error_message": s.error_message,
        "output_path": s.output_path,
        "duration_seconds": s.duration_seconds,
        "english_lyrics": s.english_lyrics,
        "korean_lyrics": s.korean_lyrics,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
    }


@router.post("/")
def create_short(payload: ShortCreate, background: BackgroundTasks):
    if payload.end_seconds <= payload.start_seconds:
        raise HTTPException(400, "end_seconds는 start_seconds보다 커야 합니다.")
    if payload.end_seconds - payload.start_seconds > 60:
        raise HTTPException(400, "쇼츠 구간은 60초 이내여야 합니다.")
    if payload.visual_source == "frame" and payload.visual_frame_seconds is None:
        raise HTTPException(400, "frame 비주얼은 visual_frame_seconds가 필요합니다.")

    short_id = str(uuid.uuid4())
    with session_scope() as s:
        short = Short(
            id=short_id,
            source_url=payload.source_url,
            song_title=payload.song_title,
            short_type=payload.short_type,
            start_seconds=payload.start_seconds,
            end_seconds=payload.end_seconds,
            visual_source=payload.visual_source,
            visual_frame_seconds=payload.visual_frame_seconds,
            status="queued",
        )
        s.add(short)
        s.flush()
        result = _to_dict(short)

    background.add_task(run_short_pipeline, short_id)
    return result


@router.get("/")
def list_shorts():
    with session_scope() as s:
        rows = s.query(Short).order_by(Short.created_at.desc()).limit(50).all()
        return [_to_dict(r) for r in rows]


@router.get("/{short_id}")
def get_short(short_id: str):
    with session_scope() as s:
        short = s.query(Short).filter(Short.id == short_id).one_or_none()
        if not short:
            raise HTTPException(404, "쇼츠를 찾을 수 없습니다.")
        return _to_dict(short)
