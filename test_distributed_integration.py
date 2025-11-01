"""
分散トレーシング統合テスト
分散サービス呼び出し、New Relic監視データの検証、エラーハンドリングの統合テスト
"""

import unittest
import time
import json
import requests
import threading
import concurrent.futures
from unittest.mock import patch, MagicMock

# New Relicモジュールのインポートを試行（テスト環境では利用できない場合がある）
try:
    import newrelic.agent
    NEWRELIC_AVAILABLE = True
except ImportError:
    NEWRELIC_AVAILABLE = False
    print("New Relicモジュールが利用できません。モック機能を使用します。")


class TestDistributedIntegration(unittest.TestCase):
    """分散トレーシング統合テストクラス"""
    
    def setUp(self):
        """テストセットアップ"""
        self.base_url = "http://localhost:5002"
        self.main_app_url = "http://localhost:5001"  # メインアプリケーション
        self.test_user_id = 999
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Integration-Test/1.0'
        })
        
    def test_distributed_service_integration(self):
        """分散サービス統合テスト"""
        print("\n=== 分散サービス統合テスト ===")
        
        try:
            # 1. 分散サービスのヘルスチェック
            print("1. 分散サービスヘルスチェック")
            health_response = self.session.get(f"{self.base_url}/health", timeout=5)
            self.assertEqual(health_response.status_code, 200)
            
            health_data = health_response.json()
            self.assertEqual(health_data['status'], 'healthy')
            print(f"   ✓ 分散サービス正常: {health_data['status']}")
            
            # 2. データベース初期化の確認
            print("2. データベース初期化確認")
            if health_data.get('database') != 'connected':
                init_response = self.session.post(f"{self.base_url}/init-db", timeout=10)
                if init_response.status_code == 200:
                    print("   ✓ データベース初期化完了")
                else:
                    print("   - データベース初期化に問題があります")
            else:
                print("   ✓ データベース接続済み")
            
            # 3. 基本的なサービス情報の取得
            print("3. サービス情報取得")
            info_response = self.session.get(f"{self.base_url}/", timeout=5)
            self.assertEqual(info_response.status_code, 200)
            
            info_data = info_response.json()
            self.assertIn('message', info_data)
            self.assertIn('endpoints', info_data)
            print(f"   ✓ サービス情報取得成功: {len(info_data['endpoints'])}個のエンドポイント")
            
            # 4. パフォーマンスエンドポイントの動作確認
            print("4. パフォーマンスエンドポイント動作確認")
            endpoints_to_test = ['n-plus-one', 'slow-query', 'database-error']
            
            for endpoint in endpoints_to_test:
                print(f"   - {endpoint} エンドポイントテスト")
                
                request_data = {'user_id': self.test_user_id}
                if endpoint == 'n-plus-one':
                    request_data['limit'] = 2
                elif endpoint == 'slow-query':
                    request_data['sleep_duration'] = 0.5
                    request_data['query_type'] = 'sleep'
                elif endpoint == 'database-error':
                    request_data['error_type'] = 'syntax'
                
                response = self.session.post(
                    f"{self.base_url}/performance/{endpoint}",
                    json=request_data,
                    timeout=10
                )
                
                # レスポンスが返されることを確認（200または500）
                self.assertIn(response.status_code, [200, 500])
                
                try:
                    response_data = response.json()
                    self.assertIn('operation', response_data)
                    print(f"     ✓ {endpoint}: {response.status_code} - {response_data.get('status', 'N/A')}")
                except json.JSONDecodeError:
                    print(f"     - {endpoint}: {response.status_code} - JSON解析エラー")
            
            print("   ✓ 分散サービス統合テスト完了")
            
        except Exception as e:
            self.fail(f"分散サービス統合テストでエラーが発生しました: {e}")
    
    def test_new_relic_monitoring_integration(self):
        """New Relic監視統合テスト"""
        print("\n=== New Relic監視統合テスト ===")
        
        try:
            # 1. Custom Attributeの設定テスト
            print("1. Custom Attribute設定テスト")
            
            request_data = {
                'user_id': self.test_user_id,
                'limit': 3
            }
            
            # 分散トレーシングヘッダーを模擬
            headers = {
                'Content-Type': 'application/json',
                'newrelic': 'test-trace-header',
                'traceparent': '00-test-trace-id-test-span-id-01'
            }
            
            response = self.session.post(
                f"{self.base_url}/performance/n-plus-one",
                json=request_data,
                headers=headers,
                timeout=10
            )
            
            # レスポンスが返されることを確認
            self.assertIn(response.status_code, [200, 500])
            
            if response.status_code in [200, 500]:
                try:
                    response_data = response.json()
                    
                    # ユーザーIDが正しく処理されていることを確認
                    self.assertEqual(response_data.get('user_id'), self.test_user_id)
                    
                    # 操作タイプが正しく設定されていることを確認
                    self.assertIn('operation', response_data)
                    
                    print(f"   ✓ Custom Attribute設定確認: user_id={response_data.get('user_id')}")
                    print(f"   ✓ 操作タイプ: {response_data.get('operation')}")
                    
                except json.JSONDecodeError:
                    print("   - レスポンスのJSON解析に失敗しました")
            
            # 2. エラー報告機能のテスト
            print("2. エラー報告機能テスト")
            
            error_request_data = {
                'user_id': self.test_user_id,
                'error_type': 'syntax'
            }
            
            error_response = self.session.post(
                f"{self.base_url}/performance/database-error",
                json=error_request_data,
                timeout=10
            )
            
            # エラーエンドポイントは通常500を返す
            self.assertEqual(error_response.status_code, 500)
            
            try:
                error_data = error_response.json()
                
                # New Relicに報告されたことを確認
                if error_data.get('new_relic_reported'):
                    print("   ✓ エラーがNew Relicに報告されました")
                
                # エラーカテゴリが設定されていることを確認
                if 'error_category' in error_data:
                    print(f"   ✓ エラーカテゴリ: {error_data['error_category']}")
                
                # 意図的なエラーであることを確認
                if error_data.get('intentional'):
                    print("   ✓ 意図的なエラーとして正しく処理されました")
                    
            except json.JSONDecodeError:
                print("   - エラーレスポンスのJSON解析に失敗しました")
            
            print("   ✓ New Relic監視統合テスト完了")
            
        except Exception as e:
            self.fail(f"New Relic監視統合テストでエラーが発生しました: {e}")
    
    def test_error_handling_integration(self):
        """エラーハンドリング統合テスト"""
        print("\n=== エラーハンドリング統合テスト ===")
        
        try:
            # 1. 様々なエラータイプのテスト
            print("1. 様々なエラータイプテスト")
            
            error_types = ['syntax', 'constraint', 'connection', 'timeout']
            
            for error_type in error_types:
                print(f"   - {error_type} エラーテスト")
                
                request_data = {
                    'user_id': self.test_user_id,
                    'error_type': error_type
                }
                
                response = self.session.post(
                    f"{self.base_url}/performance/database-error",
                    json=request_data,
                    timeout=15  # timeoutエラーの場合は長めに設定
                )
                
                # エラーエンドポイントは500を返すことを確認
                self.assertEqual(response.status_code, 500)
                
                try:
                    error_data = response.json()
                    
                    # エラータイプが正しく処理されていることを確認
                    self.assertEqual(error_data.get('error_type'), error_type)
                    
                    # 操作が正しく記録されていることを確認
                    self.assertEqual(error_data.get('operation'), 'database_error')
                    
                    print(f"     ✓ {error_type}: {error_data.get('error_category', 'N/A')}")
                    
                except json.JSONDecodeError:
                    print(f"     - {error_type}: JSON解析エラー")
            
            # 2. 無効なリクエストのテスト
            print("2. 無効なリクエストテスト")
            
            # 無効なJSON
            invalid_response = self.session.post(
                f"{self.base_url}/performance/n-plus-one",
                data="invalid json",
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            self.assertIn(invalid_response.status_code, [400, 500])
            print(f"   ✓ 無効なJSON: {invalid_response.status_code}")
            
            # 存在しないエンドポイント
            not_found_response = self.session.post(
                f"{self.base_url}/performance/non-existent",
                json={'user_id': self.test_user_id},
                timeout=5
            )
            
            self.assertEqual(not_found_response.status_code, 404)
            print(f"   ✓ 存在しないエンドポイント: {not_found_response.status_code}")
            
            # 3. エラー回復テスト
            print("3. エラー回復テスト")
            
            # エラー後に正常なリクエストが処理されることを確認
            recovery_response = self.session.get(f"{self.base_url}/health", timeout=5)
            self.assertEqual(recovery_response.status_code, 200)
            
            recovery_data = recovery_response.json()
            self.assertEqual(recovery_data['status'], 'healthy')
            print("   ✓ エラー後の回復確認: サービス正常")
            
            print("   ✓ エラーハンドリング統合テスト完了")
            
        except Exception as e:
            self.fail(f"エラーハンドリング統合テストでエラーが発生しました: {e}")
    
    def test_concurrent_requests_handling(self):
        """並行リクエスト処理テスト"""
        print("\n=== 並行リクエスト処理テスト ===")
        
        try:
            # 複数の並行リクエストを送信
            print("1. 並行リクエスト送信")
            
            def send_request(endpoint, request_data, request_id):
                """単一リクエストを送信"""
                try:
                    start_time = time.time()
                    response = requests.post(
                        f"{self.base_url}/performance/{endpoint}",
                        json=request_data,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    execution_time = time.time() - start_time
                    
                    return {
                        'request_id': request_id,
                        'endpoint': endpoint,
                        'status_code': response.status_code,
                        'execution_time': execution_time,
                        'success': response.status_code in [200, 500],
                        'response_data': response.json() if response.status_code in [200, 500] else None
                    }
                except Exception as e:
                    return {
                        'request_id': request_id,
                        'endpoint': endpoint,
                        'status_code': 'error',
                        'execution_time': 0,
                        'success': False,
                        'error': str(e)
                    }
            
            # 並行リクエストの設定
            concurrent_requests = [
                ('n-plus-one', {'user_id': self.test_user_id + i, 'limit': 2}, i)
                for i in range(3)
            ] + [
                ('slow-query', {'user_id': self.test_user_id + i + 10, 'sleep_duration': 0.3, 'query_type': 'sleep'}, i + 10)
                for i in range(2)
            ]
            
            # 並行実行
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(send_request, endpoint, request_data, request_id)
                    for endpoint, request_data, request_id in concurrent_requests
                ]
                
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            # 結果の分析
            print(f"2. 並行リクエスト結果分析")
            print(f"   - 送信したリクエスト数: {len(concurrent_requests)}")
            print(f"   - 受信したレスポンス数: {len(results)}")
            
            successful_requests = [r for r in results if r['success']]
            failed_requests = [r for r in results if not r['success']]
            
            print(f"   - 成功したリクエスト: {len(successful_requests)}")
            print(f"   - 失敗したリクエスト: {len(failed_requests)}")
            
            if successful_requests:
                avg_execution_time = sum(r['execution_time'] for r in successful_requests) / len(successful_requests)
                print(f"   - 平均実行時間: {avg_execution_time:.3f}秒")
            
            # 少なくとも一部のリクエストが成功することを確認
            self.assertGreater(len(successful_requests), 0, "少なくとも一部のリクエストが成功する必要があります")
            
            # 各リクエストの詳細
            for result in results:
                if result['success']:
                    print(f"   ✓ Request {result['request_id']} ({result['endpoint']}): {result['status_code']} - {result['execution_time']:.3f}s")
                else:
                    print(f"   ✗ Request {result['request_id']} ({result['endpoint']}): {result.get('error', 'Unknown error')}")
            
            print("   ✓ 並行リクエスト処理テスト完了")
            
        except Exception as e:
            self.fail(f"並行リクエスト処理テストでエラーが発生しました: {e}")
    
    def test_end_to_end_distributed_tracing(self):
        """エンドツーエンド分散トレーシングテスト"""
        print("\n=== エンドツーエンド分散トレーシングテスト ===")
        
        try:
            # 1. 分散トレーシングヘッダーの生成と送信
            print("1. 分散トレーシングヘッダー生成・送信")
            
            # 模擬的な分散トレーシングヘッダー
            trace_headers = {
                'newrelic': f'test-trace-{int(time.time())}',
                'traceparent': f'00-{int(time.time()):016x}-{int(time.time() * 1000) % 0xFFFFFFFFFFFFFFFF:016x}-01'
            }
            
            print(f"   - 生成されたトレースヘッダー: {list(trace_headers.keys())}")
            
            # 2. 複数のサービス呼び出しでトレーシング
            print("2. 複数サービス呼び出しトレーシング")
            
            trace_operations = [
                ('n-plus-one', {'user_id': self.test_user_id, 'limit': 2}),
                ('slow-query', {'user_id': self.test_user_id, 'sleep_duration': 0.5, 'query_type': 'sleep'})
            ]
            
            trace_results = []
            
            for operation, request_data in trace_operations:
                print(f"   - {operation} 操作実行")
                
                # トレースヘッダーを含むリクエスト
                headers = {**self.session.headers, **trace_headers}
                
                start_time = time.time()
                response = requests.post(
                    f"{self.base_url}/performance/{operation}",
                    json=request_data,
                    headers=headers,
                    timeout=10
                )
                execution_time = time.time() - start_time
                
                result = {
                    'operation': operation,
                    'status_code': response.status_code,
                    'execution_time': execution_time,
                    'trace_headers_sent': trace_headers,
                    'success': response.status_code in [200, 500]
                }
                
                if result['success']:
                    try:
                        response_data = response.json()
                        result['response_data'] = response_data
                        
                        # ユーザーIDが正しく処理されていることを確認
                        if response_data.get('user_id') == self.test_user_id:
                            result['user_id_traced'] = True
                        
                        print(f"     ✓ {operation}: {response.status_code} - {execution_time:.3f}s")
                        
                    except json.JSONDecodeError:
                        result['response_data'] = None
                        print(f"     - {operation}: {response.status_code} - JSON解析エラー")
                else:
                    print(f"     ✗ {operation}: {response.status_code}")
                
                trace_results.append(result)
                
                # 次のリクエストまで少し待機
                time.sleep(0.1)
            
            # 3. トレーシング結果の検証
            print("3. トレーシング結果検証")
            
            successful_traces = [r for r in trace_results if r['success']]
            print(f"   - 成功したトレース: {len(successful_traces)}/{len(trace_results)}")
            
            total_trace_time = sum(r['execution_time'] for r in trace_results)
            print(f"   - 総トレース時間: {total_trace_time:.3f}秒")
            
            # ユーザーIDが正しくトレースされていることを確認
            user_id_traced_count = sum(1 for r in successful_traces if r.get('user_id_traced'))
            print(f"   - ユーザーIDトレース成功: {user_id_traced_count}/{len(successful_traces)}")
            
            # 少なくとも一部のトレースが成功することを確認
            self.assertGreater(len(successful_traces), 0, "少なくとも一部のトレースが成功する必要があります")
            
            print("   ✓ エンドツーエンド分散トレーシングテスト完了")
            
        except Exception as e:
            self.fail(f"エンドツーエンド分散トレーシングテストでエラーが発生しました: {e}")
    
    def test_service_resilience(self):
        """サービス耐性テスト"""
        print("\n=== サービス耐性テスト ===")
        
        try:
            # 1. 高負荷テスト
            print("1. 高負荷テスト")
            
            # 短時間で多数のリクエストを送信
            load_test_requests = 10
            load_test_results = []
            
            start_time = time.time()
            
            for i in range(load_test_requests):
                try:
                    response = self.session.get(f"{self.base_url}/health", timeout=2)
                    load_test_results.append({
                        'request_id': i,
                        'status_code': response.status_code,
                        'success': response.status_code == 200
                    })
                except Exception as e:
                    load_test_results.append({
                        'request_id': i,
                        'status_code': 'error',
                        'success': False,
                        'error': str(e)
                    })
            
            total_load_time = time.time() - start_time
            successful_load_requests = sum(1 for r in load_test_results if r['success'])
            
            print(f"   - 送信リクエスト数: {load_test_requests}")
            print(f"   - 成功リクエスト数: {successful_load_requests}")
            print(f"   - 成功率: {(successful_load_requests/load_test_requests)*100:.1f}%")
            print(f"   - 総実行時間: {total_load_time:.3f}秒")
            print(f"   - 平均レスポンス時間: {total_load_time/load_test_requests:.3f}秒")
            
            # 2. エラー回復テスト
            print("2. エラー回復テスト")
            
            # 意図的にエラーを発生させる
            error_response = self.session.post(
                f"{self.base_url}/performance/database-error",
                json={'user_id': self.test_user_id, 'error_type': 'syntax'},
                timeout=5
            )
            
            self.assertEqual(error_response.status_code, 500)
            print("   ✓ 意図的エラー発生確認")
            
            # エラー後にサービスが正常に動作することを確認
            recovery_response = self.session.get(f"{self.base_url}/health", timeout=5)
            self.assertEqual(recovery_response.status_code, 200)
            
            recovery_data = recovery_response.json()
            self.assertEqual(recovery_data['status'], 'healthy')
            print("   ✓ エラー後の回復確認")
            
            # 3. タイムアウト処理テスト
            print("3. タイムアウト処理テスト")
            
            try:
                # 非常に短いタイムアウトでリクエスト
                timeout_response = self.session.post(
                    f"{self.base_url}/performance/slow-query",
                    json={'user_id': self.test_user_id, 'sleep_duration': 2.0, 'query_type': 'sleep'},
                    timeout=0.5  # 0.5秒でタイムアウト
                )
                
                # タイムアウトが発生しなかった場合
                print(f"   - タイムアウトなし: {timeout_response.status_code}")
                
            except requests.exceptions.Timeout:
                print("   ✓ タイムアウト処理確認")
            except Exception as e:
                print(f"   - タイムアウトテストエラー: {e}")
            
            # タイムアウト後にサービスが正常に動作することを確認
            post_timeout_response = self.session.get(f"{self.base_url}/health", timeout=5)
            self.assertEqual(post_timeout_response.status_code, 200)
            print("   ✓ タイムアウト後の回復確認")
            
            print("   ✓ サービス耐性テスト完了")
            
        except Exception as e:
            self.fail(f"サービス耐性テストでエラーが発生しました: {e}")


def run_integration_tests():
    """統合テストを実行"""
    print("=" * 80)
    print("分散トレーシング統合テスト開始")
    print("=" * 80)
    
    # テストスイートを作成
    test_suite = unittest.TestSuite()
    
    # 統合テストを追加
    test_suite.addTest(TestDistributedIntegration('test_distributed_service_integration'))
    test_suite.addTest(TestDistributedIntegration('test_new_relic_monitoring_integration'))
    test_suite.addTest(TestDistributedIntegration('test_error_handling_integration'))
    test_suite.addTest(TestDistributedIntegration('test_concurrent_requests_handling'))
    test_suite.addTest(TestDistributedIntegration('test_end_to_end_distributed_tracing'))
    test_suite.addTest(TestDistributedIntegration('test_service_resilience'))
    
    # テストを実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print("\n" + "=" * 80)
    print("分散トレーシング統合テスト完了")
    print("=" * 80)
    print(f"実行テスト数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗: {len(result.failures)}")
    print(f"エラー: {len(result.errors)}")
    
    if result.failures:
        print("\n失敗したテスト:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\nエラーが発生したテスト:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    # テスト結果のサマリー
    print(f"\n=== テスト結果サマリー ===")
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100
    print(f"成功率: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("✓ 統合テストは良好な結果です")
    elif success_rate >= 60:
        print("⚠ 統合テストは部分的に成功しています")
    else:
        print("✗ 統合テストに問題があります")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_tests()
    exit(0 if success else 1)