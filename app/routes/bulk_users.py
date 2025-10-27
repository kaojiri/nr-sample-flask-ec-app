from flask import Blueprint, request, jsonify, current_app, render_template
from flask_login import login_required
from app.services.bulk_user_creator import BulkUserCreator, UserCreationConfig
from app.models.user import User
from app import db
import uuid
from datetime import datetime

bp = Blueprint('bulk_users', __name__, url_prefix='/api/bulk-users')

# 管理画面用のルート（APIではない）
admin_bp = Blueprint('bulk_users_admin', __name__, url_prefix='/admin/bulk-users')

@admin_bp.route('/')
@login_required
def admin_dashboard():
    """一括ユーザー管理の管理画面"""
    return render_template('bulk_users/admin_dashboard.html')

@admin_bp.route('/sync')
@login_required
def sync_dashboard():
    """同期状況確認用のダッシュボード"""
    return render_template('bulk_users/sync_dashboard.html')


@bp.route('/create', methods=['POST'])
def create_bulk_users():
    """
    Create multiple test users in bulk
    
    Expected JSON payload:
    {
        "count": 100,
        "config": {
            "username_pattern": "testuser_{id}@example.com",
            "password": "TestPass123!",
            "email_domain": "example.com",
            "batch_size": 50,
            "custom_attributes": {}
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        count = data.get('count')
        if not count or not isinstance(count, int) or count <= 0:
            return jsonify({'error': 'Valid count is required'}), 400
        
        if count > 1000:
            return jsonify({'error': 'Cannot create more than 1000 users in one batch'}), 400
        
        # Parse configuration
        config_data = data.get('config', {})
        config = UserCreationConfig(
            username_pattern=config_data.get('username_pattern', 'testuser_{id}@example.com'),
            password=config_data.get('password', 'TestPass123!'),
            email_domain=config_data.get('email_domain', 'example.com'),
            batch_size=config_data.get('batch_size', 100),
            custom_attributes=config_data.get('custom_attributes', {}),
            test_batch_id=config_data.get('test_batch_id', str(uuid.uuid4()))
        )
        
        # Create bulk users
        creator = BulkUserCreator()
        result = creator.create_bulk_users(count, config)
        
        # Prepare response
        response_data = {
            'success': True,
            'batch_id': result.batch_id,
            'total_requested': result.total_requested,
            'successful_count': result.successful_count,
            'failed_count': result.failed_count,
            'execution_time': result.execution_time,
            'created_users': [
                {
                    'user_id': user.user_id,
                    'username': user.username,
                    'email': user.email
                }
                for user in result.created_users
            ],
            'failed_users': [
                {
                    'username': failed.username,
                    'email': failed.email,
                    'error': failed.error
                }
                for failed in result.failed_users
            ]
        }
        
        status_code = 201 if result.successful_count > 0 else 400
        return jsonify(response_data), status_code
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f'Bulk user creation failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/batches/<batch_id>', methods=['GET'])
def get_batch_info(batch_id):
    """Get information about a specific batch"""
    try:
        creator = BulkUserCreator()
        batch_info = creator.get_batch_info(batch_id)
        
        if batch_info['user_count'] == 0:
            return jsonify({'error': 'Batch not found'}), 404
        
        return jsonify(batch_info), 200
        
    except Exception as e:
        current_app.logger.error(f'Failed to get batch info: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/batches/<batch_id>', methods=['DELETE'])
def cleanup_batch(batch_id):
    """Delete all test users from a specific batch"""
    try:
        creator = BulkUserCreator()
        result = creator.cleanup_test_users(batch_id)
        
        response_data = {
            'success': result.deleted_count > 0,
            'batch_id': result.batch_id,
            'deleted_count': result.deleted_count,
            'errors': result.errors,
            'execution_time': result.execution_time
        }
        
        status_code = 200 if result.deleted_count > 0 else 404
        return jsonify(response_data), status_code
        
    except Exception as e:
        current_app.logger.error(f'Batch cleanup failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/export', methods=['GET'])
def export_users():
    """
    Export test users in JSON format for synchronization
    
    Query parameters:
    - batch_id: Filter by specific batch (optional)
    - test_users_only: Export only test users (default: true)
    """
    try:
        batch_id = request.args.get('batch_id')
        test_users_only = request.args.get('test_users_only', 'true').lower() == 'true'
        
        # Build query
        query = User.query
        
        if test_users_only:
            query = query.filter(User.is_test_user == True)
        
        if batch_id:
            query = query.filter(User.test_batch_id == batch_id)
        
        users = query.all()
        
        # Prepare export data
        from datetime import datetime
        export_data = {
            'export_timestamp': datetime.utcnow().isoformat(),
            'source_system': 'main_application',
            'total_count': len(users),
            'filters': {
                'batch_id': batch_id,
                'test_users_only': test_users_only
            },
            'users': [
                {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_test_user': user.is_test_user,
                    'test_batch_id': user.test_batch_id,
                    'created_by_bulk': user.created_by_bulk,
                    'created_at': user.created_at.isoformat() if user.created_at else None
                }
                for user in users
            ]
        }
        
        return jsonify(export_data), 200
        
    except Exception as e:
        current_app.logger.error(f'User export failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/sync', methods=['POST'])
def sync_users():
    """
    ユーザー同期をトリガー
    
    Expected JSON payload:
    {
        "target": "load_tester",
        "filter_criteria": {
            "batch_id": "optional_batch_id",
            "test_users_only": true
        }
    }
    """
    try:
        from app.services.user_sync_service import UserSyncService
        
        data = request.get_json() or {}
        
        # フィルタ条件の取得
        filter_criteria = data.get('filter_criteria', {"test_users_only": True})
        target = data.get('target', 'load_tester')
        
        # 同期サービス初期化
        sync_service = UserSyncService()
        
        if target == 'load_tester':
            # Load Testerへの同期実行
            sync_result = sync_service.sync_bidirectional(filter_criteria)
            
            response_data = {
                'success': sync_result.success,
                'synced_count': sync_result.synced_count,
                'failed_count': sync_result.failed_count,
                'errors': sync_result.errors,
                'sync_timestamp': sync_result.sync_timestamp,
                'duration': sync_result.duration,
                'target': target,
                'filter_criteria': filter_criteria
            }
            
            status_code = 200 if sync_result.success else 400
            return jsonify(response_data), status_code
        
        else:
            return jsonify({'error': f'Unsupported sync target: {target}'}), 400
        
    except Exception as e:
        current_app.logger.error(f'Sync trigger failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/sync/status', methods=['GET'])
def get_sync_status():
    """同期状況の確認"""
    try:
        from app.services.user_sync_service import UserSyncService
        
        batch_id = request.args.get('batch_id')
        
        sync_service = UserSyncService()
        validation_result = sync_service.validate_sync_integrity(batch_id)
        
        response_data = {
            'is_valid': validation_result.is_valid,
            'total_checked': validation_result.total_checked,
            'inconsistencies': validation_result.inconsistencies,
            'validation_timestamp': validation_result.validation_timestamp,
            'batch_id': batch_id
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        current_app.logger.error(f'Sync status check failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/sync/export-file', methods=['POST'])
def export_users_to_file():
    """ユーザーデータをJSONファイルにエクスポート"""
    try:
        from app.services.user_sync_service import UserSyncService
        
        data = request.get_json() or {}
        file_path = data.get('file_path', 'exports/users_export.json')
        filter_criteria = data.get('filter_criteria', {"test_users_only": True})
        
        sync_service = UserSyncService()
        success = sync_service.export_to_json_file(file_path, filter_criteria)
        
        if success:
            return jsonify({
                'success': True,
                'file_path': file_path,
                'message': 'ユーザーデータのエクスポートが完了しました'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'ファイルエクスポートに失敗しました'
            }), 500
        
    except Exception as e:
        current_app.logger.error(f'File export failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/stats', methods=['GET'])
def get_bulk_user_stats():
    """Get statistics about bulk users"""
    try:
        total_test_users = User.query.filter(User.is_test_user == True).count()
        total_bulk_users = User.query.filter(User.created_by_bulk == True).count()
        
        # Get batch statistics
        batch_stats = db.session.query(
            User.test_batch_id,
            db.func.count(User.id).label('user_count'),
            db.func.min(User.created_at).label('created_at')
        ).filter(
            User.test_batch_id.isnot(None)
        ).group_by(User.test_batch_id).all()
        
        batches = [
            {
                'batch_id': batch.test_batch_id,
                'user_count': batch.user_count,
                'created_at': batch.created_at.isoformat() if batch.created_at else None
            }
            for batch in batch_stats
        ]
        
        return jsonify({
            'total_test_users': total_test_users,
            'total_bulk_users': total_bulk_users,
            'batch_count': len(batches),
            'batches': batches
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Failed to get bulk user stats: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


# 設定管理エンドポイント
@bp.route('/config/templates', methods=['GET'])
def list_config_templates():
    """利用可能な設定テンプレートのリストを取得"""
    try:
        from app.services.config_template_manager import config_template_manager
        
        templates = config_template_manager.list_templates()
        return jsonify({
            'success': True,
            'templates': templates
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Failed to list config templates: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/config/templates/<template_name>', methods=['GET'])
def get_config_template(template_name):
    """指定された設定テンプレートを取得"""
    try:
        from app.services.config_template_manager import config_template_manager
        
        template = config_template_manager.get_template(template_name)
        if not template:
            return jsonify({'error': f'Template "{template_name}" not found'}), 404
        
        validation = template.validate()
        
        return jsonify({
            'success': True,
            'template_name': template_name,
            'config': template.to_dict(),
            'validation': {
                'is_valid': validation.is_valid,
                'errors': validation.errors,
                'warnings': validation.warnings
            },
            'description': config_template_manager._get_template_description(template_name)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Failed to get config template: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/config/templates', methods=['POST'])
def create_config_template():
    """新しいカスタム設定テンプレートを作成"""
    try:
        from app.services.config_template_manager import config_template_manager
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        template_name = data.get('name')
        if not template_name:
            return jsonify({'error': 'Template name is required'}), 400
        
        config_data = data.get('config', {})
        
        # UserCreationConfigオブジェクトを作成
        config = UserCreationConfig.from_dict(config_data)
        
        # テンプレートを追加
        validation = config_template_manager.add_custom_template(template_name, config)
        
        if validation.is_valid:
            return jsonify({
                'success': True,
                'template_name': template_name,
                'message': 'Template created successfully',
                'warnings': validation.warnings
            }), 201
        else:
            return jsonify({
                'success': False,
                'errors': validation.errors,
                'warnings': validation.warnings
            }), 400
        
    except Exception as e:
        current_app.logger.error(f'Failed to create config template: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/config/templates/<template_name>', methods=['DELETE'])
def delete_config_template(template_name):
    """カスタム設定テンプレートを削除"""
    try:
        from app.services.config_template_manager import config_template_manager
        
        success = config_template_manager.remove_custom_template(template_name)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Template "{template_name}" deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'Template "{template_name}" not found or cannot be deleted'
            }), 404
        
    except Exception as e:
        current_app.logger.error(f'Failed to delete config template: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/config/validate', methods=['POST'])
def validate_config():
    """設定の妥当性を検証"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # UserCreationConfigオブジェクトを作成
        config = UserCreationConfig.from_dict(data)
        
        # 検証実行
        validation = config.validate()
        
        return jsonify({
            'is_valid': validation.is_valid,
            'errors': validation.errors,
            'warnings': validation.warnings,
            'config': config.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Config validation failed: {str(e)}')
        return jsonify({'error': f'Validation error: {str(e)}'}), 400


@bp.route('/config/templates/export', methods=['POST'])
def export_config_templates():
    """設定テンプレートをファイルにエクスポート"""
    try:
        from app.services.config_template_manager import config_template_manager
        
        data = request.get_json() or {}
        file_path = data.get('file_path', 'exports/config_templates.json')
        
        success = config_template_manager.export_templates(file_path)
        
        if success:
            return jsonify({
                'success': True,
                'file_path': file_path,
                'message': 'Templates exported successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to export templates'
            }), 500
        
    except Exception as e:
        current_app.logger.error(f'Template export failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/config/templates/import', methods=['POST'])
def import_config_templates():
    """設定テンプレートをファイルからインポート"""
    try:
        from app.services.config_template_manager import config_template_manager
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        file_path = data.get('file_path')
        if not file_path:
            return jsonify({'error': 'File path is required'}), 400
        
        overwrite_existing = data.get('overwrite_existing', False)
        
        result = config_template_manager.import_templates(file_path, overwrite_existing)
        
        return jsonify({
            'success': len(result['errors']) == 0,
            'imported': result['imported'],
            'skipped': result['skipped'],
            'errors': result['errors']
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Template import failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


# テストユーザーライフサイクル管理エンドポイント
@bp.route('/lifecycle/identify', methods=['POST'])
def identify_test_users():
    """
    テストユーザーと本番ユーザーを識別
    要件 3.2: テストユーザーと本番ユーザーの識別機能
    """
    try:
        data = request.get_json() or {}
        user_ids = data.get('user_ids')  # 特定のユーザーIDリスト（省略可）
        
        creator = BulkUserCreator()
        identification_result = creator.identify_test_users(user_ids)
        
        return jsonify({
            'success': True,
            'identification_result': identification_result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'User identification failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/lifecycle/report', methods=['GET'])
def generate_lifecycle_report():
    """
    クリーンアップレポートを生成
    要件 3.3: クリーンアップレポート生成機能
    """
    try:
        batch_id = request.args.get('batch_id')  # 特定のバッチID（省略可）
        
        creator = BulkUserCreator()
        lifecycle_report = creator.generate_cleanup_report(batch_id)
        
        return jsonify({
            'success': True,
            'lifecycle_report': lifecycle_report.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Lifecycle report generation failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/lifecycle/cleanup', methods=['POST'])
def cleanup_with_protection():
    """
    非テストユーザー削除防止機能付きクリーンアップ
    要件 3.1, 3.4, 3.5: バッチ単位削除、クリーンアップレポート、非テストユーザー削除防止
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        batch_id = data.get('batch_id')
        if not batch_id:
            return jsonify({'error': 'batch_id is required'}), 400
        
        creator = BulkUserCreator()
        cleanup_result = creator.cleanup_test_users_with_protection(batch_id)
        
        response_data = {
            'success': cleanup_result.deleted_count > 0 and len(cleanup_result.errors) == 0,
            'cleanup_result': cleanup_result.to_dict()
        }
        
        status_code = 200 if cleanup_result.deleted_count > 0 else 404
        return jsonify(response_data), status_code
        
    except Exception as e:
        current_app.logger.error(f'Protected cleanup failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/lifecycle/statistics', methods=['GET'])
def get_lifecycle_statistics():
    """
    テストユーザーライフサイクルの統計情報を取得
    """
    try:
        creator = BulkUserCreator()
        statistics = creator.get_lifecycle_statistics()
        
        return jsonify({
            'success': True,
            'statistics': statistics
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Lifecycle statistics failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/lifecycle/cleanup-candidates', methods=['GET'])
def get_cleanup_candidates():
    """
    クリーンアップ候補のバッチを取得
    """
    try:
        age_days = request.args.get('age_days', 7, type=int)
        
        creator = BulkUserCreator()
        statistics = creator.get_lifecycle_statistics()
        
        # 古いバッチをクリーンアップ候補として返す
        old_batches = statistics.get('old_batches', [])
        
        return jsonify({
            'success': True,
            'age_threshold_days': age_days,
            'total_candidates': len(old_batches),
            'candidates': old_batches,
            'statistics_summary': {
                'total_test_users': statistics.get('total_test_users', 0),
                'active_batches': statistics.get('active_batches', 0),
                'protection_ratio': statistics.get('protection_ratio', 0)
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Cleanup candidates failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/lifecycle/sync-cleanup', methods=['POST'])
def sync_cleanup_with_load_tester():
    """
    Load Testerと同期してクリーンアップを実行
    要件 3.1, 3.3: バッチ単位削除、Main ApplicationとLoad Tester両方からの削除
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        batch_id = data.get('batch_id')
        if not batch_id:
            return jsonify({'error': 'batch_id is required'}), 400
        
        # Main Applicationからクリーンアップ
        creator = BulkUserCreator()
        main_app_result = creator.cleanup_test_users_with_protection(batch_id)
        
        # Load Testerからもクリーンアップ（既に_cleanup_from_load_testerで実行済み）
        load_tester_errors = main_app_result.cleanup_report.get('load_tester_sync_attempted', 0)
        
        response_data = {
            'success': main_app_result.deleted_count > 0,
            'main_application': {
                'deleted_count': main_app_result.deleted_count,
                'errors': main_app_result.errors,
                'execution_time': main_app_result.execution_time
            },
            'load_tester': {
                'sync_attempted': load_tester_errors > 0,
                'sync_errors': [error for error in main_app_result.errors if 'Load Tester' in error]
            },
            'batch_id': batch_id,
            'cleanup_report': main_app_result.cleanup_report,
            'sync_timestamp': datetime.utcnow().isoformat()
        }
        
        status_code = 200 if main_app_result.deleted_count > 0 else 404
        return jsonify(response_data), status_code
        
    except Exception as e:
        current_app.logger.error(f'Sync cleanup failed: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500