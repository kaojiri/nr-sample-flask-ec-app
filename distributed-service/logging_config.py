"""
分散サービス用ログ設定
構造化ログ出力とNew Relic統合
"""

import logging
import logging.config
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional


class StructuredFormatter(logging.Formatter):
    """構造化ログフォーマッター（JSON形式）"""
    
    def __init__(self, service_name: str = "distributed-service"):
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """ログレコードをJSON形式にフォーマット"""
        
        # 基本的なログデータ
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'service': self.service_name,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # 例外情報があれば追加
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }
        
        # カスタム属性があれば追加
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info']:
                extra_fields[key] = value
        
        if extra_fields:
            log_data['extra'] = extra_fields
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class PerformanceLogger:
    """パフォーマンス監視用ログ機能"""
    
    def __init__(self, logger_name: str = "performance"):
        self.logger = logging.getLogger(logger_name)
    
    def log_query_performance(
        self, 
        operation: str,
        user_id: Optional[int] = None,
        query_count: int = 0,
        execution_time: float = 0.0,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        クエリパフォーマンスをログ出力
        
        Args:
            operation (str): 操作名
            user_id (Optional[int]): ユーザーID
            query_count (int): クエリ実行回数
            execution_time (float): 実行時間（秒）
            additional_data (Optional[Dict[str, Any]]): 追加データ
        """
        log_data = {
            'type': 'query_performance',
            'operation': operation,
            'user_id': user_id,
            'query_count': query_count,
            'execution_time_seconds': execution_time,
            'queries_per_second': query_count / execution_time if execution_time > 0 else 0
        }
        
        if additional_data:
            log_data.update(additional_data)
        
        self.logger.info(
            f"Query performance - Operation: {operation}, "
            f"Queries: {query_count}, Time: {execution_time:.3f}s",
            extra=log_data
        )
    
    def log_http_request(
        self,
        method: str,
        url: str,
        status_code: int,
        execution_time: float,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        HTTPリクエストをログ出力
        
        Args:
            method (str): HTTPメソッド
            url (str): リクエストURL
            status_code (int): ステータスコード
            execution_time (float): 実行時間（秒）
            user_id (Optional[int]): ユーザーID
            operation (Optional[str]): 操作名
            additional_data (Optional[Dict[str, Any]]): 追加データ
        """
        log_data = {
            'type': 'http_request',
            'method': method,
            'url': url,
            'status_code': status_code,
            'execution_time_seconds': execution_time,
            'user_id': user_id,
            'operation': operation
        }
        
        if additional_data:
            log_data.update(additional_data)
        
        level = logging.INFO if 200 <= status_code < 400 else logging.WARNING
        
        self.logger.log(
            level,
            f"HTTP {method} {url} - Status: {status_code}, Time: {execution_time:.3f}s",
            extra=log_data
        )
    
    def log_database_operation(
        self,
        operation: str,
        table_name: Optional[str] = None,
        record_count: int = 0,
        execution_time: float = 0.0,
        user_id: Optional[int] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        データベース操作をログ出力
        
        Args:
            operation (str): 操作名（SELECT, INSERT, UPDATE, DELETE等）
            table_name (Optional[str]): テーブル名
            record_count (int): 処理レコード数
            execution_time (float): 実行時間（秒）
            user_id (Optional[int]): ユーザーID
            additional_data (Optional[Dict[str, Any]]): 追加データ
        """
        log_data = {
            'type': 'database_operation',
            'operation': operation,
            'table_name': table_name,
            'record_count': record_count,
            'execution_time_seconds': execution_time,
            'user_id': user_id
        }
        
        if additional_data:
            log_data.update(additional_data)
        
        self.logger.info(
            f"DB {operation} {table_name or ''} - "
            f"Records: {record_count}, Time: {execution_time:.3f}s",
            extra=log_data
        )


class SecurityLogger:
    """セキュリティ関連ログ機能"""
    
    def __init__(self, logger_name: str = "security"):
        self.logger = logging.getLogger(logger_name)
    
    def log_authentication_attempt(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        success: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        認証試行をログ出力
        
        Args:
            user_id (Optional[int]): ユーザーID
            username (Optional[str]): ユーザー名
            success (bool): 認証成功フラグ
            ip_address (Optional[str]): IPアドレス
            user_agent (Optional[str]): ユーザーエージェント
            additional_data (Optional[Dict[str, Any]]): 追加データ
        """
        log_data = {
            'type': 'authentication_attempt',
            'user_id': user_id,
            'username': username,
            'success': success,
            'ip_address': ip_address,
            'user_agent': user_agent
        }
        
        if additional_data:
            log_data.update(additional_data)
        
        level = logging.INFO if success else logging.WARNING
        
        self.logger.log(
            level,
            f"Authentication {'successful' if success else 'failed'} - "
            f"User: {username or user_id}, IP: {ip_address}",
            extra=log_data
        )
    
    def log_suspicious_activity(
        self,
        activity_type: str,
        description: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        severity: str = "medium",
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        疑わしい活動をログ出力
        
        Args:
            activity_type (str): 活動タイプ
            description (str): 説明
            user_id (Optional[int]): ユーザーID
            ip_address (Optional[str]): IPアドレス
            severity (str): 重要度（low, medium, high, critical）
            additional_data (Optional[Dict[str, Any]]): 追加データ
        """
        log_data = {
            'type': 'suspicious_activity',
            'activity_type': activity_type,
            'description': description,
            'user_id': user_id,
            'ip_address': ip_address,
            'severity': severity
        }
        
        if additional_data:
            log_data.update(additional_data)
        
        # 重要度に応じてログレベルを設定
        level_map = {
            'low': logging.INFO,
            'medium': logging.WARNING,
            'high': logging.ERROR,
            'critical': logging.CRITICAL
        }
        level = level_map.get(severity, logging.WARNING)
        
        self.logger.log(
            level,
            f"Suspicious activity detected - Type: {activity_type}, "
            f"User: {user_id}, IP: {ip_address}, Severity: {severity}",
            extra=log_data
        )


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "structured",
    log_file: Optional[str] = None,
    service_name: str = "distributed-service"
) -> Dict[str, Any]:
    """
    ログ設定をセットアップ
    
    Args:
        log_level (str): ログレベル
        log_format (str): ログフォーマット（structured, simple）
        log_file (Optional[str]): ログファイルパス
        service_name (str): サービス名
        
    Returns:
        Dict[str, Any]: ログ設定辞書
    """
    
    # ログレベルを設定
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # フォーマッターを設定
    formatters = {
        'structured': {
            '()': StructuredFormatter,
            'service_name': service_name
        },
        'simple': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    }
    
    # ハンドラーを設定
    handlers = {
        'console': {
            'class': 'logging.StreamHandler',
            'level': log_level.upper(),
            'formatter': log_format,
            'stream': 'ext://sys.stdout'
        }
    }
    
    # ファイルハンドラーを追加（指定された場合）
    if log_file:
        handlers['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': log_level.upper(),
            'formatter': log_format,
            'filename': log_file,
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'encoding': 'utf-8'
        }
    
    # ロガー設定
    loggers = {
        '': {  # ルートロガー
            'level': log_level.upper(),
            'handlers': list(handlers.keys()),
            'propagate': False
        },
        'performance': {
            'level': 'INFO',
            'handlers': list(handlers.keys()),
            'propagate': False
        },
        'security': {
            'level': 'INFO',
            'handlers': list(handlers.keys()),
            'propagate': False
        },
        'sqlalchemy.engine': {
            'level': 'INFO',
            'handlers': list(handlers.keys()),
            'propagate': False
        },
        'newrelic': {
            'level': 'WARNING',
            'handlers': list(handlers.keys()),
            'propagate': False
        }
    }
    
    # ログ設定辞書を作成
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'handlers': handlers,
        'loggers': loggers
    }
    
    return config


def configure_app_logging(app, log_level: str = None, log_format: str = None):
    """
    Flaskアプリケーションのログ設定
    
    Args:
        app: Flaskアプリケーションインスタンス
        log_level (str): ログレベル（環境変数から取得可能）
        log_format (str): ログフォーマット（環境変数から取得可能）
    """
    
    # 環境変数から設定を取得
    log_level = log_level or os.getenv('LOG_LEVEL', 'INFO')
    log_format = log_format or os.getenv('LOG_FORMAT', 'structured')
    log_file = os.getenv('LOG_FILE')
    service_name = os.getenv('SERVICE_NAME', 'distributed-service')
    
    # ログ設定を作成
    config = setup_logging(
        log_level=log_level,
        log_format=log_format,
        log_file=log_file,
        service_name=service_name
    )
    
    # ログ設定を適用
    logging.config.dictConfig(config)
    
    # Flaskアプリケーションのログレベルを設定
    app.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # ログ設定完了をログ出力
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured - Level: {log_level}, Format: {log_format}, "
        f"Service: {service_name}, File: {log_file or 'None'}"
    )
    
    return config


# グローバルロガーインスタンス
performance_logger = PerformanceLogger()
security_logger = SecurityLogger()