# AGENTS.md

> AI 에이전트(Claude Code 등)가 이 레포에 처음 들어왔을 때 빠르게 컨텍스트를 잡기 위한 안내.

## 한 줄 요약

20-30대를 위한 Pop/R&B/Jazz 플레이리스트 큐레이션 채널의 **콘텐츠 제작 자동화 백엔드**. 각 채널 운영자가 본인 컴퓨터에 클론해서 단독으로 쓰는 **데스크톱 도구** — 서버에 배포하거나 멀티유저로 굴리지 않음.

## 빠른 구조

```
backend/
├── main.py              FastAPI 앱 (단일 사용자 모드)
├── config.py            .env 로드 (Pydantic Settings)
├── db.py                SQLAlchemy 모델 + SQLite
├── api/
│   ├── playlists.py     Playlist CRUD + 곡 추가
│   ├── songs.py         Song CRUD + shorts_pick 마킹
│   └── shorts.py        ad-hoc 클립 (V0.1 호환)
├── pipeline/
│   ├── orchestrator.py  5단계 파이프라인 오케스트레이션
│   ├── steps.py         다운로드 / STT / 번역
│   └── render.py        FFmpeg + ASS 9:16 합성
└── workers/
    └── tasks.py         FastAPI BackgroundTasks 래퍼
```

## 핵심 컨벤션

- **단일 사용자 로컬 모드**: 인증·계정·멀티테넌트 없음. `user_id` 컬럼이나 인증 미들웨어 다시 도입하지 말 것.
- **API 키는 `.env`에서**: `backend/config.py`의 Pydantic Settings로 로드. 요청 헤더나 DB로 받지 않음.
- **DB 세션은 컨텍스트 매니저**: 항상 `session_scope()`를 사용 (`backend/db.py`). raw `SessionLocal()` 호출 금지.
- **사용자 메시지는 한국어**: HTTPException, RuntimeError 등 사용자에게 노출되는 텍스트는 한국어로.
- **마이그레이션은 V0.3에서**: 현재는 `Base.metadata.create_all()`만 사용. 컬럼 추가는 SQLite 재생성(`rm storage/coolvibeply.db`)으로 처리. 본격적인 마이그레이션은 V0.3에서 Alembic 도입.

## 절대 하지 말 것

- ❌ Supabase, JWT, Fernet 암호화된 사용자 키 등 V0.1 멀티유저 잔재 재도입
- ❌ Creatomate 등 외부 렌더 API 의존 추가 (FFmpeg 로컬 합성으로 V0.2에서 떼냄)
- ❌ `Short.user_id` 컬럼 부활
- ❌ `frontend/` 폴더 — V1.0까지는 백엔드만, UI는 `/docs` Swagger로

## 흔한 작업

```bash
# 의존성 설치
pip install -r backend/requirements.txt

# 서버 기동
uvicorn backend.main:app --reload

# /docs 에서 인터랙티브 테스트
open http://localhost:8000/docs
```

## 외부 의존

- **Python 3.11+**
- **FFmpeg with libass** — 자막 burn-in 필수
    - macOS: `brew install ffmpeg-full` (`ffmpeg`만 설치하면 libass 빠짐, V0.2에서 발견됨)
    - Ubuntu: `apt install ffmpeg`
- **OpenAI API key** — Whisper STT
- **Gemini API key** — 영→한 번역

## 더 읽기

- [README.md](README.md) — 사용자 관점 안내, 설치/실행
- [docs/product-specs/channel-concept.md](docs/product-specs/channel-concept.md) — 채널 콘셉트 상세
- [docs/exec-plans/active/v0.2.md](docs/exec-plans/active/v0.2.md) — V0.2 작업 진행 + 결정 로그
