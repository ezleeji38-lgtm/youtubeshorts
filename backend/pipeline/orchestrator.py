"""쇼츠 한 건의 전체 파이프라인 실행 — DB 상태 갱신 포함."""

from datetime import datetime

from ..config import settings
from ..db import Short, session_scope
from .steps import (
    build_creatomate_source,
    download_audio_segment,
    download_thumbnail,
    download_to_local,
    extract_frame,
    render_with_creatomate,
    transcribe,
    translate_to_korean,
)


def _update(short_id: str, **fields) -> None:
    with session_scope() as s:
        s.query(Short).filter(Short.id == short_id).update(fields)


def run_pipeline(short_id: str) -> None:
    """5단계 파이프라인 실행. 각 단계마다 DB 상태 갱신. 실패 시 status='failed'."""
    with session_scope() as s:
        short = s.query(Short).filter(Short.id == short_id).one()
        params = {
            "source_url": short.source_url,
            "start_seconds": short.start_seconds,
            "end_seconds": short.end_seconds,
            "visual_source": short.visual_source,
            "visual_frame_seconds": short.visual_frame_seconds,
        }

    missing = [
        k for k, v in (
            ("OPENAI_API_KEY", settings.openai_api_key),
            ("GEMINI_API_KEY", settings.gemini_api_key),
            ("CREATOMATE_API_KEY", settings.creatomate_api_key),
        ) if not v
    ]
    if missing:
        _update(short_id, status="failed", error_message=f".env에 누락된 키: {missing}")
        return

    work_dir = settings.storage_path / short_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 다운로드
        _update(short_id, status="downloading", progress_percent=10)
        audio_path = download_audio_segment(
            params["source_url"],
            params["start_seconds"],
            params["end_seconds"],
            work_dir,
            short_id,
        )
        if params["visual_source"] == "thumbnail":
            image_path = download_thumbnail(params["source_url"], work_dir, short_id)
        else:
            image_path = extract_frame(
                params["source_url"],
                params["visual_frame_seconds"],
                work_dir,
                short_id,
            )

        # 2. STT
        _update(short_id, status="transcribing", progress_percent=35)
        transcript = transcribe(audio_path, settings.openai_api_key)

        # 3. 번역
        _update(short_id, status="translating", progress_percent=55)
        translated = translate_to_korean(transcript["segments"], settings.gemini_api_key)

        # 4. 렌더
        _update(
            short_id,
            status="rendering",
            progress_percent=70,
            english_lyrics={"segments": transcript["segments"]},
            korean_lyrics={"segments": translated},
        )
        # V0.2 예정: Creatomate가 외부 URL을 요구하므로 현재는 placeholder.
        # 로컬 FFmpeg 합성으로 대체 또는 Cloudflare R2 업로드 후 public URL 획득.
        public_image_url = f"file://{image_path}"
        public_audio_url = f"file://{audio_path}"

        duration = params["end_seconds"] - params["start_seconds"]
        source = build_creatomate_source(
            public_image_url,
            public_audio_url,
            translated,
            duration,
            base_offset=0.0,
        )
        render_url = render_with_creatomate(source, settings.creatomate_api_key)

        # 5. 결과물 저장
        output_path = work_dir / f"{short_id}.mp4"
        download_to_local(render_url, output_path)

        _update(
            short_id,
            status="completed",
            progress_percent=100,
            output_path=str(output_path.relative_to(settings.storage_path)),
            duration_seconds=duration,
            completed_at=datetime.utcnow(),
        )
    except Exception as e:  # noqa: BLE001
        _update(short_id, status="failed", error_message=str(e))
        raise
