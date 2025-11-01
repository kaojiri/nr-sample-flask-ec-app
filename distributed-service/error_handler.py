"""
分散サービス用エラーハンドラー
データベース接続エラー、HTTP通信エラー、その他のエラーを統合的に処理
"""

import logging
import traceback
import time
from datetime import datetime
from typing import Dict, Any, Optional, Union
from flask import jsonify, request
import newrelic.agent
from sqlalchemy.exc import (
    SQLAlchemyError, 
    DatabaseError, 
    DisconnectionError,
    TimeoutError as SQLTimeoutError,
    IntegrityError,
    OperationalError
)
import psycopg2
from requests.exceptions import RequestException, Timeout, ConnectionError

logger = logging.getLogger(__name__)


class DistributedServiceErrorHandler:
    """分散サービス用の統合エラーハンドラー"""
    
    @staticmethod
    def handle_database_error(
        error: Exception, 
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        データベースエラーを処理
        
        Args:
            error (Exception): データベースエラー
            user_id (Optional[int]): ユーザーID
            operation (Optional[str]): 実行していた操作
            context (Optional[Dict[str, Any]]): 追加のコンテキスト情報
            
        Returns:
            Dict[str, Any]: エラーレスポンス
        """
        error_type = "database_error"
        error_category = "unknown"
        error_message = str(error)
        http_status = 500
        
        # エラーの種類を判定
        if isinstance(error, DisconnectionError):
            error_category = "connection_lost"
            error_message = "データベース接続が失われました"
            http_status = 503
        elif isinstance(error, SQLTimeoutError):
            error_category = "timeout"
            error_message = "データベースクエリがタイムアウトしました"
            http_status = 504
        elif isinstance(error, IntegrityError):
            error_category = "constraint_violation"
            error_message = "データベース制約違反が発生しました"
            http_status = 400
        elif isinstance(error, OperationalError):
            error_category = "operational_error"
            if "connection" in error_message.lower():
                error_message = "データベースへの接続に失敗しました"
                http_status = 503
            else:
                error_message = "データベース操作エラーが発生しました"
        elif isinstance(error, DatabaseError):
            error_category = "database_error"
            error_message = "データベースエラーが発生しました"
        elif isinstance(error, psycopg2.Error):
            error_category = "postgresql_error"
            if isinstance(error, psycopg2.OperationalError):
                error_message = "PostgreSQL接続エラーが発生しました"
                http_status = 503
            elif isinstance(error, psycopg2.IntegrityError):
                error_message = "PostgreSQL制約違反が発生しました"
                http_status = 400
            else:
                error_message = "PostgreSQLエラーが発生しました"
        
        # 構造化ログを出力
        DistributedServiceErrorHandler._log_structured_error(
            error_type=error_type,
            error_category=error_category,
            error_message=error_message,
            original_error=error,
            user_id=user_id,
            operation=operation,
            context=context,
            http_status=http_status
        )
        
        # New Relicにエラーを報告
        DistributedServiceErrorHandler._report_to_newrelic(
            error=error,
            error_type=error_type,
            error_category=error_category,
            user_id=user_id,
            operation=operation,
            context=context
        )
        
        return {
            'status': 'error',
            'error_type': error_type,
            'error_category': error_category,
            'message': error_message,
            'user_id': user_id,
            'operation': operation,
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'distributed-service'
        }, http_status
    
    @staticmethod
    def handle_http_error(
        error: Exception,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        HTTP通信エラーを処理
        
        Args:
            error (Exception): HTTP通信エラー
            user_id (Optional[int]): ユーザーID
            operation (Optional[str]): 実行していた操作
            context (Optional[Dict[str, Any]]): 追加のコンテキスト情報
            
        Returns:
            Dict[str, Any]: エラーレスポンス
        """
        error_type = "http_error"
        error_category = "unknown"
        error_message = str(error)
        http_status = 500
        
        # エラーの種類を判定
        if isinstance(error, Timeout):
            error_category = "timeout"
            error_message = "HTTP通信がタイムアウトしました"
            http_status = 504
        elif isinstance(error, ConnectionError):
            error_category = "connection_error"
            error_message = "HTTP接続エラーが発生しました"
            http_status = 503
        elif isinstance(error, RequestException):
            error_category = "request_error"
            error_message = "HTTPリクエストエラーが発生しました"
            http_status = 502
        
        # 構造化ログを出力
        DistributedServiceErrorHandler._log_structured_error(
            error_type=error_type,
            error_category=error_category,
            error_message=error_message,
            original_error=error,
            user_id=user_id,
            operation=operation,
            context=context,
            http_status=http_status
        )
        
        # New Relicにエラーを報告
        DistributedServiceErrorHandler._report_to_newrelic(
            error=error,
            error_type=error_type,
            error_category=error_category,
            user_id=user_id,
            operation=operation,
            context=context
        )
        
        return {
            'status': 'error',
            'error_type': error_type,
            'error_category': error_category,
            'message': error_message,
            'user_id': user_id,
            'operation': operation,
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'distributed-service'
        }, http_status
    
    @staticmethod
    def handle_general_error(
        error: Exception,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        一般的なエラーを処理
        
        Args:
            error (Exception): 一般的なエラー
            user_id (Optional[int]): ユーザーID
            operation (Optional[str]): 実行していた操作
            context (Optional[Dict[str, Any]]): 追加のコンテキスト情報
            
        Returns:
            Dict[str, Any]: エラーレスポンス
        """
        error_type = "general_error"
        error_category = type(error).__name__
        error_message = str(error)
        http_status = 500
        
        # 特定のエラータイプを判定
        if isinstance(error, ValueError):
            error_category = "validation_error"
            error_message = "入力値が無効です"
            http_status = 400
        elif isinstance(error, KeyError):
            error_category = "missing_parameter"
            error_message = "必要なパラメータが不足しています"
            http_status = 400
        elif isinstance(error, TypeError):
            error_category = "type_error"
            error_message = "データ型エラーが発生しました"
            http_status = 400
        elif isinstance(error, AttributeError):
            error_category = "attribute_error"
            error_message = "属性エラーが発生しました"
        
        # 構造化ログを出力
        DistributedServiceErrorHandler._log_structured_error(
            error_type=error_type,
            error_category=error_category,
            error_message=error_message,
            original_error=error,
            user_id=user_id,
            operation=operation,
            context=context,
            http_status=http_status
        )
        
        # New Relicにエラーを報告
        DistributedServiceErrorHandler._report_to_newrelic(
            error=error,
            error_type=error_type,
            error_category=error_category,
            user_id=user_id,
            operation=operation,
            context=context
        )
        
        return {
            'status': 'error',
            'error_type': error_type,
            'error_category': error_category,
            'message': error_message,
            'user_id': user_id,
            'operation': operation,
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'distributed-service'
        }, http_status
    
    @staticmethod
    def _log_structured_error(
        error_type: str,
        error_category: str,
        error_message: str,
        original_error: Exception,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_status: int = 500
    ):
        """
        構造化されたエラーログを出力
        
        Args:
            error_type (str): エラータイプ
            error_category (str): エラーカテゴリ
            error_message (str): エラーメッセージ
            original_error (Exception): 元のエラー
            user_id (Optional[int]): ユーザーID
            operation (Optional[str]): 操作名
            context (Optional[Dict[str, Any]]): コンテキスト情報
            http_status (int): HTTPステータスコード
        """
        # リクエスト情報を取得
        request_info = {}
        try:
            if request:
                request_info = {
                    'method': request.method,
                    'url': request.url,
                    'remote_addr': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'content_type': request.headers.get('Content-Type', ''),
                    'content_length': request.headers.get('Content-Length', 0)
                }
        except:
            pass
        
        # 構造化ログデータを作成
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': 'ERROR',
            'service': 'distributed-service',
            'error': {
                'type': error_type,
                'category': error_category,
                'message': error_message,
                'exception_type': type(original_error).__name__,
                'exception_message': str(original_error),
                'traceback': traceback.format_exc()
            },
            'request': request_info,
            'user_id': user_id,
            'operation': operation,
            'context': context or {},
            'http_status': http_status
        }
        
        # JSONログとして出力
        logger.error(f"STRUCTURED_ERROR: {log_data}")
        
        # 通常のログも出力（可読性のため）
        logger.error(
            f"Error occurred - Type: {error_type}, Category: {error_category}, "
            f"Message: {error_message}, User: {user_id}, Operation: {operation}, "
            f"Status: {http_status}"
        )
    
    @staticmethod
    def _report_to_newrelic(
        error: Exception,
        error_type: str,
        error_category: str,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        New Relicにエラーを報告
        
        Args:
            error (Exception): エラー
            error_type (str): エラータイプ
            error_category (str): エラーカテゴリ
            user_id (Optional[int]): ユーザーID
            operation (Optional[str]): 操作名
            context (Optional[Dict[str, Any]]): コンテキスト情報
        """
        try:
            # Custom Attributeを設定
            if user_id:
                newrelic.agent.add_custom_attribute('error_user_id', user_id)
                newrelic.agent.add_custom_attribute('user_id', user_id)
            
            if operation:
                newrelic.agent.add_custom_attribute('error_operation', operation)
                newrelic.agent.add_custom_attribute('operation_type', operation)
            
            newrelic.agent.add_custom_attribute('error_type', error_type)
            newrelic.agent.add_custom_attribute('error_category', error_category)
            newrelic.agent.add_custom_attribute('service_name', 'distributed-service')
            newrelic.agent.add_custom_attribute('error_timestamp', datetime.utcnow().isoformat())
            
            # コンテキスト情報をCustom Attributeとして追加
            if context:
                for key, value in context.items():
                    try:
                        # New Relicは特定の型のみサポートするため、文字列に変換
                        attr_key = f"context_{key}"
                        attr_value = str(value) if not isinstance(value, (str, int, float, bool)) else value
                        newrelic.agent.add_custom_attribute(attr_key, attr_value)
                    except Exception as attr_error:
                        logger.warning(f"Failed to set custom attribute {key}: {attr_error}")
            
            # リクエスト情報をCustom Attributeとして追加
            try:
                if request:
                    newrelic.agent.add_custom_attribute('request_method', request.method)
                    newrelic.agent.add_custom_attribute('request_url', request.url)
                    newrelic.agent.add_custom_attribute('request_remote_addr', request.remote_addr)
            except:
                pass
            
            # エラーをNew Relicに記録
            newrelic.agent.notice_error()
            
            logger.info(f"Error reported to New Relic: {error_type}/{error_category}")
            
        except Exception as nr_error:
            logger.error(f"Failed to report error to New Relic: {nr_error}")


class DatabaseConnectionManager:
    """データベース接続管理クラス"""
    
    @staticmethod
    def check_connection(db) -> bool:
        """
        データベース接続をチェック
        
        Args:
            db: SQLAlchemyデータベースインスタンス
            
        Returns:
            bool: 接続が正常かどうか
        """
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    @staticmethod
    def reconnect_with_retry(db, max_retries: int = 3, retry_delay: float = 1.0) -> bool:
        """
        データベース再接続をリトライ付きで実行
        
        Args:
            db: SQLAlchemyデータベースインスタンス
            max_retries (int): 最大リトライ回数
            retry_delay (float): リトライ間隔（秒）
            
        Returns:
            bool: 再接続が成功したかどうか
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Database reconnection attempt {attempt + 1}/{max_retries}")
                
                # 既存の接続をクリーンアップ
                try:
                    db.session.rollback()
                    db.session.close()
                except:
                    pass
                
                # 新しい接続をテスト
                if DatabaseConnectionManager.check_connection(db):
                    logger.info("Database reconnection successful")
                    return True
                
            except Exception as e:
                logger.error(f"Database reconnection attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数バックオフ
        
        logger.error("Database reconnection failed after all attempts")
        return False


def create_error_handlers(app):
    """
    Flaskアプリケーションにエラーハンドラーを登録
    
    Args:
        app: Flaskアプリケーションインスタンス
    """
    
    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(error):
        """SQLAlchemyエラーハンドラー"""
        user_id = getattr(request, 'user_id', None)
        operation = getattr(request, 'operation', None)
        
        response_data, status_code = DistributedServiceErrorHandler.handle_database_error(
            error=error,
            user_id=user_id,
            operation=operation,
            context={'endpoint': request.endpoint, 'method': request.method}
        )
        
        return jsonify(response_data), status_code
    
    @app.errorhandler(RequestException)
    def handle_request_error(error):
        """HTTPリクエストエラーハンドラー"""
        user_id = getattr(request, 'user_id', None)
        operation = getattr(request, 'operation', None)
        
        response_data, status_code = DistributedServiceErrorHandler.handle_http_error(
            error=error,
            user_id=user_id,
            operation=operation,
            context={'endpoint': request.endpoint, 'method': request.method}
        )
        
        return jsonify(response_data), status_code
    
    @app.errorhandler(500)
    def handle_internal_server_error(error):
        """内部サーバーエラーハンドラー"""
        user_id = getattr(request, 'user_id', None)
        operation = getattr(request, 'operation', None)
        
        # 元のエラーを取得
        original_error = getattr(error, 'original_exception', error)
        
        response_data, status_code = DistributedServiceErrorHandler.handle_general_error(
            error=original_error,
            user_id=user_id,
            operation=operation,
            context={'endpoint': request.endpoint, 'method': request.method}
        )
        
        return jsonify(response_data), status_code
    
    @app.errorhandler(400)
    def handle_bad_request(error):
        """不正なリクエストエラーハンドラー"""
        user_id = getattr(request, 'user_id', None)
        operation = getattr(request, 'operation', None)
        
        response_data = {
            'status': 'error',
            'error_type': 'bad_request',
            'error_category': 'client_error',
            'message': '不正なリクエストです',
            'user_id': user_id,
            'operation': operation,
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'distributed-service'
        }
        
        # New Relicに報告
        newrelic.agent.add_custom_attribute('error_type', 'bad_request')
        if user_id:
            newrelic.agent.add_custom_attribute('user_id', user_id)
        if operation:
            newrelic.agent.add_custom_attribute('operation_type', operation)
        
        logger.warning(f"Bad request: {request.url}, User: {user_id}, Operation: {operation}")
        
        return jsonify(response_data), 400
    
    logger.info("Error handlers registered successfully")