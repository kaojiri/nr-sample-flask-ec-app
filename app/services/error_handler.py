"""
エラーハンドリングとログ機能の実装
要件 1.4, 2.5, 3.4: 部分的成功処理、詳細エラーログ、リトライ機構、データ整合性保持
"""
import logging
import time
import traceback
import functools
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

from app import db


class ErrorSeverity(Enum):
    """エラーの重要度レベル"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """エラーカテゴリ"""
    USER_CREATION = "user_creation"
    DATA_SYNC = "data_sync"
    DATABASE = "database"
    NETWORK = "network"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    RESOURCE = "resource"
    CONFIGURATION = "configuration"


@dataclass
class ErrorDetail:
    """詳細エラー情報"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception_type: str
    stack_trace: str
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    retry_count: int = 0
    is_recoverable: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "error_id": self.error_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "exception_type": self.exception_type,
            "stack_trace": self.stack_trace,
            "context": self.context,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "is_recoverable": self.is_recoverable
        }


@dataclass
class PartialSuccessResult:
    """部分的成功処理の結果"""
    total_requested: int
    successful_count: int
    failed_count: int
    success_items: List[Any] = field(default_factory=list)
    failed_items: List[ErrorDetail] = field(default_factory=list)
    execution_time: float = 0.0
    overall_success: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "total_requested": self.total_requested,
            "successful_count": self.successful_count,
            "failed_count": self.failed_count,
            "success_rate": round(self.successful_count / self.total_requested * 100, 2) if self.total_requested > 0 else 0,
            "failed_items": [item.to_dict() for item in self.failed_items],
            "execution_time": self.execution_time,
            "overall_success": self.overall_success
        }


@dataclass
class RetryConfig:
    """リトライ設定"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_backoff: bool = True
    retry_on_exceptions: List[type] = field(default_factory=lambda: [Exception])
    
    def get_delay(self, attempt: int) -> float:
        """リトライ遅延時間を計算"""
        if self.exponential_backoff:
            delay = self.base_delay * (2 ** attempt)
            return min(delay, self.max_delay)
        return self.base_delay


class BulkUserErrorHandler:
    """一括ユーザー管理のエラーハンドリングクラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_log_file = Path("logs/bulk_user_errors.log")
        self.error_log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # ファイルハンドラーの設定
        file_handler = logging.FileHandler(self.error_log_file, encoding='utf-8')
        file_handler.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    def create_error_detail(
        self,
        exception: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity,
        context: Dict[str, Any] = None,
        retry_count: int = 0
    ) -> ErrorDetail:
        """詳細エラー情報を作成"""
        import uuid
        
        error_id = str(uuid.uuid4())[:8]
        
        # 回復可能性を判定
        is_recoverable = self._is_recoverable_error(exception, category)
        
        return ErrorDetail(
            error_id=error_id,
            category=category,
            severity=severity,
            message=str(exception),
            exception_type=type(exception).__name__,
            stack_trace=traceback.format_exc(),
            context=context or {},
            retry_count=retry_count,
            is_recoverable=is_recoverable
        )
    
    def _is_recoverable_error(self, exception: Exception, category: ErrorCategory) -> bool:
        """エラーが回復可能かどうかを判定"""
        # ネットワークエラーは通常回復可能
        if category == ErrorCategory.NETWORK:
            return True
        
        # データベース接続エラーは回復可能
        if "connection" in str(exception).lower():
            return True
        
        # タイムアウトエラーは回復可能
        if "timeout" in str(exception).lower():
            return True
        
        # バリデーションエラーは通常回復不可能
        if category == ErrorCategory.VALIDATION:
            return False
        
        # 認証エラーは通常回復不可能
        if category == ErrorCategory.AUTHENTICATION:
            return False
        
        # その他は回復可能として扱う
        return True
    
    def log_error(self, error_detail: ErrorDetail):
        """エラーを詳細ログに記録"""
        log_message = (
            f"[{error_detail.error_id}] {error_detail.category.value.upper()} ERROR "
            f"({error_detail.severity.value}): {error_detail.message}"
        )
        
        # コンテキスト情報を追加
        if error_detail.context:
            log_message += f" | Context: {json.dumps(error_detail.context, ensure_ascii=False)}"
        
        # 重要度に応じてログレベルを設定
        if error_detail.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error_detail.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error_detail.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
        
        # スタックトレースを別途記録
        if error_detail.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self.logger.error(f"[{error_detail.error_id}] Stack trace:\n{error_detail.stack_trace}")
    
    def with_retry(
        self,
        func: Callable,
        retry_config: RetryConfig = None,
        error_category: ErrorCategory = ErrorCategory.DATABASE,
        context: Dict[str, Any] = None
    ):
        """リトライ機構付きでfunction実行"""
        if retry_config is None:
            retry_config = RetryConfig()
        
        last_exception = None
        
        for attempt in range(retry_config.max_attempts):
            try:
                return func()
            
            except Exception as e:
                last_exception = e
                
                # リトライ対象の例外かチェック
                if not any(isinstance(e, exc_type) for exc_type in retry_config.retry_on_exceptions):
                    break
                
                # エラー詳細を作成してログ
                error_detail = self.create_error_detail(
                    e, error_category, ErrorSeverity.MEDIUM, context, attempt + 1
                )
                self.log_error(error_detail)
                
                # 最後の試行でない場合は待機
                if attempt < retry_config.max_attempts - 1:
                    delay = retry_config.get_delay(attempt)
                    self.logger.info(f"リトライ {attempt + 1}/{retry_config.max_attempts} - {delay}秒後に再試行")
                    time.sleep(delay)
        
        # 全ての試行が失敗した場合
        if last_exception:
            final_error = self.create_error_detail(
                last_exception, error_category, ErrorSeverity.HIGH, context, retry_config.max_attempts
            )
            self.log_error(final_error)
            raise last_exception
    
    def process_with_partial_success(
        self,
        items: List[Any],
        process_func: Callable[[Any], Any],
        error_category: ErrorCategory = ErrorCategory.USER_CREATION,
        continue_on_error: bool = True,
        context: Dict[str, Any] = None
    ) -> PartialSuccessResult:
        """部分的成功処理でアイテムを処理"""
        start_time = time.time()
        
        successful_items = []
        failed_items = []
        
        self.logger.info(f"部分的成功処理開始: {len(items)}件の処理")
        
        for i, item in enumerate(items):
            try:
                # 個別アイテムの処理
                result = process_func(item)
                successful_items.append(result)
                
                # 進捗ログ（100件ごと）
                if (i + 1) % 100 == 0:
                    self.logger.info(f"処理進捗: {i + 1}/{len(items)} 完了")
            
            except Exception as e:
                # エラー詳細を作成
                item_context = {
                    "item_index": i,
                    "item_data": str(item)[:200],  # 最初の200文字のみ
                    **(context or {})
                }
                
                error_detail = self.create_error_detail(
                    e, error_category, ErrorSeverity.MEDIUM, item_context
                )
                failed_items.append(error_detail)
                self.log_error(error_detail)
                
                # 継続するかどうかの判定
                if not continue_on_error:
                    self.logger.error(f"致命的エラーのため処理を中断: {str(e)}")
                    break
        
        execution_time = time.time() - start_time
        
        # 結果の作成
        result = PartialSuccessResult(
            total_requested=len(items),
            successful_count=len(successful_items),
            failed_count=len(failed_items),
            success_items=successful_items,
            failed_items=failed_items,
            execution_time=execution_time,
            overall_success=len(failed_items) == 0
        )
        
        # 結果ログ
        self.logger.info(
            f"部分的成功処理完了: 成功={result.successful_count}, "
            f"失敗={result.failed_count}, 時間={execution_time:.2f}秒"
        )
        
        return result
    
    def preserve_data_integrity(self, operation_func: Callable, rollback_func: Callable = None):
        """データ整合性保持機能付きで操作実行"""
        try:
            # 操作前の状態を記録
            self.logger.info("データ整合性保持操作開始")
            
            # 操作実行
            result = operation_func()
            
            # 成功時はコミット
            db.session.commit()
            self.logger.info("データ整合性保持操作完了 - コミット成功")
            
            return result
        
        except Exception as e:
            # エラー時はロールバック
            db.session.rollback()
            self.logger.error(f"データ整合性保持操作失敗 - ロールバック実行: {str(e)}")
            
            # カスタムロールバック処理があれば実行
            if rollback_func:
                try:
                    rollback_func()
                    self.logger.info("カスタムロールバック処理完了")
                except Exception as rollback_error:
                    self.logger.error(f"カスタムロールバック処理失敗: {str(rollback_error)}")
            
            # エラー詳細を作成してログ
            error_detail = self.create_error_detail(
                e, ErrorCategory.DATABASE, ErrorSeverity.HIGH,
                {"operation": "data_integrity_preservation"}
            )
            self.log_error(error_detail)
            
            raise e
    
    def generate_error_report(self, start_time: datetime = None, end_time: datetime = None) -> Dict[str, Any]:
        """エラーレポートを生成"""
        try:
            # ログファイルからエラー情報を読み取り
            if not self.error_log_file.exists():
                return {
                    "total_errors": 0,
                    "error_summary": {},
                    "report_period": "No errors found",
                    "generated_at": datetime.utcnow().isoformat()
                }
            
            error_summary = {
                "by_category": {},
                "by_severity": {},
                "by_hour": {},
                "recoverable_errors": 0,
                "non_recoverable_errors": 0
            }
            
            total_errors = 0
            
            # ログファイルを解析（簡易版）
            with open(self.error_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if "ERROR" in line or "CRITICAL" in line or "WARNING" in line:
                        total_errors += 1
                        
                        # カテゴリ別集計
                        for category in ErrorCategory:
                            if category.value.upper() in line:
                                error_summary["by_category"][category.value] = \
                                    error_summary["by_category"].get(category.value, 0) + 1
                                break
                        
                        # 重要度別集計
                        for severity in ErrorSeverity:
                            if severity.value.upper() in line:
                                error_summary["by_severity"][severity.value] = \
                                    error_summary["by_severity"].get(severity.value, 0) + 1
                                break
            
            return {
                "total_errors": total_errors,
                "error_summary": error_summary,
                "report_period": f"{start_time or 'All time'} - {end_time or 'Present'}",
                "generated_at": datetime.utcnow().isoformat(),
                "log_file_path": str(self.error_log_file)
            }
        
        except Exception as e:
            self.logger.error(f"エラーレポート生成失敗: {str(e)}")
            return {
                "error": f"レポート生成エラー: {str(e)}",
                "generated_at": datetime.utcnow().isoformat()
            }


# デコレータ関数
def with_error_handling(
    category: ErrorCategory = ErrorCategory.DATABASE,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    retry_config: RetryConfig = None,
    preserve_integrity: bool = False
):
    """エラーハンドリング機能付きデコレータ"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = BulkUserErrorHandler()
            
            if preserve_integrity:
                return error_handler.preserve_data_integrity(
                    lambda: func(*args, **kwargs)
                )
            elif retry_config:
                return error_handler.with_retry(
                    lambda: func(*args, **kwargs),
                    retry_config,
                    category
                )
            else:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_detail = error_handler.create_error_detail(
                        e, category, severity, {"function": func.__name__}
                    )
                    error_handler.log_error(error_detail)
                    raise
        
        return wrapper
    return decorator


# グローバルエラーハンドラーインスタンス
error_handler = BulkUserErrorHandler()