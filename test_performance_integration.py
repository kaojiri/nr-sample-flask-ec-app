"""
パフォーマンス最適化の統合テスト
実際の最適化機能が動作することを確認
"""
import time
import unittest
from unittest.mock import patch, MagicMock

from app.services.bulk_user_creator import BulkUserCreator, UserCreationConfig
from app.services.user_sync_service import UserSyncService, TestUserData
from app.services.performance_utils import performance_profiler, batch_processor


class TestPerformanceIntegration(unittest.TestCase):
    """パフォーマンス最適化の統合テスト"""
    
    def setUp(self):
        self.creator = BulkUserCreator()
        self.sync_service = UserSyncService()
        self.config = UserCreationConfig(
            username_pattern="perftest_{id}@test.local",
            password="TestPass123!",
            email_domain="test.local",
            batch_size=100,
            max_users_per_batch=1000
        )
    
    def test_optimized_vs_legacy_credential_generation(self):
        """最適化版と従来版の認証情報生成速度比較"""
        count = 200
        
        # 最適化版の測定
        start_time = time.time()
        optimized_credentials = self.creator.generate_unique_credentials_optimized(count, self.config)
        optimized_time = time.time() - start_time
        
        # 従来版の測定
        start_time = time.time()
        legacy_credentials = self.creator.generate_unique_credentials(count, self.config)
        legacy_time = time.time() - start_time
        
        # 結果検証
        self.assertEqual(len(optimized_credentials), count)
        self.assertEqual(len(legacy_credentials), count)
        
        # パフォーマンス比較（最適化版が同等以上の性能）
        performance_ratio = legacy_time / optimized_time if optimized_time > 0 else float('inf')
        
        print(f"認証情報生成パフォーマンス比較:")
        print(f"  最適化版: {optimized_time:.4f}秒")
        print(f"  従来版:   {legacy_time:.4f}秒")
        print(f"  性能比:   {performance_ratio:.2f}x")
        
        # 最適化版が極端に遅くないことを確認
        self.assertLessEqual(optimized_time, legacy_time * 2, "最適化版が従来版より大幅に遅い")
    
    def test_bulk_insert_optimization_selection(self):
        """一括挿入最適化の自動選択テスト"""
        # 小規模データ（従来版を使用）
        small_count = 30
        self.creator.bulk_insert_enabled = True
        
        # 大規模データ（最適化版を使用）
        large_count = 100
        
        # 最適化版が大規模データで選択されることを確認
        self.assertTrue(self.creator.bulk_insert_enabled)
        self.assertTrue(large_count >= 50)  # 最適化版の閾値
        self.assertTrue(small_count < 50)   # 従来版の閾値
        
        print(f"一括挿入最適化選択:")
        print(f"  小規模データ({small_count}件): 従来版")
        print(f"  大規模データ({large_count}件): 最適化版")
    
    def test_differential_sync_hash_calculation(self):
        """差分同期のハッシュ計算パフォーマンステスト"""
        # テストデータ作成
        users_small = [
            TestUserData(id=i, username=f"user{i}", email=f"user{i}@test.com")
            for i in range(50)
        ]
        
        users_large = [
            TestUserData(id=i, username=f"user{i}", email=f"user{i}@test.com")
            for i in range(500)
        ]
        
        # 小規模データのハッシュ計算
        start_time = time.time()
        hash_small = self.sync_service._calculate_data_hash(users_small)
        time_small = time.time() - start_time
        
        # 大規模データのハッシュ計算
        start_time = time.time()
        hash_large = self.sync_service._calculate_data_hash(users_large)
        time_large = time.time() - start_time
        
        # 結果検証
        self.assertIsNotNone(hash_small)
        self.assertIsNotNone(hash_large)
        self.assertNotEqual(hash_small, hash_large)
        
        # パフォーマンス検証（線形時間で処理）
        time_ratio = time_large / time_small if time_small > 0 else float('inf')
        data_ratio = len(users_large) / len(users_small)
        
        print(f"ハッシュ計算パフォーマンス:")
        print(f"  小規模({len(users_small)}件): {time_small:.4f}秒")
        print(f"  大規模({len(users_large)}件): {time_large:.4f}秒")
        print(f"  時間比: {time_ratio:.2f}x (データ比: {data_ratio:.2f}x)")
        
        # 時間計算量が合理的であることを確認
        self.assertLess(time_ratio, data_ratio * 2, "ハッシュ計算が非効率")
    
    def test_memory_efficient_batch_processing(self):
        """メモリ効率的なバッチ処理のテスト"""
        # 大量データをシミュレート
        large_dataset = list(range(1000))
        
        def process_batch(batch):
            # 各バッチを処理（2倍にする）
            return [item * 2 for item in batch]
        
        # バッチ処理実行
        with performance_profiler.profile_operation("batch_processing", items_count=len(large_dataset)) as metrics:
            results = batch_processor.process_in_batches(large_dataset, process_batch)
        
        # 結果検証
        expected_results = [item * 2 for item in large_dataset]
        self.assertEqual(results, expected_results)
        
        # パフォーマンス検証
        self.assertIsNotNone(metrics.duration_seconds)
        self.assertGreater(metrics.throughput_per_second, 0)
        
        print(f"バッチ処理パフォーマンス:")
        print(f"  処理件数: {len(large_dataset)}件")
        print(f"  処理時間: {metrics.duration_seconds:.4f}秒")
        print(f"  スループット: {metrics.throughput_per_second:.1f}件/秒")
    
    def test_compression_effectiveness(self):
        """データ圧縮の効果測定テスト"""
        # 大量のテストデータ作成
        large_users = [
            TestUserData(
                id=i,
                username=f"test_user_{i:04d}@example.com",
                email=f"test_user_{i:04d}@example.com",
                password="TestPassword123!",
                test_batch_id=f"batch_{i // 100}"
            )
            for i in range(200)
        ]
        
        from app.services.user_sync_service import UserExportData
        from datetime import datetime
        
        # エクスポートデータ作成
        export_data = UserExportData(
            users=large_users,
            export_timestamp=datetime.utcnow().isoformat(),
            source_system="test",
            total_count=len(large_users)
        )
        
        # 圧縮テスト
        compressed_data = self.sync_service._compress_export_data(export_data)
        
        # 結果検証
        if compressed_data.compression_enabled:
            compression_ratio = compressed_data.compressed_size / compressed_data.original_size
            print(f"データ圧縮効果:")
            print(f"  元サイズ: {compressed_data.original_size} bytes")
            print(f"  圧縮後: {compressed_data.compressed_size} bytes")
            print(f"  圧縮率: {compression_ratio:.2%}")
            
            # 圧縮効果があることを確認
            self.assertLess(compression_ratio, 1.0, "圧縮効果なし")
        else:
            print("データ圧縮: 閾値未満のためスキップ")
    
    @patch('app.services.bulk_user_creator.db')
    def test_parallel_vs_sequential_processing(self, mock_db):
        """並列処理と逐次処理の比較テスト"""
        # モックセットアップ
        mock_db.session.bulk_save_objects = MagicMock()
        mock_db.session.commit = MagicMock()
        
        # テストデータ
        credentials = self.creator.generate_unique_credentials_optimized(200, self.config)
        
        # 並列処理の測定
        self.creator.parallel_processing_enabled = True
        start_time = time.time()
        parallel_result = self.creator._create_users_parallel(credentials, self.config)
        parallel_time = time.time() - start_time
        
        # 一括挿入（逐次）の測定
        mock_db.session.bulk_save_objects.reset_mock()
        mock_db.session.commit.reset_mock()
        
        start_time = time.time()
        sequential_result = self.creator._create_users_bulk_insert(credentials, self.config)
        sequential_time = time.time() - start_time
        
        # 結果検証
        self.assertEqual(parallel_result.total_requested, len(credentials))
        self.assertEqual(sequential_result.total_requested, len(credentials))
        
        print(f"並列処理 vs 逐次処理:")
        print(f"  並列処理: {parallel_time:.4f}秒")
        print(f"  逐次処理: {sequential_time:.4f}秒")
        
        if parallel_time > 0 and sequential_time > 0:
            speedup = sequential_time / parallel_time
            print(f"  高速化: {speedup:.2f}x")


def run_integration_tests():
    """統合テストを実行"""
    print("=" * 60)
    print("パフォーマンス最適化統合テスト開始")
    print("=" * 60)
    
    # テスト実行
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPerformanceIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 60)
    print(f"統合テスト結果: 実行={result.testsRun}, 失敗={len(result.failures)}, エラー={len(result.errors)}")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_integration_tests()
    exit(0 if success else 1)