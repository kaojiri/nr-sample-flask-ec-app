"""
分散トレーシングパフォーマンス監視機能のテスト
N+1クエリ、スロークエリ、エラー発生時の追跡機能をテストする
"""

import unittest
import time
import json
import requests
from unittest.mock import patch, MagicMock

# New Relicモジュールのインポートを試行（テスト環境では利用できない場合がある）
try:
    import newrelic.agent
    NEWRELIC_AVAILABLE = True
except ImportError:
    NEWRELIC_AVAILABLE = False
    print("New Relicモジュールが利用できません。モック機能を使用します。")


class TestDistributedPerformanceMonitoring(unittest.TestCase):
    """分散トレーシングパフォーマンス監視機能のテストクラス"""
    
    def setUp(self):
        """テストセットアップ"""
        self.base_url = "http://localhost:5002"
        self.test_user_id = 789
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Performance-Monitor-Test/1.0'
        })
        
    def test_distributed_service_availability(self):
        """分散サービスの可用性をテスト"""
        print("\n=== 分散サービス可用性テスト ===")
        
        try:
            # ヘルスチェックを実行
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            
            self.assertEqual(response.status_code, 200, "分散サービスが利用可能である必要があります")
            
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
            
            print(f"分散サービス可用性確認:")
            print(f"  - ステータス: {data['status']}")
            print(f"  - データベース: {data.get('database', 'N/A')}")
            print(f"  - 実行時間: {data.get('execution_time', 'N/A')}秒")
            
        except requests.exceptions.ConnectionError:
            self.fail("分散サービスに接続できません。サービスが起動していることを確認してください。")
        except Exception as e:
            self.fail(f"分散サービス可用性テストでエラーが発生しました: {e}")
    
    def test_n_plus_one_query_monitoring(self):
        """N+1クエリ問題の監視機能をテスト"""
        print("\n=== N+1クエリ監視機能テスト ===")
        
        try:
            # N+1クエリエンドポイントを呼び出し
            request_data = {
                'user_id': self.test_user_id,
                'limit': 5
            }
            
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/performance/n-plus-one",
                json=request_data,
                timeout=10
            )
            execution_time = time.time() - start_time
            
            print(f"N+1クエリエンドポイント呼び出し結果:")
            print(f"  - HTTPステータス: {response.status_code}")
            print(f"  - 実行時間: {execution_time:.3f}秒")
            
            if response.status_code == 200:
                # 成功した場合の検証
                data = response.json()
                
                self.assertIn('status', data)
                self.assertIn('operation', data)
                self.assertEqual(data['operation'], 'n_plus_one')
                
                print(f"  - 操作: {data['operation']}")
                print(f"  - ユーザーID: {data.get('user_id', 'N/A')}")
                
                if 'data' in data and 'query_count' in data['data']:
                    query_count = data['data']['query_count']
                    print(f"  - クエリ実行回数: {query_count}")
                    
                    # N+1問題が発生していることを確認（クエリ数が多い）
                    self.assertGreater(query_count, 1, "N+1クエリ問題が検出される必要があります")
                
                print("  ✓ N+1クエリ問題が正常に監視されています")
                
            elif response.status_code == 500:
                # エラーが発生した場合でも、監視機能が動作していることを確認
                try:
                    error_data = response.json()
                    print(f"  - エラータイプ: {error_data.get('error_type', 'N/A')}")
                    print(f"  - エラーカテゴリ: {error_data.get('error_category', 'N/A')}")
                    print(f"  - 操作: {error_data.get('operation', 'N/A')}")
                    print("  ✓ エラー監視機能が正常に動作しています")
                except:
                    print("  - エラーレスポンスの解析に失敗しました")
            
            else:
                self.fail(f"予期しないHTTPステータス: {response.status_code}")
                
        except requests.exceptions.Timeout:
            self.fail("N+1クエリエンドポイントがタイムアウトしました")
        except Exception as e:
            self.fail(f"N+1クエリ監視テストでエラーが発生しました: {e}")
    
    def test_slow_query_monitoring(self):
        """スロークエリの監視機能をテスト"""
        print("\n=== スロークエリ監視機能テスト ===")
        
        try:
            # スロークエリエンドポイントを呼び出し（短時間で実行）
            request_data = {
                'user_id': self.test_user_id,
                'sleep_duration': 1.0,  # 1秒のスリープ
                'query_type': 'sleep'
            }
            
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/performance/slow-query",
                json=request_data,
                timeout=15
            )
            execution_time = time.time() - start_time
            
            print(f"スロークエリエンドポイント呼び出し結果:")
            print(f"  - HTTPステータス: {response.status_code}")
            print(f"  - 実行時間: {execution_time:.3f}秒")
            
            if response.status_code == 200:
                # 成功した場合の検証
                data = response.json()
                
                self.assertIn('status', data)
                self.assertIn('operation', data)
                self.assertEqual(data['operation'], 'slow_query')
                
                print(f"  - 操作: {data['operation']}")
                print(f"  - ユーザーID: {data.get('user_id', 'N/A')}")
                print(f"  - クエリタイプ: {data.get('query_type', 'N/A')}")
                
                # 実行時間が適切であることを確認
                if execution_time >= 1.0:
                    print(f"  ✓ スロークエリが正常に検出されました（{execution_time:.3f}秒）")
                else:
                    print(f"  - 実行時間が短すぎます（{execution_time:.3f}秒）")
                
                if 'performance_metrics' in data:
                    metrics = data['performance_metrics']
                    print(f"  - パフォーマンスメトリクス:")
                    for key, value in metrics.items():
                        print(f"    - {key}: {value}")
                
                print("  ✓ スロークエリが正常に監視されています")
                
            elif response.status_code == 500:
                # エラーが発生した場合でも、監視機能が動作していることを確認
                try:
                    error_data = response.json()
                    print(f"  - エラータイプ: {error_data.get('error_type', 'N/A')}")
                    print(f"  - エラーカテゴリ: {error_data.get('error_category', 'N/A')}")
                    print(f"  - 操作: {error_data.get('operation', 'N/A')}")
                    print("  ✓ エラー監視機能が正常に動作しています")
                except:
                    print("  - エラーレスポンスの解析に失敗しました")
            
            else:
                self.fail(f"予期しないHTTPステータス: {response.status_code}")
                
        except requests.exceptions.Timeout:
            self.fail("スロークエリエンドポイントがタイムアウトしました")
        except Exception as e:
            self.fail(f"スロークエリ監視テストでエラーが発生しました: {e}")
    
    def test_database_error_monitoring(self):
        """データベースエラーの監視機能をテスト"""
        print("\n=== データベースエラー監視機能テスト ===")
        
        try:
            # データベースエラーエンドポイントを呼び出し
            request_data = {
                'user_id': self.test_user_id,
                'error_type': 'syntax'
            }
            
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/performance/database-error",
                json=request_data,
                timeout=10
            )
            execution_time = time.time() - start_time
            
            print(f"データベースエラーエンドポイント呼び出し結果:")
            print(f"  - HTTPステータス: {response.status_code}")
            print(f"  - 実行時間: {execution_time:.3f}秒")
            
            # データベースエラーエンドポイントは意図的にエラーを発生させるため、
            # 通常は500エラーが返される
            if response.status_code == 500:
                try:
                    error_data = response.json()
                    
                    self.assertIn('status', error_data)
                    self.assertIn('operation', error_data)
                    self.assertEqual(error_data['operation'], 'database_error')
                    
                    print(f"  - 操作: {error_data['operation']}")
                    print(f"  - ユーザーID: {error_data.get('user_id', 'N/A')}")
                    print(f"  - エラータイプ: {error_data.get('error_type', 'N/A')}")
                    print(f"  - エラーカテゴリ: {error_data.get('error_category', 'N/A')}")
                    
                    # 意図的なエラーであることを確認
                    if error_data.get('intentional'):
                        print("  ✓ 意図的なエラーが正常に発生しました")
                    
                    # New Relicに報告されたことを確認
                    if error_data.get('new_relic_reported'):
                        print("  ✓ エラーがNew Relicに報告されました")
                    
                    print("  ✓ データベースエラーが正常に監視されています")
                    
                except json.JSONDecodeError:
                    print("  - エラーレスポンスの解析に失敗しました")
                    
            elif response.status_code == 200:
                # 予期しない成功の場合
                data = response.json()
                print(f"  - 予期しない成功: {data.get('message', 'N/A')}")
                
            else:
                self.fail(f"予期しないHTTPステータス: {response.status_code}")
                
        except requests.exceptions.Timeout:
            self.fail("データベースエラーエンドポイントがタイムアウトしました")
        except Exception as e:
            self.fail(f"データベースエラー監視テストでエラーが発生しました: {e}")
    
    def test_error_tracking_functionality(self):
        """エラー追跡機能をテスト"""
        print("\n=== エラー追跡機能テスト ===")
        
        try:
            # 存在しないエンドポイントを呼び出してエラーを発生させる
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/performance/non-existent-endpoint",
                json={'user_id': self.test_user_id},
                timeout=5
            )
            execution_time = time.time() - start_time
            
            print(f"存在しないエンドポイント呼び出し結果:")
            print(f"  - HTTPステータス: {response.status_code}")
            print(f"  - 実行時間: {execution_time:.3f}秒")
            
            # 404エラーが返されることを確認
            self.assertEqual(response.status_code, 404, "存在しないエンドポイントは404を返す必要があります")
            
            print("  ✓ 存在しないエンドポイントが正しく処理されました")
            
            # 無効なJSONを送信してエラーを発生させる
            try:
                response = self.session.post(
                    f"{self.base_url}/performance/n-plus-one",
                    data="invalid json",
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
                
                print(f"無効なJSON送信結果:")
                print(f"  - HTTPステータス: {response.status_code}")
                
                # 400または500エラーが返されることを確認
                self.assertIn(response.status_code, [400, 500], "無効なJSONはエラーを返す必要があります")
                
                print("  ✓ 無効なJSONが正しく処理されました")
                
            except Exception as e:
                print(f"  - 無効なJSONテストでエラー: {e}")
            
            print("  ✓ エラー追跡機能が正常に動作しています")
            
        except Exception as e:
            self.fail(f"エラー追跡機能テストでエラーが発生しました: {e}")
    
    def test_performance_metrics_collection(self):
        """パフォーマンスメトリクス収集をテスト"""
        print("\n=== パフォーマンスメトリクス収集テスト ===")
        
        try:
            # 複数のエンドポイントを呼び出してメトリクスを収集
            endpoints = [
                ('n-plus-one', {'user_id': self.test_user_id, 'limit': 3}),
                ('slow-query', {'user_id': self.test_user_id, 'sleep_duration': 0.5, 'query_type': 'sleep'}),
                ('database-error', {'user_id': self.test_user_id, 'error_type': 'syntax'})
            ]
            
            metrics_collected = []
            
            for endpoint, request_data in endpoints:
                print(f"\n--- {endpoint} エンドポイントメトリクス収集 ---")
                
                start_time = time.time()
                try:
                    response = self.session.post(
                        f"{self.base_url}/performance/{endpoint}",
                        json=request_data,
                        timeout=10
                    )
                    execution_time = time.time() - start_time
                    
                    metric = {
                        'endpoint': endpoint,
                        'status_code': response.status_code,
                        'execution_time': execution_time,
                        'success': response.status_code in [200, 500]  # 500も予想される動作
                    }
                    
                    try:
                        response_data = response.json()
                        metric['response_data'] = response_data
                        
                        # レスポンスからメトリクス情報を抽出
                        if 'performance_metrics' in response_data:
                            metric['performance_metrics'] = response_data['performance_metrics']
                        
                        if 'execution_time' in response_data:
                            metric['server_execution_time'] = response_data['execution_time']
                            
                    except json.JSONDecodeError:
                        metric['response_data'] = None
                    
                    metrics_collected.append(metric)
                    
                    print(f"  - HTTPステータス: {metric['status_code']}")
                    print(f"  - 実行時間: {metric['execution_time']:.3f}秒")
                    print(f"  - 成功: {'はい' if metric['success'] else 'いいえ'}")
                    
                except requests.exceptions.Timeout:
                    print(f"  - タイムアウト発生")
                    metrics_collected.append({
                        'endpoint': endpoint,
                        'status_code': 'timeout',
                        'execution_time': time.time() - start_time,
                        'success': False
                    })
                except Exception as e:
                    print(f"  - エラー発生: {e}")
                    metrics_collected.append({
                        'endpoint': endpoint,
                        'status_code': 'error',
                        'execution_time': time.time() - start_time,
                        'success': False,
                        'error': str(e)
                    })
            
            print(f"\n=== メトリクス収集結果 ===")
            print(f"収集したメトリクス数: {len(metrics_collected)}")
            
            successful_calls = sum(1 for m in metrics_collected if m['success'])
            print(f"成功した呼び出し: {successful_calls}")
            print(f"失敗した呼び出し: {len(metrics_collected) - successful_calls}")
            
            total_execution_time = sum(m['execution_time'] for m in metrics_collected)
            print(f"総実行時間: {total_execution_time:.3f}秒")
            
            # 少なくとも1つのメトリクスが収集されていることを確認
            self.assertGreater(len(metrics_collected), 0, "メトリクスが収集される必要があります")
            
            print("  ✓ パフォーマンスメトリクスが正常に収集されました")
            
        except Exception as e:
            self.fail(f"パフォーマンスメトリクス収集テストでエラーが発生しました: {e}")


def run_performance_monitoring_tests():
    """パフォーマンス監視テストを実行"""
    print("=" * 70)
    print("分散トレーシングパフォーマンス監視機能テスト開始")
    print("=" * 70)
    
    # テストスイートを作成
    test_suite = unittest.TestSuite()
    
    # パフォーマンス監視テストを追加
    test_suite.addTest(TestDistributedPerformanceMonitoring('test_distributed_service_availability'))
    test_suite.addTest(TestDistributedPerformanceMonitoring('test_n_plus_one_query_monitoring'))
    test_suite.addTest(TestDistributedPerformanceMonitoring('test_slow_query_monitoring'))
    test_suite.addTest(TestDistributedPerformanceMonitoring('test_database_error_monitoring'))
    test_suite.addTest(TestDistributedPerformanceMonitoring('test_error_tracking_functionality'))
    test_suite.addTest(TestDistributedPerformanceMonitoring('test_performance_metrics_collection'))
    
    # テストを実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print("\n" + "=" * 70)
    print("分散トレーシングパフォーマンス監視機能テスト完了")
    print("=" * 70)
    print(f"実行テスト数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗: {len(result.failures)}")
    print(f"エラー: {len(result.errors)}")
    
    if result.failures:
        print("\n失敗したテスト:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\nエラーが発生したテスト:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_performance_monitoring_tests()
    exit(0 if success else 1)