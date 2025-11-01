"""
分散サービスHTTPクライアント
メインアプリケーションから分散サービスへのHTTP呼び出し機能
"""

import requests
import logging
import time
from typing import Dict, Any, Optional
from flask import current_app
import newrelic.agent

logger = logging.getLogger(__name__)


class DistributedServiceClient:
    """分散サービスへのHTTPクライアント"""
    
    def __init__(self, base_url: str = None, timeout: int = 30):
        """
        クライアントを初期化
        
        Args:
            base_url (str): 分散サービスのベースURL
            timeout (int): リクエストタイムアウト（秒）
        """
        self.base_url = base_url or "http://distributed-service:5000"
        self.timeout = timeout
        self.session = requests.Session()
        
        # デフォルトヘッダーを設定
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Flask-EC-Main-App/1.0'
        })
        
        logger.info(f"DistributedServiceClient initialized: base_url={self.base_url}")
    
    def _create_distributed_trace_headers(self) -> Dict[str, str]:
        """
        New Relic分散トレーシングヘッダーを作成
        
        Returns:
            Dict[str, str]: 分散トレーシングヘッダー
        """
        try:
            headers = {}
            newrelic.agent.insert_distributed_trace_headers(headers)
            logger.debug(f"Distributed trace headers created: {list(headers.keys())}")
            return headers
        except Exception as e:
            logger.warning(f"Failed to create distributed trace headers: {e}")
            return {}
    
    def _set_custom_attributes(self, user_id: Optional[int], operation: str):
        """
        New RelicにCustom Attributeを設定
        
        Args:
            user_id (Optional[int]): ユーザーID
            operation (str): 操作名
        """
        try:
            if user_id:
                newrelic.agent.add_custom_attribute('user_id', user_id)
                newrelic.agent.add_custom_attribute('enduser.id', str(user_id))
            
            newrelic.agent.add_custom_attribute('distributed_call', True)
            newrelic.agent.add_custom_attribute('operation_type', operation)
            newrelic.agent.add_custom_attribute('service_name', 'main-app')
            newrelic.agent.add_custom_attribute('target_service', 'distributed-service')
            
            logger.debug(f"Custom attributes set: user_id={user_id}, operation={operation}")
        except Exception as e:
            logger.warning(f"Failed to set custom attributes: {e}")
    
    @newrelic.agent.function_trace()
    def call_performance_endpoint(
        self, 
        user_id: int, 
        operation: str, 
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        分散サービスのパフォーマンスエンドポイントを呼び出し
        
        Args:
            user_id (int): ユーザーID
            operation (str): 操作タイプ（n-plus-one, slow-query, database-error）
            parameters (Optional[Dict[str, Any]]): 追加パラメータ
            
        Returns:
            Dict[str, Any]: レスポンスデータ
            
        Raises:
            DistributedServiceError: 分散サービス呼び出しエラー
        """
        start_time = time.time()
        
        # Custom Attributeを設定
        self._set_custom_attributes(user_id, operation)
        
        # リクエストデータを準備
        request_data = {
            'user_id': user_id
        }
        if parameters:
            request_data.update(parameters)
        
        # 分散トレーシングヘッダーを作成
        trace_headers = self._create_distributed_trace_headers()
        
        # エンドポイントURLを構築
        endpoint_url = f"{self.base_url}/performance/{operation}"
        
        logger.info(f"Calling distributed service: {endpoint_url}, user_id={user_id}")
        
        try:
            # HTTPリクエストを送信
            response = self.session.post(
                endpoint_url,
                json=request_data,
                headers=trace_headers,
                timeout=self.timeout
            )
            
            execution_time = time.time() - start_time
            
            # レスポンスステータスをチェック
            if response.status_code == 200:
                response_data = response.json()
                
                # 成功時のログとメトリクス
                logger.info(
                    f"Distributed service call successful: "
                    f"operation={operation}, user_id={user_id}, "
                    f"execution_time={execution_time:.3f}s"
                )
                
                # New RelicにCustom Attributeを追加
                newrelic.agent.add_custom_attribute('http_status_code', response.status_code)
                newrelic.agent.add_custom_attribute('execution_time_seconds', execution_time)
                newrelic.agent.add_custom_attribute('distributed_call_success', True)
                
                return {
                    'status': 'success',
                    'data': response_data,
                    'execution_time': execution_time,
                    'http_status': response.status_code
                }
            
            else:
                # エラーレスポンスの処理
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    error_data = {'error': response.text}
                
                logger.error(
                    f"Distributed service call failed: "
                    f"status={response.status_code}, operation={operation}, "
                    f"user_id={user_id}, execution_time={execution_time:.3f}s"
                )
                
                # New RelicにエラーAttributeを追加
                newrelic.agent.add_custom_attribute('http_status_code', response.status_code)
                newrelic.agent.add_custom_attribute('execution_time_seconds', execution_time)
                newrelic.agent.add_custom_attribute('distributed_call_success', False)
                newrelic.agent.add_custom_attribute('error_response', str(error_data))
                
                raise DistributedServiceError(
                    f"HTTP {response.status_code}: {error_data.get('error', 'Unknown error')}",
                    status_code=response.status_code,
                    response_data=error_data
                )
        
        except requests.exceptions.Timeout:
            execution_time = time.time() - start_time
            error_msg = f"Timeout calling distributed service: {endpoint_url}"
            logger.error(f"{error_msg}, execution_time={execution_time:.3f}s")
            
            # New RelicにタイムアウトAttributeを追加
            newrelic.agent.add_custom_attribute('execution_time_seconds', execution_time)
            newrelic.agent.add_custom_attribute('distributed_call_success', False)
            newrelic.agent.add_custom_attribute('error_type', 'timeout')
            newrelic.agent.add_custom_attribute('error_category', 'http_timeout')
            newrelic.agent.add_custom_attribute('target_url', endpoint_url)
            
            # エラーをNew Relicに報告
            newrelic.agent.notice_error()
            
            raise DistributedServiceError(error_msg, error_type='timeout')
        
        except requests.exceptions.ConnectionError as conn_err:
            execution_time = time.time() - start_time
            error_msg = f"Connection error calling distributed service: {endpoint_url}"
            logger.error(f"{error_msg}, execution_time={execution_time:.3f}s, details: {str(conn_err)}")
            
            # New Relicに接続エラーAttributeを追加
            newrelic.agent.add_custom_attribute('execution_time_seconds', execution_time)
            newrelic.agent.add_custom_attribute('distributed_call_success', False)
            newrelic.agent.add_custom_attribute('error_type', 'connection_error')
            newrelic.agent.add_custom_attribute('error_category', 'http_connection')
            newrelic.agent.add_custom_attribute('target_url', endpoint_url)
            newrelic.agent.add_custom_attribute('connection_error_details', str(conn_err)[:500])
            
            # エラーをNew Relicに報告
            newrelic.agent.notice_error()
            
            raise DistributedServiceError(error_msg, error_type='connection_error', original_error=conn_err)
        
        except requests.exceptions.RequestException as req_err:
            execution_time = time.time() - start_time
            error_msg = f"HTTP request error calling distributed service: {str(req_err)}"
            logger.error(f"{error_msg}, execution_time={execution_time:.3f}s")
            
            # New RelicにHTTPリクエストエラーAttributeを追加
            newrelic.agent.add_custom_attribute('execution_time_seconds', execution_time)
            newrelic.agent.add_custom_attribute('distributed_call_success', False)
            newrelic.agent.add_custom_attribute('error_type', 'http_request_error')
            newrelic.agent.add_custom_attribute('error_category', 'http_request')
            newrelic.agent.add_custom_attribute('target_url', endpoint_url)
            newrelic.agent.add_custom_attribute('request_error_details', str(req_err)[:500])
            
            # エラーをNew Relicに報告
            newrelic.agent.notice_error()
            
            raise DistributedServiceError(error_msg, error_type='http_request_error', original_error=req_err)
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Unexpected error calling distributed service: {str(e)}"
            logger.error(f"{error_msg}, execution_time={execution_time:.3f}s")
            
            # New Relicに予期しないエラーAttributeを追加
            newrelic.agent.add_custom_attribute('execution_time_seconds', execution_time)
            newrelic.agent.add_custom_attribute('distributed_call_success', False)
            newrelic.agent.add_custom_attribute('error_type', 'unexpected_error')
            newrelic.agent.add_custom_attribute('error_category', 'general_error')
            newrelic.agent.add_custom_attribute('error_message', str(e)[:500])
            newrelic.agent.add_custom_attribute('target_url', endpoint_url)
            newrelic.agent.add_custom_attribute('exception_type', type(e).__name__)
            
            # エラーをNew Relicに報告
            newrelic.agent.notice_error()
            
            raise DistributedServiceError(error_msg, error_type='unexpected_error', original_error=e)
    
    @newrelic.agent.function_trace()
    def call_n_plus_one(self, user_id: int, limit: int = 20) -> Dict[str, Any]:
        """
        N+1クエリ問題のエンドポイントを呼び出し
        
        Args:
            user_id (int): ユーザーID
            limit (int): 取得する商品数の上限
            
        Returns:
            Dict[str, Any]: レスポンスデータ
        """
        return self.call_performance_endpoint(
            user_id=user_id,
            operation='n-plus-one',
            parameters={'limit': limit}
        )
    
    @newrelic.agent.function_trace()
    def call_slow_query(
        self, 
        user_id: int, 
        sleep_duration: float = 3.0, 
        query_type: str = 'sleep'
    ) -> Dict[str, Any]:
        """
        スロークエリのエンドポイントを呼び出し
        
        Args:
            user_id (int): ユーザーID
            sleep_duration (float): スリープ時間（秒）
            query_type (str): クエリタイプ（sleep, complex_join, cartesian_product）
            
        Returns:
            Dict[str, Any]: レスポンスデータ
        """
        return self.call_performance_endpoint(
            user_id=user_id,
            operation='slow-query',
            parameters={
                'sleep_duration': sleep_duration,
                'query_type': query_type
            }
        )
    
    @newrelic.agent.function_trace()
    def call_database_error(self, user_id: int, error_type: str = 'syntax') -> Dict[str, Any]:
        """
        データベースエラーのエンドポイントを呼び出し
        
        Args:
            user_id (int): ユーザーID
            error_type (str): エラータイプ（syntax, constraint, connection, timeout）
            
        Returns:
            Dict[str, Any]: レスポンスデータ
        """
        return self.call_performance_endpoint(
            user_id=user_id,
            operation='database-error',
            parameters={'error_type': error_type}
        )
    
    @newrelic.agent.function_trace()
    def call_test_all(self, user_id: int) -> Dict[str, Any]:
        """
        全パフォーマンステストのエンドポイントを呼び出し
        
        Args:
            user_id (int): ユーザーID
            
        Returns:
            Dict[str, Any]: レスポンスデータ
        """
        return self.call_performance_endpoint(
            user_id=user_id,
            operation='test-all'
        )
    
    def health_check(self) -> bool:
        """
        分散サービスのヘルスチェック
        
        Returns:
            bool: サービスが利用可能かどうか
        """
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=5
            )
            is_healthy = response.status_code == 200
            
            logger.info(f"Distributed service health check: {'OK' if is_healthy else 'FAILED'}")
            return is_healthy
            
        except Exception as e:
            logger.error(f"Distributed service health check failed: {e}")
            return False


class DistributedServiceError(Exception):
    """分散サービス呼び出しエラー"""
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        response_data: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.response_data = response_data
        self.original_error = original_error


# グローバルクライアントインスタンス
_client_instance = None

def get_distributed_client() -> DistributedServiceClient:
    """
    分散サービスクライアントのシングルトンインスタンスを取得
    
    Returns:
        DistributedServiceClient: クライアントインスタンス
    """
    global _client_instance
    
    if _client_instance is None:
        # 設定からベースURLを取得（環境変数またはデフォルト値）
        import os
        base_url = os.getenv('DISTRIBUTED_SERVICE_URL', 'http://distributed-service:5000')
        timeout = int(os.getenv('DISTRIBUTED_SERVICE_TIMEOUT', '30'))
        
        _client_instance = DistributedServiceClient(
            base_url=base_url,
            timeout=timeout
        )
        
        logger.info(f"Created distributed service client: {base_url}")
    
    return _client_instance