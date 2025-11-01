"""
New Relic統合ユーティリティ
Custom Attributeの設定と分散トレーシングヘッダーの処理
エラー報告機能の強化版
"""

import newrelic.agent
from flask import request
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


def set_user_custom_attribute(user_id: Optional[Union[int, str]]):
    """
    userIdをCustom AttributeとしてNew Relicに設定
    
    Args:
        user_id (Optional[Union[int, str]]): ユーザーID
    """
    try:
        if user_id is not None:
            # ユーザーIDを文字列として設定（New Relicの推奨）
            user_id_str = str(user_id)
            newrelic.agent.add_custom_attribute('user_id', user_id_str)
            newrelic.agent.add_custom_attribute('enduser.id', user_id_str)
            newrelic.agent.add_custom_attribute('service_name', 'distributed-service')
            logger.debug(f"Custom attribute set: user_id={user_id_str}")
    except Exception as e:
        logger.error(f"Failed to set user custom attribute: {e}")


def set_operation_custom_attribute(operation_type: str):
    """
    操作タイプをCustom AttributeとしてNew Relicに設定
    
    Args:
        operation_type (str): 操作タイプ（n_plus_one, slow_query, database_error等）
    """
    try:
        if operation_type:
            newrelic.agent.add_custom_attribute('operation_type', operation_type)
            newrelic.agent.add_custom_attribute('operation_name', operation_type)
            logger.debug(f"Custom attribute set: operation_type={operation_type}")
    except Exception as e:
        logger.error(f"Failed to set operation custom attribute: {e}")


def set_performance_attributes(
    execution_time: Optional[float] = None,
    query_count: Optional[int] = None,
    record_count: Optional[int] = None,
    additional_attributes: Optional[Dict[str, Any]] = None
):
    """
    パフォーマンス関連のCustom Attributeを設定
    
    Args:
        execution_time (Optional[float]): 実行時間（秒）
        query_count (Optional[int]): クエリ実行回数
        record_count (Optional[int]): 処理レコード数
        additional_attributes (Optional[Dict[str, Any]]): 追加属性
    """
    try:
        if execution_time is not None:
            newrelic.agent.add_custom_attribute('execution_time_seconds', execution_time)
            newrelic.agent.add_custom_attribute('performance.execution_time', execution_time)
        
        if query_count is not None:
            newrelic.agent.add_custom_attribute('query_count', query_count)
            newrelic.agent.add_custom_attribute('database.query_count', query_count)
        
        if record_count is not None:
            newrelic.agent.add_custom_attribute('record_count', record_count)
            newrelic.agent.add_custom_attribute('database.record_count', record_count)
        
        if additional_attributes:
            for key, value in additional_attributes.items():
                try:
                    # New Relicは特定の型のみサポートするため適切に変換
                    if isinstance(value, (str, int, float, bool)):
                        newrelic.agent.add_custom_attribute(key, value)
                    else:
                        newrelic.agent.add_custom_attribute(key, str(value))
                except Exception as attr_error:
                    logger.warning(f"Failed to set custom attribute {key}: {attr_error}")
        
        logger.debug("Performance attributes set successfully")
    except Exception as e:
        logger.error(f"Failed to set performance attributes: {e}")


def process_distributed_trace_headers():
    """
    分散トレーシングヘッダーを処理
    
    Returns:
        bool: ヘッダー処理の成功/失敗
    """
    try:
        # リクエストヘッダーから分散トレーシング情報を受け入れ
        if request and request.headers:
            newrelic.agent.accept_distributed_trace_headers(request.headers)
            
            # リクエスト情報もCustom Attributeとして設定
            newrelic.agent.add_custom_attribute('request.method', request.method)
            newrelic.agent.add_custom_attribute('request.url', request.url)
            newrelic.agent.add_custom_attribute('request.remote_addr', request.remote_addr)
            
            # User-Agentがあれば設定
            user_agent = request.headers.get('User-Agent')
            if user_agent:
                newrelic.agent.add_custom_attribute('request.user_agent', user_agent[:200])  # 長さ制限
            
            logger.debug("Distributed trace headers processed successfully")
            return True
        else:
            logger.warning("No request context available for distributed trace headers")
            return False
    except Exception as e:
        logger.error(f"Failed to process distributed trace headers: {e}")
        return False


def report_error_to_newrelic(
    error: Exception, 
    user_id: Optional[Union[int, str]] = None, 
    operation_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    error_category: Optional[str] = None
):
    """
    エラーをNew Relicに報告（強化版）
    
    Args:
        error (Exception): 報告するエラー
        user_id (Optional[Union[int, str]]): ユーザーID
        operation_type (Optional[str]): 操作タイプ
        context (Optional[Dict[str, Any]]): エラーコンテキスト
        error_category (Optional[str]): エラーカテゴリ
    """
    try:
        # 基本的なエラー情報をCustom Attributeとして設定
        newrelic.agent.add_custom_attribute('error.type', type(error).__name__)
        newrelic.agent.add_custom_attribute('error.message', str(error))
        newrelic.agent.add_custom_attribute('error.timestamp', datetime.utcnow().isoformat())
        newrelic.agent.add_custom_attribute('service_name', 'distributed-service')
        
        # ユーザーIDを設定
        if user_id is not None:
            user_id_str = str(user_id)
            newrelic.agent.add_custom_attribute('error.user_id', user_id_str)
            newrelic.agent.add_custom_attribute('user_id', user_id_str)
            newrelic.agent.add_custom_attribute('enduser.id', user_id_str)
        
        # 操作タイプを設定
        if operation_type:
            newrelic.agent.add_custom_attribute('error.operation_type', operation_type)
            newrelic.agent.add_custom_attribute('operation_type', operation_type)
        
        # エラーカテゴリを設定
        if error_category:
            newrelic.agent.add_custom_attribute('error.category', error_category)
        
        # コンテキスト情報を設定
        if context:
            for key, value in context.items():
                try:
                    attr_key = f"error.context.{key}"
                    if isinstance(value, (str, int, float, bool)):
                        newrelic.agent.add_custom_attribute(attr_key, value)
                    else:
                        newrelic.agent.add_custom_attribute(attr_key, str(value)[:500])  # 長さ制限
                except Exception as attr_error:
                    logger.warning(f"Failed to set error context attribute {key}: {attr_error}")
        
        # リクエスト情報を設定（利用可能な場合）
        try:
            if request:
                newrelic.agent.add_custom_attribute('error.request.method', request.method)
                newrelic.agent.add_custom_attribute('error.request.url', request.url)
                newrelic.agent.add_custom_attribute('error.request.remote_addr', request.remote_addr)
                
                # リクエストボディのサイズ
                content_length = request.headers.get('Content-Length')
                if content_length:
                    newrelic.agent.add_custom_attribute('error.request.content_length', int(content_length))
        except Exception:
            pass  # リクエストコンテキストが利用できない場合は無視
        
        # スタックトレース情報を設定（制限付き）
        try:
            stack_trace = traceback.format_exc()
            if stack_trace and stack_trace != 'NoneType: None\n':
                # スタックトレースを短縮（New Relicの制限を考慮）
                short_trace = stack_trace[:1000] + '...' if len(stack_trace) > 1000 else stack_trace
                newrelic.agent.add_custom_attribute('error.stack_trace', short_trace)
        except Exception:
            pass
        
        # エラーをNew Relicに記録
        newrelic.agent.notice_error()
        
        logger.info(
            f"Error reported to New Relic - Type: {type(error).__name__}, "
            f"User: {user_id}, Operation: {operation_type}, Category: {error_category}"
        )
        
    except Exception as nr_error:
        logger.error(f"Failed to report error to New Relic: {nr_error}")


def create_distributed_trace_headers():
    """
    分散トレーシング用のヘッダーを作成
    
    Returns:
        Dict[str, str]: 分散トレーシングヘッダー
    """
    try:
        headers = {}
        newrelic.agent.insert_distributed_trace_headers(headers)
        
        # 作成されたヘッダーをログ出力（デバッグ用）
        logger.debug(f"Distributed trace headers created: {list(headers.keys())}")
        
        return headers
    except Exception as e:
        logger.error(f"Failed to create distributed trace headers: {e}")
        return {}


def record_custom_event(
    event_type: str,
    attributes: Dict[str, Any],
    user_id: Optional[Union[int, str]] = None
):
    """
    カスタムイベントをNew Relicに記録
    
    Args:
        event_type (str): イベントタイプ
        attributes (Dict[str, Any]): イベント属性
        user_id (Optional[Union[int, str]]): ユーザーID
    """
    try:
        # 基本属性を追加
        event_attributes = {
            'service_name': 'distributed-service',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # ユーザーIDを追加
        if user_id is not None:
            event_attributes['user_id'] = str(user_id)
        
        # 提供された属性を追加
        for key, value in attributes.items():
            if isinstance(value, (str, int, float, bool)):
                event_attributes[key] = value
            else:
                event_attributes[key] = str(value)
        
        # カスタムイベントを記録
        newrelic.agent.record_custom_event(event_type, event_attributes)
        
        logger.debug(f"Custom event recorded: {event_type}")
        
    except Exception as e:
        logger.error(f"Failed to record custom event: {e}")


def record_metric(name: str, value: Union[int, float], unit: Optional[str] = None):
    """
    カスタムメトリクスをNew Relicに記録
    
    Args:
        name (str): メトリクス名
        value (Union[int, float]): メトリクス値
        unit (Optional[str]): 単位
    """
    try:
        # メトリクス名にサービス名を含める
        metric_name = f"Custom/DistributedService/{name}"
        
        if unit:
            metric_name += f"[{unit}]"
        
        newrelic.agent.record_custom_metric(metric_name, value)
        
        logger.debug(f"Custom metric recorded: {metric_name} = {value}")
        
    except Exception as e:
        logger.error(f"Failed to record custom metric: {e}")


def start_background_task(name: str):
    """
    バックグラウンドタスクを開始
    
    Args:
        name (str): タスク名
        
    Returns:
        New Relicバックグラウンドタスクオブジェクト
    """
    try:
        task_name = f"DistributedService/{name}"
        return newrelic.agent.background_task(name=task_name)
    except Exception as e:
        logger.error(f"Failed to start background task: {e}")
        return None