"""正常系ベースライン負荷 API（完全独立）

既存の api.py / worker_pool / load_test_manager には一切依存しない、
baseline_worker だけを操作する専用ルーター。

エンドポイント:
- POST /baseline/start   : 正常系ベースライン負荷を開始
- POST /baseline/stop    : 停止
- GET  /baseline/status  : 状態・統計取得
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from baseline_worker import baseline_generator, DEFAULT_BASELINE_PATHS

logger = logging.getLogger("baseline_api")

router = APIRouter()


class BaselineStartRequest(BaseModel):
    """ベースライン負荷開始リクエスト"""
    concurrency: int = 10
    duration_minutes: int = 30
    interval_min: float = 0.5
    interval_max: float = 2.0
    paths: Optional[List[str]] = None
    timeout: int = 30
    # 未指定なら環境変数 LOAD_TESTER_TARGET_APP_URL / 既定 http://web:5000 を使う
    target_app_url: Optional[str] = None


def _resolve_target_url(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    import os
    return os.environ.get("LOAD_TESTER_TARGET_APP_URL", "http://web:5000")


@router.post("/baseline/start")
async def start_baseline(request: BaselineStartRequest):
    """正常系ページのみを並列に叩くベースライン負荷を開始する"""
    if baseline_generator.is_running:
        raise HTTPException(
            status_code=409,
            detail="Baseline load is already running",
        )
    # 安全上限（既存 config とは独立した最小限のガード）
    if not (1 <= request.concurrency <= 100):
        raise HTTPException(status_code=400, detail="concurrency must be 1..100")
    if not (1 <= request.duration_minutes <= 240):
        raise HTTPException(status_code=400, detail="duration_minutes must be 1..240")
    if request.interval_min < 0 or request.interval_max <= request.interval_min:
        raise HTTPException(
            status_code=400,
            detail="interval_max must be greater than interval_min (>=0)",
        )

    target = _resolve_target_url(request.target_app_url)
    try:
        await baseline_generator.start(
            target_base_url=target,
            concurrency=request.concurrency,
            duration_minutes=request.duration_minutes,
            interval_min=request.interval_min,
            interval_max=request.interval_max,
            paths=request.paths,
            timeout=request.timeout,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start baseline load: {e}")
        raise HTTPException(status_code=500, detail="Failed to start baseline load")

    return {
        "message": "Baseline load started",
        "target_app_url": target,
        "paths": request.paths or list(DEFAULT_BASELINE_PATHS),
        "concurrency": request.concurrency,
        "duration_minutes": request.duration_minutes,
    }


@router.post("/baseline/stop")
async def stop_baseline():
    """ベースライン負荷を停止する"""
    if not baseline_generator.is_running:
        return {"message": "Baseline load is not running"}
    await baseline_generator.stop()
    return {"message": "Baseline load stopped"}


@router.get("/baseline/status")
async def baseline_status():
    """ベースライン負荷の状態と統計を返す"""
    return baseline_generator.get_status()
