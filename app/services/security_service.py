"""
セキュリティサービス - 一括ユーザー作成APIの認証・認可とアクセスログ機能
要件 3.2, 3.5: テストユーザーと本番ユーザーの分離、セキュリティ機能
"""

import logging
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import wraps
from flask import request, jsonify, current_app, g
from flask_login import current_user
from dataclasses import dataclass, field
import json
import os
from pathlib import Path


@dataclass
class AccessLogEntry:
    """アクセスログエントリ"""
    timestamp: str
    user_id: Optional[int]
    username: Optional[str]
    endpoint: str
    method: str
    ip_address: str
    user_agent: str
    request_data: Dict[str, Any]
    response_status: int
    execution_time: float
    security_level: str = "standard"
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "username": self.username,
            "endpoint": self.endpoint,
            "method": self.method,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_data": self.request_data,
            "response_status": self.response_status,
            "execution_time": self.execution_time,
            "security_level": self.security_level
        }


@dataclass
class SecurityConfig:
    """セキュリティ設定"""
    require_authentication: bool = True
    allowed_roles: List[str] = field(default_factory=lambda: ["admin", "test_manager"])
    max_requests_per_hour: int = 100
    max_users_per_request: int = 1000
    enable_access_logging: bool = True
    log_request_data: bool = True
    log_response_data: bool = False
    password_hash_algorithm: str = "pbkdf2:sha256"
    
    @classmethod
    def from_env(cls) -> 'SecurityConfig':
        """環境変数から設定を読み込み"""
        return cls(
            require_authentication=os.getenv('BULK_USER_REQUIRE_AUTH', 'true').lower() == 'true',
            allowed_roles=os.getenv('BULK_USER_ALLOWED_ROLES', 'admin,test_manager').split(','),
            max_requests_per_hour=int(os.getenv('BULK_USER_MAX_REQUESTS_PER_HOUR', '100')),
            max_users_per_request=int(os.getenv('BULK_USER_MAX_USERS_PER_REQUEST', '1000')),
            enable_access_logging=os.getenv('BULK_USER_ENABLE_ACCESS_LOG', 'true').lower() == 'true',
            log_request_data=os.getenv('BULK_USER_LOG_REQUEST_DATA', 'true').lower() == 'true',
            log_response_data=os.getenv('BULK_USER_LOG_RESPONSE_DATA', 'false').lower() == 'true'
        )


class SecurityService:
    """セキュリティサービス - 認証・認可・ログ機能を提供"""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig.from_env()
        self.logger = logging.getLogger(__name__)
        self.access_logger = self._setup_access_logger()
        
        # レート制限用のメモリストレージ（本番環境ではRedis等を使用）
        self._rate_limit_storage = {}
        
        # セキュリティイベントログ
        self.security_logger = self._setup_security_logger()
    
    def _setup_access_logger(self) -> logging.Logger:
        """アクセスログ専用のロガーを設定"""
        access_logger = logging.getLogger('bulk_user_access')
        access_logger.setLevel(logging.INFO)
        
        # ログファイルハンドラーを設定
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        handler = logging.FileHandler(log_dir / 'bulk_user_access.log')
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        if not access_logger.handlers:
            access_logger.addHandler(handler)
        
        return access_logger
    
    def _setup_security_logger(self) -> logging.Logger:
        """セキュリティイベント専用のロガーを設定"""
        security_logger = logging.getLogger('bulk_user_security')
        security_logger.setLevel(logging.WARNING)
        
        # ログファイルハンドラーを設定
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        handler = logging.FileHandler(log_dir / 'bulk_user_security.log')
        formatter = logging.Formatter(
            '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        if not security_logger.handlers:
            security_logger.addHandler(handler)
        
        return security_logger
    
    def require_authentication(self, allowed_roles: Optional[List[str]] = None):
        """
        認証・認可デコレータ
        要件: 一括ユーザー作成APIの認証・認可
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                start_time = time.time()
                
                try:
                    # 認証チェック
                    if self.config.require_authentication:
                        if not current_user.is_authenticated:
                            self._log_security_event(
                                "AUTHENTICATION_FAILED",
                                "未認証ユーザーによるアクセス試行",
                                {"endpoint": request.endpoint, "ip": request.remote_addr}
                            )
                            return jsonify({'error': 'Authentication required'}), 401
                    
                    # 認可チェック
                    roles_to_check = allowed_roles or self.config.allowed_roles
                    if roles_to_check and current_user.is_authenticated:
                        user_role = getattr(current_user, 'role', 'user')
                        if user_role not in roles_to_check:
                            self._log_security_event(
                                "AUTHORIZATION_FAILED",
                                f"権限不足: ユーザー {current_user.username} (role: {user_role})",
                                {"required_roles": roles_to_check, "user_role": user_role}
                            )
                            return jsonify({'error': 'Insufficient permissions'}), 403
                    
                    # レート制限チェック
                    if not self._check_rate_limit():
                        self._log_security_event(
                            "RATE_LIMIT_EXCEEDED",
                            f"レート制限超過: {request.remote_addr}",
                            {"endpoint": request.endpoint}
                        )
                        return jsonify({'error': 'Rate limit exceeded'}), 429
                    
                    # リクエスト実行
                    response = f(*args, **kwargs)
                    
                    # アクセスログ記録
                    if self.config.enable_access_logging:
                        self._log_access(start_time, response)
                    
                    return response
                    
                except Exception as e:
                    # エラーログ記録
                    self._log_security_event(
                        "REQUEST_ERROR",
                        f"リクエスト処理エラー: {str(e)}",
                        {"endpoint": request.endpoint, "error": str(e)}
                    )
                    raise
            
            return decorated_function
        return decorator
    
    def _check_rate_limit(self) -> bool:
        """レート制限チェック"""
        if not hasattr(current_user, 'id') or not current_user.id:
            # 未認証ユーザーはIPアドレスベース
            key = f"ip_{request.remote_addr}"
        else:
            # 認証済みユーザーはユーザーIDベース
            key = f"user_{current_user.id}"
        
        current_time = time.time()
        hour_ago = current_time - 3600  # 1時間前
        
        # 古いエントリを削除
        if key in self._rate_limit_storage:
            self._rate_limit_storage[key] = [
                timestamp for timestamp in self._rate_limit_storage[key]
                if timestamp > hour_ago
            ]
        else:
            self._rate_limit_storage[key] = []
        
        # 現在のリクエスト数をチェック
        if len(self._rate_limit_storage[key]) >= self.config.max_requests_per_hour:
            return False
        
        # 新しいリクエストを記録
        self._rate_limit_storage[key].append(current_time)
        return True
    
    def _log_access(self, start_time: float, response) -> None:
        """アクセスログを記録"""
        try:
            execution_time = time.time() - start_time
            
            # リクエストデータの準備
            request_data = {}
            if self.config.log_request_data:
                if request.is_json:
                    request_data = request.get_json() or {}
                    # パスワード等の機密情報をマスク
                    request_data = self._mask_sensitive_data(request_data)
                else:
                    request_data = dict(request.form)
            
            # レスポンスステータスの取得
            response_status = 200
            if hasattr(response, 'status_code'):
                response_status = response.status_code
            elif isinstance(response, tuple) and len(response) > 1:
                response_status = response[1]
            
            # アクセスログエントリを作成
            log_entry = AccessLogEntry(
                timestamp=datetime.utcnow().isoformat(),
                user_id=current_user.id if current_user.is_authenticated else None,
                username=current_user.username if current_user.is_authenticated else None,
                endpoint=request.endpoint or request.path,
                method=request.method,
                ip_address=request.remote_addr or 'unknown',
                user_agent=request.headers.get('User-Agent', 'unknown'),
                request_data=request_data,
                response_status=response_status,
                execution_time=execution_time,
                security_level="high" if "bulk" in request.path else "standard"
            )
            
            # ログ出力
            self.access_logger.info(json.dumps(log_entry.to_dict(), ensure_ascii=False))
            
        except Exception as e:
            self.logger.error(f"アクセスログ記録エラー: {str(e)}")
    
    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """機密データをマスク"""
        if not isinstance(data, dict):
            return data
        
        masked_data = data.copy()
        sensitive_keys = ['password', 'token', 'secret', 'key', 'auth']
        
        for key, value in masked_data.items():
            if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
                masked_data[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked_data[key] = self._mask_sensitive_data(value)
        
        return masked_data
    
    def _log_security_event(self, event_type: str, message: str, context: Dict[str, Any]) -> None:
        """セキュリティイベントをログ記録"""
        security_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "message": message,
            "context": context,
            "user_id": current_user.id if current_user.is_authenticated else None,
            "username": current_user.username if current_user.is_authenticated else None,
            "ip_address": request.remote_addr if request else None,
            "user_agent": request.headers.get('User-Agent') if request else None
        }
        
        self.security_logger.warning(json.dumps(security_event, ensure_ascii=False))
    
    def validate_bulk_request(self, count: int) -> bool:
        """一括リクエストの妥当性検証"""
        if count > self.config.max_users_per_request:
            self._log_security_event(
                "BULK_REQUEST_LIMIT_EXCEEDED",
                f"一括作成数制限超過: {count} > {self.config.max_users_per_request}",
                {"requested_count": count, "max_allowed": self.config.max_users_per_request}
            )
            return False
        return True
    
    def ensure_test_user_separation(self, user_data: Dict[str, Any]) -> bool:
        """
        テストユーザーと本番ユーザーの分離を確保
        要件 3.2, 3.5: テストユーザーと本番ユーザーの分離機能
        """
        # テストユーザーの必須フィールドをチェック
        if not user_data.get('is_test_user', False):
            self._log_security_event(
                "TEST_USER_SEPARATION_VIOLATION",
                "一括作成でis_test_userがFalseに設定されています",
                {"user_data": self._mask_sensitive_data(user_data)}
            )
            return False
        
        # テストユーザー専用のドメインやパターンをチェック
        email = user_data.get('email', '')
        username = user_data.get('username', '')
        
        test_domains = ['test.local', 'loadtest.local', 'example.com']
        test_prefixes = ['test', 'load', 'perf', 'sec']
        
        is_test_domain = any(domain in email for domain in test_domains)
        is_test_prefix = any(username.startswith(prefix) for prefix in test_prefixes)
        
        if not (is_test_domain or is_test_prefix):
            self._log_security_event(
                "TEST_USER_PATTERN_VIOLATION",
                "テストユーザーが適切なパターンに従っていません",
                {"email": email, "username": username}
            )
            return False
        
        return True
    
    def get_access_logs(self, hours: int = 24, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """アクセスログを取得"""
        try:
            log_file = Path('logs') / 'bulk_user_access.log'
            if not log_file.exists():
                return []
            
            logs = []
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        # ログ行をパース（JSON部分を抽出）
                        json_start = line.find('{')
                        if json_start == -1:
                            continue
                        
                        log_data = json.loads(line[json_start:])
                        log_time = datetime.fromisoformat(log_data['timestamp'])
                        
                        # 時間フィルタ
                        if log_time < cutoff_time:
                            continue
                        
                        # ユーザーフィルタ
                        if user_id and log_data.get('user_id') != user_id:
                            continue
                        
                        logs.append(log_data)
                        
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
            
            # 新しい順にソート
            logs.sort(key=lambda x: x['timestamp'], reverse=True)
            return logs
            
        except Exception as e:
            self.logger.error(f"アクセスログ取得エラー: {str(e)}")
            return []
    
    def get_security_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        """セキュリティイベントを取得"""
        try:
            log_file = Path('logs') / 'bulk_user_security.log'
            if not log_file.exists():
                return []
            
            events = []
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        # ログ行をパース（JSON部分を抽出）
                        json_start = line.find('{')
                        if json_start == -1:
                            continue
                        
                        event_data = json.loads(line[json_start:])
                        event_time = datetime.fromisoformat(event_data['timestamp'])
                        
                        # 時間フィルタ
                        if event_time < cutoff_time:
                            continue
                        
                        events.append(event_data)
                        
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
            
            # 新しい順にソート
            events.sort(key=lambda x: x['timestamp'], reverse=True)
            return events
            
        except Exception as e:
            self.logger.error(f"セキュリティイベント取得エラー: {str(e)}")
            return []


# グローバルセキュリティサービスインスタンス
security_service = SecurityService()


def require_bulk_user_auth(allowed_roles: Optional[List[str]] = None):
    """一括ユーザー管理API用の認証デコレータ"""
    return security_service.require_authentication(allowed_roles)


def log_bulk_user_access(f):
    """一括ユーザー管理API用のアクセスログデコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        try:
            response = f(*args, **kwargs)
            if security_service.config.enable_access_logging:
                security_service._log_access(start_time, response)
            return response
        except Exception as e:
            security_service._log_security_event(
                "API_ERROR",
                f"API実行エラー: {str(e)}",
                {"function": f.__name__, "error": str(e)}
            )
            raise
    return decorated_function