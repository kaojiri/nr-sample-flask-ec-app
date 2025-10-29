"""
Load Tester側のユーザー同期API（パフォーマンス最適化版）
"""
import asyncio
import logging
import traceback
import gzip
import io
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
from pathlib import Path
import concurrent.futures
from threading import Lock

from user_session_manager import get_user_session_manager, TestUser
from config import config_manager

logger = logging.getLogger(__name__)

# エラーハンドリング用のクラス（簡易版）
class LoadTesterErrorHandler:
    """Load Tester用の簡易エラーハンドリング"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_log_file = Path("logs/load_tester_errors.log")
        self.error_log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_error(self, operation: str, error: Exception, context: Dict[str, Any] = None):
        """エラーをログに記録"""
        error_msg = f"[{operation}] エラー: {str(error)}"
        if context:
            error_msg += f" | コンテキスト: {json.dumps(context, ensure_ascii=False)}"
        
        self.logger.error(error_msg)
        self.logger.error(f"[{operation}] スタックトレース:\n{traceback.format_exc()}")
        
        # ファイルにも記録
        try:
            with open(self.error_log_file, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.utcnow().isoformat()} - {error_msg}\n")
        except Exception:
            pass  # ログファイル書き込み失敗は無視
    
    def with_error_handling(self, operation: str, func, context: Dict[str, Any] = None):
        """エラーハンドリング付きで関数を実行"""
        try:
            return func()
        except Exception as e:
            self.log_error(operation, e, context)
            raise


class PerformanceOptimizedSyncHandler:
    """パフォーマンス最適化された同期ハンドラー"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_handler = LoadTesterErrorHandler()
        
        # パフォーマンス設定
        self.compression_enabled = True
        self.differential_sync_enabled = True
        self.batch_processing_enabled = True
        self.batch_size = 100
        self.max_workers = 4
        
        # 同期状態管理
        self._last_sync_hash = None
        self._user_cache = {}
        self._sync_lock = Lock()
    
    def process_import_request_optimized(self, import_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        最適化されたインポート処理
        - 差分同期対応
        - バッチ処理
        - 並列処理
        """
        try:
            start_time = datetime.utcnow()
            
            # データ解凍（必要に応じて）
            if import_data.get("compression_enabled", False):
                import_data = self._decompress_import_data(import_data)
            
            # 差分同期チェック
            if self.differential_sync_enabled and self._should_use_differential_sync(import_data):
                result = self._process_differential_import(import_data)
            else:
                result = self._process_full_import(import_data)
            
            # 処理時間を記録
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            result["processing_time"] = processing_time
            
            self.logger.info(f"最適化インポート完了: {processing_time:.2f}秒")
            return result
            
        except Exception as e:
            self.error_handler.log_error("optimized_import", e, {"data_size": len(str(import_data))})
            return {
                "success": False,
                "error": f"最適化インポート処理エラー: {str(e)}",
                "imported_count": 0
            }
    
    def _decompress_import_data(self, import_data: Dict[str, Any]) -> Dict[str, Any]:
        """インポートデータを解凍"""
        try:
            compressed_data = import_data.get("compressed_data")
            if compressed_data:
                # Base64デコードしてgzip解凍
                import base64
                compressed_bytes = base64.b64decode(compressed_data)
                
                with gzip.GzipFile(fileobj=io.BytesIO(compressed_bytes)) as gz_file:
                    decompressed_json = gz_file.read().decode('utf-8')
                
                decompressed_data = json.loads(decompressed_json)
                self.logger.debug(f"データ解凍完了: {len(compressed_bytes)} -> {len(decompressed_json)} bytes")
                return decompressed_data
            
            return import_data
            
        except Exception as e:
            self.logger.warning(f"データ解凍エラー: {str(e)}")
            return import_data
    
    def _should_use_differential_sync(self, import_data: Dict[str, Any]) -> bool:
        """差分同期を使用すべきかチェック"""
        metadata = import_data.get("metadata", {})
        sync_type = metadata.get("sync_type", "full")
        
        return (
            sync_type == "differential" and
            self._last_sync_hash is not None and
            "current_hash" in metadata
        )
    
    def _process_differential_import(self, import_data: Dict[str, Any]) -> Dict[str, Any]:
        """差分インポート処理"""
        try:
            metadata = import_data.get("metadata", {})
            users_data = import_data.get("users", [])
            
            # 差分データを処理
            added_count = metadata.get("added_count", 0)
            updated_count = metadata.get("updated_count", 0)
            deleted_user_ids = metadata.get("deleted_user_ids", [])
            
            total_processed = 0
            
            # 追加・更新ユーザーを処理
            if users_data:
                if self.batch_processing_enabled and len(users_data) > self.batch_size:
                    processed_count = self._process_users_batch_parallel(users_data)
                else:
                    processed_count = self._process_users_batch(users_data)
                total_processed += processed_count
            
            # 削除ユーザーを処理
            if deleted_user_ids:
                deleted_count = self._process_user_deletions(deleted_user_ids)
                total_processed += deleted_count
            
            # 同期ハッシュを更新
            self._last_sync_hash = metadata.get("current_hash")
            
            self.logger.info(
                f"差分同期完了: 追加/更新={len(users_data)}, 削除={len(deleted_user_ids)}"
            )
            
            return {
                "success": True,
                "imported_count": total_processed,
                "sync_type": "differential",
                "added_updated_count": len(users_data),
                "deleted_count": len(deleted_user_ids)
            }
            
        except Exception as e:
            self.error_handler.log_error("differential_import", e)
            return {
                "success": False,
                "error": f"差分インポートエラー: {str(e)}",
                "imported_count": 0
            }
    
    def _process_full_import(self, import_data: Dict[str, Any]) -> Dict[str, Any]:
        """フルインポート処理"""
        try:
            users_data = import_data.get("users", [])
            
            if not users_data:
                return {
                    "success": True,
                    "imported_count": 0,
                    "sync_type": "full",
                    "message": "インポートするユーザーデータがありません"
                }
            
            # バッチ処理または並列処理
            if self.batch_processing_enabled and len(users_data) > self.batch_size:
                processed_count = self._process_users_batch_parallel(users_data)
            else:
                processed_count = self._process_users_batch(users_data)
            
            # 同期ハッシュを更新
            data_hash = import_data.get("data_hash")
            if data_hash:
                self._last_sync_hash = data_hash
            
            self.logger.info(f"フル同期完了: {processed_count}件")
            
            return {
                "success": True,
                "imported_count": processed_count,
                "sync_type": "full"
            }
            
        except Exception as e:
            self.error_handler.log_error("full_import", e)
            return {
                "success": False,
                "error": f"フルインポートエラー: {str(e)}",
                "imported_count": 0
            }
    
    def _process_users_batch_parallel(self, users_data: List[Dict]) -> int:
        """並列バッチ処理"""
        try:
            # データをチャンクに分割
            chunks = [
                users_data[i:i + self.batch_size]
                for i in range(0, len(users_data), self.batch_size)
            ]
            
            total_processed = 0
            
            # ThreadPoolExecutorで並列処理
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_chunk = {
                    executor.submit(self._process_users_batch, chunk): chunk
                    for chunk in chunks
                }
                
                for future in concurrent.futures.as_completed(future_to_chunk):
                    try:
                        chunk_processed = future.result()
                        total_processed += chunk_processed
                    except Exception as e:
                        self.logger.error(f"並列処理チャンクエラー: {str(e)}")
            
            return total_processed
            
        except Exception as e:
            self.logger.error(f"並列バッチ処理エラー: {str(e)}")
            # フォールバック: 通常のバッチ処理
            return self._process_users_batch(users_data)
    
    def _process_users_batch(self, users_data: List[Dict]) -> int:
        """バッチユーザー処理"""
        try:
            session_manager = get_user_session_manager()
            processed_count = 0
            
            # 現在の設定を取得
            current_config = config_manager.get_config()
            test_users = current_config.get("test_users", [])
            
            # 既存ユーザーのマップを作成（効率的な検索のため）
            existing_users_map = {user.get("username", ""): user for user in test_users}
            
            # バッチ処理でユーザーを追加/更新
            new_users = []
            updated_users = []
            
            for user_data in users_data:
                username = user_data.get("username", "")
                
                # TestUserオブジェクトに変換
                test_user_dict = {
                    "user_id": f"sync_{user_data.get('id', '')}",
                    "username": username,
                    "password": user_data.get("password", "TestPass123"),
                    "enabled": True,
                    "description": f"同期ユーザー (バッチ: {user_data.get('test_batch_id', 'unknown')})",
                    "test_batch_id": user_data.get("test_batch_id"),
                    "is_test_user": user_data.get("is_test_user", True),
                    "created_by_bulk": user_data.get("created_by_bulk", False)
                }
                
                if username in existing_users_map:
                    # 既存ユーザーを更新
                    existing_users_map[username].update(test_user_dict)
                    updated_users.append(test_user_dict)
                else:
                    # 新規ユーザーを追加
                    new_users.append(test_user_dict)
                
                processed_count += 1
            
            # 設定を一括更新
            if new_users or updated_users:
                with self._sync_lock:
                    # 新規ユーザーを追加
                    test_users.extend(new_users)
                    
                    # 設定を保存
                    current_config["test_users"] = test_users
                    config_manager.update_config(current_config)
                    
                    # セッションマネージャーに反映
                    session_manager.reload_users()
            
            self.logger.debug(f"バッチ処理完了: 新規={len(new_users)}, 更新={len(updated_users)}")
            return processed_count
            
        except Exception as e:
            self.logger.error(f"バッチ処理エラー: {str(e)}")
            return 0
    
    def _process_user_deletions(self, deleted_user_ids: List[int]) -> int:
        """ユーザー削除処理"""
        try:
            if not deleted_user_ids:
                return 0
            
            session_manager = get_user_session_manager()
            current_config = config_manager.get_config()
            test_users = current_config.get("test_users", [])
            
            # 削除対象ユーザーを特定
            deleted_count = 0
            remaining_users = []
            
            for user in test_users:
                user_id = user.get("user_id", "")
                # sync_プレフィックスを除去してIDを比較
                if user_id.startswith("sync_"):
                    sync_id = int(user_id.replace("sync_", ""))
                    if sync_id in deleted_user_ids:
                        deleted_count += 1
                        continue
                
                remaining_users.append(user)
            
            # 設定を更新
            if deleted_count > 0:
                with self._sync_lock:
                    current_config["test_users"] = remaining_users
                    config_manager.update_config(current_config)
                    session_manager.reload_users()
            
            self.logger.info(f"ユーザー削除完了: {deleted_count}件")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"ユーザー削除エラー: {str(e)}")
            return 0


# グローバルインスタンス
performance_sync_handler = PerformanceOptimizedSyncHandler()

# グローバルエラーハンドラー
error_handler = LoadTesterErrorHandler()


@dataclass
class ImportResult:
    """インポート結果"""
    success: bool
    imported_count: int
    failed_count: int
    errors: List[str]
    import_timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "success": self.success,
            "imported_count": self.imported_count,
            "failed_count": self.failed_count,
            "errors": self.errors,
            "import_timestamp": self.import_timestamp
        }


class UserSyncAPI:
    """Load Tester側のユーザー同期API（強化されたエラーハンドリング付き）"""
    
    def __init__(self):
        self.session_manager = get_user_session_manager()
        self.auto_login_enabled = config_manager.get_config().get("bulk_user_management", {}).get("auto_login_on_sync", True)
        self.error_handler = error_handler
    
    def import_users(self, user_data: Dict[str, Any]) -> ImportResult:
        """
        Main Applicationからのユーザーデータをインポート（強化されたエラーハンドリング付き）
        要件 2.5: 同期失敗時のデータ整合性保持機能
        
        Args:
            user_data: インポートするユーザーデータ
            
        Returns:
            ImportResult: インポート結果
        """
        def import_operation():
            start_time = datetime.utcnow()
            errors = []
            imported_count = 0
            
            # ユーザーデータの取得
            users_list = user_data.get("users", [])
            total_count = len(users_list)
            
            logger.info(f"ユーザーインポート開始: {total_count}件")
            
            # データ整合性チェック
            if not users_list:
                logger.warning("インポートするユーザーデータが空です")
                return ImportResult(
                    success=True,
                    imported_count=0,
                    failed_count=0,
                    errors=["インポートするユーザーデータが空です"],
                    import_timestamp=start_time.isoformat()
                )
            
            # 既存のテストユーザーを取得
            existing_users = self.session_manager.get_test_users()
            logger.info(f"既存ユーザー数: {len(existing_users)}")
            
            # 既存のテストユーザーをクリア（オプション）
            clear_existing = user_data.get("metadata", {}).get("clear_existing", False)
            if clear_existing:
                try:
                    existing_users = []  # 既存ユーザーをクリア
                    logger.info("既存のテストユーザーをクリアしました")
                except Exception as e:
                    error_msg = f"既存ユーザークリアエラー: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 新しいテストユーザーリスト作成（部分的成功処理）
            new_test_users = []
            
            for i, user_info in enumerate(users_list):
                try:
                    # 必須フィールドの検証
                    if not user_info.get("username"):
                        raise ValueError("ユーザー名が指定されていません")
                    
                    # TestUserオブジェクト作成
                    test_user = TestUser(
                        user_id=f"sync_{user_info.get('id', i)}",
                        username=user_info.get("email", user_info["username"]),  # emailを優先、なければusername
                        password=user_info.get("password", "TestPass123"),
                        enabled=True,
                        description=f"Synced from Main App (batch: {user_info.get('test_batch_id', 'unknown')})",
                        test_batch_id=user_info.get('test_batch_id'),
                        is_bulk_created=True
                    )
                    
                    new_test_users.append(test_user)
                    imported_count += 1
                    
                    # 進捗ログ（100件ごと）
                    if (i + 1) % 100 == 0:
                        logger.info(f"インポート進捗: {i + 1}/{total_count} 完了")
                    
                except Exception as e:
                    error_msg = f"ユーザー変換エラー {user_info.get('username', f'index_{i}')}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
            
            # 設定ファイルを更新（データ整合性保持）
            if new_test_users:
                try:
                    # バックアップ作成
                    backup_users = self.session_manager.get_test_users()
                    
                    # 重複チェック：既存ユーザーのuser_idとusernameを取得
                    existing_user_ids = {user.user_id for user in existing_users}
                    existing_usernames = {user.username for user in existing_users}
                    
                    # 重複しない新規ユーザーのみを追加
                    unique_new_users = []
                    for user in new_test_users:
                        if user.user_id not in existing_user_ids and user.username not in existing_usernames:
                            unique_new_users.append(user)
                        else:
                            logger.warning(f"重複ユーザーをスキップ: {user.username} (ID: {user.user_id})")
                    
                    # 既存ユーザーと重複しない新規ユーザーを結合
                    all_users = existing_users + unique_new_users
                    logger.info(f"結合後のユーザー数: {len(all_users)} (既存: {len(existing_users)}, 新規: {len(unique_new_users)})")
                    
                    # 実際に追加されたユーザー数を更新
                    imported_count = len(unique_new_users)
                    
                    success = self.session_manager.update_test_users_config(all_users)
                    logger.info(f"設定ファイル更新結果: {success}")
                    
                    if not success:
                        # 失敗時は元の状態に復元
                        self.session_manager.update_test_users_config(backup_users)
                        raise Exception("設定ファイルの更新に失敗しました")
                    
                    # 更新後の設定ファイルを確認
                    from config import config_manager
                    updated_config = config_manager.get_config()
                    updated_users = updated_config.get("test_users", [])
                    logger.info(f"更新後の設定ファイル内ユーザー数: {len(updated_users)}")
                    
                    # セッションマネージャーをリロード
                    self.session_manager.reload_test_users()
                    logger.info(f"テストユーザー設定を更新: {len(new_test_users)}件")
                    
                    # 同期されたユーザーの詳細をログ出力
                    for user in new_test_users[:5]:  # 最初の5件のみ
                        logger.info(f"同期ユーザー: {user.username}, バッチID: {user.test_batch_id}")
                    
                    # 自動ログインが有効な場合は一括ログインを実行
                    if self.auto_login_enabled and new_test_users:
                        self._perform_auto_login(new_test_users, errors)
                
                except Exception as e:
                    error_msg = f"設定更新エラー: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    imported_count = 0  # 設定更新失敗時は成功数を0にリセット
            
            # 結果作成（自動ログインエラーは警告として扱い、同期自体は成功とする）
            sync_success = imported_count > 0
            sync_errors = [error for error in errors if "自動ログイン失敗" not in error]
            
            import_result = ImportResult(
                success=sync_success and len(sync_errors) == 0,
                imported_count=imported_count,
                failed_count=total_count - imported_count,
                errors=errors,  # 全てのエラー（警告含む）を記録
                import_timestamp=start_time.isoformat()
            )
            
            logger.info(f"ユーザーインポート完了: 成功={imported_count}件, 失敗={len(errors)}件")
            return import_result
        
        # エラーハンドリング付きで実行
        return self.error_handler.with_error_handling(
            "import_users",
            import_operation,
            {
                "user_count": len(user_data.get("users", [])),
                "source_system": user_data.get("source_system", "unknown")
            }
        )
    
    def _perform_auto_login(self, new_test_users: List[TestUser], errors: List[str]):
        """自動ログイン処理（エラーハンドリング付き）"""
        try:
            # バッチIDがある場合はバッチ単位でログイン
            batch_ids = set(user.test_batch_id for user in new_test_users if user.test_batch_id)
            
            if batch_ids:
                for batch_id in batch_ids:
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            sessions = loop.run_until_complete(
                                self.session_manager.login_batch_users(batch_id)
                            )
                            logger.info(f"バッチ {batch_id} で {len(sessions)} ユーザーが自動ログインしました")
                        finally:
                            loop.close()
                    except Exception as e:
                        error_msg = f"バッチ {batch_id} の自動ログイン失敗: {str(e)}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
            else:
                # バッチIDがない場合は全ユーザーログイン
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        sessions = loop.run_until_complete(
                            self.session_manager.login_all_users()
                        )
                        logger.info(f"{len(sessions)} ユーザーが自動ログインしました")
                    finally:
                        loop.close()
                except Exception as e:
                    error_msg = f"全ユーザー自動ログイン失敗: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
        
        except Exception as e:
            error_msg = f"自動ログイン処理エラー: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
    
    def _clear_existing_test_users(self):
        """既存のテストユーザーをクリア"""
        try:
            empty_users = []
            self.session_manager.update_test_users_config(empty_users)
            logger.info("既存のテストユーザーをクリアしました")
        except Exception as e:
            logger.error(f"テストユーザークリアエラー: {str(e)}")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """
        現在の同期状況を取得
        
        Returns:
            Dict: 同期状況情報
        """
        try:
            test_users = self.session_manager.get_test_users()
            session_stats = self.session_manager.get_session_stats()
            
            users_info = []
            for user in test_users:
                users_info.append({
                    "user_id": user.user_id,
                    "username": user.username,
                    "enabled": user.enabled,
                    "description": user.description
                })
            
            return {
                "total_users": len(test_users),
                "users": users_info,
                "session_stats": session_stats.to_dict(),
                "last_sync_check": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"同期状況取得エラー: {str(e)}")
            return {
                "error": str(e),
                "last_sync_check": datetime.utcnow().isoformat()
            }
    
    def bulk_login_users(self) -> Dict[str, Any]:
        """
        同期されたユーザーで一括ログイン実行
        
        Returns:
            Dict: ログイン結果
        """
        try:
            # 非同期ログイン実行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                sessions = loop.run_until_complete(self.session_manager.login_all_users())
                
                return {
                    "success": True,
                    "logged_in_count": len(sessions),
                    "sessions": [
                        {
                            "user_id": session.user_id,
                            "username": session.username,
                            "login_time": session.login_time.isoformat(),
                            "is_valid": session.is_valid
                        }
                        for session in sessions.values()
                    ],
                    "login_timestamp": datetime.utcnow().isoformat()
                }
                
            finally:
                loop.close()
                
        except Exception as e:
            error_msg = f"一括ログインエラー: {str(e)}"
            logger.error(error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "login_timestamp": datetime.utcnow().isoformat()
            }
    
    def get_batch_info(self) -> Dict[str, Any]:
        """
        バッチ情報を取得
        
        Returns:
            Dict: バッチ情報
        """
        try:
            batches = self.session_manager.get_all_batches()
            batch_info = []
            
            for batch_id in batches:
                batch_stats = self.session_manager.get_batch_session_stats(batch_id)
                batch_info.append(batch_stats)
            
            return {
                "total_batches": len(batches),
                "batches": batch_info,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"バッチ情報取得エラー: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def login_batch(self, batch_id: str) -> Dict[str, Any]:
        """
        指定バッチのユーザーで一括ログイン
        
        Args:
            batch_id: ログインするバッチID
            
        Returns:
            Dict: ログイン結果
        """
        try:
            # 非同期ログイン実行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                sessions = loop.run_until_complete(
                    self.session_manager.login_batch_users(batch_id)
                )
                
                return {
                    "success": True,
                    "batch_id": batch_id,
                    "logged_in_count": len(sessions),
                    "sessions": [
                        {
                            "user_id": session.user_id,
                            "username": session.username,
                            "login_time": session.login_time.isoformat(),
                            "is_valid": session.is_valid
                        }
                        for session in sessions.values()
                    ],
                    "login_timestamp": datetime.utcnow().isoformat()
                }
                
            finally:
                loop.close()
                
        except Exception as e:
            error_msg = f"バッチログインエラー (batch: {batch_id}): {str(e)}"
            logger.error(error_msg)
            
            return {
                "success": False,
                "batch_id": batch_id,
                "error": error_msg,
                "login_timestamp": datetime.utcnow().isoformat()
            }
    
    def remove_batch(self, batch_id: str) -> Dict[str, Any]:
        """
        指定バッチのユーザーを削除
        
        Args:
            batch_id: 削除するバッチID
            
        Returns:
            Dict: 削除結果
        """
        try:
            removed_count = self.session_manager.remove_batch_users(batch_id)
            
            # 設定ファイルを更新
            remaining_users = self.session_manager.get_test_users()
            self.session_manager.update_test_users_config(remaining_users)
            
            return {
                "success": True,
                "batch_id": batch_id,
                "removed_count": removed_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_msg = f"バッチ削除エラー (batch: {batch_id}): {str(e)}"
            logger.error(error_msg)
            
            return {
                "success": False,
                "batch_id": batch_id,
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def cleanup_all_test_users(self) -> Dict[str, Any]:
        """
        全てのテストユーザーをクリーンアップ
        要件 3.1: バッチ単位でのテストユーザー削除機能
        
        Returns:
            Dict: クリーンアップ結果
        """
        try:
            test_users = self.session_manager.get_test_users()
            initial_count = len(test_users)
            
            # 全ユーザーをクリア
            self._clear_existing_test_users()
            
            # セッションもクリア
            self.session_manager.clear_all_sessions()
            
            return {
                "success": True,
                "removed_count": initial_count,
                "cleanup_type": "all_users",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_msg = f"全ユーザークリーンアップエラー: {str(e)}"
            logger.error(error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "cleanup_type": "all_users",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_cleanup_candidates(self, age_days: int = 7) -> Dict[str, Any]:
        """
        クリーンアップ候補を取得
        要件 3.3: クリーンアップレポート生成機能
        
        Args:
            age_days: 何日以上古いバッチを候補とするか
            
        Returns:
            Dict: クリーンアップ候補情報
        """
        try:
            from datetime import timedelta
            
            test_users = self.session_manager.get_test_users()
            batches = self.session_manager.get_all_batches()
            
            cleanup_candidates = []
            current_time = datetime.utcnow()
            cutoff_time = current_time - timedelta(days=age_days)
            
            for batch_id in batches:
                batch_stats = self.session_manager.get_batch_session_stats(batch_id)
                batch_users = [user for user in test_users if getattr(user, 'test_batch_id', None) == batch_id]
                
                # バッチの作成時間を推定（最初のユーザーの作成時間）
                if batch_users:
                    # Load Testerでは作成時間が直接取得できないため、セッション統計から推定
                    estimated_age_days = 1  # デフォルト値
                    
                    cleanup_candidates.append({
                        'batch_id': batch_id,
                        'user_count': len(batch_users),
                        'estimated_age_days': estimated_age_days,
                        'active_sessions': batch_stats.get('active_sessions', 0),
                        'total_sessions': batch_stats.get('total_sessions', 0),
                        'is_candidate': estimated_age_days >= age_days,
                        'usernames': [user.username for user in batch_users[:5]]  # 最初の5ユーザー
                    })
            
            total_candidates = sum(1 for candidate in cleanup_candidates if candidate['is_candidate'])
            total_candidate_users = sum(
                candidate['user_count'] for candidate in cleanup_candidates 
                if candidate['is_candidate']
            )
            
            return {
                'total_batches': len(batches),
                'total_candidates': total_candidates,
                'total_candidate_users': total_candidate_users,
                'age_threshold_days': age_days,
                'candidates': cleanup_candidates,
                'report_timestamp': current_time.isoformat(),
                'system': 'load_tester'
            }
            
        except Exception as e:
            error_msg = f"クリーンアップ候補取得エラー: {str(e)}"
            logger.error(error_msg)
            
            return {
                'error': error_msg,
                'report_timestamp': datetime.utcnow().isoformat(),
                'system': 'load_tester'
            }


# FastAPI用のユーザー同期APIクラス（上記で定義済み）
# このファイルはFastAPIのapi.pyから使用されます