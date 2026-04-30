"""백그라운드 태스크 진입점. FastAPI BackgroundTasks가 호출하는 얇은 래퍼."""

import logging
import traceback

from ..pipeline.orchestrator import run_pipeline

logger = logging.getLogger(__name__)


def run_short_pipeline(short_id: str) -> None:
    try:
        run_pipeline(short_id)
    except Exception:  # noqa: BLE001
        logger.error("쇼츠 파이프라인 실패: %s\n%s", short_id, traceback.format_exc())
