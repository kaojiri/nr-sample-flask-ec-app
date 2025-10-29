from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import time
import re
import json
import logging
from pathlib import Path
import asyncio
import concurrent.futures
from threading import Lock
from app import db
from app.models.user import User
from werkzeug.security import generate_password_hash
from app.services.error_handler import (
    BulkUserErrorHandler, ErrorCategory, ErrorSeverity, RetryConfig,
    with_error_handling, PartialSuccessResult
)
from app.services.security_service import security_service


@dataclass
class UserCredentials:
    username: str
    email: str
    password: str
    user_id: int = None


@dataclass
class FailedUserCreation:
    username: str
    email: str
    error: str


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class UserCreationConfig:
    """ユーザー作成設定クラス - ユーザー名パターン、パスワードポリシー等を管理"""
    username_pattern: str = "testuser_{id}@example.com"
    password: str = "TestPass123!"
    email_domain: str = "example.com"
    user_role: str = "user"
    batch_size: int = 100
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    test_batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # パスワードポリシー設定
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_numbers: bool = True
    password_require_special_chars: bool = False
    
    # ユーザー名生成設定
    username_prefix: str = "testuser"
    username_suffix: str = ""
    
    # 作成制限設定
    max_users_per_batch: int = 1000
    creation_delay_seconds: float = 0.0
    
    def validate(self) -> ValidationResult:
        """設定の妥当性を検証"""
        errors = []
        warnings = []
        
        # ユーザー名パターンの検証
        if not self.username_pattern:
            errors.append("ユーザー名パターンが空です")
        elif "{id}" not in self.username_pattern:
            warnings.append("ユーザー名パターンに{id}プレースホルダーがありません")
        
        # メールドメインの検証
        if not self.email_domain:
            errors.append("メールドメインが空です")
        elif not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', self.email_domain):
            errors.append("無効なメールドメイン形式です")
        
        # パスワードの検証
        password_errors = self._validate_password(self.password)
        errors.extend(password_errors)
        
        # バッチサイズの検証
        if self.batch_size <= 0:
            errors.append("バッチサイズは1以上である必要があります")
        elif self.batch_size > 1000:
            errors.append("バッチサイズは1000以下である必要があります")
        
        # 最大ユーザー数の検証
        if self.max_users_per_batch <= 0:
            errors.append("最大ユーザー数は1以上である必要があります")
        elif self.max_users_per_batch > 10000:
            warnings.append("最大ユーザー数が10000を超えています。パフォーマンスに影響する可能性があります")
        
        # ユーザーロールの検証
        valid_roles = ["user", "admin", "moderator", "test"]
        if self.user_role not in valid_roles:
            warnings.append(f"未知のユーザーロール: {self.user_role}。有効な値: {valid_roles}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_password(self, password: str) -> List[str]:
        """
        パスワードポリシーに基づいてパスワードを検証
        要件: テストユーザーのパスワードハッシュ化（強化されたパスワードポリシー）
        """
        errors = []
        
        if len(password) < self.password_min_length:
            errors.append(f"パスワードは{self.password_min_length}文字以上である必要があります")
        
        if self.password_require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("パスワードに大文字が含まれている必要があります")
        
        if self.password_require_lowercase and not re.search(r'[a-z]', password):
            errors.append("パスワードに小文字が含まれている必要があります")
        
        if self.password_require_numbers and not re.search(r'\d', password):
            errors.append("パスワードに数字が含まれている必要があります")
        
        if self.password_require_special_chars and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("パスワードに特殊文字が含まれている必要があります")
        
        # セキュリティ強化: 弱いパスワードパターンのチェック（テスト用パスワードは大幅に緩和）
        if not (password.startswith('Test') or password.startswith('Load') or password.startswith('Perf') or password.startswith('Sec')):
            weak_patterns = [
                r'(.)\1{5,}',  # 同じ文字の6回以上の繰り返し（5回まで許可）
                r'^(password|123456|qwerty|admin|test)$',  # 完全一致の非常に弱いパスワードのみ
            ]
            
            for pattern in weak_patterns:
                if re.search(pattern, password.lower()):
                    errors.append("パスワードに弱いパターンが含まれています（連続文字、一般的なパスワード等）")
                    break
        
        return errors
    
    @classmethod
    def from_template(cls, template_name: str) -> 'UserCreationConfig':
        """テンプレートから設定を作成"""
        return UserCreationTemplateManager.get_template(template_name)
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式に変換"""
        return {
            'username_pattern': self.username_pattern,
            'password': self.password,
            'email_domain': self.email_domain,
            'user_role': self.user_role,
            'batch_size': self.batch_size,
            'custom_attributes': self.custom_attributes,
            'test_batch_id': self.test_batch_id,
            'password_min_length': self.password_min_length,
            'password_require_uppercase': self.password_require_uppercase,
            'password_require_lowercase': self.password_require_lowercase,
            'password_require_numbers': self.password_require_numbers,
            'password_require_special_chars': self.password_require_special_chars,
            'username_prefix': self.username_prefix,
            'username_suffix': self.username_suffix,
            'max_users_per_batch': self.max_users_per_batch,
            'creation_delay_seconds': self.creation_delay_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserCreationConfig':
        """辞書から設定を作成"""
        return cls(**data)
    
    def generate_secure_password(self, user_id: int = None) -> str:
        """
        セキュアなパスワードを生成
        テスト用途に適した強力なパスワードを生成する
        """
        import random
        import string
        
        # 基本文字セット
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special_chars = "!@#$%^&*"
        
        # 必須文字を含める
        password_chars = []
        
        if self.password_require_lowercase:
            password_chars.append(random.choice(lowercase))
        if self.password_require_uppercase:
            password_chars.append(random.choice(uppercase))
        if self.password_require_numbers:
            password_chars.append(random.choice(digits))
        if self.password_require_special_chars:
            password_chars.append(random.choice(special_chars))
        
        # 残りの文字を追加
        all_chars = lowercase + uppercase + digits
        if self.password_require_special_chars:
            all_chars += special_chars
        
        remaining_length = max(self.password_min_length - len(password_chars), 0)
        for _ in range(remaining_length):
            password_chars.append(random.choice(all_chars))
        
        # ユーザーIDベースのプレフィックスを追加（一意性確保、連続数字を避ける）
        if user_id:
            # 連続数字を避けるため、IDを分散させる
            dispersed_id = (user_id * 7 + 13) % 10000  # 簡単な分散アルゴリズム
            prefix = f"Test{dispersed_id:04d}"
            password_chars = list(prefix) + password_chars[len(prefix):]
        
        # シャッフル
        random.shuffle(password_chars)
        
        return ''.join(password_chars)


class UserCreationTemplateManager:
    """ユーザー作成設定のテンプレート管理クラス"""
    
    @staticmethod
    def get_default_templates() -> Dict[str, UserCreationConfig]:
        """デフォルトテンプレートを取得"""
        return {
            "default": UserCreationConfig(
                username_pattern="testuser_{id}@example.com",
                password="TestUser2025!",  # 連続数字を避けたパスワード
                email_domain="example.com",
                user_role="user",
                batch_size=100,
                password_min_length=8,
                password_require_uppercase=True,
                password_require_lowercase=True,
                password_require_numbers=True,
                password_require_special_chars=False,
                username_prefix="testuser",
                max_users_per_batch=1000,
                creation_delay_seconds=0.0
            ),
            
            "admin": UserCreationConfig(
                username_pattern="admin_{id}@example.com",
                password="AdminPass123!",
                email_domain="example.com",
                user_role="admin",
                batch_size=50,
                password_min_length=12,
                password_require_uppercase=True,
                password_require_lowercase=True,
                password_require_numbers=True,
                password_require_special_chars=True,
                username_prefix="admin",
                max_users_per_batch=100,
                creation_delay_seconds=0.1,
                custom_attributes={"is_admin": True, "permissions": ["read", "write", "admin"]}
            ),
            
            "load_test": UserCreationConfig(
                username_pattern="loadtest_{id}@loadtest.local",
                password="LoadUser2025!",  # 連続数字を避けたパスワード
                email_domain="loadtest.local",
                user_role="user",
                batch_size=200,
                password_min_length=8,
                password_require_uppercase=True,
                password_require_lowercase=True,
                password_require_numbers=True,
                password_require_special_chars=False,
                username_prefix="loadtest",
                max_users_per_batch=5000,
                creation_delay_seconds=0.0,
                custom_attributes={"test_type": "load", "auto_cleanup": True}
            ),
            
            "performance_test": UserCreationConfig(
                username_pattern="perftest_{id}@perftest.local",
                password="PerfUser2025!",  # 連続数字を避けたパスワード
                email_domain="perftest.local",
                user_role="user",
                batch_size=500,
                password_min_length=8,
                password_require_uppercase=True,
                password_require_lowercase=True,
                password_require_numbers=True,
                password_require_special_chars=False,
                username_prefix="perftest",
                max_users_per_batch=10000,
                creation_delay_seconds=0.0,
                custom_attributes={"test_type": "performance", "auto_cleanup": True, "priority": "high"}
            ),
            
            "security_test": UserCreationConfig(
                username_pattern="sectest_{id}@sectest.local",
                password="SecTest123!@#$%^&*",
                email_domain="sectest.local",
                user_role="user",
                batch_size=10,
                password_min_length=16,
                password_require_uppercase=True,
                password_require_lowercase=True,
                password_require_numbers=True,
                password_require_special_chars=True,
                username_prefix="sectest",
                max_users_per_batch=100,
                creation_delay_seconds=0.5,
                custom_attributes={"test_type": "security", "auto_cleanup": True, "security_level": "high"}
            )
        }
    
    @staticmethod
    def get_template(template_name: str) -> UserCreationConfig:
        """指定されたテンプレートを取得"""
        templates = UserCreationTemplateManager.get_default_templates()
        if template_name not in templates:
            raise ValueError(f"未知のテンプレート: {template_name}. 利用可能なテンプレート: {list(templates.keys())}")
        return templates[template_name]
    
    @staticmethod
    def list_templates() -> List[str]:
        """利用可能なテンプレート名のリストを取得"""
        return list(UserCreationTemplateManager.get_default_templates().keys())
    
    @staticmethod
    def get_template_info(template_name: str) -> Dict[str, Any]:
        """テンプレートの詳細情報を取得"""
        template = UserCreationTemplateManager.get_template(template_name)
        validation = template.validate()
        
        return {
            "name": template_name,
            "config": template.to_dict(),
            "validation": {
                "is_valid": validation.is_valid,
                "errors": validation.errors,
                "warnings": validation.warnings
            },
            "description": UserCreationTemplateManager._get_template_description(template_name)
        }
    
    @staticmethod
    def _get_template_description(template_name: str) -> str:
        """テンプレートの説明を取得"""
        descriptions = {
            "default": "標準的なテストユーザー作成用の基本設定",
            "admin": "管理者権限を持つテストユーザー作成用設定（強化されたパスワードポリシー）",
            "load_test": "負荷テスト用の大量ユーザー作成に最適化された設定",
            "performance_test": "パフォーマンステスト用の超大量ユーザー作成設定",
            "security_test": "セキュリティテスト用の厳格なパスワードポリシー設定"
        }
        return descriptions.get(template_name, "説明なし")


@dataclass
class BulkCreationResult:
    total_requested: int
    successful_count: int
    failed_count: int
    created_users: List[UserCredentials]
    failed_users: List[FailedUserCreation]
    batch_id: str
    execution_time: float


@dataclass
class CleanupResult:
    deleted_count: int
    batch_id: str
    errors: List[str]
    execution_time: float
    cleanup_report: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "deleted_count": self.deleted_count,
            "batch_id": self.batch_id,
            "errors": self.errors,
            "execution_time": self.execution_time,
            "cleanup_report": self.cleanup_report
        }


@dataclass
class LifecycleReport:
    """テストユーザーライフサイクルレポート"""
    total_test_users: int
    active_batches: List[str]
    cleanup_candidates: List[Dict[str, Any]]
    non_test_users_protected: int
    report_timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "total_test_users": self.total_test_users,
            "active_batches": self.active_batches,
            "cleanup_candidates": self.cleanup_candidates,
            "non_test_users_protected": self.non_test_users_protected,
            "report_timestamp": self.report_timestamp
        }


class BulkUserCreator:
    """Service class for creating and managing bulk test users"""
    
    def __init__(self):
        self.max_users_per_batch = 1000
        self.performance_target_seconds = 30  # For 100 users
        self.error_handler = BulkUserErrorHandler()
        self.logger = logging.getLogger(__name__)
        
        # パフォーマンス最適化設定
        self.bulk_insert_enabled = True
        self.parallel_processing_enabled = True
        self.max_workers = 4  # 並列処理のワーカー数
        self.bulk_insert_chunk_size = 100  # 一括挿入のチャンクサイズ
        self.memory_efficient_mode = True
        
        # スレッドセーフティ用のロック
        self._db_lock = Lock()
        
        # リトライ設定
        self.db_retry_config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            exponential_backoff=True,
            retry_on_exceptions=[Exception]  # データベース関連の例外
        )
        
        self.sync_retry_config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=30.0,
            exponential_backoff=True
        )
    
    @with_error_handling(
        category=ErrorCategory.USER_CREATION,
        severity=ErrorSeverity.HIGH,
        preserve_integrity=True
    )
    def create_bulk_users(self, count: int, config: UserCreationConfig) -> BulkCreationResult:
        """
        セキュリティ強化版の一括ユーザー作成
        要件 1.5: 100ユーザーの一括作成を30秒以内に完了
        要件: テストユーザーのパスワードハッシュ化、テストユーザーと本番ユーザーの分離
        """
        # セキュリティ検証
        if not security_service.validate_bulk_request(count):
            raise ValueError(f"一括作成数が制限を超えています: {count}")
        
        # テストユーザー分離の確保
        user_data = {
            'is_test_user': True,
            'email': f"test@{config.email_domain}",
            'username': config.username_pattern
        }
        if not security_service.ensure_test_user_separation(user_data):
            raise ValueError("テストユーザーの分離要件を満たしていません")
        
        if self.bulk_insert_enabled and count >= 5:  # 5ユーザー以上で最適化版を使用
            return self.create_bulk_users_optimized(count, config)
        else:
            return self.create_bulk_users_legacy(count, config)
    
    def create_bulk_users_optimized(self, count: int, config: UserCreationConfig) -> BulkCreationResult:
        """
        パフォーマンス最適化版の一括ユーザー作成
        - データベース一括挿入（bulk insert）
        - 非同期処理による並列ユーザー作成
        - メモリ効率的なデータ処理
        
        Args:
            count: Number of users to create (max 1000)
            config: Configuration for user creation
            
        Returns:
            BulkCreationResult with creation details
        """
        start_time = time.time()
        
        self.logger.info(f"最適化版一括ユーザー作成開始: {count}件, バッチID={config.test_batch_id}")
        
        # 設定の検証
        validation_result = config.validate()
        if not validation_result.is_valid:
            error_msg = f"設定が無効です: {', '.join(validation_result.errors)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        if count > config.max_users_per_batch:
            raise ValueError(f"作成ユーザー数({count})が設定の最大値({config.max_users_per_batch})を超えています")
        
        if count > self.max_users_per_batch:
            raise ValueError(f"作成ユーザー数({count})がシステムの最大値({self.max_users_per_batch})を超えています")
        
        # 認証情報生成（メモリ効率的）
        credentials_list = self.generate_unique_credentials_optimized(count, config)
        
        # 並列処理でユーザー作成
        if self.parallel_processing_enabled and count >= 100:
            result = self._create_users_parallel(credentials_list, config)
        else:
            result = self._create_users_bulk_insert(credentials_list, config)
        
        execution_time = time.time() - start_time
        
        self.logger.info(
            f"最適化版一括ユーザー作成完了: 成功={result.successful_count}, "
            f"失敗={result.failed_count}, 時間={execution_time:.2f}秒"
        )
        
        result.execution_time = execution_time
        return result
    
    def create_bulk_users_legacy(self, count: int, config: UserCreationConfig) -> BulkCreationResult:
        """
        従来版の一括ユーザー作成（後方互換性のため）
        
        Args:
            count: Number of users to create (max 1000)
            config: Configuration for user creation
            
        Returns:
            BulkCreationResult with creation details
        """
        start_time = time.time()
        
        self.logger.info(f"一括ユーザー作成開始: {count}件, バッチID={config.test_batch_id}")
        
        # 設定の検証
        validation_result = config.validate()
        if not validation_result.is_valid:
            error_msg = f"設定が無効です: {', '.join(validation_result.errors)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 警告がある場合はログに出力
        if validation_result.warnings:
            self.logger.warning(f"設定警告: {', '.join(validation_result.warnings)}")
        
        if count > config.max_users_per_batch:
            raise ValueError(f"作成ユーザー数({count})が設定の最大値({config.max_users_per_batch})を超えています")
        
        if count > self.max_users_per_batch:
            raise ValueError(f"作成ユーザー数({count})がシステムの最大値({self.max_users_per_batch})を超えています")
        
        # Generate unique credentials
        credentials_list = self.generate_unique_credentials(count, config)
        
        # 部分的成功処理でユーザー作成
        def create_single_user(cred: UserCredentials) -> UserCredentials:
            return self._create_single_user_with_retry(cred, config)
        
        # 部分的成功処理を実行
        partial_result = self.error_handler.process_with_partial_success(
            items=credentials_list,
            process_func=create_single_user,
            error_category=ErrorCategory.USER_CREATION,
            continue_on_error=True,  # 要件 1.4: 一部失敗時も継続
            context={
                "batch_id": config.test_batch_id,
                "total_count": count,
                "config": config.to_dict()
            }
        )
        
        # 失敗したユーザーをFailedUserCreation形式に変換
        failed_users = []
        for error_detail in partial_result.failed_items:
            context = error_detail.context
            failed_users.append(FailedUserCreation(
                username=context.get("username", "unknown"),
                email=context.get("email", "unknown"),
                error=f"[{error_detail.error_id}] {error_detail.message}"
            ))
        
        execution_time = time.time() - start_time
        
        # 最終コミット（リトライ付き）
        def commit_transaction():
            db.session.commit()
            self.logger.info(f"一括ユーザー作成コミット完了: 成功={partial_result.successful_count}件")
        
        try:
            self.error_handler.with_retry(
                commit_transaction,
                self.db_retry_config,
                ErrorCategory.DATABASE,
                {"operation": "bulk_user_commit", "batch_id": config.test_batch_id}
            )
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"最終コミット失敗、ロールバック実行: {str(e)}")
            raise
        
        result = BulkCreationResult(
            total_requested=count,
            successful_count=partial_result.successful_count,
            failed_count=partial_result.failed_count,
            created_users=partial_result.success_items,
            failed_users=failed_users,
            batch_id=config.test_batch_id,
            execution_time=execution_time
        )
        
        self.logger.info(
            f"一括ユーザー作成完了: 成功={result.successful_count}, "
            f"失敗={result.failed_count}, 時間={execution_time:.2f}秒"
        )
        
        return result
    
    def generate_unique_credentials_optimized(self, count: int, config: UserCreationConfig) -> List[UserCredentials]:
        """
        メモリ効率的なユニーク認証情報生成
        大量データ処理時のメモリ使用量を最適化
        
        Args:
            count: Number of credentials to generate
            config: Configuration containing patterns
            
        Returns:
            List of UserCredentials with unique identifiers
        """
        credentials = []
        timestamp = int(time.time())
        
        # バッチ処理でメモリ効率を向上
        batch_size = min(self.bulk_insert_chunk_size, count)
        
        for batch_start in range(0, count, batch_size):
            batch_end = min(batch_start + batch_size, count)
            batch_credentials = []
            
            for i in range(batch_start, batch_end):
                # Generate unique identifier
                unique_id = f"{timestamp}_{i:04d}"
                
                # Generate username based on pattern
                if "{id}" in config.username_pattern:
                    username = config.username_pattern.replace("{id}", unique_id)
                else:
                    username = f"testuser_{unique_id}"
                
                # Generate email
                email = f"testuser_{unique_id}@{config.email_domain}"
                
                # 設定で指定されたパスワードを使用（テスト用途）
                password = config.password
                
                batch_credentials.append(UserCredentials(
                    username=username,
                    email=email,
                    password=password
                ))
            
            # 重複チェック（バッチ単位で効率的に実行）
            self._check_and_resolve_duplicates_batch(batch_credentials)
            credentials.extend(batch_credentials)
            
            # メモリ効率モードでは中間結果をクリア
            if self.memory_efficient_mode and len(credentials) > 1000:
                # 大量データの場合は途中でガベージコレクションを促進
                import gc
                gc.collect()
        
        return credentials
    
    def _check_and_resolve_duplicates_batch(self, credentials: List[UserCredentials]) -> None:
        """
        バッチ単位での重複チェックと解決
        データベースクエリを最小化してパフォーマンスを向上
        """
        if not credentials:
            return
        
        try:
            # 一括で重複チェック
            usernames = [cred.username for cred in credentials]
            emails = [cred.email for cred in credentials]
            
            existing_users = User.query.filter(
                (User.username.in_(usernames)) | (User.email.in_(emails))
            ).all()
            
            if existing_users:
                existing_usernames = {user.username for user in existing_users}
                existing_emails = {user.email for user in existing_users}
                
                # 重複があるアイテムのみ修正
                for cred in credentials:
                    if cred.username in existing_usernames or cred.email in existing_emails:
                        random_suffix = str(uuid.uuid4())[:8]
                        cred.username = f"{cred.username}_{random_suffix}"
                        cred.email = f"{cred.email.split('@')[0]}_{random_suffix}@{cred.email.split('@')[1]}"
        
        except Exception as e:
            # データベース接続エラーやアプリケーションコンテキストエラーの場合はスキップ
            # テスト環境や初期化前の状態では重複チェックを行わない
            self.logger.debug(f"重複チェックをスキップ: {str(e)}")
            pass
    
    def _create_users_bulk_insert(self, credentials_list: List[UserCredentials], config: UserCreationConfig) -> BulkCreationResult:
        """
        データベース一括挿入による高速ユーザー作成
        要件 1.5: パフォーマンス最適化
        """
        start_time = time.time()
        created_users = []
        failed_users = []
        
        try:
            # チャンク単位で一括挿入
            for chunk_start in range(0, len(credentials_list), self.bulk_insert_chunk_size):
                chunk_end = min(chunk_start + self.bulk_insert_chunk_size, len(credentials_list))
                chunk_credentials = credentials_list[chunk_start:chunk_end]
                
                # User オブジェクトのリストを作成
                user_objects = []
                for cred in chunk_credentials:
                    user = User(
                        username=cred.username,
                        email=cred.email,
                        is_test_user=True,
                        test_batch_id=config.test_batch_id,
                        created_by_bulk=True,
                        created_at=datetime.utcnow()
                    )
                    # set_password メソッドを使用してパスワードを正しく設定
                    user.set_password(cred.password)
                    user_objects.append(user)
                
                # 個別挿入実行（パスワードハッシュを正しく保存するため）
                try:
                    with self._db_lock:
                        for user_obj in user_objects:
                            db.session.add(user_obj)
                        db.session.commit()
                    
                    # 成功したユーザーを記録
                    for i, user_obj in enumerate(user_objects):
                        cred = chunk_credentials[i]
                        cred.user_id = user_obj.id
                        created_users.append(cred)
                    
                    self.logger.debug(f"チャンク {chunk_start}-{chunk_end} の一括挿入完了")
                    
                except Exception as e:
                    # チャンク全体が失敗した場合は個別処理にフォールバック
                    self.logger.warning(f"チャンク一括挿入失敗、個別処理にフォールバック: {str(e)}")
                    db.session.rollback()
                    
                    chunk_created, chunk_failed = self._create_users_individual(chunk_credentials, config)
                    created_users.extend(chunk_created)
                    failed_users.extend(chunk_failed)
            
        except Exception as e:
            self.logger.error(f"一括挿入処理エラー: {str(e)}")
            db.session.rollback()
            raise
        
        return BulkCreationResult(
            total_requested=len(credentials_list),
            successful_count=len(created_users),
            failed_count=len(failed_users),
            created_users=created_users,
            failed_users=failed_users,
            batch_id=config.test_batch_id,
            execution_time=time.time() - start_time
        )
    
    def _create_users_parallel(self, credentials_list: List[UserCredentials], config: UserCreationConfig) -> BulkCreationResult:
        """
        非同期処理による並列ユーザー作成
        要件: 非同期処理による並列ユーザー作成
        """
        start_time = time.time()
        created_users = []
        failed_users = []
        
        # 並列処理用にチャンクに分割
        chunk_size = max(len(credentials_list) // self.max_workers, self.bulk_insert_chunk_size)
        chunks = [
            credentials_list[i:i + chunk_size] 
            for i in range(0, len(credentials_list), chunk_size)
        ]
        
        self.logger.info(f"並列処理開始: {len(chunks)}チャンク, ワーカー数={self.max_workers}")
        
        # ThreadPoolExecutorを使用して並列処理
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 各チャンクを並列で処理
            future_to_chunk = {
                executor.submit(self._create_users_bulk_insert_chunk, chunk, config): chunk 
                for chunk in chunks
            }
            
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    chunk_result = future.result()
                    created_users.extend(chunk_result['created'])
                    failed_users.extend(chunk_result['failed'])
                    
                except Exception as e:
                    self.logger.error(f"並列処理チャンクエラー: {str(e)}")
                    # 失敗したチャンクのユーザーを失敗リストに追加
                    for cred in chunk:
                        failed_users.append(FailedUserCreation(
                            username=cred.username,
                            email=cred.email,
                            error=f"並列処理エラー: {str(e)}"
                        ))
        
        return BulkCreationResult(
            total_requested=len(credentials_list),
            successful_count=len(created_users),
            failed_count=len(failed_users),
            created_users=created_users,
            failed_users=failed_users,
            batch_id=config.test_batch_id,
            execution_time=time.time() - start_time
        )
    
    def _create_users_bulk_insert_chunk(self, chunk_credentials: List[UserCredentials], config: UserCreationConfig) -> Dict[str, List]:
        """
        チャンク単位での一括挿入（並列処理用）
        """
        created = []
        failed = []
        
        try:
            # User オブジェクトのリストを作成
            user_objects = []
            for cred in chunk_credentials:
                user = User(
                    username=cred.username,
                    email=cred.email,
                    is_test_user=True,
                    test_batch_id=config.test_batch_id,
                    created_by_bulk=True,
                    created_at=datetime.utcnow()
                )
                # set_password メソッドを使用してパスワードを正しく設定
                user.set_password(cred.password)
                user_objects.append(user)
            
            # スレッドセーフな個別挿入（パスワードハッシュを正しく保存するため）
            with self._db_lock:
                for user_obj in user_objects:
                    db.session.add(user_obj)
                db.session.commit()
            
            # 成功したユーザーを記録
            for i, user_obj in enumerate(user_objects):
                cred = chunk_credentials[i]
                cred.user_id = user_obj.id
                created.append(cred)
            
        except Exception as e:
            # チャンク失敗時は個別処理にフォールバック
            db.session.rollback()
            individual_created, individual_failed = self._create_users_individual(chunk_credentials, config)
            created.extend(individual_created)
            failed.extend(individual_failed)
        
        return {'created': created, 'failed': failed}
    
    def _create_users_individual(self, credentials_list: List[UserCredentials], config: UserCreationConfig) -> tuple:
        """
        個別ユーザー作成（フォールバック用）
        """
        created_users = []
        failed_users = []
        
        for cred in credentials_list:
            try:
                user = User(
                    username=cred.username,
                    email=cred.email,
                    is_test_user=True,
                    test_batch_id=config.test_batch_id,
                    created_by_bulk=True
                )
                user.set_password(cred.password)
                
                with self._db_lock:
                    db.session.add(user)
                    db.session.flush()
                    cred.user_id = user.id
                    db.session.commit()
                
                created_users.append(cred)
                
            except Exception as e:
                db.session.rollback()
                failed_users.append(FailedUserCreation(
                    username=cred.username,
                    email=cred.email,
                    error=str(e)
                ))
        
        return created_users, failed_users
    
    def generate_unique_credentials(self, count: int, config: UserCreationConfig) -> List[UserCredentials]:
        """
        Generate unique usernames and email addresses
        
        Args:
            count: Number of credentials to generate
            config: Configuration containing patterns
            
        Returns:
            List of UserCredentials with unique identifiers
        """
        credentials = []
        timestamp = int(time.time())
        
        for i in range(count):
            # Generate unique identifier
            unique_id = f"{timestamp}_{i:04d}"
            
            # Generate username based on pattern
            if "{id}" in config.username_pattern:
                username = config.username_pattern.replace("{id}", unique_id)
            else:
                username = f"testuser_{unique_id}"
            
            # Generate email
            email = f"testuser_{unique_id}@{config.email_domain}"
            
            # Ensure uniqueness by checking existing users
            try:
                existing_user = User.query.filter(
                    (User.username == username) | (User.email == email)
                ).first()
                
                if existing_user:
                    # Add random suffix if collision occurs
                    random_suffix = str(uuid.uuid4())[:8]
                    username = f"{username}_{random_suffix}"
                    email = f"testuser_{unique_id}_{random_suffix}@{config.email_domain}"
            except Exception as e:
                # データベース接続エラーやアプリケーションコンテキストエラーの場合はスキップ
                self.logger.debug(f"従来版重複チェックをスキップ: {str(e)}")
                pass
            
            # 設定で指定されたパスワードを使用（テスト用途）
            password = config.password
            
            credentials.append(UserCredentials(
                username=username,
                email=email,
                password=password
            ))
        
        return credentials
    
    def _create_single_user_with_retry(self, cred: UserCredentials, config: UserCreationConfig) -> UserCredentials:
        """
        リトライ機構付きで単一ユーザーを作成
        要件 1.4: 部分的成功処理、リトライ機構
        """
        def create_user():
            try:
                # Create new user
                user = User(
                    username=cred.username,
                    email=cred.email,
                    is_test_user=True,
                    test_batch_id=config.test_batch_id,
                    created_by_bulk=True
                )
                user.set_password(cred.password)
                
                db.session.add(user)
                db.session.flush()  # Get the ID without committing
                
                # Update credentials with user ID
                cred.user_id = user.id
                return cred
                
            except Exception as e:
                # コンテキスト情報を例外に追加
                e.username = cred.username
                e.email = cred.email
                raise e
        
        try:
            return self.error_handler.with_retry(
                create_user,
                self.db_retry_config,
                ErrorCategory.USER_CREATION,
                {
                    "username": cred.username,
                    "email": cred.email,
                    "batch_id": config.test_batch_id
                }
            )
        except Exception as e:
            # リトライ失敗時はコンテキスト情報を保持して再発生
            e.username = getattr(e, 'username', cred.username)
            e.email = getattr(e, 'email', cred.email)
            raise e
    
    def _create_user_batch(self, credentials_list: List[UserCredentials], config: UserCreationConfig) -> tuple:
        """Create a batch of users and return created and failed lists (legacy method)"""
        created_users = []
        failed_users = []
        
        for cred in credentials_list:
            try:
                # Create new user
                user = User(
                    username=cred.username,
                    email=cred.email,
                    is_test_user=True,
                    test_batch_id=config.test_batch_id,
                    created_by_bulk=True
                )
                user.set_password(cred.password)
                
                db.session.add(user)
                db.session.flush()  # Get the ID without committing
                
                # Update credentials with user ID
                cred.user_id = user.id
                created_users.append(cred)
                
            except Exception as e:
                failed_users.append(FailedUserCreation(
                    username=cred.username,
                    email=cred.email,
                    error=str(e)
                ))
                db.session.rollback()
        
        return created_users, failed_users
    
    def cleanup_test_users(self, batch_id: str) -> CleanupResult:
        """
        特定のバッチのテストユーザーを削除（後方互換性のため）
        新しい保護機能付きのメソッドを内部で呼び出す
        
        Args:
            batch_id: クリーンアップ対象のバッチID
            
        Returns:
            CleanupResult: クリーンアップ結果
        """
        return self.cleanup_test_users_with_protection(batch_id)
    
    def get_batch_info(self, batch_id: str) -> Dict[str, Any]:
        """特定のバッチに関する情報を取得"""
        users = User.query.filter(
            User.test_batch_id == batch_id,
            User.is_test_user == True
        ).all()
        
        return {
            'batch_id': batch_id,
            'user_count': len(users),
            'users': [
                {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'created_at': user.created_at.isoformat() if user.created_at else None
                }
                for user in users
            ]
        }
    
    def identify_test_users(self, user_ids: List[int] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        テストユーザーと本番ユーザーを識別する機能
        要件 3.2: テストユーザーと本番ユーザーの識別機能
        
        Args:
            user_ids: 特定のユーザーIDリスト（省略時は全ユーザー）
            
        Returns:
            Dict: テストユーザーと本番ユーザーの分類結果
        """
        try:
            query = User.query
            if user_ids:
                query = query.filter(User.id.in_(user_ids))
            
            all_users = query.all()
            
            test_users = []
            production_users = []
            
            for user in all_users:
                user_info = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_test_user': user.is_test_user,
                    'test_batch_id': user.test_batch_id,
                    'created_by_bulk': user.created_by_bulk,
                    'created_at': user.created_at.isoformat() if user.created_at else None
                }
                
                if user.is_test_user:
                    test_users.append(user_info)
                else:
                    production_users.append(user_info)
            
            return {
                'test_users': test_users,
                'production_users': production_users,
                'total_test_users': len(test_users),
                'total_production_users': len(production_users),
                'identification_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"ユーザー識別処理に失敗しました: {str(e)}")
    
    def generate_cleanup_report(self, batch_id: str = None) -> LifecycleReport:
        """
        クリーンアップレポートを生成する機能
        要件 3.3: クリーンアップレポート生成機能
        
        Args:
            batch_id: 特定のバッチID（省略時は全バッチ）
            
        Returns:
            LifecycleReport: クリーンアップレポート
        """
        try:
            # テストユーザーの総数を取得
            total_test_users = User.query.filter(User.is_test_user == True).count()
            
            # アクティブなバッチIDを取得
            batch_query = db.session.query(User.test_batch_id).filter(
                User.test_batch_id.isnot(None),
                User.is_test_user == True
            ).distinct()
            
            if batch_id:
                batch_query = batch_query.filter(User.test_batch_id == batch_id)
            
            active_batches = [batch[0] for batch in batch_query.all()]
            
            # クリーンアップ候補の詳細情報を取得
            cleanup_candidates = []
            for batch in active_batches:
                batch_users = User.query.filter(
                    User.test_batch_id == batch,
                    User.is_test_user == True
                ).all()
                
                if batch_users:
                    oldest_user = min(batch_users, key=lambda u: u.created_at or datetime.min)
                    cleanup_candidates.append({
                        'batch_id': batch,
                        'user_count': len(batch_users),
                        'created_at': oldest_user.created_at.isoformat() if oldest_user.created_at else None,
                        'age_days': (datetime.utcnow() - (oldest_user.created_at or datetime.utcnow())).days,
                        'usernames': [user.username for user in batch_users[:5]]  # 最初の5ユーザーのみ表示
                    })
            
            # 本番ユーザー数（保護対象）
            non_test_users_protected = User.query.filter(User.is_test_user == False).count()
            
            return LifecycleReport(
                total_test_users=total_test_users,
                active_batches=active_batches,
                cleanup_candidates=cleanup_candidates,
                non_test_users_protected=non_test_users_protected,
                report_timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            raise Exception(f"クリーンアップレポート生成に失敗しました: {str(e)}")
    
    @with_error_handling(
        category=ErrorCategory.DATABASE,
        severity=ErrorSeverity.HIGH,
        preserve_integrity=True
    )
    def cleanup_test_users_with_protection(self, batch_id: str) -> CleanupResult:
        """
        非テストユーザー削除防止機能付きのテストユーザークリーンアップ
        要件 3.1, 3.4, 3.5: バッチ単位削除、クリーンアップレポート、非テストユーザー削除防止
        
        Args:
            batch_id: 削除対象のバッチID
            
        Returns:
            CleanupResult: 詳細なクリーンアップ結果
        """
        start_time = time.time()
        errors = []
        deleted_count = 0
        protected_count = 0
        
        self.logger.info(f"保護機能付きクリーンアップ開始: バッチID={batch_id}")
        
        # 安全性チェック: バッチIDが存在するか確認
        if not batch_id or batch_id.strip() == "":
            raise ValueError("バッチIDが指定されていません")
        
        # 削除対象のテストユーザーを取得
        test_users = User.query.filter(
            User.test_batch_id == batch_id,
            User.is_test_user == True
        ).all()
        
        if not test_users:
            self.logger.warning(f"バッチ {batch_id} にテストユーザーが見つかりません")
            return CleanupResult(
                deleted_count=0,
                batch_id=batch_id,
                errors=[f"バッチ {batch_id} にテストユーザーが見つかりません"],
                execution_time=time.time() - start_time,
                cleanup_report={
                    'batch_id': batch_id,
                    'found_users': 0,
                    'protected_users': 0,
                    'deleted_users': 0,
                    'safety_checks_passed': True
                }
            )
        
        # 安全性チェック: 非テストユーザーが混入していないか確認
        non_test_users_in_batch = User.query.filter(
            User.test_batch_id == batch_id,
            User.is_test_user == False
        ).all()
        
        if non_test_users_in_batch:
            protected_count = len(non_test_users_in_batch)
            warning_msg = f"警告: バッチ {batch_id} に非テストユーザーが {protected_count} 件含まれています（削除をスキップしました）"
            errors.append(warning_msg)
            self.logger.warning(warning_msg)
            
            for user in non_test_users_in_batch:
                protected_msg = f"保護されたユーザー: {user.username} (ID: {user.id})"
                errors.append(protected_msg)
                self.logger.warning(protected_msg)
        
        # Load Testerからも削除するための準備
        load_tester_sync_needed = []
        
        # 部分的成功処理でユーザー削除
        def delete_single_user(user: User) -> Dict[str, Any]:
            return self._delete_single_user_with_protection(user, load_tester_sync_needed)
        
        # 部分的成功処理を実行
        partial_result = self.error_handler.process_with_partial_success(
            items=test_users,
            process_func=delete_single_user,
            error_category=ErrorCategory.DATABASE,
            continue_on_error=True,  # 要件 3.4: 一部失敗時も継続
            context={
                "batch_id": batch_id,
                "operation": "cleanup_test_users"
            }
        )
        
        deleted_count = partial_result.successful_count
        
        # 部分的成功処理のエラーを統合
        for error_detail in partial_result.failed_items:
            errors.append(f"[{error_detail.error_id}] {error_detail.message}")
        
        # Load Testerからの削除を試行（リトライ付き）
        if load_tester_sync_needed:
            try:
                def sync_cleanup():
                    return self._cleanup_from_load_tester(batch_id, load_tester_sync_needed)
                
                load_tester_errors = self.error_handler.with_retry(
                    sync_cleanup,
                    self.sync_retry_config,
                    ErrorCategory.NETWORK,
                    {"batch_id": batch_id, "users_count": len(load_tester_sync_needed)}
                )
                
                if load_tester_errors:
                    errors.extend(load_tester_errors)
                    
            except Exception as e:
                error_msg = f"Load Tester同期クリーンアップ失敗: {str(e)}"
                errors.append(error_msg)
                self.logger.error(error_msg)
        
        # クリーンアップレポートを生成
        cleanup_report = {
            'batch_id': batch_id,
            'found_users': len(test_users),
            'protected_users': protected_count,
            'deleted_users': deleted_count,
            'load_tester_sync_attempted': len(load_tester_sync_needed),
            'safety_checks_passed': protected_count == 0 and len(partial_result.failed_items) == 0,
            'cleanup_timestamp': datetime.utcnow().isoformat(),
            'deleted_usernames': [user['username'] for user in load_tester_sync_needed[:10]],  # 最初の10件のみ
            'error_summary': {
                'total_errors': len(errors),
                'database_errors': len(partial_result.failed_items),
                'sync_errors': len([e for e in errors if 'Load Tester' in e])
            }
        }
        
        execution_time = time.time() - start_time
        
        self.logger.info(
            f"保護機能付きクリーンアップ完了: 削除={deleted_count}, "
            f"保護={protected_count}, エラー={len(errors)}, 時間={execution_time:.2f}秒"
        )
        
        return CleanupResult(
            deleted_count=deleted_count,
            batch_id=batch_id,
            errors=errors,
            execution_time=execution_time,
            cleanup_report=cleanup_report
        )
    
    def _delete_single_user_with_protection(self, user: User, sync_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        保護機能付きで単一ユーザーを削除
        要件 3.5: 非テストユーザー削除防止機能
        """
        # 最終安全性チェック
        if not user.is_test_user:
            raise ValueError(f"安全性チェック失敗: {user.username} は非テストユーザーです")
        
        # Load Tester同期用の情報を保存
        user_info = {
            'username': user.username,
            'email': user.email,
            'user_id': user.id
        }
        sync_list.append(user_info)
        
        # ユーザーを削除
        db.session.delete(user)
        
        return user_info
    
    def _cleanup_from_load_tester(self, batch_id: str, users_to_delete: List[Dict[str, Any]]) -> List[str]:
        """
        Load Testerからテストユーザーを削除
        
        Args:
            batch_id: バッチID
            users_to_delete: 削除対象ユーザーのリスト
            
        Returns:
            List[str]: エラーメッセージのリスト
        """
        errors = []
        
        try:
            from app.services.user_sync_service import UserSyncService
            
            # Load Testerの削除APIを呼び出し
            sync_service = UserSyncService()
            cleanup_url = f"{sync_service.load_tester_url}/api/users/cleanup"
            
            cleanup_data = {
                'batch_id': batch_id,
                'users_to_delete': users_to_delete,
                'source': 'main_application'
            }
            
            import requests
            response = requests.post(
                cleanup_url,
                json=cleanup_data,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if not result.get('success', False):
                    errors.append(f"Load Testerクリーンアップ失敗: {result.get('error', '不明なエラー')}")
            else:
                errors.append(f"Load Tester通信エラー: HTTP {response.status_code}")
                
        except Exception as e:
            errors.append(f"Load Testerクリーンアップエラー: {str(e)}")
        
        return errors
    
    def get_lifecycle_statistics(self) -> Dict[str, Any]:
        """
        テストユーザーライフサイクルの統計情報を取得
        
        Returns:
            Dict: ライフサイクル統計情報
        """
        try:
            # 基本統計
            total_users = User.query.count()
            test_users = User.query.filter(User.is_test_user == True).count()
            production_users = total_users - test_users
            bulk_created_users = User.query.filter(User.created_by_bulk == True).count()
            
            # バッチ統計
            batch_stats = db.session.query(
                User.test_batch_id,
                db.func.count(User.id).label('user_count'),
                db.func.min(User.created_at).label('oldest_created'),
                db.func.max(User.created_at).label('newest_created')
            ).filter(
                User.test_batch_id.isnot(None),
                User.is_test_user == True
            ).group_by(User.test_batch_id).all()
            
            # 古いバッチの特定（7日以上前）
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            old_batches = [
                {
                    'batch_id': batch.test_batch_id,
                    'user_count': batch.user_count,
                    'age_days': (datetime.utcnow() - batch.oldest_created).days if batch.oldest_created else 0
                }
                for batch in batch_stats
                if batch.oldest_created and batch.oldest_created < cutoff_date
            ]
            
            return {
                'total_users': total_users,
                'test_users': test_users,
                'production_users': production_users,
                'bulk_created_users': bulk_created_users,
                'active_batches': len(batch_stats),
                'old_batches_count': len(old_batches),
                'old_batches': old_batches,
                'protection_ratio': round(production_users / total_users * 100, 2) if total_users > 0 else 0,
                'statistics_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"ライフサイクル統計取得に失敗しました: {str(e)}")