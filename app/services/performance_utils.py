"""
パフォーマンス最適化ユーティリティ
メモリ効率的なデータ処理とリソース管理
"""
import gc
import psutil
import logging
from typing import Iterator, List, Any, Dict, Optional
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import threading
import time

logger = logging.getLogger(__name__)


@dataclass
class MemoryStats:
    """メモリ使用量統計"""
    total_mb: float
    available_mb: float
    used_mb: float
    percent: float
    timestamp: str


@dataclass
class PerformanceMetrics:
    """パフォーマンス指標"""
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    memory_before: Optional[MemoryStats] = None
    memory_after: Optional[MemoryStats] = None
    memory_peak: Optional[MemoryStats] = None
    items_processed: int = 0
    throughput_per_second: Optional[float] = None


class MemoryMonitor:
    """メモリ使用量監視クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._monitoring = False
        self._monitor_thread = None
        self._peak_memory = None
        self._memory_threshold_mb = 1024  # 1GB
    
    def get_current_memory_stats(self) -> MemoryStats:
        """現在のメモリ使用量を取得"""
        try:
            memory = psutil.virtual_memory()
            return MemoryStats(
                total_mb=memory.total / 1024 / 1024,
                available_mb=memory.available / 1024 / 1024,
                used_mb=memory.used / 1024 / 1024,
                percent=memory.percent,
                timestamp=datetime.utcnow().isoformat()
            )
        except Exception as e:
            self.logger.warning(f"メモリ統計取得エラー: {str(e)}")
            return MemoryStats(0, 0, 0, 0, datetime.utcnow().isoformat())
    
    def start_monitoring(self, interval_seconds: float = 1.0):
        """メモリ監視を開始"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._peak_memory = self.get_current_memory_stats()
        
        def monitor_loop():
            while self._monitoring:
                try:
                    current_memory = self.get_current_memory_stats()
                    
                    # ピークメモリを更新
                    if current_memory.used_mb > self._peak_memory.used_mb:
                        self._peak_memory = current_memory
                    
                    # メモリ使用量が閾値を超えた場合は警告
                    if current_memory.used_mb > self._memory_threshold_mb:
                        self.logger.warning(
                            f"高メモリ使用量検出: {current_memory.used_mb:.1f}MB "
                            f"({current_memory.percent:.1f}%)"
                        )
                    
                    time.sleep(interval_seconds)
                    
                except Exception as e:
                    self.logger.error(f"メモリ監視エラー: {str(e)}")
                    time.sleep(interval_seconds)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        self.logger.debug("メモリ監視を開始しました")
    
    def stop_monitoring(self) -> MemoryStats:
        """メモリ監視を停止してピーク値を返す"""
        self._monitoring = False
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        
        peak_memory = self._peak_memory
        self._peak_memory = None
        
        self.logger.debug("メモリ監視を停止しました")
        return peak_memory


class BatchProcessor:
    """メモリ効率的なバッチ処理クラス"""
    
    def __init__(self, batch_size: int = 100, memory_limit_mb: int = 512):
        self.batch_size = batch_size
        self.memory_limit_mb = memory_limit_mb
        self.logger = logging.getLogger(__name__)
        self.memory_monitor = MemoryMonitor()
    
    def process_in_batches(
        self, 
        items: List[Any], 
        process_func: callable,
        progress_callback: Optional[callable] = None
    ) -> List[Any]:
        """
        アイテムをバッチ単位で処理
        
        Args:
            items: 処理対象のアイテムリスト
            process_func: 各バッチを処理する関数
            progress_callback: 進捗コールバック関数
            
        Returns:
            処理結果のリスト
        """
        results = []
        total_items = len(items)
        
        self.logger.info(f"バッチ処理開始: {total_items}件, バッチサイズ={self.batch_size}")
        
        # メモリ監視開始
        self.memory_monitor.start_monitoring()
        
        try:
            for i in range(0, total_items, self.batch_size):
                batch_start = i
                batch_end = min(i + self.batch_size, total_items)
                batch = items[batch_start:batch_end]
                
                # メモリ使用量チェック
                current_memory = self.memory_monitor.get_current_memory_stats()
                if current_memory.used_mb > self.memory_limit_mb:
                    self.logger.warning(
                        f"メモリ制限に近づいています: {current_memory.used_mb:.1f}MB"
                    )
                    # ガベージコレクションを実行
                    gc.collect()
                
                # バッチ処理実行
                try:
                    batch_result = process_func(batch)
                    if batch_result:
                        results.extend(batch_result if isinstance(batch_result, list) else [batch_result])
                    
                    # 進捗報告
                    if progress_callback:
                        progress = (batch_end / total_items) * 100
                        progress_callback(batch_end, total_items, progress)
                    
                    self.logger.debug(f"バッチ {batch_start}-{batch_end} 処理完了")
                    
                except Exception as e:
                    self.logger.error(f"バッチ {batch_start}-{batch_end} 処理エラー: {str(e)}")
                    # エラーが発生してもバッチ処理は継続
                    continue
            
        finally:
            # メモリ監視停止
            peak_memory = self.memory_monitor.stop_monitoring()
            self.logger.info(
                f"バッチ処理完了: 処理済み={len(results)}, "
                f"ピークメモリ={peak_memory.used_mb:.1f}MB"
            )
        
        return results
    
    def process_generator(
        self, 
        items_generator: Iterator[Any], 
        process_func: callable
    ) -> Iterator[Any]:
        """
        ジェネレータを使用したメモリ効率的な処理
        
        Args:
            items_generator: アイテムのジェネレータ
            process_func: 各アイテムを処理する関数
            
        Yields:
            処理結果
        """
        batch = []
        processed_count = 0
        
        self.memory_monitor.start_monitoring()
        
        try:
            for item in items_generator:
                batch.append(item)
                
                if len(batch) >= self.batch_size:
                    # バッチ処理実行
                    try:
                        batch_results = process_func(batch)
                        if batch_results:
                            for result in batch_results:
                                yield result
                        
                        processed_count += len(batch)
                        batch.clear()
                        
                        # メモリ管理
                        if processed_count % (self.batch_size * 10) == 0:
                            gc.collect()
                        
                    except Exception as e:
                        self.logger.error(f"ジェネレータバッチ処理エラー: {str(e)}")
                        batch.clear()
            
            # 残りのバッチを処理
            if batch:
                try:
                    batch_results = process_func(batch)
                    if batch_results:
                        for result in batch_results:
                            yield result
                except Exception as e:
                    self.logger.error(f"最終バッチ処理エラー: {str(e)}")
        
        finally:
            peak_memory = self.memory_monitor.stop_monitoring()
            self.logger.info(
                f"ジェネレータ処理完了: 処理済み={processed_count}, "
                f"ピークメモリ={peak_memory.used_mb:.1f}MB"
            )


class PerformanceProfiler:
    """パフォーマンス測定クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.memory_monitor = MemoryMonitor()
    
    @contextmanager
    def profile_operation(self, operation_name: str, items_count: int = 0):
        """
        操作のパフォーマンスを測定するコンテキストマネージャー
        
        Args:
            operation_name: 操作名
            items_count: 処理アイテム数
            
        Yields:
            PerformanceMetrics: パフォーマンス指標
        """
        metrics = PerformanceMetrics(
            operation_name=operation_name,
            start_time=datetime.utcnow(),
            items_processed=items_count
        )
        
        # 開始時のメモリ使用量
        metrics.memory_before = self.memory_monitor.get_current_memory_stats()
        
        # メモリ監視開始
        self.memory_monitor.start_monitoring()
        
        try:
            yield metrics
            
        finally:
            # 終了時の処理
            metrics.end_time = datetime.utcnow()
            metrics.duration_seconds = (metrics.end_time - metrics.start_time).total_seconds()
            
            # メモリ監視停止
            metrics.memory_peak = self.memory_monitor.stop_monitoring()
            metrics.memory_after = self.memory_monitor.get_current_memory_stats()
            
            # スループット計算
            if metrics.duration_seconds > 0 and metrics.items_processed > 0:
                metrics.throughput_per_second = metrics.items_processed / metrics.duration_seconds
            
            # ログ出力
            self._log_performance_metrics(metrics)
    
    def _log_performance_metrics(self, metrics: PerformanceMetrics):
        """パフォーマンス指標をログ出力"""
        log_msg = (
            f"[{metrics.operation_name}] "
            f"時間={metrics.duration_seconds:.2f}秒, "
            f"処理件数={metrics.items_processed}"
        )
        
        if metrics.throughput_per_second:
            log_msg += f", スループット={metrics.throughput_per_second:.1f}件/秒"
        
        if metrics.memory_before and metrics.memory_after:
            memory_diff = metrics.memory_after.used_mb - metrics.memory_before.used_mb
            log_msg += f", メモリ変化={memory_diff:+.1f}MB"
        
        if metrics.memory_peak:
            log_msg += f", ピークメモリ={metrics.memory_peak.used_mb:.1f}MB"
        
        self.logger.info(log_msg)


# グローバルインスタンス
memory_monitor = MemoryMonitor()
batch_processor = BatchProcessor()
performance_profiler = PerformanceProfiler()


def optimize_memory_usage():
    """メモリ使用量を最適化"""
    try:
        # ガベージコレクション実行
        collected = gc.collect()
        
        # 現在のメモリ使用量を取得
        current_memory = memory_monitor.get_current_memory_stats()
        
        logger.debug(
            f"メモリ最適化実行: GC回収={collected}オブジェクト, "
            f"現在使用量={current_memory.used_mb:.1f}MB ({current_memory.percent:.1f}%)"
        )
        
        return current_memory
        
    except Exception as e:
        logger.warning(f"メモリ最適化エラー: {str(e)}")
        return None


def get_system_performance_info() -> Dict[str, Any]:
    """システムパフォーマンス情報を取得"""
    try:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # メモリ情報
        memory = psutil.virtual_memory()
        
        # ディスク使用率
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu_percent,
            "memory": {
                "total_gb": memory.total / 1024 / 1024 / 1024,
                "available_gb": memory.available / 1024 / 1024 / 1024,
                "used_gb": memory.used / 1024 / 1024 / 1024,
                "percent": memory.percent
            },
            "disk": {
                "total_gb": disk.total / 1024 / 1024 / 1024,
                "free_gb": disk.free / 1024 / 1024 / 1024,
                "used_gb": disk.used / 1024 / 1024 / 1024,
                "percent": (disk.used / disk.total) * 100
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"システム情報取得エラー: {str(e)}")
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }