"""환경 변수 로드 및 공용 설정 (단일 사용자 로컬 모드)."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    channel_name: str = "coolvibeply"

    openai_api_key: str = ""
    gemini_api_key: str = ""

    # 자막 폰트 (시스템에 설치된 폰트명)
    # macOS 기본: "Helvetica" + "AppleSDGothicNeo-Bold"
    # Windows: "Arial" + "Malgun Gothic"
    # 설치된 다른 폰트로 자유롭게 교체 가능
    font_en: str = "Helvetica"
    font_ko: str = "AppleSDGothicNeo-Bold"

    storage_local_dir: str = "./storage"
    allowed_origins: str = "http://localhost:3000"

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_local_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
