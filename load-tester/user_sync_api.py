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
from flask import Flask, request, jsonify
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
                    "password": user_data.get("password", "TestPass123!"),
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
            
            # 既存のテストユーザーをクリア（オプション）
            clear_existing = user_data.get("metadata", {}).get("clear_existing", False)
            if clear_existing:
                try:
                    self._clear_existing_test_users()
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
                        username=user_info["username"],
                        password=user_info.get("password", "TestPass123!"),
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
                    
                    success = self.session_manager.update_test_users_config(new_test_users)
                    
                    if not success:
                        # 失敗時は元の状態に復元
                        self.session_manager.update_test_users_config(backup_users)
                        raise Exception("設定ファイルの更新に失敗しました")
                    
                    # セッションマネージャーをリロード
                    self.session_manager.reload_test_users()
                    logger.info(f"テストユーザー設定を更新: {len(new_test_users)}件")
                    
                    # 自動ログインが有効な場合は一括ログインを実行
                    if self.auto_login_enabled and new_test_users:
                        self._perform_auto_login(new_test_users, errors)
                
                except Exception as e:
                    error_msg = f"設定更新エラー: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    imported_count = 0  # 設定更新失敗時は成功数を0にリセット
            
            # 結果作成
            import_result = ImportResult(
                success=imported_count > 0 and len(errors) == 0,
                imported_count=imported_count,
                failed_count=total_count - imported_count,
                errors=errors,
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


# Flask アプリケーション設定
def create_sync_api_app() -> Flask:
    """同期API用のFlaskアプリケーションを作成"""
    app = Flask(__name__)
    sync_api = UserSyncAPI()
    
    @app.route('/api/users/import', methods=['POST'])
    def import_users():
        """ユーザーデータインポート"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            result = sync_api.import_users(data)
            
            status_code = 200 if result.success else 400
            return jsonify(result.to_dict()), status_code
            
        except Exception as e:
            logger.error(f'Import API error: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/users/sync-status', methods=['GET'])
    def get_sync_status():
        """同期状況取得"""
        try:
            status = sync_api.get_sync_status()
            return jsonify(status), 200
            
        except Exception as e:
            logger.error(f'Sync status API error: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/users/sessions/bulk-login', methods=['POST'])
    def bulk_login():
        """一括ログイン実行"""
        try:
            result = sync_api.bulk_login_users()
            
            status_code = 200 if result.get("success", False) else 400
            return jsonify(result), status_code
            
        except Exception as e:
            logger.error(f'Bulk login API error: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/users/health', methods=['GET'])
    def health_check():
        """ヘルスチェック"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'user_sync_api'
        }), 200
    
    @app.route('/api/users/batches', methods=['GET'])
    def get_batch_info():
        """バッチ情報取得"""
        try:
            batch_info = sync_api.get_batch_info()
            return jsonify(batch_info), 200
            
        except Exception as e:
            logger.error(f'Batch info API error: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/users/batches/<batch_id>/login', methods=['POST'])
    def login_batch_users(batch_id):
        """指定バッチのユーザーで一括ログイン"""
        try:
            result = sync_api.login_batch(batch_id)
            
            status_code = 200 if result.get("success", False) else 400
            return jsonify(result), status_code
            
        except Exception as e:
            logger.error(f'Batch login API error: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/users/batches/<batch_id>', methods=['DELETE'])
    def remove_batch_users(batch_id):
        """指定バッチのユーザーを削除"""
        try:
            result = sync_api.remove_batch(batch_id)
            
            status_code = 200 if result.get("success", False) else 400
            return jsonify(result), status_code
            
        except Exception as e:
            logger.error(f'Batch removal API error: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/users/batches/<batch_id>/stats', methods=['GET'])
    def get_batch_stats(batch_id):
        """指定バッチのセッション統計取得"""
        try:
            from user_session_manager import get_user_session_manager
            
            manager = get_user_session_manager()
            stats = manager.get_batch_session_stats(batch_id)
            
            return jsonify(stats), 200
            
        except Exception as e:
            logger.error(f'Batch stats API error: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    # 設定管理エンドポイント
    @app.route('/api/config/templates', methods=['GET'])
    def list_config_templates():
        """利用可能な設定テンプレートのリストを取得"""
        try:
            templates = config_manager.get_user_creation_templates()
            template_list = []
            
            for name, template_config in templates.items():
                validation_result = config_manager._validate_user_creation_template(template_config)
                template_list.append({
                    "name": name,
                    "config": template_config,
                    "validation": validation_result,
                    "description": template_config.get("description", "説明なし")
                })
            
            return jsonify({
                'success': True,
                'templates': template_list
            }), 200
            
        except Exception as e:
            logger.error(f'Failed to list config templates: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/config/templates/<template_name>', methods=['GET'])
    def get_config_template(template_name):
        """指定された設定テンプレートを取得"""
        try:
            template = config_manager.get_user_creation_template(template_name)
            
            if not template:
                return jsonify({'error': f'Template "{template_name}" not found'}), 404
            
            validation_result = config_manager._validate_user_creation_template(template)
            
            return jsonify({
                'success': True,
                'template_name': template_name,
                'config': template,
                'validation': validation_result,
                'description': template.get("description", "説明なし")
            }), 200
            
        except Exception as e:
            logger.error(f'Failed to get config template: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/config/templates', methods=['POST'])
    def create_config_template():
        """新しい設定テンプレートを作成"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            template_name = data.get('name')
            if not template_name:
                return jsonify({'error': 'Template name is required'}), 400
            
            template_config = data.get('config', {})
            
            # テンプレートを追加
            success = config_manager.add_user_creation_template(template_name, template_config)
            
            if success:
                return jsonify({
                    'success': True,
                    'template_name': template_name,
                    'message': 'Template created successfully'
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to create template'
                }), 400
            
        except Exception as e:
            logger.error(f'Failed to create config template: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/config/templates/<template_name>', methods=['DELETE'])
    def delete_config_template(template_name):
        """設定テンプレートを削除"""
        try:
            success = config_manager.remove_user_creation_template(template_name)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Template "{template_name}" deleted successfully'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': f'Template "{template_name}" not found'
                }), 404
            
        except Exception as e:
            logger.error(f'Failed to delete config template: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/config/validate', methods=['POST'])
    def validate_config():
        """設定の妥当性を検証"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            validation_result = config_manager._validate_user_creation_template(data)
            
            return jsonify({
                'validation': validation_result,
                'config': data
            }), 200
            
        except Exception as e:
            logger.error(f'Config validation failed: {str(e)}')
            return jsonify({'error': f'Validation error: {str(e)}'}), 400
    
    @app.route('/api/config/bulk-user-management', methods=['GET'])
    def get_bulk_user_management_config():
        """一括ユーザー管理設定を取得"""
        try:
            bulk_config = config_manager.get_bulk_user_management_config()
            return jsonify({
                'success': True,
                'config': bulk_config
            }), 200
            
        except Exception as e:
            logger.error(f'Failed to get bulk user management config: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/config/bulk-user-management', methods=['PUT'])
    def update_bulk_user_management_config():
        """一括ユーザー管理設定を更新"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            success = config_manager.update_bulk_user_management_config(data)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Bulk user management config updated successfully'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update config'
                }), 400
            
        except Exception as e:
            logger.error(f'Failed to update bulk user management config: {str(e)}')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/users/cleanup', methods=['POST'])
    def cleanup_users():
        """
        テストユーザーのクリーンアップ（Main Applicationからの要求）
        要件 3.1, 3.3: バッチ単位削除、Load Testerからの削除
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            batch_id = data.get('batch_id')
            users_to_delete = data.get('users_to_delete', [])
            source = data.get('source', 'unknown')
            
            if not batch_id:
                return jsonify({'error': 'batch_id is required'}), 400
            
            logger.info(f"クリーンアップ要求受信: batch_id={batch_id}, source={source}, users={len(users_to_delete)}")
            
            # バッチのユーザーを削除
            result = sync_api.remove_batch(batch_id)
            
            # 個別ユーザーの削除も実行（念のため）
            additional_removed = 0
            if users_to_delete:
                for user_info in users_to_delete:
                    try:
                        username = user_info.get('username')
                        if username:
                            removed = sync_api.session_manager.remove_user_by_username(username)
                            if removed:
                                additional_removed += 1
                    except Exception as e:
                        logger.warning(f"個別ユーザー削除エラー {username}: {str(e)}")
            
            # 設定ファイルを更新
            remaining_users = sync_api.session_manager.get_test_users()
            sync_api.session_manager.update_test_users_config(remaining_users)
            
            total_removed = result.get('removed_count', 0) + additional_removed
            
            return jsonify({
                'success': True,
                'batch_id': batch_id,
                'removed_count': total_removed,
                'batch_removed': result.get('removed_count', 0),
                'individual_removed': additional_removed,
                'source': source,
                'cleanup_timestamp': datetime.utcnow().isoformat()
            }), 200
            
        except Exception as e:
            error_msg = f'Cleanup API error: {str(e)}'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': error_msg,
                'cleanup_timestamp': datetime.utcnow().isoformat()
            }), 500
    
    @app.route('/api/users/lifecycle/report', methods=['GET'])
    def get_lifecycle_report():
        """
        Load Tester側のライフサイクルレポートを取得
        要件 3.3: クリーンアップレポート生成機能
        """
        try:
            test_users = sync_api.session_manager.get_test_users()
            session_stats = sync_api.session_manager.get_session_stats()
            
            # バッチ別統計
            batch_stats = {}
            for user in test_users:
                batch_id = getattr(user, 'test_batch_id', 'unknown')
                if batch_id not in batch_stats:
                    batch_stats[batch_id] = {
                        'user_count': 0,
                        'enabled_count': 0,
                        'bulk_created_count': 0,
                        'usernames': []
                    }
                
                batch_stats[batch_id]['user_count'] += 1
                if user.enabled:
                    batch_stats[batch_id]['enabled_count'] += 1
                if getattr(user, 'is_bulk_created', False):
                    batch_stats[batch_id]['bulk_created_count'] += 1
                batch_stats[batch_id]['usernames'].append(user.username)
            
            # アクティブセッション統計
            active_sessions = session_stats.active_sessions
            total_sessions = session_stats.total_sessions
            
            return jsonify({
                'total_test_users': len(test_users),
                'total_batches': len(batch_stats),
                'batch_statistics': batch_stats,
                'session_statistics': {
                    'active_sessions': active_sessions,
                    'total_sessions': total_sessions,
                    'success_rate': session_stats.success_rate
                },
                'report_timestamp': datetime.utcnow().isoformat(),
                'system': 'load_tester'
            }), 200
            
        except Exception as e:
            error_msg = f'Lifecycle report API error: {str(e)}'
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500
    
    @app.route('/api/users/identify', methods=['POST'])
    def identify_users():
        """
        ユーザー識別機能（テストユーザーと本番ユーザーの区別）
        要件 3.2: テストユーザーと本番ユーザーの識別機能
        """
        try:
            data = request.get_json() or {}
            filter_criteria = data.get('filter_criteria', {})
            
            test_users = sync_api.session_manager.get_test_users()
            
            # フィルタリング
            filtered_users = test_users
            if 'batch_id' in filter_criteria:
                batch_id = filter_criteria['batch_id']
                filtered_users = [
                    user for user in test_users 
                    if getattr(user, 'test_batch_id', None) == batch_id
                ]
            
            # Load Testerでは全てテストユーザーとして扱う
            user_classification = {
                'test_users': [
                    {
                        'user_id': user.user_id,
                        'username': user.username,
                        'enabled': user.enabled,
                        'test_batch_id': getattr(user, 'test_batch_id', None),
                        'is_bulk_created': getattr(user, 'is_bulk_created', False),
                        'description': user.description
                    }
                    for user in filtered_users
                ],
                'production_users': [],  # Load Testerには本番ユーザーは存在しない
                'total_test_users': len(filtered_users),
                'total_production_users': 0,
                'identification_timestamp': datetime.utcnow().isoformat(),
                'system': 'load_tester'
            }
            
            return jsonify(user_classification), 200
            
        except Exception as e:
            error_msg = f'User identification API error: {str(e)}'
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500
    
    return app


if __name__ == '__main__':
    # スタンドアロン実行用
    app = create_sync_api_app()
    app.run(host='0.0.0.0', port=8080, debug=True)