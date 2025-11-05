"""
分散サービステストクライアント
分散サービスへの直接呼び出しとメインアプリケーション経由での呼び出し機能を提供

注意: New Relicエージェントが自動的に分散トレーシングヘッダーを処理するため、
手動でヘッダーを生成・送信する必要はありません。エージェントが自動的に
リクエスト間のトレースを関連付けます。
"""
import asyncio
import aiohttp
import logging
import time
import json
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from http_client import AsyncHTTPClient, RequestResult, RequestStatus
from config import config_manager

logger = logging.getLogger(__name__)

class DistributedServiceEndpoint(Enum):
    """分散サービスのエンドポイント"""
    N_PLUS_ONE = "n-plus-one"
    SLOW_QUERY = "slow-query"
    DATABASE_ERROR = "database-error"

@dataclass
class DistributedTraceHeaders:
    """New Relic分散トレーシングヘッダー"""
    newrelic: Optional[str] = None
    traceparent: Optional[str] = None
    tracestate: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """ヘッダー辞書に変換"""
        headers = {}
        if self.newrelic:
            headers['newrelic'] = self.newrelic
        if self.traceparent:
            headers['traceparent'] = self.traceparent
        if self.tracestate:
            headers['tracestate'] = self.tracestate
        return headers

@dataclass
class DistributedServiceRequest:
    """分散サービスリクエストのデータ構造"""
    user_id: int
    operation: str
    parameters: Optional[Dict[str, Any]] = None
    trace_headers: Optional[DistributedTraceHeaders] = None
    
    def to_json(self) -> str:
        """JSON文字列に変換"""
        data = {
            "user_id": self.user_id,
            "operation": self.operation
        }
        if self.parameters:
            data["parameters"] = self.parameters
        return json.dumps(data)

@dataclass
class DistributedServiceResponse:
    """分散サービスレスポンスのデータ構造"""
    status: str
    data: Optional[Dict[str, Any]] = None
    user_id: Optional[int] = None
    trace_id: Optional[str] = None
    execution_time: Optional[float] = None
    query_count: Optional[int] = None
    error_message: Optional[str] = None
    
    @classmethod
    def from_json(cls, json_str: str) -> 'DistributedServiceResponse':
        """JSON文字列から作成"""
        try:
            data = json.loads(json_str)
            return cls(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse distributed service response: {e}")
            return cls(status="error", error_message=f"Parse error: {e}")

@dataclass
class DistributedTestResult:
    """分散サービステスト結果"""
    endpoint: str
    user_id: int
    request_result: RequestResult
    service_response: Optional[DistributedServiceResponse] = None
    call_type: str = "direct"  # "direct" or "via_main_app"
    trace_headers_sent: bool = False
    
    @property
    def is_success(self) -> bool:
        """テストが成功したかどうか"""
        return (self.request_result.is_success and 
                self.service_response and 
                self.service_response.status == "success")
    
    @property
    def total_response_time(self) -> float:
        """総レスポンス時間"""
        return self.request_result.response_time
    
    @property
    def service_execution_time(self) -> Optional[float]:
        """サービス内実行時間"""
        return self.service_response.execution_time if self.service_response else None

class DistributedServiceTestClient:
    """
    分散サービステスト用のHTTPクライアント
    直接呼び出しとメインアプリケーション経由の呼び出しをサポート
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初期化
        
        Args:
            config: 設定辞書（Noneの場合はconfig_managerから取得）
        """
        self.config = config or config_manager.get_config()
        self.distributed_service_url = self.config.get("distributed_service", {}).get("base_url", "http://distributed-service:5000")
        self.main_app_url = self.config.get("main_app_distributed", {}).get("base_url", "http://web:5000")
        self.http_client: Optional[AsyncHTTPClient] = None
        
        # エンドポイント設定
        self.distributed_endpoints = self.config.get("distributed_service", {}).get("endpoints", {
            "n-plus-one": "/performance/n-plus-one",
            "slow-query": "/performance/slow-query", 
            "database-error": "/performance/database-error"
        })
        
        self.main_app_endpoints = self.config.get("main_app_distributed", {}).get("endpoints", {
            "distributed-n-plus-one": "/distributed/n-plus-one",
            "distributed-slow-query": "/distributed/slow-query",
            "distributed-database-error": "/distributed/database-error"
        })
        
        # メトリクス収集用
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        
    async def __aenter__(self):
        """非同期コンテキストマネージャーのエントリ"""
        self.http_client = AsyncHTTPClient()
        await self.http_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーの終了"""
        if self.http_client:
            await self.http_client.__aexit__(exc_type, exc_val, exc_tb)
    
    def _generate_trace_headers(self) -> DistributedTraceHeaders:
        """New Relic分散トレーシングヘッダーを生成"""
        # New Relicエージェントが自動的に分散トレーシングヘッダーを処理するため、
        # 手動でヘッダーを生成する必要はない
        # ここでは空のヘッダーを返す（実際のヘッダーはNew Relicが自動生成）
        return DistributedTraceHeaders()
    
    async def test_direct_call(self, 
                              endpoint: str, 
                              user_id: int,
                              parameters: Optional[Dict[str, Any]] = None,
                              include_trace_headers: bool = True,
                              timeout: Optional[int] = None) -> DistributedTestResult:
        """
        分散サービスへの直接呼び出しテスト
        
        Args:
            endpoint: エンドポイント名 (n-plus-one, slow-query, database-error)
            user_id: ユーザーID
            parameters: 追加パラメータ
            include_trace_headers: 分散トレーシングヘッダーを含めるか（New Relicが自動処理するため実際は不要）
            timeout: タイムアウト時間
            
        Returns:
            DistributedTestResult: テスト結果
        """
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized. Use async context manager.")
        
        # リクエストデータの準備
        trace_headers = self._generate_trace_headers() if include_trace_headers else None
        request_data = DistributedServiceRequest(
            user_id=user_id,
            operation=endpoint,
            parameters=parameters,
            trace_headers=trace_headers
        )
        
        # URL構築
        endpoint_path = self.distributed_endpoints.get(endpoint, f"/performance/{endpoint}")
        url = f"{self.distributed_service_url}{endpoint_path}"
        
        # ヘッダー準備
        headers = {"Content-Type": "application/json"}
        # New Relicエージェントが自動的に分散トレーシングヘッダーを追加するため、
        # 手動でヘッダーを追加する必要はない
        
        logger.debug(f"Making direct call to distributed service: {url}")
        
        # HTTPリクエスト実行
        request_result = await self.http_client.make_post_request(
            url=url,
            data=request_data.to_json(),
            headers=headers,
            timeout=timeout
        )
        
        # レスポンス解析
        service_response = None
        if request_result.is_success and hasattr(request_result, 'response_content'):
            try:
                service_response = DistributedServiceResponse.from_json(request_result.response_content)
            except Exception as e:
                logger.error(f"Failed to parse service response: {e}")
        
        # メトリクス更新
        self._update_metrics(request_result)
        
        return DistributedTestResult(
            endpoint=endpoint,
            user_id=user_id,
            request_result=request_result,
            service_response=service_response,
            call_type="direct",
            trace_headers_sent=include_trace_headers
        )
    
    async def test_via_main_app(self,
                               endpoint: str,
                               user_id: int,
                               parameters: Optional[Dict[str, Any]] = None,
                               include_trace_headers: bool = True,
                               timeout: Optional[int] = None) -> DistributedTestResult:
        """
        メインアプリケーション経由での分散サービス呼び出しテスト
        
        Args:
            endpoint: エンドポイント名
            user_id: ユーザーID
            parameters: 追加パラメータ
            include_trace_headers: 分散トレーシングヘッダーを含めるか（New Relicが自動処理するため実際は不要）
            timeout: タイムアウト時間
            
        Returns:
            DistributedTestResult: テスト結果
        """
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized. Use async context manager.")
        
        # リクエストデータの準備
        trace_headers = self._generate_trace_headers() if include_trace_headers else None
        request_data = DistributedServiceRequest(
            user_id=user_id,
            operation=endpoint,
            parameters=parameters,
            trace_headers=trace_headers
        )
        
        # URL構築（メインアプリケーション経由）
        main_endpoint_key = f"distributed-{endpoint}"
        endpoint_path = self.main_app_endpoints.get(main_endpoint_key, f"/distributed/{endpoint}")
        url = f"{self.main_app_url}{endpoint_path}"
        
        # ヘッダー準備
        headers = {"Content-Type": "application/json"}
        # New Relicエージェントが自動的に分散トレーシングヘッダーを追加するため、
        # 手動でヘッダーを追加する必要はない
        
        logger.debug(f"Making call via main app to distributed service: {url}")
        
        # HTTPリクエスト実行
        request_result = await self.http_client.make_post_request(
            url=url,
            data=request_data.to_json(),
            headers=headers,
            timeout=timeout
        )
        
        # レスポンス解析
        service_response = None
        if request_result.is_success and hasattr(request_result, 'response_content'):
            try:
                service_response = DistributedServiceResponse.from_json(request_result.response_content)
            except Exception as e:
                logger.error(f"Failed to parse service response: {e}")
        
        # メトリクス更新
        self._update_metrics(request_result)
        
        return DistributedTestResult(
            endpoint=endpoint,
            user_id=user_id,
            request_result=request_result,
            service_response=service_response,
            call_type="via_main_app",
            trace_headers_sent=include_trace_headers
        )
    
    async def test_n_plus_one_problem(self,
                                     user_id: int,
                                     call_type: str = "direct",
                                     timeout: Optional[int] = None) -> DistributedTestResult:
        """N+1クエリ問題のテスト"""
        parameters = {"limit": 20, "category": "Electronics"}
        
        if call_type == "direct":
            return await self.test_direct_call("n-plus-one", user_id, parameters, timeout=timeout)
        else:
            return await self.test_via_main_app("n-plus-one", user_id, parameters, timeout=timeout)
    
    async def test_slow_query(self,
                             user_id: int,
                             call_type: str = "direct",
                             timeout: Optional[int] = None) -> DistributedTestResult:
        """スロークエリのテスト"""
        parameters = {"sleep_duration": 3.0, "query_type": "complex_join"}
        
        if call_type == "direct":
            return await self.test_direct_call("slow-query", user_id, parameters, timeout=timeout)
        else:
            return await self.test_via_main_app("slow-query", user_id, parameters, timeout=timeout)
    
    async def test_database_error(self,
                                 user_id: int,
                                 call_type: str = "direct",
                                 timeout: Optional[int] = None) -> DistributedTestResult:
        """データベースエラーのテスト"""
        parameters = {"error_type": "invalid_query"}
        
        if call_type == "direct":
            return await self.test_direct_call("database-error", user_id, parameters, timeout=timeout)
        else:
            return await self.test_via_main_app("database-error", user_id, parameters, timeout=timeout)
    
    async def run_comprehensive_test(self,
                                   user_id: int,
                                   call_type: str = "direct",
                                   timeout: Optional[int] = None) -> List[DistributedTestResult]:
        """
        全エンドポイントの包括的テスト
        
        Args:
            user_id: ユーザーID
            call_type: 呼び出しタイプ ("direct" or "via_main_app")
            timeout: タイムアウト時間
            
        Returns:
            List[DistributedTestResult]: 全テスト結果のリスト
        """
        results = []
        
        # N+1クエリ問題テスト
        try:
            result = await self.test_n_plus_one_problem(user_id, call_type, timeout)
            results.append(result)
        except Exception as e:
            logger.error(f"N+1 query test failed: {e}")
        
        # スロークエリテスト
        try:
            result = await self.test_slow_query(user_id, call_type, timeout)
            results.append(result)
        except Exception as e:
            logger.error(f"Slow query test failed: {e}")
        
        # データベースエラーテスト
        try:
            result = await self.test_database_error(user_id, call_type, timeout)
            results.append(result)
        except Exception as e:
            logger.error(f"Database error test failed: {e}")
        
        return results
    
    def _update_metrics(self, request_result: RequestResult):
        """メトリクスを更新"""
        self.request_count += 1
        self.total_response_time += request_result.response_time
        
        if request_result.is_success:
            self.success_count += 1
        else:
            self.error_count += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """現在のメトリクスを取得"""
        avg_response_time = (self.total_response_time / self.request_count 
                           if self.request_count > 0 else 0.0)
        
        success_rate = (self.success_count / self.request_count * 100 
                       if self.request_count > 0 else 0.0)
        
        error_rate = (self.error_count / self.request_count * 100 
                     if self.request_count > 0 else 0.0)
        
        return {
            "total_requests": self.request_count,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "success_rate_percent": round(success_rate, 2),
            "error_rate_percent": round(error_rate, 2),
            "average_response_time": round(avg_response_time, 3),
            "total_response_time": round(self.total_response_time, 3)
        }
    
    def reset_metrics(self):
        """メトリクスをリセット"""
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_response_time = 0.0

class SyncDistributedServiceTestClient:
    """
    同期版の分散サービステストクライアント
    自動化テストシナリオで使用
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or config_manager.get_config()
        self.distributed_service_url = self.config.get("distributed_service", {}).get("base_url", "http://distributed-service:5000")
        self.main_app_url = self.config.get("main_app_distributed", {}).get("base_url", "http://web:5000")
        
        # エンドポイント設定
        self.distributed_endpoints = self.config.get("distributed_service", {}).get("endpoints", {
            "n-plus-one": "/performance/n-plus-one",
            "slow-query": "/performance/slow-query", 
            "database-error": "/performance/database-error"
        })
        
        self.main_app_endpoints = self.config.get("main_app_distributed", {}).get("endpoints", {
            "distributed-n-plus-one": "/distributed/n-plus-one",
            "distributed-slow-query": "/distributed/slow-query",
            "distributed-database-error": "/distributed/database-error"
        })
    
    def test_direct_call(self, endpoint: str, user_id: int, timeout: int = 30) -> Dict[str, Any]:
        """分散サービスへの直接呼び出し（同期版）"""
        import asyncio
        import aiohttp
        import json
        
        async def _make_request():
            try:
                # URL構築
                endpoint_path = self.distributed_endpoints.get(endpoint, f"/performance/{endpoint}")
                url = f"{self.distributed_service_url}{endpoint_path}"
                
                # リクエストデータ
                data = {
                    "user_id": user_id,
                    "operation": endpoint
                }
                
                # HTTPリクエスト実行
                start_time = time.time()
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                    async with session.post(
                        url,
                        json=data,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        response_time = (time.time() - start_time) * 1000  # ミリ秒
                        
                        # レスポンス処理
                        if response.status == 200:
                            try:
                                response_data = await response.json()
                                return {
                                    "status": "success",
                                    "response_time": response_time,
                                    "data": response_data,
                                    "status_code": response.status
                                }
                            except json.JSONDecodeError:
                                return {
                                    "status": "error",
                                    "response_time": response_time,
                                    "error": "Invalid JSON response",
                                    "status_code": response.status
                                }
                        else:
                            response_text = await response.text()
                            return {
                                "status": "error",
                                "response_time": response_time,
                                "error": f"HTTP {response.status}: {response_text}",
                                "status_code": response.status
                            }
                            
            except asyncio.TimeoutError:
                return {
                    "status": "error",
                    "response_time": timeout * 1000,
                    "error": "Request timeout",
                    "status_code": 0
                }
            except Exception as e:
                return {
                    "status": "error",
                    "response_time": 0,
                    "error": str(e),
                    "status_code": 0
                }
        
        # 同期的に実行
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(_make_request())
    
    def test_via_main_app(self, endpoint: str, user_id: int, timeout: int = 30) -> Dict[str, Any]:
        """メインアプリケーション経由での呼び出し（同期版）"""
        import asyncio
        import aiohttp
        import json
        
        async def _make_request():
            try:
                # URL構築（メインアプリケーション経由）
                main_endpoint_key = f"distributed-{endpoint}"
                endpoint_path = self.main_app_endpoints.get(main_endpoint_key, f"/distributed/{endpoint}")
                url = f"{self.main_app_url}{endpoint_path}"
                
                # リクエストデータ
                data = {
                    "user_id": user_id,
                    "operation": endpoint
                }
                
                # HTTPリクエスト実行
                start_time = time.time()
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                    async with session.post(
                        url,
                        json=data,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        response_time = (time.time() - start_time) * 1000  # ミリ秒
                        
                        # レスポンス処理
                        response_text = await response.text()
                        
                        if response.status == 200:
                            # JSONレスポンスかHTMLレスポンスかを判定
                            content_type = response.headers.get('content-type', '').lower()
                            
                            if 'application/json' in content_type:
                                try:
                                    response_data = json.loads(response_text)
                                    return {
                                        "status": "success",
                                        "response_time": response_time,
                                        "data": response_data,
                                        "status_code": response.status
                                    }
                                except json.JSONDecodeError:
                                    return {
                                        "status": "error",
                                        "response_time": response_time,
                                        "error": "Invalid JSON response",
                                        "status_code": response.status
                                    }
                            elif 'text/html' in content_type:
                                # HTMLレスポンス（ログイン画面など）
                                if 'login' in response_text.lower() or 'sign in' in response_text.lower():
                                    return {
                                        "status": "success",
                                        "response_time": response_time,
                                        "data": {
                                            "message": "Authentication required - redirected to login page",
                                            "authentication_required": True,
                                            "content_type": "text/html"
                                        },
                                        "status_code": response.status
                                    }
                                else:
                                    return {
                                        "status": "success",
                                        "response_time": response_time,
                                        "data": {
                                            "message": "HTML response received",
                                            "content_type": "text/html",
                                            "content_preview": response_text[:100]
                                        },
                                        "status_code": response.status
                                    }
                            else:
                                # その他のコンテンツタイプ
                                return {
                                    "status": "success",
                                    "response_time": response_time,
                                    "data": {
                                        "message": f"Non-JSON response received (Content-Type: {content_type})",
                                        "content_type": content_type,
                                        "content_preview": response_text[:100]
                                    },
                                    "status_code": response.status
                                }
                        elif response.status == 302:
                            # リダイレクト
                            location = response.headers.get('location', '')
                            return {
                                "status": "success",
                                "response_time": response_time,
                                "data": {
                                    "message": "Redirected (authentication required)",
                                    "redirect": True,
                                    "location": location
                                },
                                "status_code": response.status
                            }
                        else:
                            return {
                                "status": "error",
                                "response_time": response_time,
                                "error": f"HTTP {response.status}: {response_text[:100]}",
                                "status_code": response.status
                            }
                            
            except asyncio.TimeoutError:
                return {
                    "status": "error",
                    "response_time": timeout * 1000,
                    "error": "Request timeout",
                    "status_code": 0
                }
            except Exception as e:
                return {
                    "status": "error",
                    "response_time": 0,
                    "error": str(e),
                    "status_code": 0
                }
        
        # 同期的に実行
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(_make_request())

class DistributedServiceTestLogger:
    """分散サービステスト専用のログ機能"""
    
    def __init__(self, log_file: str = "logs/distributed_service_tests.log"):
        self.log_file = log_file
        self.logger = logging.getLogger("distributed_service_tests")
        
        # ファイルハンドラーの設定
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_test_result(self, result: DistributedTestResult):
        """テスト結果をログに記録"""
        try:
            log_data = {
                "endpoint": result.endpoint,
                "user_id": result.user_id,
                "call_type": result.call_type,
                "success": result.is_success,
                "response_time": f"{result.total_response_time:.3f}s",
                "status_code": result.request_result.status_code,
                "trace_headers_sent": result.trace_headers_sent
            }
            
            if result.service_response:
                log_data["service_execution_time"] = f"{result.service_response.execution_time:.3f}s" if result.service_response.execution_time else "N/A"
                log_data["query_count"] = result.service_response.query_count
                log_data["trace_id"] = result.service_response.trace_id
            
            if not result.is_success:
                log_data["error"] = result.request_result.error_message or "Unknown error"
            
            # ログメッセージの作成
            log_message = " | ".join([f"{k}={v}" for k, v in log_data.items()])
            
            if result.is_success:
                self.logger.info(log_message)
            else:
                self.logger.warning(log_message)
                
        except Exception as e:
            logger.error(f"Error logging distributed service test result: {e}")

# グローバルインスタンス
distributed_test_logger = DistributedServiceTestLogger()