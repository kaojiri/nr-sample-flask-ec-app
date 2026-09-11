"""正常系ベースライン負荷ワーカー（完全独立・自己完結）

Rage Click インシデントのデモで「平常時の賑わい」を作るための、
正常系ページだけを並列に叩く軽量負荷ジェネレータ。

設計方針:
- 既存の worker_pool / endpoint_selector / load_test_manager / config(ConfigManager)
  には一切依存しない。import もしない。
- asyncio + aiohttp で完結。並列数(concurrency)ぶんのタスクが、
  正常系ページをランダム間隔で叩き続けるだけ。
- 叩くのは正常系ページのみ(/、/products、/products/1、/products/2)。
  重い処理(/performance/*)やエラー系は一切叩かないので、ベースラインが荒れない。

これにより「平常は健全 → 承認画面の連打で急変 → 他機能まで巻き添え」の
コントラストが綺麗に出る。
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import aiohttp

logger = logging.getLogger("baseline_worker")

# 正常系ページ（重い処理・エラー系は含めない）
DEFAULT_BASELINE_PATHS: List[str] = [
    "/",
    "/products",
    "/products/1",
    "/products/2",
]


@dataclass
class BaselineStats:
    """ベースライン負荷の実行統計"""
    started_at: Optional[str] = None
    concurrency: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    per_path_counts: dict = field(default_factory=dict)

    @property
    def average_response_time(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_response_time / self.successful_requests

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "concurrency": self.concurrency,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "average_response_time_ms": round(self.average_response_time * 1000, 1),
            "per_path_counts": self.per_path_counts,
        }


class BaselineLoadGenerator:
    """正常系ページを並列に叩き続ける自己完結ジェネレータ"""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._running: bool = False
        self._stats: BaselineStats = BaselineStats()
        self._config: dict = {}

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "config": self._config,
            "stats": self._stats.to_dict(),
        }

    async def start(
        self,
        target_base_url: str,
        concurrency: int = 10,
        duration_minutes: int = 30,
        interval_min: float = 0.5,
        interval_max: float = 2.0,
        paths: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> None:
        """ベースライン負荷を開始する"""
        if self._running:
            raise RuntimeError("Baseline load is already running")

        paths = paths or list(DEFAULT_BASELINE_PATHS)
        base = target_base_url.rstrip("/")

        self._stop_event = asyncio.Event()
        self._stats = BaselineStats(
            started_at=datetime.now(timezone.utc).isoformat(),
            concurrency=concurrency,
            per_path_counts={p: 0 for p in paths},
        )
        self._config = {
            "target_base_url": base,
            "concurrency": concurrency,
            "duration_minutes": duration_minutes,
            "interval_min": interval_min,
            "interval_max": interval_max,
            "paths": paths,
            "timeout": timeout,
        }
        self._running = True

        self._task = asyncio.create_task(
            self._run(base, concurrency, duration_minutes,
                      interval_min, interval_max, paths, timeout)
        )
        logger.info(
            f"Baseline load started: {concurrency} workers hitting {paths} "
            f"on {base} for {duration_minutes} min"
        )

    async def stop(self) -> None:
        """ベースライン負荷を停止する"""
        if not self._running:
            return
        if self._stop_event:
            self._stop_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=15.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
        self._running = False
        logger.info("Baseline load stopped")

    async def _run(self, base, concurrency, duration_minutes,
                   interval_min, interval_max, paths, timeout):
        end_time = time.time() + duration_minutes * 60
        connector = aiohttp.TCPConnector(limit=concurrency * 2)
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        try:
            async with aiohttp.ClientSession(
                connector=connector, timeout=client_timeout
            ) as session:
                workers = [
                    asyncio.create_task(
                        self._worker(session, base, paths,
                                     interval_min, interval_max, end_time)
                    )
                    for _ in range(concurrency)
                ]
                await asyncio.gather(*workers, return_exceptions=True)
        except Exception as e:
            logger.error(f"Baseline load run error: {e}")
        finally:
            self._running = False
            logger.info(
                f"Baseline load finished: {self._stats.total_requests} requests "
                f"({self._stats.successful_requests} ok, "
                f"{self._stats.failed_requests} failed)"
            )

    async def _worker(self, session, base, paths,
                      interval_min, interval_max, end_time):
        while not self._stop_event.is_set() and time.time() < end_time:
            path = random.choice(paths)
            url = f"{base}{path}"
            start = time.time()
            try:
                async with session.get(url) as resp:
                    await resp.read()
                    elapsed = time.time() - start
                    self._stats.total_requests += 1
                    self._stats.per_path_counts[path] = (
                        self._stats.per_path_counts.get(path, 0) + 1
                    )
                    if resp.status < 400:
                        self._stats.successful_requests += 1
                        self._stats.total_response_time += elapsed
                    else:
                        self._stats.failed_requests += 1
            except Exception:
                self._stats.total_requests += 1
                self._stats.failed_requests += 1

            # ランダム間隔で待機（stop で即中断可能）
            interval = random.uniform(interval_min, interval_max)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                break  # stop された
            except asyncio.TimeoutError:
                continue


# シングルトン（このモジュール内で完結）
baseline_generator = BaselineLoadGenerator()
