"""
New Relic API連携機能
分散トレーシング、Custom Attribute、エラー追跡データの検証機能を提供
"""
import os
import time
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import requests
from dataclasses import dataclass
from config import config_manager

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TraceData:
    """分散トレーシングデータを表すクラス"""
    trace_id: str
    span_id: str
    service_name: str
    operation_name: str
    duration_ms: float
    timestamp: datetime
    custom_attributes: Dict[str, Any]
    error_count: int = 0
    error_messages: List[str] = None

    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = []

@dataclass
class PerformanceMetrics:
    """パフォーマンスメトリクスを表すクラス"""
    response_time_avg: float
    response_time_95th: float
    throughput: float
    error_rate: float
    database_query_count: int
    database_query_time: float

class NewRelicAPIClient:
    """New Relic API クライアント"""
    
    def __init__(self, api_key: str, account_id: str):
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = "https://api.newrelic.com"
        self.graphql_url = f"{self.base_url}/graphql"
        self.headers = {
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """API リクエストを実行"""
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"New Relic API request failed: {e}")
            raise
    
    def _execute_nrql_query(self, nrql_query: str) -> Dict[str, Any]:
        """NRQL クエリを実行"""
        query = {
            "query": f"""
            {{
                actor {{
                    account(id: {self.account_id}) {{
                        nrql(query: "{nrql_query}") {{
                            results
                        }}
                    }}
                }}
            }}
            """
        }
        
        response = self._make_request("POST", self.graphql_url, json=query)
        data = response.json()
        
        if "errors" in data:
            raise Exception(f"NRQL query failed: {data['errors']}")
        
        return data["data"]["actor"]["account"]["nrql"]["results"]
    
    def get_distributed_traces(self, 
                             app_names: List[str], 
                             time_range_minutes: int = 60,
                             user_id: Optional[str] = None) -> List[TraceData]:
        """分散トレーシングデータを取得"""
        since_clause = f"SINCE {time_range_minutes} minutes ago"
        app_filter = " OR ".join([f"appName = '{app}'" for app in app_names])
        
        # ベースクエリ
        base_query = f"""
        SELECT traceId, duration, timestamp, appName, name, 
               custom.user_id, custom.operation_type, custom.service_name
        FROM Span 
        WHERE ({app_filter}) 
        {since_clause}
        """
        
        # userIdフィルターを追加
        if user_id:
            base_query += f" AND custom.user_id = '{user_id}'"
        
        base_query += " LIMIT 1000"
        
        try:
            results = self._execute_nrql_query(base_query)
            traces = []
            
            for result in results:
                custom_attrs = {}
                if result.get("custom.user_id"):
                    custom_attrs["user_id"] = result["custom.user_id"]
                if result.get("custom.operation_type"):
                    custom_attrs["operation_type"] = result["custom.operation_type"]
                if result.get("custom.service_name"):
                    custom_attrs["service_name"] = result["custom.service_name"]
                
                trace = TraceData(
                    trace_id=result.get("traceId", ""),
                    span_id="",  # Spanクエリでは直接取得できない
                    service_name=result.get("appName", ""),
                    operation_name=result.get("name", ""),
                    duration_ms=result.get("duration", 0) * 1000,  # 秒からミリ秒に変換
                    timestamp=datetime.fromtimestamp(result.get("timestamp", 0) / 1000),
                    custom_attributes=custom_attrs
                )
                traces.append(trace)
            
            logger.info(f"Retrieved {len(traces)} distributed traces")
            return traces
            
        except Exception as e:
            logger.error(f"Failed to get distributed traces: {e}")
            return []
    
    def verify_custom_attributes(self, 
                               app_names: List[str], 
                               expected_user_ids: List[str],
                               time_range_minutes: int = 60) -> Dict[str, bool]:
        """Custom Attributeの設定を検証"""
        verification_results = {}
        
        for user_id in expected_user_ids:
            try:
                # 特定のuserIdでCustom Attributeが設定されているかチェック
                query = f"""
                SELECT count(*) as trace_count
                FROM Span 
                WHERE ({" OR ".join([f"appName = '{app}'" for app in app_names])})
                AND custom.user_id = '{user_id}'
                SINCE {time_range_minutes} minutes ago
                """
                
                results = self._execute_nrql_query(query)
                trace_count = results[0].get("trace_count", 0) if results else 0
                
                verification_results[user_id] = trace_count > 0
                logger.info(f"User ID {user_id}: {trace_count} traces found")
                
            except Exception as e:
                logger.error(f"Failed to verify custom attributes for user {user_id}: {e}")
                verification_results[user_id] = False
        
        return verification_results
    
    def get_error_traces(self, 
                        app_names: List[str], 
                        time_range_minutes: int = 60,
                        user_id: Optional[str] = None) -> List[TraceData]:
        """エラー追跡データを取得"""
        app_filter = " OR ".join([f"appName = '{app}'" for app in app_names])
        
        query = f"""
        SELECT traceId, duration, timestamp, appName, name, error.message,
               custom.user_id, custom.operation_type, custom.service_name
        FROM Span 
        WHERE ({app_filter}) 
        AND error IS true
        SINCE {time_range_minutes} minutes ago
        """
        
        if user_id:
            query += f" AND custom.user_id = '{user_id}'"
        
        query += " LIMIT 500"
        
        try:
            results = self._execute_nrql_query(query)
            error_traces = []
            
            for result in results:
                custom_attrs = {}
                if result.get("custom.user_id"):
                    custom_attrs["user_id"] = result["custom.user_id"]
                if result.get("custom.operation_type"):
                    custom_attrs["operation_type"] = result["custom.operation_type"]
                if result.get("custom.service_name"):
                    custom_attrs["service_name"] = result["custom.service_name"]
                
                error_messages = []
                if result.get("error.message"):
                    error_messages.append(result["error.message"])
                
                trace = TraceData(
                    trace_id=result.get("traceId", ""),
                    span_id="",
                    service_name=result.get("appName", ""),
                    operation_name=result.get("name", ""),
                    duration_ms=result.get("duration", 0) * 1000,
                    timestamp=datetime.fromtimestamp(result.get("timestamp", 0) / 1000),
                    custom_attributes=custom_attrs,
                    error_count=1,
                    error_messages=error_messages
                )
                error_traces.append(trace)
            
            logger.info(f"Retrieved {len(error_traces)} error traces")
            return error_traces
            
        except Exception as e:
            logger.error(f"Failed to get error traces: {e}")
            return []
    
    def get_performance_metrics(self, 
                              app_names: List[str], 
                              time_range_minutes: int = 60,
                              operation_name: Optional[str] = None) -> Dict[str, PerformanceMetrics]:
        """パフォーマンスメトリクスを取得"""
        metrics_by_app = {}
        
        for app_name in app_names:
            try:
                # ベースクエリ条件
                where_clause = f"appName = '{app_name}'"
                if operation_name:
                    where_clause += f" AND name LIKE '%{operation_name}%'"
                
                # レスポンス時間メトリクス
                response_time_query = f"""
                SELECT average(duration) as avg_response_time,
                       percentile(duration, 95) as p95_response_time,
                       count(*) as request_count
                FROM Span 
                WHERE {where_clause}
                SINCE {time_range_minutes} minutes ago
                """
                
                # エラー率メトリクス
                error_rate_query = f"""
                SELECT percentage(count(*), WHERE error IS true) as error_rate
                FROM Span 
                WHERE {where_clause}
                SINCE {time_range_minutes} minutes ago
                """
                
                # データベースクエリメトリクス
                db_query = f"""
                SELECT count(*) as db_query_count,
                       average(duration) as avg_db_time
                FROM Span 
                WHERE {where_clause}
                AND category = 'datastore'
                SINCE {time_range_minutes} minutes ago
                """
                
                # メトリクス取得
                response_results = self._execute_nrql_query(response_time_query)
                error_results = self._execute_nrql_query(error_rate_query)
                db_results = self._execute_nrql_query(db_query)
                
                # 結果の処理
                response_data = response_results[0] if response_results else {}
                error_data = error_results[0] if error_results else {}
                db_data = db_results[0] if db_results else {}
                
                # スループット計算（リクエスト数/分）
                request_count = response_data.get("request_count", 0)
                throughput = request_count / time_range_minutes if time_range_minutes > 0 else 0
                
                metrics = PerformanceMetrics(
                    response_time_avg=response_data.get("avg_response_time", 0) * 1000,  # ミリ秒に変換
                    response_time_95th=response_data.get("p95_response_time", 0) * 1000,
                    throughput=throughput,
                    error_rate=error_data.get("error_rate", 0),
                    database_query_count=db_data.get("db_query_count", 0),
                    database_query_time=db_data.get("avg_db_time", 0) * 1000
                )
                
                metrics_by_app[app_name] = metrics
                logger.info(f"Retrieved performance metrics for {app_name}")
                
            except Exception as e:
                logger.error(f"Failed to get performance metrics for {app_name}: {e}")
                # デフォルト値でメトリクスを作成
                metrics_by_app[app_name] = PerformanceMetrics(
                    response_time_avg=0, response_time_95th=0, throughput=0,
                    error_rate=0, database_query_count=0, database_query_time=0
                )
        
        return metrics_by_app

class NewRelicVerificationService:
    """New Relic検証サービス"""
    
    def __init__(self):
        self.config = config_manager.get_config()
        self.nr_config = self.config.get("newrelic_verification", {})
        
        # 環境変数から設定を取得
        api_key = os.getenv("NEW_RELIC_API_KEY") or self.nr_config.get("api_key", "")
        account_id = os.getenv("NEW_RELIC_ACCOUNT_ID") or self.nr_config.get("account_id", "")
        
        if not api_key or not account_id:
            logger.warning("New Relic API key or account ID not configured")
            self.client = None
        else:
            # プレースホルダーの場合は無効とする
            if api_key.startswith("${") or account_id.startswith("${"):
                logger.warning("New Relic API credentials contain placeholders")
                self.client = None
            else:
                self.client = NewRelicAPIClient(api_key, account_id)
        
        self.app_names = self.nr_config.get("app_names", [])
        self.timeout_seconds = self.nr_config.get("verification_timeout_seconds", 300)
        self.retry_attempts = self.nr_config.get("retry_attempts", 3)
        self.retry_delay = self.nr_config.get("retry_delay_seconds", 10)
    
    def is_enabled(self) -> bool:
        """New Relic検証機能が有効かどうか"""
        return (self.nr_config.get("enabled", False) and 
                self.client is not None)
    
    def verify_distributed_trace_propagation(self, 
                                           test_user_ids: List[str],
                                           wait_time_seconds: int = 60) -> Dict[str, Any]:
        """分散トレーシングヘッダー伝播の検証"""
        if not self.is_enabled():
            return {"status": "disabled", "message": "New Relic verification is disabled"}
        
        logger.info(f"Verifying distributed trace propagation for {len(test_user_ids)} users")
        
        # 少し待ってからデータを取得（New Relicのデータ遅延を考慮）
        time.sleep(wait_time_seconds)
        
        verification_results = {
            "status": "success",
            "total_users_tested": len(test_user_ids),
            "users_with_traces": 0,
            "trace_propagation_success": False,
            "details": {},
            "traces_found": []
        }
        
        try:
            # 分散トレーシングデータを取得
            all_traces = self.client.get_distributed_traces(
                app_names=self.app_names,
                time_range_minutes=10  # 直近10分のデータを確認
            )
            
            # ユーザーIDごとにトレースを分類
            traces_by_user = {}
            for trace in all_traces:
                user_id = trace.custom_attributes.get("user_id")
                if user_id and str(user_id) in [str(uid) for uid in test_user_ids]:
                    if user_id not in traces_by_user:
                        traces_by_user[user_id] = []
                    traces_by_user[user_id].append(trace)
            
            # 各ユーザーのトレース状況を確認
            for user_id in test_user_ids:
                user_traces = traces_by_user.get(str(user_id), [])
                has_main_app_trace = any(
                    "Flask-EC-Main-App" in trace.service_name for trace in user_traces
                )
                has_distributed_service_trace = any(
                    "Flask-EC-Distributed-Service" in trace.service_name for trace in user_traces
                )
                
                verification_results["details"][str(user_id)] = {
                    "trace_count": len(user_traces),
                    "has_main_app_trace": has_main_app_trace,
                    "has_distributed_service_trace": has_distributed_service_trace,
                    "propagation_success": has_main_app_trace and has_distributed_service_trace
                }
                
                if user_traces:
                    verification_results["users_with_traces"] += 1
                    verification_results["traces_found"].extend([
                        {
                            "trace_id": trace.trace_id,
                            "service": trace.service_name,
                            "operation": trace.operation_name,
                            "duration_ms": trace.duration_ms,
                            "user_id": trace.custom_attributes.get("user_id")
                        } for trace in user_traces
                    ])
            
            # 全体的な成功判定
            successful_propagations = sum(
                1 for details in verification_results["details"].values()
                if details["propagation_success"]
            )
            verification_results["trace_propagation_success"] = successful_propagations > 0
            verification_results["propagation_success_rate"] = (
                successful_propagations / len(test_user_ids) if test_user_ids else 0
            )
            
            logger.info(f"Trace propagation verification completed: "
                       f"{successful_propagations}/{len(test_user_ids)} successful")
            
        except Exception as e:
            logger.error(f"Failed to verify distributed trace propagation: {e}")
            verification_results["status"] = "error"
            verification_results["error"] = str(e)
        
        return verification_results
    
    def verify_custom_attributes(self, 
                               expected_user_ids: List[str],
                               wait_time_seconds: int = 60) -> Dict[str, Any]:
        """Custom Attributeの自動検証"""
        if not self.is_enabled():
            return {"status": "disabled", "message": "New Relic verification is disabled"}
        
        logger.info(f"Verifying custom attributes for {len(expected_user_ids)} users")
        
        # データ遅延を考慮して待機
        time.sleep(wait_time_seconds)
        
        verification_results = {
            "status": "success",
            "total_users_expected": len(expected_user_ids),
            "users_with_attributes": 0,
            "verification_success": False,
            "user_details": {}
        }
        
        try:
            # Custom Attributeの検証
            attribute_results = self.client.verify_custom_attributes(
                app_names=self.app_names,
                expected_user_ids=[str(uid) for uid in expected_user_ids],
                time_range_minutes=10
            )
            
            for user_id, has_attributes in attribute_results.items():
                verification_results["user_details"][user_id] = {
                    "has_custom_attributes": has_attributes,
                    "user_id_found": has_attributes
                }
                
                if has_attributes:
                    verification_results["users_with_attributes"] += 1
            
            # 成功判定
            verification_results["verification_success"] = (
                verification_results["users_with_attributes"] > 0
            )
            verification_results["success_rate"] = (
                verification_results["users_with_attributes"] / len(expected_user_ids)
                if expected_user_ids else 0
            )
            
            logger.info(f"Custom attribute verification completed: "
                       f"{verification_results['users_with_attributes']}/{len(expected_user_ids)} successful")
            
        except Exception as e:
            logger.error(f"Failed to verify custom attributes: {e}")
            verification_results["status"] = "error"
            verification_results["error"] = str(e)
        
        return verification_results
    
    def verify_performance_scenarios(self, 
                                   scenario_names: List[str],
                                   wait_time_seconds: int = 120) -> Dict[str, Any]:
        """パフォーマンス問題シナリオの実行結果検証"""
        if not self.is_enabled():
            return {"status": "disabled", "message": "New Relic verification is disabled"}
        
        logger.info(f"Verifying performance scenarios: {scenario_names}")
        
        # パフォーマンス問題の検出に時間がかかるため、長めに待機
        time.sleep(wait_time_seconds)
        
        verification_results = {
            "status": "success",
            "scenarios_tested": scenario_names,
            "scenario_results": {},
            "overall_success": False
        }
        
        try:
            for scenario in scenario_names:
                scenario_result = {
                    "scenario_name": scenario,
                    "detected": False,
                    "metrics": {},
                    "error_traces": []
                }
                
                # シナリオ別のメトリクス取得
                if scenario == "n_plus_one":
                    metrics = self.client.get_performance_metrics(
                        app_names=self.app_names,
                        time_range_minutes=15,
                        operation_name="n-plus-one"
                    )
                    
                    # N+1問題の検出判定（高いデータベースクエリ数）
                    for app_name, app_metrics in metrics.items():
                        if app_metrics.database_query_count > 10:  # 閾値
                            scenario_result["detected"] = True
                        scenario_result["metrics"][app_name] = {
                            "db_query_count": app_metrics.database_query_count,
                            "avg_response_time": app_metrics.response_time_avg
                        }
                
                elif scenario == "slow_query":
                    metrics = self.client.get_performance_metrics(
                        app_names=self.app_names,
                        time_range_minutes=15,
                        operation_name="slow-query"
                    )
                    
                    # スロークエリの検出判定（高いレスポンス時間）
                    for app_name, app_metrics in metrics.items():
                        if app_metrics.response_time_avg > 3000:  # 3秒以上
                            scenario_result["detected"] = True
                        scenario_result["metrics"][app_name] = {
                            "avg_response_time": app_metrics.response_time_avg,
                            "p95_response_time": app_metrics.response_time_95th
                        }
                
                elif scenario == "database_error":
                    # エラートレースの取得
                    error_traces = self.client.get_error_traces(
                        app_names=self.app_names,
                        time_range_minutes=15
                    )
                    
                    # データベースエラーの検出判定
                    db_error_traces = [
                        trace for trace in error_traces
                        if any("database" in msg.lower() or "sql" in msg.lower() 
                              for msg in trace.error_messages)
                    ]
                    
                    if db_error_traces:
                        scenario_result["detected"] = True
                        scenario_result["error_traces"] = [
                            {
                                "trace_id": trace.trace_id,
                                "service": trace.service_name,
                                "error_messages": trace.error_messages
                            } for trace in db_error_traces[:5]  # 最大5件
                        ]
                
                verification_results["scenario_results"][scenario] = scenario_result
            
            # 全体的な成功判定
            detected_scenarios = sum(
                1 for result in verification_results["scenario_results"].values()
                if result["detected"]
            )
            verification_results["overall_success"] = detected_scenarios > 0
            verification_results["detection_rate"] = (
                detected_scenarios / len(scenario_names) if scenario_names else 0
            )
            
            logger.info(f"Performance scenario verification completed: "
                       f"{detected_scenarios}/{len(scenario_names)} detected")
            
        except Exception as e:
            logger.error(f"Failed to verify performance scenarios: {e}")
            verification_results["status"] = "error"
            verification_results["error"] = str(e)
        
        return verification_results
    
    def generate_verification_report(self, 
                                   trace_results: Dict[str, Any],
                                   attribute_results: Dict[str, Any],
                                   performance_results: Dict[str, Any]) -> Dict[str, Any]:
        """検証結果の総合レポートを生成"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "success",
            "summary": {
                "trace_propagation_success": trace_results.get("trace_propagation_success", False),
                "custom_attributes_success": attribute_results.get("verification_success", False),
                "performance_scenarios_success": performance_results.get("overall_success", False)
            },
            "detailed_results": {
                "distributed_tracing": trace_results,
                "custom_attributes": attribute_results,
                "performance_scenarios": performance_results
            },
            "recommendations": []
        }
        
        # 推奨事項の生成
        if not report["summary"]["trace_propagation_success"]:
            report["recommendations"].append(
                "分散トレーシングヘッダーの伝播が正常に動作していません。"
                "New Relicエージェントの設定とHTTPヘッダーの送信を確認してください。"
            )
        
        if not report["summary"]["custom_attributes_success"]:
            report["recommendations"].append(
                "Custom Attributeの設定が正常に動作していません。"
                "userIdの設定処理とNew Relicエージェントの統合を確認してください。"
            )
        
        if not report["summary"]["performance_scenarios_success"]:
            report["recommendations"].append(
                "パフォーマンス問題シナリオが正常に検出されていません。"
                "テストシナリオの実行とNew Relicでの監視設定を確認してください。"
            )
        
        # 全体的なステータス判定
        success_count = sum(report["summary"].values())
        if success_count == 0:
            report["overall_status"] = "failed"
        elif success_count < 3:
            report["overall_status"] = "partial"
        
        return report

# グローバルインスタンス
verification_service = NewRelicVerificationService()