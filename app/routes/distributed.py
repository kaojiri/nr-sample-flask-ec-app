"""
分散トレーシングサービス呼び出しルート
メインアプリケーションから分散サービスへのプロキシエンドポイント
"""

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
import newrelic.agent
import logging

from app.services.distributed_client import get_distributed_client, DistributedServiceError

logger = logging.getLogger(__name__)

# Blueprintの作成
distributed_bp = Blueprint('distributed', __name__, url_prefix='/distributed')


@distributed_bp.route('/')
@login_required
def index():
    """分散トレーシングデモのインデックスページ"""
    try:
        # New RelicにCustom Attributeを設定
        newrelic.agent.add_custom_attribute('user_id', current_user.id)
        newrelic.agent.add_custom_attribute('enduser.id', str(current_user.id))
        newrelic.agent.add_custom_attribute('page_type', 'distributed_demo_index')
        
        current_app.logger.info(
            f'Distributed tracing demo index accessed by user: {current_user.username} (ID: {current_user.id})',
            extra={
                'event_type': 'demo_page_view',
                'page': 'distributed_index',
                'user_id': current_user.id
            }
        )
        
        # 分散サービスのヘルスチェック
        client = get_distributed_client()
        service_available = client.health_check()
        
        return render_template(
            'distributed/index.html',
            user=current_user,
            service_available=service_available
        )
        
    except Exception as e:
        logger.error(f"Error loading distributed demo index: {e}")
        newrelic.agent.notice_error()
        return render_template(
            'distributed/index.html',
            user=current_user,
            service_available=False,
            error="分散サービスの状態を確認できませんでした"
        )


@distributed_bp.route('/n-plus-one', methods=['POST'])
@login_required
@newrelic.agent.function_trace()
def call_n_plus_one():
    """N+1クエリ問題のエンドポイントを分散サービスで実行"""
    try:
        # ユーザー認証とuserIdの取得
        user_id = current_user.id
        
        # New RelicにCustom Attributeを設定
        newrelic.agent.add_custom_attribute('user_id', user_id)
        newrelic.agent.add_custom_attribute('enduser.id', str(user_id))
        newrelic.agent.add_custom_attribute('operation_type', 'n_plus_one')
        newrelic.agent.add_custom_attribute('distributed_call', True)
        
        # リクエストパラメータを取得
        data = request.get_json() or {}
        limit = data.get('limit', 20)
        
        logger.info(f"N+1 query request from user {user_id}, limit={limit}")
        
        # 分散サービスを呼び出し
        client = get_distributed_client()
        result = client.call_n_plus_one(user_id=user_id, limit=limit)
        
        logger.info(f"N+1 query completed for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'N+1クエリが正常に実行されました',
            'result': result
        })
        
    except DistributedServiceError as e:
        logger.error(f"Distributed service error in N+1 query: {e}")
        
        # New RelicにエラーAttributeを追加
        newrelic.agent.add_custom_attribute('distributed_error', True)
        newrelic.agent.add_custom_attribute('error_type', e.error_type or 'unknown')
        newrelic.agent.notice_error()
        
        return jsonify({
            'success': False,
            'error': 'N+1クエリの実行中にエラーが発生しました',
            'details': str(e)
        }), 500
        
    except Exception as e:
        logger.error(f"Unexpected error in N+1 query: {e}")
        newrelic.agent.notice_error()
        
        return jsonify({
            'success': False,
            'error': '予期しないエラーが発生しました',
            'details': str(e)
        }), 500


@distributed_bp.route('/slow-query', methods=['POST'])
@login_required
@newrelic.agent.function_trace()
def call_slow_query():
    """スロークエリのエンドポイントを分散サービスで実行"""
    try:
        # ユーザー認証とuserIdの取得
        user_id = current_user.id
        
        # New RelicにCustom Attributeを設定
        newrelic.agent.add_custom_attribute('user_id', user_id)
        newrelic.agent.add_custom_attribute('enduser.id', str(user_id))
        newrelic.agent.add_custom_attribute('operation_type', 'slow_query')
        newrelic.agent.add_custom_attribute('distributed_call', True)
        
        # リクエストパラメータを取得
        data = request.get_json() or {}
        sleep_duration = data.get('sleep_duration', 3.0)
        query_type = data.get('query_type', 'sleep')
        
        logger.info(f"Slow query request from user {user_id}, type={query_type}, duration={sleep_duration}")
        
        # 分散サービスを呼び出し
        client = get_distributed_client()
        result = client.call_slow_query(
            user_id=user_id,
            sleep_duration=sleep_duration,
            query_type=query_type
        )
        
        logger.info(f"Slow query completed for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'スロークエリが正常に実行されました',
            'result': result
        })
        
    except DistributedServiceError as e:
        logger.error(f"Distributed service error in slow query: {e}")
        
        # New RelicにエラーAttributeを追加
        newrelic.agent.add_custom_attribute('distributed_error', True)
        newrelic.agent.add_custom_attribute('error_type', e.error_type or 'unknown')
        newrelic.agent.notice_error()
        
        return jsonify({
            'success': False,
            'error': 'スロークエリの実行中にエラーが発生しました',
            'details': str(e)
        }), 500
        
    except Exception as e:
        logger.error(f"Unexpected error in slow query: {e}")
        newrelic.agent.notice_error()
        
        return jsonify({
            'success': False,
            'error': '予期しないエラーが発生しました',
            'details': str(e)
        }), 500


@distributed_bp.route('/database-error', methods=['POST'])
@login_required
@newrelic.agent.function_trace()
def call_database_error():
    """データベースエラーのエンドポイントを分散サービスで実行"""
    try:
        # ユーザー認証とuserIdの取得
        user_id = current_user.id
        
        # New RelicにCustom Attributeを設定
        newrelic.agent.add_custom_attribute('user_id', user_id)
        newrelic.agent.add_custom_attribute('enduser.id', str(user_id))
        newrelic.agent.add_custom_attribute('operation_type', 'database_error')
        newrelic.agent.add_custom_attribute('distributed_call', True)
        
        # リクエストパラメータを取得
        data = request.get_json() or {}
        error_type = data.get('error_type', 'syntax')
        
        logger.info(f"Database error request from user {user_id}, type={error_type}")
        
        # 分散サービスを呼び出し
        client = get_distributed_client()
        result = client.call_database_error(user_id=user_id, error_type=error_type)
        
        logger.info(f"Database error completed for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'データベースエラーが正常に実行されました',
            'result': result
        })
        
    except DistributedServiceError as e:
        logger.error(f"Distributed service error in database error: {e}")
        
        # New RelicにエラーAttributeを追加
        newrelic.agent.add_custom_attribute('distributed_error', True)
        newrelic.agent.add_custom_attribute('error_type', e.error_type or 'unknown')
        newrelic.agent.notice_error()
        
        return jsonify({
            'success': False,
            'error': 'データベースエラーの実行中にエラーが発生しました',
            'details': str(e)
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in database error: {e}")
        newrelic.agent.notice_error()
        
        return jsonify({
            'success': False,
            'error': '予期しないエラーが発生しました',
            'details': str(e)
        })


@distributed_bp.route('/test-all', methods=['POST'])
@login_required
@newrelic.agent.function_trace()
def call_test_all():
    """全パフォーマンステストのエンドポイントを分散サービスで実行"""
    try:
        # ユーザー認証とuserIdの取得
        user_id = current_user.id
        
        # New RelicにCustom Attributeを設定
        newrelic.agent.add_custom_attribute('user_id', user_id)
        newrelic.agent.add_custom_attribute('enduser.id', str(user_id))
        newrelic.agent.add_custom_attribute('operation_type', 'test_all')
        newrelic.agent.add_custom_attribute('distributed_call', True)
        
        logger.info(f"Test all request from user {user_id}")
        
        # 分散サービスを呼び出し
        client = get_distributed_client()
        result = client.call_test_all(user_id=user_id)
        
        logger.info(f"Test all completed for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': '全パフォーマンステストが正常に実行されました',
            'result': result
        })
        
    except DistributedServiceError as e:
        logger.error(f"Distributed service error in test all: {e}")
        
        # New RelicにエラーAttributeを追加
        newrelic.agent.add_custom_attribute('distributed_error', True)
        newrelic.agent.add_custom_attribute('error_type', e.error_type or 'unknown')
        newrelic.agent.notice_error()
        
        return jsonify({
            'success': False,
            'error': '全パフォーマンステストの実行中にエラーが発生しました',
            'details': str(e)
        }), 500
        
    except Exception as e:
        logger.error(f"Unexpected error in test all: {e}")
        newrelic.agent.notice_error()
        
        return jsonify({
            'success': False,
            'error': '予期しないエラーが発生しました',
            'details': str(e)
        }), 500


@distributed_bp.route('/health')
def health_check():
    """分散サービスのヘルスチェック"""
    try:
        client = get_distributed_client()
        is_healthy = client.health_check()
        
        return jsonify({
            'distributed_service_available': is_healthy,
            'status': 'ok' if is_healthy else 'error'
        })
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'distributed_service_available': False,
            'status': 'error',
            'error': str(e)
        }), 500