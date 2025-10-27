"""
エラーレポート生成用のAPIエンドポイント
要件: 詳細エラーログとレポート機能
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import logging

from app.services.error_handler import error_handler
from app.services.bulk_user_creator import BulkUserCreator
from app.services.user_sync_service import UserSyncService

logger = logging.getLogger(__name__)

error_reports_bp = Blueprint('error_reports', __name__)


@error_reports_bp.route('/api/error-reports/bulk-user-management', methods=['GET'])
def get_bulk_user_management_error_report():
    """
    一括ユーザー管理のエラーレポートを取得
    
    Query Parameters:
        - start_date: 開始日時 (ISO format)
        - end_date: 終了日時 (ISO format)
        - category: エラーカテゴリフィルタ
        - severity: エラー重要度フィルタ
    """
    try:
        # クエリパラメータの取得
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        category_filter = request.args.get('category')
        severity_filter = request.args.get('severity')
        
        # 日時の解析
        start_date = None
        end_date = None
        
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': '無効な開始日時形式です'}), 400
        
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': '無効な終了日時形式です'}), 400
        
        # エラーレポート生成
        report = error_handler.generate_error_report(start_date, end_date)
        
        # フィルタリング（簡易版）
        if category_filter or severity_filter:
            report['filters_applied'] = {
                'category': category_filter,
                'severity': severity_filter
            }
        
        return jsonify({
            'success': True,
            'report': report,
            'generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"エラーレポート取得失敗: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'エラーレポート生成に失敗しました: {str(e)}'
        }), 500


@error_reports_bp.route('/api/error-reports/system-health', methods=['GET'])
def get_system_health_report():
    """
    システムヘルスレポートを取得
    """
    try:
        bulk_creator = BulkUserCreator()
        sync_service = UserSyncService()
        
        # 基本統計情報
        lifecycle_stats = bulk_creator.get_lifecycle_statistics()
        
        # 同期整合性チェック
        integrity_result = sync_service.validate_sync_integrity()
        
        # エラー統計
        error_report = error_handler.generate_error_report(
            start_time=datetime.utcnow() - timedelta(hours=24)  # 過去24時間
        )
        
        # ヘルスステータス判定
        health_status = "healthy"
        health_issues = []
        
        if error_report.get("total_errors", 0) > 100:
            health_status = "warning"
            health_issues.append("過去24時間のエラー数が多すぎます")
        
        if not integrity_result.is_valid:
            health_status = "critical"
            health_issues.append("データ整合性に問題があります")
        
        if lifecycle_stats.get("old_batches_count", 0) > 10:
            health_status = "warning" if health_status == "healthy" else health_status
            health_issues.append("古いテストバッチが多数存在します")
        
        health_report = {
            "status": health_status,
            "issues": health_issues,
            "statistics": {
                "lifecycle": lifecycle_stats,
                "integrity": integrity_result.to_dict(),
                "errors_24h": error_report
            },
            "recommendations": []
        }
        
        # 推奨事項の生成
        if health_status != "healthy":
            if "データ整合性" in str(health_issues):
                health_report["recommendations"].append("同期処理を再実行してください")
            
            if "エラー数" in str(health_issues):
                health_report["recommendations"].append("エラーログを確認し、根本原因を調査してください")
            
            if "古いテストバッチ" in str(health_issues):
                health_report["recommendations"].append("不要なテストバッチをクリーンアップしてください")
        
        return jsonify({
            'success': True,
            'health_report': health_report,
            'generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"システムヘルスレポート取得失敗: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'システムヘルスレポート生成に失敗しました: {str(e)}'
        }), 500


@error_reports_bp.route('/api/error-reports/batch-analysis/<batch_id>', methods=['GET'])
def get_batch_error_analysis(batch_id: str):
    """
    特定バッチのエラー分析レポートを取得
    
    Args:
        batch_id: 分析対象のバッチID
    """
    try:
        bulk_creator = BulkUserCreator()
        sync_service = UserSyncService()
        
        # バッチ情報取得
        batch_info = bulk_creator.get_batch_info(batch_id)
        
        if batch_info['user_count'] == 0:
            return jsonify({
                'success': False,
                'error': f'バッチ {batch_id} が見つかりません'
            }), 404
        
        # バッチ固有の整合性チェック
        integrity_result = sync_service.validate_sync_integrity(batch_id)
        
        # クリーンアップレポート生成
        cleanup_report = bulk_creator.generate_cleanup_report(batch_id)
        
        # バッチ分析結果
        analysis_result = {
            "batch_id": batch_id,
            "batch_info": batch_info,
            "integrity_check": integrity_result.to_dict(),
            "cleanup_analysis": cleanup_report.to_dict(),
            "recommendations": []
        }
        
        # 推奨事項の生成
        if not integrity_result.is_valid:
            analysis_result["recommendations"].append(
                f"バッチ {batch_id} の同期を再実行してください"
            )
        
        if len(cleanup_report.cleanup_candidates) > 0:
            analysis_result["recommendations"].append(
                f"バッチ {batch_id} はクリーンアップ候補です"
            )
        
        return jsonify({
            'success': True,
            'analysis': analysis_result,
            'generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"バッチエラー分析失敗 (batch: {batch_id}): {str(e)}")
        return jsonify({
            'success': False,
            'error': f'バッチエラー分析に失敗しました: {str(e)}'
        }), 500


@error_reports_bp.route('/api/error-reports/export', methods=['POST'])
def export_error_report():
    """
    エラーレポートをファイルにエクスポート
    """
    try:
        data = request.get_json() or {}
        
        # エクスポート設定
        export_format = data.get('format', 'json')  # json, csv
        include_details = data.get('include_details', True)
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        
        # 日時の解析
        start_date = None
        end_date = None
        
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # レポート生成
        report = error_handler.generate_error_report(start_date, end_date)
        
        # ファイル名生成
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"bulk_user_error_report_{timestamp}.{export_format}"
        
        # エクスポート処理（簡易版）
        export_path = f"logs/exports/{filename}"
        
        if export_format == 'json':
            import json
            from pathlib import Path
            
            Path(export_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'export_file': export_path,
            'filename': filename,
            'format': export_format,
            'exported_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"エラーレポートエクスポート失敗: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'エラーレポートエクスポートに失敗しました: {str(e)}'
        }), 500