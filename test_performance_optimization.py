"""
パフォーマンス最適化機能のテスト
タスク9: パフォーマンス最適化の実装のテスト
"""
import unittest
import time
import tempfile
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

# テスト対象のインポート
from app.services.bulk_user_creator import BulkUserCreator, UserCreationConfig
from app.services.user_sync_service import UserSyncService
from app.services.performance_utils import (
    MemoryMonitor, BatchProcessor, PerformanceProfiler,
    optimize_memory_usage, get_system_performance_info
)


class TestBulkUserCreatorOptimization(unittest.TestCase):
    """BulkUserCreatorのパフォーマンス最適化テスト"""
    
    def setUp(self):
        self.creator = BulkUserCreator()
        self.config = UserCreationConfig(
            username_pattern="perftest_{id}@test.local",
            password="TestPass123!",
            email_domain="test.local",
            batch_size=50,
            max_users_per_batch=500
        )
    
    def test_bulk_insert_optimization_enabled(self):
        """一括挿入最適化が有効になっているかテスト"""
        self.assertTrue(self.creator.bulk_insert_enabled)
        self.assertTrue(self.creator.parallel_processing_enabled)
        self.assertEqual(self.creator.bulk_insert_chunk_size, 100)
        self.assertEqual(self.creator.max_workers, 4)
    
    def test_optimized_credential_generation(self):
        """最適化された認証情報生成のテスト"""
        count = 150
        
        start_time = time.time()
        credentials = self.creator.generate_unique_credentials_optimized(count, self.config)
        generation_time = time.time() - start_time
        
        # 結果検証
        self.assertEqual(len(credentials), count)
        self.assertTrue(all(cred.username for cred in credentials))
        self.assertTrue(all(cred.email for cred in credentials))
        self.assertTrue(all(cred.password for cred in credentials))
        
        # パフォーマンス検証（150件を1秒以内）
        self.assertLess(generation_time, 1.0, f"認証情報生成が遅すぎます: {generation_time:.2f}秒")
        
        print(f"最適化認証情報生成: {count}件を{generation_time:.3f}秒で完了")
    
    def test_memory_efficient_mode(self):
        """メモリ効率モードのテスト"""
        self.creator.memory_efficient_mode = True
        
        # 大量データでのテスト
        count = 200
        credentials = self.creator.generate_unique_credentials_optimized(count, self.config)
        
        # メモリ効率モードでも正常に動作することを確認
        self.assertEqual(len(credentials), count)
        
        # ユニーク性の確認
        usernames = [cred.username for cred in credentials]
        emails = [cred.email for cred in credentials]
        
        self.assertEqual(len(set(usernames)), count, "ユーザー名に重複があります")
        self.assertEqual(len(set(emails)), count, "メールアドレスに重複があります")
    
    @patch('app.services.bulk_user_creator.db')
    def test_bulk_insert_chunk_processing(self, mock_db):
        """一括挿入のチャンク処理テスト"""
        # モックセットアップ
        mock_db.session.bulk_save_objects = MagicMock()
        mock_db.session.commit = MagicMock()
        
        # テストデータ
        credentials = self.creator.generate_unique_credentials_optimized(150, self.config)
        
        # 一括挿入実行
        result = self.creator._create_users_bulk_insert(credentials, self.config)
        
        # チャンク処理が実行されたことを確認
        expected_chunks = (len(credentials) + self.creator.bulk_insert_chunk_size - 1) // self.creator.bulk_insert_chunk_size
        self.assertEqual(mock_db.session.bulk_save_objects.call_count, expected_chunks)
        
        print(f"一括挿入チャンク処理: {len(credentials)}件を{expected_chunks}チャンクで処理")
    
    def test_performance_target_compliance(self):
        """パフォーマンス目標の達成テスト（要件1.5: 100ユーザーを30秒以内）"""
        # 小規模テスト（実際のDB操作なし）
        count = 100
        
        start_time = time.time()
        credentials = self.creator.generate_unique_credentials_optimized(count, self.config)
        generation_time = time.time() - start_time
        
        # 認証情報生成は十分高速であることを確認
        self.assertLess(generation_time, 5.0, f"認証情報生成が目標を超過: {generation_time:.2f}秒")
        
        print(f"パフォーマンス目標テスト: {count}件の認証情報を{generation_time:.3f}秒で生成")


class TestUserSyncServiceOptimization(unittest.TestCase):
    """UserSyncServiceのパフォーマンス最適化テスト"""
    
    def setUp(self):
        self.sync_service = UserSyncService()
    
    def test_differential_sync_enabled(self):
        """差分同期が有効になっているかテスト"""
        self.assertTrue(self.sync_service.differential_sync_enabled)
        self.assertTrue(self.sync_service.compression_enabled)
        self.assertEqual(self.sync_service.compression_threshold, 1024)
        self.assertTrue(self.sync_service.memory_efficient_mode)
    
    def test_data_hash_calculation(self):
        """データハッシュ計算のテスト"""
        from app.services.user_sync_service import TestUserData
        
        # テストデータ
        users = [
            TestUserData(id=1, username="user1", email="user1@test.com"),
            TestUserData(id=2, username="user2", email="user2@test.com"),
            TestUserData(id=3, username="user3", email="user3@test.com")
        ]
        
        # ハッシュ計算
        hash1 = self.sync_service._calculate_data_hash(users)
        hash2 = self.sync_service._calculate_data_hash(users)
        
        # 同じデータは同じハッシュ
        self.assertEqual(hash1, hash2)
        
        # データが変わるとハッシュも変わる
        users[0].username = "changed_user1"
        hash3 = self.sync_service._calculate_data_hash(users)
        self.assertNotEqual(hash1, hash3)
        
        print(f"データハッシュ計算テスト: {hash1[:16]}... -> {hash3[:16]}...")
    
    def test_user_change_detection(self):
        """ユーザー変更検出のテスト"""
        from app.services.user_sync_service import TestUserData
        
        user1 = TestUserData(id=1, username="user1", email="user1@test.com", test_batch_id="batch1")
        user2 = TestUserData(id=1, username="user1", email="user1@test.com", test_batch_id="batch1")
        user3 = TestUserData(id=1, username="user1_changed", email="user1@test.com", test_batch_id="batch1")
        
        # 同じユーザーは変更なし
        self.assertFalse(self.sync_service._user_has_changed(user1, user2))
        
        # ユーザー名が変わった場合は変更あり
        self.assertTrue(self.sync_service._user_has_changed(user1, user3))
        
        print("ユーザー変更検出テスト: 正常に動作")
    
    def test_compression_threshold(self):
        """圧縮閾値のテスト"""
        from app.services.user_sync_service import UserExportData, TestUserData
        
        # 小さなデータ（圧縮されない）
        small_users = [TestUserData(id=1, username="user1", email="user1@test.com")]
        small_export = UserExportData(
            users=small_users,
            export_timestamp=datetime.utcnow().isoformat(),
            source_system="test",
            total_count=1
        )
        
        compressed_small = self.sync_service._compress_export_data(small_export)
        self.assertFalse(compressed_small.compression_enabled)
        
        print("圧縮閾値テスト: 小さなデータは圧縮されない")


class TestPerformanceUtils(unittest.TestCase):
    """パフォーマンスユーティリティのテスト"""
    
    def test_memory_monitor(self):
        """メモリ監視のテスト"""
        monitor = MemoryMonitor()
        
        # 現在のメモリ統計取得
        stats = monitor.get_current_memory_stats()
        
        self.assertGreater(stats.total_mb, 0)
        self.assertGreaterEqual(stats.available_mb, 0)
        self.assertGreater(stats.used_mb, 0)
        self.assertGreaterEqual(stats.percent, 0)
        self.assertLessEqual(stats.percent, 100)
        
        print(f"メモリ監視テスト: 使用量={stats.used_mb:.1f}MB ({stats.percent:.1f}%)")
    
    def test_batch_processor(self):
        """バッチ処理のテスト"""
        processor = BatchProcessor(batch_size=10)
        
        # テストデータ
        items = list(range(25))  # 0-24の25個のアイテム
        
        def process_batch(batch):
            return [item * 2 for item in batch]  # 各アイテムを2倍にする
        
        # バッチ処理実行
        results = processor.process_in_batches(items, process_batch)
        
        # 結果検証
        expected = [item * 2 for item in items]
        self.assertEqual(results, expected)
        
        print(f"バッチ処理テスト: {len(items)}件を正常に処理")
    
    def test_performance_profiler(self):
        """パフォーマンスプロファイラーのテスト"""
        profiler = PerformanceProfiler()
        
        # プロファイリング実行
        with profiler.profile_operation("test_operation", items_count=100) as metrics:
            # 何らかの処理をシミュレート
            time.sleep(0.1)
            total = sum(range(1000))
        
        # メトリクス検証
        self.assertEqual(metrics.operation_name, "test_operation")
        self.assertEqual(metrics.items_processed, 100)
        self.assertIsNotNone(metrics.duration_seconds)
        self.assertGreater(metrics.duration_seconds, 0.05)  # 最低0.05秒はかかる
        self.assertIsNotNone(metrics.throughput_per_second)
        
        print(f"パフォーマンスプロファイラーテスト: {metrics.duration_seconds:.3f}秒, "
              f"スループット={metrics.throughput_per_second:.1f}件/秒")
    
    def test_memory_optimization(self):
        """メモリ最適化のテスト"""
        # メモリ最適化実行
        memory_stats = optimize_memory_usage()
        
        if memory_stats:
            self.assertIsNotNone(memory_stats.used_mb)
            self.assertIsNotNone(memory_stats.percent)
            print(f"メモリ最適化テスト: 現在使用量={memory_stats.used_mb:.1f}MB")
        else:
            print("メモリ最適化テスト: 統計取得に失敗（環境依存）")
    
    def test_system_performance_info(self):
        """システムパフォーマンス情報取得のテスト"""
        info = get_system_performance_info()
        
        if "error" not in info:
            self.assertIn("cpu_percent", info)
            self.assertIn("memory", info)
            self.assertIn("disk", info)
            self.assertIn("timestamp", info)
            
            print(f"システム情報テスト: CPU={info['cpu_percent']:.1f}%, "
                  f"メモリ={info['memory']['percent']:.1f}%")
        else:
            print(f"システム情報テスト: エラー={info['error']}")


class TestIntegratedPerformance(unittest.TestCase):
    """統合パフォーマンステスト"""
    
    def test_end_to_end_performance(self):
        """エンドツーエンドパフォーマンステスト"""
        from app.services.performance_utils import performance_profiler
        
        # 統合テスト実行
        with performance_profiler.profile_operation("integrated_test", items_count=50) as metrics:
            # BulkUserCreator最適化テスト
            creator = BulkUserCreator()
            config = UserCreationConfig(
                username_pattern="integrated_{id}@test.local",
                batch_size=25
            )
            
            credentials = creator.generate_unique_credentials_optimized(50, config)
            
            # UserSyncService最適化テスト
            sync_service = UserSyncService()
            from app.services.user_sync_service import TestUserData
            
            test_users = [
                TestUserData(
                    id=i,
                    username=cred.username,
                    email=cred.email,
                    password=cred.password
                )
                for i, cred in enumerate(credentials[:10])  # 最初の10件のみ
            ]
            
            data_hash = sync_service._calculate_data_hash(test_users)
        
        # パフォーマンス検証
        self.assertLess(metrics.duration_seconds, 5.0, "統合テストが5秒を超過")
        self.assertIsNotNone(data_hash)
        
        print(f"統合パフォーマンステスト完了: {metrics.duration_seconds:.3f}秒")


def run_performance_tests():
    """パフォーマンステストを実行"""
    print("=" * 60)
    print("パフォーマンス最適化テスト開始")
    print("=" * 60)
    
    # テストスイート作成
    loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    
    # BulkUserCreator最適化テスト
    test_suite.addTests(loader.loadTestsFromTestCase(TestBulkUserCreatorOptimization))
    
    # UserSyncService最適化テスト
    test_suite.addTests(loader.loadTestsFromTestCase(TestUserSyncServiceOptimization))
    
    # パフォーマンスユーティリティテスト
    test_suite.addTests(loader.loadTestsFromTestCase(TestPerformanceUtils))
    
    # 統合パフォーマンステスト
    test_suite.addTests(loader.loadTestsFromTestCase(TestIntegratedPerformance))
    
    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print("=" * 60)
    print(f"テスト結果: 実行={result.testsRun}, 失敗={len(result.failures)}, エラー={len(result.errors)}")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_performance_tests()
    exit(0 if success else 1)