"""쇼츠 파이프라인의 개별 스텝 함수들 (다운로드/STT/번역).

렌더링은 pipeline/render.py에서 ffmpeg로 직접 처리한다.
"""

import re
import subprocess
from pathlib import Path

import yt_dlp


# ── 1. 다운로드 ─────────────────────────────────────────────
def download_audio_segment(
    source_url: str, start: float, end: float, out_dir: Path, short_id: str
) -> Path:
    """yt-dlp로 오디오 받고 ffmpeg로 구간 잘라 mp3 저장."""
    full_audio = out_dir / f"{short_id}_full.m4a"
    segment = out_dir / f"{short_id}_segment.mp3"

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / f"{short_id}_full.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(source_url, download=True)
    downloaded = list(out_dir.glob(f"{short_id}_full.*"))
    if not downloaded:
        raise RuntimeError("yt-dlp 다운로드 실패")
    full_audio = downloaded[0]

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(full_audio),
            "-ss", str(start), "-to", str(end),
            "-vn", "-acodec", "libmp3lame", "-b:a", "128k",
            str(segment),
        ],
        check=True, capture_output=True,
    )
    full_audio.unlink(missing_ok=True)
    return segment


def download_thumbnail(source_url: str, out_dir: Path, short_id: str) -> Path:
    """yt-dlp로 최고 해상도 썸네일 추출."""
    out_path = out_dir / f"{short_id}_thumb.jpg"
    opts = {
        "skip_download": True,
        "writethumbnail": True,
        "outtmpl": str(out_dir / f"{short_id}_thumb"),
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(source_url, download=True)
    candidates = list(out_dir.glob(f"{short_id}_thumb.*"))
    candidates = [c for c in candidates if c.suffix in (".jpg", ".jpeg", ".png", ".webp")]
    if not candidates:
        raise RuntimeError("썸네일 다운로드 실패")
    if candidates[0].suffix != ".jpg":
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(candidates[0]), str(out_path)],
            check=True, capture_output=True,
        )
        candidates[0].unlink(missing_ok=True)
    else:
        candidates[0].rename(out_path)
    return out_path


def extract_frame(source_url: str, frame_seconds: float, out_dir: Path, short_id: str) -> Path:
    """롱폼 영상의 특정 시점 프레임을 JPG로 추출."""
    out_path = out_dir / f"{short_id}_frame.jpg"
    opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": str(out_dir / f"{short_id}_video.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(source_url, download=True)
    video = next(out_dir.glob(f"{short_id}_video.*"))
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", str(frame_seconds), "-i", str(video),
            "-frames:v", "1", "-q:v", "2", str(out_path),
        ],
        check=True, capture_output=True,
    )
    video.unlink(missing_ok=True)
    return out_path


# ── 2. STT (Whisper) ───────────────────────────────────────
def transcribe(audio_path: Path, openai_key: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=openai_key)
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    return {
        "language": result.language,
        "duration": result.duration,
        "segments": [
            {"start": s.start, "end": s.end, "text": s.text.strip()}
            for s in result.segments
        ],
    }


# ── 3. 번역 (Gemini) ───────────────────────────────────────
def translate_to_korean(segments: list[dict], gemini_key: str) -> list[dict]:
    import google.generativeai as genai

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    numbered = "\n".join(f"[{i}] {s['text']}" for i, s in enumerate(segments))
    prompt = (
        "아래 영어 가사를 자연스럽고 감성적인 한국어로 번역해줘. "
        "유튜브 쇼츠 자막용이라 짧고 임팩트 있게. "
        "원래 의미를 유지하되 한국어로 들었을 때 어색하지 않게.\n"
        "각 번호에 맞춰 한 줄씩만 출력:\n"
        "[0] 한국어 번역\n[1] 한국어 번역\n...\n\n"
        "원문:\n"
        f"{numbered}"
    )
    response = model.generate_content(prompt)
    text = (response.text or "").strip()

    translated: dict[int, str] = {}
    for line in text.splitlines():
        m = re.match(r"\[(\d+)\]\s*(.+)", line.strip())
        if m:
            translated[int(m.group(1))] = m.group(2).strip()

    return [{**s, "text_ko": translated.get(i, s["text"])} for i, s in enumerate(segments)]
