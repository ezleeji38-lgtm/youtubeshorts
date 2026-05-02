"""로컬 FFmpeg 합성 — 9:16 영상 + 듀얼 자막 + 블러 배경.

Creatomate 같은 외부 렌더 API에 의존하지 않고, 로컬 ffmpeg 한 번 호출로
배경 블러 + 전경 이미지 + 영/한 듀얼 자막 + 오디오를 합성한다.
"""

import shutil
import subprocess
from pathlib import Path

# 9:16 1080×1920 (YouTube Shorts / Instagram Reels / TikTok)
WIDTH = 1080
HEIGHT = 1920

# 자막 위치 (Creatomate 시절 y_alignment 매칭)
ENG_Y_PCT = 0.70
KO_Y_PCT = 0.82

# 전경 이미지 영역 (썸네일/프레임 표시 영역)
FG_HEIGHT_PCT = 0.55
FG_Y_CENTER_PCT = 0.40


def _seconds_to_ass(t: float) -> str:
    """ASS 타임스탬프 (H:MM:SS.cs)."""
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    """ASS Dialogue 줄에서 위험한 문자 처리."""
    return text.replace("\n", " ").replace("\r", " ").replace("{", "(").replace("}", ")").strip()


def compose_ass(
    segments: list[dict],
    output_path: Path,
    font_en: str,
    font_ko: str,
) -> Path:
    """영/한 듀얼 자막 ASS 생성.

    segments: [{start, end, text, text_ko}, ...] (orchestrator가 넘겨줌)
    """
    eng_y = int(HEIGHT * ENG_Y_PCT)
    ko_y = int(HEIGHT * KO_Y_PCT)

    # ASS 색상은 &HAABBGGRR (alpha 00=불투명, 80=반투명)
    # 영문: 반투명 흰색 (Creatomate rgba(255,255,255,0.85) ≈ alpha 0x40)
    # 한글: 불투명 흰색 + 검정 테두리
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Eng,{font_en},56,&H40FFFFFF,&H40000000,&H00000000,0,0,0,0,100,100,0,0,1,0,2,8,80,80,{eng_y},1
Style: Ko,{font_ko},88,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,8,80,80,{ko_y},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for seg in segments:
        start = _seconds_to_ass(seg["start"])
        end = _seconds_to_ass(max(seg["start"] + 0.3, seg["end"]))
        text_en = _ass_escape(seg.get("text", ""))
        text_ko = _ass_escape(seg.get("text_ko", ""))
        if text_en:
            lines.append(f"Dialogue: 0,{start},{end},Eng,,0,0,0,,{text_en}\n")
        if text_ko:
            lines.append(f"Dialogue: 1,{start},{end},Ko,,0,0,0,,{text_ko}\n")

    output_path.write_text("".join(lines), encoding="utf-8")
    return output_path


def _filter_path(p: Path) -> str:
    """ffmpeg filter graph 인자 안에서 경로 이스케이프 (Windows의 C: 같은 콜론 처리)."""
    s = str(p).replace("\\", "/")
    return s.replace(":", r"\:")


def _check_ffmpeg_capabilities() -> None:
    """ffmpeg와 libass(ass 필터) 사용 가능 여부를 사전 검증."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg가 설치되어 있지 않습니다.\n"
            "  macOS: brew install ffmpeg-full\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg"
        )
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            check=True, capture_output=True, text=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg 필터 목록 조회 실패: {e}") from e
    if " ass " not in out and " subtitles " not in out:
        raise RuntimeError(
            "현재 설치된 ffmpeg에 libass 자막 필터가 없습니다.\n"
            "Homebrew 기본 'ffmpeg' 패키지는 자막 라이브러리가 빠져 있어 "
            "'ffmpeg-full'로 교체해야 합니다.\n"
            "  brew uninstall ffmpeg && brew install ffmpeg-full\n"
            "Ubuntu/Debian의 'ffmpeg'에는 보통 libass가 포함되어 있습니다."
        )


def render_local(
    image_path: Path,
    audio_path: Path,
    segments: list[dict],
    duration: float,
    output_path: Path,
    font_en: str,
    font_ko: str,
) -> Path:
    """이미지 + 오디오 + 듀얼 자막 → 9:16 mp4 한 번에 합성."""
    _check_ffmpeg_capabilities()

    work = output_path.parent
    ass_path = work / f"{output_path.stem}.ass"
    compose_ass(segments, ass_path, font_en, font_ko)

    fg_h = int(HEIGHT * FG_HEIGHT_PCT)
    fg_y_center = int(HEIGHT * FG_Y_CENTER_PCT)

    # 배경: 이미지 cover + 박스 블러
    # 전경: 이미지 contain (높이 55%, 세로 중심 40%)
    # 자막: ASS burn-in
    filter_complex = (
        f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},boxblur=20:5[bg];"
        f"[0:v]scale={WIDTH}:{fg_h}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:({fg_y_center}-h/2)[v];"
        f"[v]ass={_filter_path(ass_path)}[final]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", "[final]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration:.3f}",
        "-shortest",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace")[-1500:]
        raise RuntimeError(f"ffmpeg 합성 실패:\n{stderr}") from e

    return output_path
