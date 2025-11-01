"""
分散トレーシングサービスのメインアプリケーション
New Relicエージェントを統合したFlaskアプリケーション
エラーハンドリングとログ機能を強化
"""

import os
import logging
import newrelic.agent

# New Relicエージェントの初期化（環境変数を考慮）
config_file = os.environ.get('NEW_RELIC_CONFIG_FILE', 'newrelic.ini')
environment = os.environ.get('NEW_RELIC_ENVIRONMENT', 'development')

try:
    newrelic.agent.initialize(config_file, environment=environment)
    print(f"New Relic initialized: config={config_file}, env={environment}")
except Exception as e:
    print(f"New Relic initialization failed: {e}")
    # 初期化に失敗してもアプリケーションは続行

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# ログ設定とエラーハンドリングをインポート
from logging_config import configure_app_logging, performance_logger, security_logger
from error_handler import (
    create_error_handlers, 
    DistributedServiceErrorHandler, 
    DatabaseConnectionManager
)

# Flaskアプリケーションの作成
app = Flask(__name__)

# ログ設定を適用
configure_app_logging(app)
logger = logging.getLogger(__name__)

# データベース設定
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    'postgresql://postgres:postgres@postgres:5432/ecdb'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# エラーハンドリング設定
app.config['PROPAGATE_EXCEPTIONS'] = True

# データベースとマイグレーションの初期化
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# エラーハンドラーを登録
create_error_handlers(app)

# New Relicユーティリティをインポート
from newrelic_utils import (
    set_user_custom_attribute, 
    process_distributed_trace_headers,
    report_error_to_newrelic,
    set_performance_attributes,
    record_custom_event
)

# モデルを初期化（循環インポートを避けるため）
from models import create_models, init_database, check_database_connection
User, Product, Order, OrderItem, CartItem = create_models(db)

# パフォーマンスルートを登録
from routes.performance import performance_bp
app.register_blueprint(performance_bp)

@app.route('/health', methods=['GET'])
@newrelic.agent.function_trace()
def health_check():
    """ヘルスチェックエンドポイント（エラーハンドリング強化版）"""
    import time
    start_time = time.time()
    
    try:
        # 分散トレーシングヘッダーを処理
        process_distributed_trace_headers()
        
        # データベース接続をテスト
        connection_status = DatabaseConnectionManager.check_connection(db)
        
        # パフォーマンス情報を記録
        execution_time = time.time() - start_time
        set_performance_attributes(execution_time=execution_time)
        
        # ヘルスチェック結果をログ出力
        performance_logger.log_http_request(
            method='GET',
            url='/health',
            status_code=200 if connection_status else 503,
            execution_time=execution_time,
            additional_data={'database_status': connection_status}
        )
        
        # カスタムイベントを記録
        record_custom_event('HealthCheck', {
            'database_connected': connection_status,
            'execution_time': execution_time,
            'status': 'healthy' if connection_status else 'unhealthy'
        })
        
        status_code = 200 if connection_status else 503
        response_data = {
            'status': 'healthy' if connection_status else 'unhealthy',
            'service': 'distributed-tracing-service',
            'version': '1.0.0',
            'database': 'connected' if connection_status else 'disconnected',
            'execution_time': execution_time
        }
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        execution_time = time.time() - start_time
        
        # エラーハンドリング
        response_data, status_code = DistributedServiceErrorHandler.handle_general_error(
            error=e,
            operation='health_check',
            context={
                'execution_time': execution_time,
                'endpoint': '/health'
            }
        )
        
        return jsonify(response_data), status_code

@app.route('/init-db', methods=['POST'])
@newrelic.agent.function_trace()
def initialize_database():
    """データベース初期化エンドポイント（エラーハンドリング強化版）"""
    import time
    start_time = time.time()
    
    try:
        # 分散トレーシングヘッダーを処理
        process_distributed_trace_headers()
        
        # データベースの初期化を実行
        logger.info("データベース初期化を開始します")
        success = init_database(db)
        
        execution_time = time.time() - start_time
        
        if success:
            # 成功時のログとメトリクス
            performance_logger.log_database_operation(
                operation='INIT_DATABASE',
                execution_time=execution_time,
                additional_data={'tables_created': 5}
            )
            
            set_performance_attributes(execution_time=execution_time)
            
            record_custom_event('DatabaseInitialization', {
                'success': True,
                'execution_time': execution_time,
                'tables_created': 5
            })
            
            logger.info(f"データベース初期化が完了しました（実行時間: {execution_time:.3f}秒）")
            
            return jsonify({
                'status': 'success',
                'message': 'データベースの初期化が完了しました',
                'tables_created': ['users', 'products', 'orders', 'order_items', 'cart_items'],
                'execution_time': execution_time
            })
        else:
            # 失敗時のエラーハンドリング
            error = Exception("データベースの初期化に失敗しました")
            response_data, status_code = DistributedServiceErrorHandler.handle_database_error(
                error=error,
                operation='init_database',
                context={
                    'execution_time': execution_time,
                    'endpoint': '/init-db'
                }
            )
            
            return jsonify(response_data), status_code
            
    except Exception as e:
        execution_time = time.time() - start_time
        
        # データベースエラーとして処理
        response_data, status_code = DistributedServiceErrorHandler.handle_database_error(
            error=e,
            operation='init_database',
            context={
                'execution_time': execution_time,
                'endpoint': '/init-db'
            }
        )
        
        return jsonify(response_data), status_code

@app.route('/', methods=['GET'])
@newrelic.agent.function_trace()
def index():
    """基本的なインデックスエンドポイント（エラーハンドリング強化版）"""
    import time
    start_time = time.time()
    
    try:
        # 分散トレーシングヘッダーを処理
        process_distributed_trace_headers()
        
        # データベース接続状態を確認
        db_status = DatabaseConnectionManager.check_connection(db)
        
        execution_time = time.time() - start_time
        
        # パフォーマンス情報を記録
        performance_logger.log_http_request(
            method='GET',
            url='/',
            status_code=200,
            execution_time=execution_time,
            additional_data={'database_connected': db_status}
        )
        
        set_performance_attributes(execution_time=execution_time)
        
        return jsonify({
            'message': 'Distributed Tracing Service',
            'description': 'New Relic分散トレーシング用のWebサービス',
            'endpoints': [
                '/health - ヘルスチェック',
                '/init-db - データベース初期化',
                '/ - サービス情報',
                '/performance/* - パフォーマンステスト'
            ],
            'status': 'running',
            'database_status': 'connected' if db_status else 'disconnected',
            'models': ['User', 'Product', 'Order', 'OrderItem', 'CartItem'],
            'execution_time': execution_time,
            'version': '1.0.0',
            'features': [
                'New Relic分散トレーシング',
                'Custom Attribute設定',
                'エラーハンドリング',
                '構造化ログ出力',
                'パフォーマンス監視'
            ]
        })
        
    except Exception as e:
        execution_time = time.time() - start_time
        
        # 一般的なエラーとして処理
        response_data, status_code = DistributedServiceErrorHandler.handle_general_error(
            error=e,
            operation='index',
            context={
                'execution_time': execution_time,
                'endpoint': '/'
            }
        )
        
        return jsonify(response_data), status_code

if __name__ == '__main__':
    # アプリケーション起動時にデータベース接続を確認
    with app.app_context():
        logger.info("分散トレーシングサービスを起動しています...")
        
        # データベース接続確認（リトライ付き）
        if DatabaseConnectionManager.check_connection(db):
            logger.info("データベース接続が確認されました")
            
            # 必要に応じてテーブルを作成
            try:
                init_database(db)
                logger.info("データベース初期化が完了しました")
            except Exception as e:
                logger.error(f"データベース初期化エラー: {e}")
        else:
            logger.warning("データベース接続に問題があります - リトライを試行します")
            
            # 再接続を試行
            if DatabaseConnectionManager.reconnect_with_retry(db, max_retries=3):
                logger.info("データベース再接続が成功しました")
                try:
                    init_database(db)
                    logger.info("データベース初期化が完了しました")
                except Exception as e:
                    logger.error(f"データベース初期化エラー: {e}")
            else:
                logger.error("データベース接続に失敗しました - サービスは制限モードで起動します")
        
        # 起動完了ログ
        logger.info("分散トレーシングサービスが正常に起動しました")
        logger.info("利用可能なエンドポイント:")
        logger.info("  GET  / - サービス情報")
        logger.info("  GET  /health - ヘルスチェック")
        logger.info("  POST /init-db - データベース初期化")
        logger.info("  POST /performance/* - パフォーマンステスト")
    
    # サービス開始
    app.run(host='0.0.0.0', port=5000, debug=True)