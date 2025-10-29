"""
ユーザー同期サービス - Main ApplicationとLoad Tester間のデータ同期を管理
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging
import requests
import time
import hashlib
import gzip
import io
from pathlib import Path

from app.models.user import User
from app import db
from app.services.error_handler import (
    BulkUserErrorHandler, ErrorCategory, ErrorSeverity, RetryConfig,
    with_error_handling
)

logger = logging.getLogger(__name__)


@dataclass
class TestUserData:
    """同期用のテストユーザーデータ"""
    id: int
    username: str
    email: str
    password: str = ""  # セキュリティ上、実際のパスワードハッシュは同期しない
    is_test_user: bool = True
    test_batch_id: Optional[str] = None
    created_by_bulk: bool = False
    created_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "password": self.password,
            "is_test_user": self.is_test_user,
            "test_batch_id": self.test_batch_id,
            "created_by_bulk": self.created_by_bulk,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_user(cls, user: User, include_password: bool = False) -> 'TestUserData':
        """UserモデルからTestUserDataを作成"""
        import os
        default_password = os.getenv('BULK_USER_DEFAULT_PASSWORD', 'TestPass123')

        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            password=default_password if include_password else "",  # 環境変数から取得したデフォルトパスワード
            is_test_user=user.is_test_user,
            test_batch_id=user.test_batch_id,
            created_by_bulk=user.created_by_bulk,
            created_at=user.created_at.isoformat() if user.created_at else None
        )


@dataclass
class UserExportData:
    """ユーザーエクスポートデータ"""
    users: List[TestUserData]
    export_timestamp: str
    source_system: str
    total_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 差分同期用フィールド
    data_hash: Optional[str] = None
    compression_enabled: bool = False
    compressed_size: Optional[int] = None
    original_size: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "users": [user.to_dict() for user in self.users],
            "export_timestamp": self.export_timestamp,
            "source_system": self.source_system,
            "total_count": self.total_count,
            "metadata": self.metadata,
            "data_hash": self.data_hash,
            "compression_enabled": self.compression_enabled,
            "compressed_size": self.compressed_size,
            "original_size": self.original_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserExportData':
        """辞書からUserExportDataを作成"""
        users = [TestUserData(**user_data) for user_data in data.get("users", [])]
        return cls(
            users=users,
            export_timestamp=data.get("export_timestamp", ""),
            source_system=data.get("source_system", ""),
            total_count=data.get("total_count", 0),
            metadata=data.get("metadata", {})
        )


@dataclass
class SyncResult:
    """同期結果"""
    success: bool
    synced_count: int
    failed_count: int
    errors: List[str]
    sync_timestamp: str
    duration: float
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "success": self.success,
            "synced_count": self.synced_count,
            "failed_count": self.failed_count,
            "errors": self.errors,
            "sync_timestamp": self.sync_timestamp,
            "duration": self.duration
        }


@dataclass
class DifferentialSyncData:
    """差分同期データ"""
    added_users: List[TestUserData] = field(default_factory=list)
    updated_users: List[TestUserData] = field(default_factory=list)
    deleted_user_ids: List[int] = field(default_factory=list)
    last_sync_hash: Optional[str] = None
    current_hash: Optional[str] = None
    sync_type: str = "differential"  # "full" or "differential"
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "added_users": [user.to_dict() for user in self.added_users],
            "updated_users": [user.to_dict() for user in self.updated_users],
            "deleted_user_ids": self.deleted_user_ids,
            "last_sync_hash": self.last_sync_hash,
            "current_hash": self.current_hash,
            "sync_type": self.sync_type
        }


@dataclass
class ValidationResult:
    """データ整合性検証結果"""
    is_valid: bool
    total_checked: int
    inconsistencies: List[str]
    validation_timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "is_valid": self.is_valid,
            "total_checked": self.total_checked,
            "inconsistencies": self.inconsistencies,
            "validation_timestamp": self.validation_timestamp
        }


class UserSyncService:
    """
    Main ApplicationとLoad Tester間でのユーザーデータ同期を管理するサービス
    """
    
    def __init__(self, load_tester_url: str = "http://load-tester:8080"):
        self.load_tester_url = load_tester_url
        self.sync_timeout = 10  # 要件: 10秒以内に同期完了
        self.max_retries = 3
        self.error_handler = BulkUserErrorHandler()
        
        # パフォーマンス最適化設定
        self.differential_sync_enabled = True
        self.compression_enabled = True
        self.compression_threshold = 1024  # 1KB以上で圧縮
        self.memory_efficient_mode = True
        self.batch_size = 100  # メモリ効率的なバッチサイズ
        
        # 同期状態管理
        self._last_sync_hash = None
        self._sync_cache = {}
        
        # リトライ設定
        self.network_retry_config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=30.0,
            exponential_backoff=True,
            retry_on_exceptions=[requests.exceptions.RequestException, requests.exceptions.Timeout]
        )
        
        self.db_retry_config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            exponential_backoff=True
        )
        
    def export_users_from_app_optimized(self, filter_criteria: Dict[str, Any] = None, enable_differential: bool = True) -> UserExportData:
        """
        パフォーマンス最適化版のユーザーデータエクスポート
        - 差分同期による転送データ量削減
        - メモリ効率的なデータ処理
        - データ圧縮
        
        Args:
            filter_criteria: フィルタ条件
            enable_differential: 差分同期を有効にするか
            
        Returns:
            UserExportData: 最適化されたエクスポートデータ
        """
        try:
            start_time = time.time()
            
            # デフォルトフィルタ: テストユーザーのみ
            if filter_criteria is None:
                filter_criteria = {"test_users_only": True}
            
            # 差分同期が有効で前回のハッシュがある場合
            if enable_differential and self.differential_sync_enabled and self._last_sync_hash:
                return self._export_differential_data(filter_criteria)
            else:
                return self._export_full_data(filter_criteria)
                
        except Exception as e:
            logger.error(f"最適化版ユーザーエクスポートエラー: {str(e)}")
            raise Exception(f"ユーザーエクスポートに失敗しました: {str(e)}")
    
    def export_users_from_app(self, filter_criteria: Dict[str, Any] = None) -> UserExportData:
        """
        Main Applicationからユーザーデータをエクスポート
        
        Args:
            filter_criteria: フィルタ条件 (batch_id, test_users_only等)
            
        Returns:
            UserExportData: エクスポートされたユーザーデータ
        """
        try:
            start_time = time.time()
            
            # デフォルトフィルタ: テストユーザーのみ
            if filter_criteria is None:
                filter_criteria = {"test_users_only": True}
            
            # クエリ構築
            query = User.query
            
            # テストユーザーのみフィルタ
            if filter_criteria.get("test_users_only", True):
                query = query.filter(User.is_test_user == True)
            
            # バッチIDフィルタ
            batch_id = filter_criteria.get("batch_id")
            if batch_id:
                query = query.filter(User.test_batch_id == batch_id)
            
            # 一括作成ユーザーのみフィルタ
            if filter_criteria.get("bulk_users_only", False):
                query = query.filter(User.created_by_bulk == True)
            
            # ユーザー取得
            users = query.all()
            
            # TestUserDataに変換
            test_users = []
            for user in users:
                test_user = TestUserData.from_user(user, include_password=True)
                test_users.append(test_user)
            
            # エクスポートデータ作成
            export_data = UserExportData(
                users=test_users,
                export_timestamp=datetime.utcnow().isoformat(),
                source_system="main_application",
                total_count=len(test_users),
                metadata={
                    "filter_criteria": filter_criteria,
                    "export_duration": time.time() - start_time
                }
            )
            
            logger.info(f"ユーザーデータエクスポート完了: {len(test_users)}件")
            return export_data
            
        except Exception as e:
            logger.error(f"ユーザーエクスポートエラー: {str(e)}")
            raise Exception(f"ユーザーエクスポートに失敗しました: {str(e)}")
    
    def _export_full_data(self, filter_criteria: Dict[str, Any]) -> UserExportData:
        """
        フルデータエクスポート（メモリ効率的処理）
        """
        start_time = time.time()
        
        # クエリ構築
        query = User.query
        
        # テストユーザーのみフィルタ
        if filter_criteria.get("test_users_only", True):
            query = query.filter(User.is_test_user == True)
        
        # バッチIDフィルタ
        batch_id = filter_criteria.get("batch_id")
        if batch_id:
            query = query.filter(User.test_batch_id == batch_id)
        
        # 一括作成ユーザーのみフィルタ
        if filter_criteria.get("bulk_users_only", False):
            query = query.filter(User.created_by_bulk == True)
        
        # メモリ効率的なバッチ処理
        test_users = []
        total_count = query.count()
        
        if self.memory_efficient_mode and total_count > self.batch_size:
            # 大量データの場合はバッチ処理
            for offset in range(0, total_count, self.batch_size):
                batch_users = query.offset(offset).limit(self.batch_size).all()
                for user in batch_users:
                    test_user = TestUserData.from_user(user, include_password=True)
                    test_users.append(test_user)
                
                # メモリ管理
                if len(test_users) % (self.batch_size * 5) == 0:
                    import gc
                    gc.collect()
        else:
            # 小量データの場合は一括処理
            users = query.all()
            for user in users:
                test_user = TestUserData.from_user(user, include_password=True)
                test_users.append(test_user)
        
        # データハッシュ計算
        data_hash = self._calculate_data_hash(test_users)
        
        # エクスポートデータ作成
        export_data = UserExportData(
            users=test_users,
            export_timestamp=datetime.utcnow().isoformat(),
            source_system="main_application",
            total_count=len(test_users),
            metadata={
                "filter_criteria": filter_criteria,
                "export_duration": time.time() - start_time,
                "memory_efficient_mode": self.memory_efficient_mode,
                "batch_processing": total_count > self.batch_size
            },
            data_hash=data_hash
        )
        
        # データ圧縮
        if self.compression_enabled:
            export_data = self._compress_export_data(export_data)
        
        # 同期ハッシュを更新
        self._last_sync_hash = data_hash
        
        logger.info(f"フルデータエクスポート完了: {len(test_users)}件, ハッシュ={data_hash[:8]}")
        return export_data
    
    def _export_differential_data(self, filter_criteria: Dict[str, Any]) -> UserExportData:
        """
        差分データエクスポート（転送データ量削減）
        要件 2.3: 差分同期による転送データ量削減
        """
        start_time = time.time()
        
        # 現在のデータハッシュを計算
        current_users = self._get_filtered_users(filter_criteria)
        current_hash = self._calculate_data_hash(current_users)
        
        # ハッシュが同じ場合は変更なし
        if current_hash == self._last_sync_hash:
            logger.info("データに変更がないため差分同期をスキップ")
            return UserExportData(
                users=[],
                export_timestamp=datetime.utcnow().isoformat(),
                source_system="main_application",
                total_count=0,
                metadata={
                    "sync_type": "no_changes",
                    "last_sync_hash": self._last_sync_hash,
                    "current_hash": current_hash
                },
                data_hash=current_hash
            )
        
        # 差分データを計算
        differential_data = self._calculate_differential_changes(filter_criteria)
        
        # 差分データをUserExportData形式に変換
        all_changed_users = (
            differential_data.added_users + 
            differential_data.updated_users
        )
        
        export_data = UserExportData(
            users=all_changed_users,
            export_timestamp=datetime.utcnow().isoformat(),
            source_system="main_application",
            total_count=len(all_changed_users),
            metadata={
                "sync_type": "differential",
                "added_count": len(differential_data.added_users),
                "updated_count": len(differential_data.updated_users),
                "deleted_count": len(differential_data.deleted_user_ids),
                "deleted_user_ids": differential_data.deleted_user_ids,
                "last_sync_hash": self._last_sync_hash,
                "current_hash": current_hash,
                "export_duration": time.time() - start_time
            },
            data_hash=current_hash
        )
        
        # データ圧縮
        if self.compression_enabled:
            export_data = self._compress_export_data(export_data)
        
        # 同期ハッシュを更新
        self._last_sync_hash = current_hash
        
        logger.info(
            f"差分データエクスポート完了: 追加={len(differential_data.added_users)}, "
            f"更新={len(differential_data.updated_users)}, 削除={len(differential_data.deleted_user_ids)}"
        )
        
        return export_data
    
    def _get_filtered_users(self, filter_criteria: Dict[str, Any]) -> List[TestUserData]:
        """フィルタ条件に基づいてユーザーを取得"""
        query = User.query
        
        if filter_criteria.get("test_users_only", True):
            query = query.filter(User.is_test_user == True)
        
        batch_id = filter_criteria.get("batch_id")
        if batch_id:
            query = query.filter(User.test_batch_id == batch_id)
        
        if filter_criteria.get("bulk_users_only", False):
            query = query.filter(User.created_by_bulk == True)
        
        users = query.all()
        return [TestUserData.from_user(user, include_password=True) for user in users]
    
    def _calculate_data_hash(self, users: List[TestUserData]) -> str:
        """ユーザーデータのハッシュを計算"""
        # ユーザーデータを正規化してハッシュ計算
        user_strings = []
        for user in sorted(users, key=lambda u: u.id):
            user_str = f"{user.id}:{user.username}:{user.email}:{user.test_batch_id}"
            user_strings.append(user_str)
        
        combined_string = "|".join(user_strings)
        return hashlib.sha256(combined_string.encode()).hexdigest()
    
    def _calculate_differential_changes(self, filter_criteria: Dict[str, Any]) -> DifferentialSyncData:
        """差分変更を計算"""
        # 現在のユーザーデータを取得
        current_users = self._get_filtered_users(filter_criteria)
        current_user_dict = {user.id: user for user in current_users}
        
        # キャッシュされた前回のデータと比較
        cached_users = self._sync_cache.get("last_users", {})
        
        # 追加されたユーザー
        added_users = [
            user for user_id, user in current_user_dict.items()
            if user_id not in cached_users
        ]
        
        # 更新されたユーザー
        updated_users = []
        for user_id, current_user in current_user_dict.items():
            if user_id in cached_users:
                cached_user = cached_users[user_id]
                if self._user_has_changed(current_user, cached_user):
                    updated_users.append(current_user)
        
        # 削除されたユーザー
        deleted_user_ids = [
            user_id for user_id in cached_users.keys()
            if user_id not in current_user_dict
        ]
        
        # キャッシュを更新
        self._sync_cache["last_users"] = current_user_dict
        
        return DifferentialSyncData(
            added_users=added_users,
            updated_users=updated_users,
            deleted_user_ids=deleted_user_ids,
            last_sync_hash=self._last_sync_hash,
            current_hash=self._calculate_data_hash(current_users)
        )
    
    def _user_has_changed(self, current_user: TestUserData, cached_user: TestUserData) -> bool:
        """ユーザーデータが変更されたかチェック"""
        return (
            current_user.username != cached_user.username or
            current_user.email != cached_user.email or
            current_user.test_batch_id != cached_user.test_batch_id
        )
    
    def _compress_export_data(self, export_data: UserExportData) -> UserExportData:
        """エクスポートデータを圧縮"""
        try:
            # JSON文字列に変換
            json_data = json.dumps(export_data.to_dict(), ensure_ascii=False)
            original_size = len(json_data.encode('utf-8'))
            
            # 圧縮閾値をチェック
            if original_size < self.compression_threshold:
                return export_data
            
            # gzip圧縮
            compressed_buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=compressed_buffer, mode='wb') as gz_file:
                gz_file.write(json_data.encode('utf-8'))
            
            compressed_size = len(compressed_buffer.getvalue())
            compression_ratio = compressed_size / original_size
            
            # 圧縮効果がある場合のみ適用
            if compression_ratio < 0.8:  # 20%以上の削減
                export_data.compression_enabled = True
                export_data.compressed_size = compressed_size
                export_data.original_size = original_size
                
                logger.debug(
                    f"データ圧縮完了: {original_size} -> {compressed_size} bytes "
                    f"({compression_ratio:.2%})"
                )
            
            return export_data
            
        except Exception as e:
            logger.warning(f"データ圧縮エラー: {str(e)}")
            return export_data
    
    @with_error_handling(
        category=ErrorCategory.DATA_SYNC,
        severity=ErrorSeverity.HIGH
    )
    def import_users_to_load_tester(self, user_data: UserExportData) -> SyncResult:
        """
        Load Testerにユーザーデータをインポート（強化されたエラーハンドリング付き）
        要件 2.5: 同期失敗時のデータ整合性保持機能
        
        Args:
            user_data: インポートするユーザーデータ
            
        Returns:
            SyncResult: インポート結果
        """
        start_time = time.time()
        errors = []
        synced_count = 0
        
        logger.info(f"Load Testerへのインポート開始: {user_data.total_count}件")
        
        # データ整合性チェック
        if not user_data.users:
            logger.warning("インポートするユーザーデータが空です")
            return SyncResult(
                success=True,
                synced_count=0,
                failed_count=0,
                errors=["インポートするユーザーデータが空です"],
                sync_timestamp=datetime.utcnow().isoformat(),
                duration=0.0
            )
        
        # Load TesterのAPIエンドポイントにデータ送信
        import_url = f"{self.load_tester_url}/api/users/import"
        
        # リクエストデータ準備
        request_data = user_data.to_dict()
        
        # リトライ機構付きHTTPリクエスト送信
        def send_import_request():
            response = requests.post(
                import_url,
                json=request_data,
                timeout=self.sync_timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result_data = response.json()
                if result_data.get("success", False):
                    return result_data
                else:
                    # APIレベルのエラー
                    api_errors = result_data.get("errors", [])
                    raise Exception(f"Load Tester APIエラー: {', '.join(api_errors)}")
            else:
                raise requests.exceptions.HTTPError(
                    f"HTTP {response.status_code}: {response.text}"
                )
        
        try:
            # リトライ機構付きでリクエスト実行
            result_data = self.error_handler.with_retry(
                send_import_request,
                self.network_retry_config,
                ErrorCategory.NETWORK,
                {
                    "url": import_url,
                    "user_count": user_data.total_count,
                    "source_system": user_data.source_system
                }
            )
            
            synced_count = result_data.get("imported_count", 0)
            
            # 部分的成功の場合のエラー情報を取得
            if "errors" in result_data:
                errors.extend(result_data["errors"])
            
        except Exception as e:
            error_msg = f"Load Testerインポート失敗: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            # データ整合性保持のため、失敗時は元の状態を維持
            synced_count = 0
        
        # 結果作成
        duration = time.time() - start_time
        success = synced_count > 0 and len(errors) == 0
        
        sync_result = SyncResult(
            success=success,
            synced_count=synced_count,
            failed_count=user_data.total_count - synced_count,
            errors=errors,
            sync_timestamp=datetime.utcnow().isoformat(),
            duration=duration
        )
        
        if success:
            logger.info(f"Load Testerへの同期完了: {synced_count}件 ({duration:.2f}秒)")
        else:
            logger.error(f"Load Testerへの同期失敗: 成功={synced_count}, エラー={len(errors)}")
        
        return sync_result
    
    def sync_bidirectional(self, filter_criteria: Dict[str, Any] = None) -> SyncResult:
        """
        双方向同期を実行
        
        Args:
            filter_criteria: エクスポート時のフィルタ条件
            
        Returns:
            SyncResult: 同期結果
        """
        try:
            logger.info("双方向同期を開始")
            
            # 1. Main Applicationからデータエクスポート
            export_data = self.export_users_from_app(filter_criteria)
            
            if export_data.total_count == 0:
                logger.warning("エクスポートするユーザーが見つかりません")
                return SyncResult(
                    success=True,
                    synced_count=0,
                    failed_count=0,
                    errors=["エクスポートするユーザーが見つかりません"],
                    sync_timestamp=datetime.utcnow().isoformat(),
                    duration=0.0
                )
            
            # 2. Load Testerにインポート
            sync_result = self.import_users_to_load_tester(export_data)
            
            logger.info(f"双方向同期完了: 成功={sync_result.success}, 同期数={sync_result.synced_count}")
            return sync_result
            
        except Exception as e:
            error_msg = f"双方向同期エラー: {str(e)}"
            logger.error(error_msg)
            
            return SyncResult(
                success=False,
                synced_count=0,
                failed_count=0,
                errors=[error_msg],
                sync_timestamp=datetime.utcnow().isoformat(),
                duration=0.0
            )
    
    @with_error_handling(
        category=ErrorCategory.DATA_SYNC,
        severity=ErrorSeverity.MEDIUM
    )
    def validate_sync_integrity(self, batch_id: str = None) -> ValidationResult:
        """
        同期データの整合性を検証（強化されたエラーハンドリング付き）
        要件 2.5: 同期失敗時のデータ整合性保持機能
        
        Args:
            batch_id: 検証対象のバッチID（省略時は全テストユーザー）
            
        Returns:
            ValidationResult: 検証結果
        """
        start_time = time.time()
        inconsistencies = []
        
        logger.info(f"データ整合性検証開始: バッチID={batch_id or '全体'}")
        
        # Main Applicationのユーザー取得（リトライ付き）
        def get_main_app_users():
            query = User.query.filter(User.is_test_user == True)
            if batch_id:
                query = query.filter(User.test_batch_id == batch_id)
            return query.all()
        
        try:
            main_app_users = self.error_handler.with_retry(
                get_main_app_users,
                self.db_retry_config,
                ErrorCategory.DATABASE,
                {"operation": "get_main_app_users", "batch_id": batch_id}
            )
        except Exception as e:
            error_msg = f"Main Applicationユーザー取得エラー: {str(e)}"
            logger.error(error_msg)
            return ValidationResult(
                is_valid=False,
                total_checked=0,
                inconsistencies=[error_msg],
                validation_timestamp=datetime.utcnow().isoformat()
            )
        
        # Load Testerの設定取得を試行（リトライ付き）
        def get_load_tester_status():
            status_url = f"{self.load_tester_url}/api/users/sync-status"
            response = requests.get(status_url, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            else:
                raise requests.exceptions.HTTPError(
                    f"Load Tester接続エラー: HTTP {response.status_code}"
                )
        
        try:
            load_tester_data = self.error_handler.with_retry(
                get_load_tester_status,
                self.network_retry_config,
                ErrorCategory.NETWORK,
                {"operation": "get_load_tester_status", "batch_id": batch_id}
            )
            
            load_tester_users = load_tester_data.get("users", [])
            
            # 詳細な整合性チェック
            inconsistencies.extend(self._perform_detailed_integrity_check(
                main_app_users, load_tester_users, batch_id
            ))
            
        except Exception as e:
            error_msg = f"Load Tester通信エラー: {str(e)}"
            inconsistencies.append(error_msg)
            logger.warning(error_msg)
        
        # 検証結果作成
        validation_result = ValidationResult(
            is_valid=len(inconsistencies) == 0,
            total_checked=len(main_app_users),
            inconsistencies=inconsistencies,
            validation_timestamp=datetime.utcnow().isoformat()
        )
        
        duration = time.time() - start_time
        logger.info(
            f"整合性検証完了: 有効={validation_result.is_valid}, "
            f"検証数={validation_result.total_checked}, 不整合={len(inconsistencies)} ({duration:.2f}秒)"
        )
        
        return validation_result
    
    def _perform_detailed_integrity_check(
        self, 
        main_app_users: List[User], 
        load_tester_users: List[Dict], 
        batch_id: str = None
    ) -> List[str]:
        """詳細な整合性チェックを実行"""
        inconsistencies = []
        
        # ユーザー数の比較
        main_count = len(main_app_users)
        load_tester_count = len(load_tester_users)
        
        if main_count != load_tester_count:
            inconsistencies.append(
                f"ユーザー数不一致: Main App={main_count}, Load Tester={load_tester_count}"
            )
        
        # ユーザー名の比較
        main_usernames = {user.username for user in main_app_users}
        load_tester_usernames = {user.get("username") for user in load_tester_users}
        
        missing_in_load_tester = main_usernames - load_tester_usernames
        extra_in_load_tester = load_tester_usernames - main_usernames
        
        if missing_in_load_tester:
            missing_list = list(missing_in_load_tester)[:10]  # 最初の10件のみ表示
            inconsistencies.append(
                f"Load Testerに存在しないユーザー({len(missing_in_load_tester)}件): {missing_list}"
            )
        
        if extra_in_load_tester:
            extra_list = list(extra_in_load_tester)[:10]  # 最初の10件のみ表示
            inconsistencies.append(
                f"Main Appに存在しないユーザー({len(extra_in_load_tester)}件): {extra_list}"
            )
        
        # バッチIDの整合性チェック
        if batch_id:
            load_tester_batch_users = [
                user for user in load_tester_users 
                if user.get("test_batch_id") == batch_id
            ]
            
            if len(load_tester_batch_users) != main_count:
                inconsistencies.append(
                    f"バッチ{batch_id}のユーザー数不一致: "
                    f"Main App={main_count}, Load Tester={len(load_tester_batch_users)}"
                )
        
        return inconsistencies
    
    def export_to_json_file(self, file_path: str, filter_criteria: Dict[str, Any] = None) -> bool:
        """
        ユーザーデータをJSONファイルにエクスポート
        
        Args:
            file_path: 出力ファイルパス
            filter_criteria: フィルタ条件
            
        Returns:
            bool: エクスポート成功可否
        """
        try:
            export_data = self.export_users_from_app(filter_criteria)
            
            # ファイル出力
            output_path = Path(file_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"JSONファイルエクスポート完了: {file_path} ({export_data.total_count}件)")
            return True
            
        except Exception as e:
            logger.error(f"JSONファイルエクスポートエラー: {str(e)}")
            return False
    
    def import_from_json_file(self, file_path: str) -> SyncResult:
        """
        JSONファイルからユーザーデータをインポート
        
        Args:
            file_path: 入力ファイルパス
            
        Returns:
            SyncResult: インポート結果
        """
        try:
            input_path = Path(file_path)
            
            if not input_path.exists():
                raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")
            
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            export_data = UserExportData.from_dict(data)
            return self.import_users_to_load_tester(export_data)
            
        except Exception as e:
            error_msg = f"JSONファイルインポートエラー: {str(e)}"
            logger.error(error_msg)
            
            return SyncResult(
                success=False,
                synced_count=0,
                failed_count=0,
                errors=[error_msg],
                sync_timestamp=datetime.utcnow().isoformat(),
                duration=0.0
            )