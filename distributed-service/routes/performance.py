"""
パフォーマンス問題のあるエンドポイント
N+1クエリ、スロークエリ、データベースエラーを意図的に発生させる
"""

import time
import random
import logging
from flask import Blueprint, request, jsonify
from sqlalchemy import text
import newrelic.agent

from newrelic_utils import (
    set_user_custom_attribute,
    set_operation_custom_attribute,
    process_distributed_trace_headers,
    report_error_to_newrelic
)

logger = logging.getLogger(__name__)

# Blueprintの作成
performance_bp = Blueprint('performance', __name__, url_prefix='/performance')

def get_models_and_db():
    """モデルクラスとデータベースインスタンスを取得"""
    from flask import current_app
    
    # Flask-SQLAlchemyのdbインスタンスを取得
    db = current_app.extensions['sqlalchemy']
    
    # グローバルスコープからモデルクラスを取得
    import __main__
    if hasattr(__main__, 'User'):
        User = __main__.User
        Product = __main__.Product
        Order = __main__.Order
        OrderItem = __main__.OrderItem
    else:
        # モデルクラスを動的に作成
        from models import create_models
        User, Product, Order, OrderItem, CartItem = create_models(db)
    
    return User, Product, Order, OrderItem, db

def ensure_test_data(User, Product, Order, OrderItem, db):
    """テストデータが存在することを確認し、なければ作成"""
    try:
        # 商品データが存在するかチェック
        product_count = Product.query.count()
        
        if product_count < 10:
            # テスト商品を作成
            for i in range(10):
                product = Product(
                    name=f'商品 {i + 1}',
                    description=f'テスト商品 {i + 1} の説明',
                    price=1000 + (i * 100),
                    stock=100,
                    category='テスト'
                )
                db.session.add(product)
            
            # テストユーザーを作成
            for i in range(5):
                user = User(
                    username=f'testuser{i + 1}',
                    email=f'test{i + 1}@example.com',
                    password_hash='dummy_hash'
                )
                db.session.add(user)
            
            db.session.commit()
            
            # テスト注文を作成
            users = User.query.all()
            products = Product.query.all()
            
            for user in users:
                for i in range(3):  # 各ユーザー3つの注文
                    order = Order(
                        user_id=user.id,
                        total_amount=5000.0,
                        status='completed'
                    )
                    db.session.add(order)
                    db.session.flush()  # IDを取得するため
                    
                    # 各注文に2-3個の商品を追加
                    for j in range(2 + (i % 2)):
                        product = products[j % len(products)]
                        order_item = OrderItem(
                            order_id=order.id,
                            product_id=product.id,
                            quantity=1 + j,
                            price=product.price
                        )
                        db.session.add(order_item)
            
            db.session.commit()
            logger.info("テストデータを作成しました")
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"テストデータ作成エラー: {e}")
        raise

@performance_bp.route('/n-plus-one', methods=['POST'])
@newrelic.agent.function_trace()
def n_plus_one_query():
    """
    N+1クエリ問題を発生させるエンドポイント
    
    Request JSON:
    {
        "user_id": 123,
        "limit": 20
    }
    """
    start_time = time.time()
    query_count = 0
    
    try:
        # 分散トレーシングヘッダーを処理
        process_distributed_trace_headers()
        
        # リクエストデータを取得
        data = request.get_json() or {}
        user_id = data.get('user_id')
        limit = data.get('limit', 20)
        
        # Custom Attributeを設定
        set_user_custom_attribute(user_id)
        set_operation_custom_attribute('n_plus_one')
        newrelic.agent.add_custom_attribute('query_limit', limit)
        
        logger.info(f"N+1クエリ開始: user_id={user_id}, limit={limit}")
        
        # モデルクラスとデータベースインスタンスを取得
        User, Product, Order, OrderItem, db = get_models_and_db()
        
        # テストデータが存在することを確認
        ensure_test_data(User, Product, Order, OrderItem, db)
        
        logger.info(f"N+1クエリ問題を実行: limit={limit}")
        
        # 1. 最初のクエリ：商品一覧を取得（実際のクエリ）
        products = Product.query.limit(limit).all()
        query_count += 1
        logger.info(f"商品一覧取得: {len(products)}件")
        
        results = []
        
        # 2. N個のクエリ：各商品に対して注文アイテム数を個別に取得（N+1問題）
        for product in products:
            # 各商品ごとに個別のクエリを実行（N+1問題）
            order_count = OrderItem.query.filter_by(product_id=product.id).count()
            query_count += 1
            
            # さらに各商品の最新注文も個別に取得
            latest_order = db.session.query(Order).join(OrderItem).filter(
                OrderItem.product_id == product.id
            ).order_by(Order.created_at.desc()).first()
            query_count += 1
            
            results.append({
                'product_id': product.id,
                'product_name': product.name,
                'price': float(product.price),
                'order_count': order_count,
                'latest_order_id': latest_order.id if latest_order else None,
                'latest_order_date': latest_order.created_at.isoformat() if latest_order else None
            })
        
        execution_time = time.time() - start_time
        
        # ログ出力
        logger.info(f"N+1クエリ完了: クエリ実行回数={query_count}, 実行時間={execution_time:.3f}秒")
        
        # New RelicにCustom Attributeとして実行情報を追加
        newrelic.agent.add_custom_attribute('total_queries', query_count)
        newrelic.agent.add_custom_attribute('execution_time_seconds', execution_time)
        newrelic.agent.add_custom_attribute('products_processed', len(results))
        
        return jsonify({
            'status': 'success',
            'operation': 'n_plus_one',
            'user_id': user_id,
            'data': {
                'products': results,
                'query_count': query_count,
                'execution_time': execution_time,
                'products_processed': len(results)
            },
            'performance_metrics': {
                'total_queries': query_count,
                'execution_time_seconds': execution_time,
                'queries_per_product': query_count / len(products) if products else 0
            }
        })
        
    except Exception as e:
        execution_time = time.time() - start_time
        
        # エラーハンドリング（強化版）
        from error_handler import DistributedServiceErrorHandler
        
        # データベースエラーかどうかを判定
        from sqlalchemy.exc import SQLAlchemyError
        if isinstance(e, SQLAlchemyError):
            response_data, status_code = DistributedServiceErrorHandler.handle_database_error(
                error=e,
                user_id=user_id,
                operation='n_plus_one',
                context={
                    'execution_time': execution_time,
                    'query_count': query_count,
                    'limit': data.get('limit', 20)
                }
            )
        else:
            response_data, status_code = DistributedServiceErrorHandler.handle_general_error(
                error=e,
                user_id=user_id,
                operation='n_plus_one',
                context={
                    'execution_time': execution_time,
                    'query_count': query_count,
                    'limit': data.get('limit', 20)
                }
            )
        
        return jsonify(response_data), status_code


@performance_bp.route('/slow-query', methods=['POST'])
@newrelic.agent.function_trace()
def slow_query():
    """
    スロークエリを発生させるエンドポイント
    pg_sleepと複雑なJOINを使用
    
    Request JSON:
    {
        "user_id": 123,
        "sleep_duration": 3.0,
        "query_type": "sleep|complex_join|cartesian_product"
    }
    """
    start_time = time.time()
    
    try:
        # 分散トレーシングヘッダーを処理
        process_distributed_trace_headers()
        
        # リクエストデータを取得
        data = request.get_json() or {}
        user_id = data.get('user_id')
        sleep_duration = data.get('sleep_duration', random.uniform(3.0, 5.0))
        query_type = data.get('query_type', 'sleep')
        
        # Custom Attributeを設定
        set_user_custom_attribute(user_id)
        set_operation_custom_attribute('slow_query')
        newrelic.agent.add_custom_attribute('sleep_duration', sleep_duration)
        newrelic.agent.add_custom_attribute('query_type', query_type)
        
        logger.info(f"スロークエリ開始: user_id={user_id}, type={query_type}, duration={sleep_duration}")
        
        # モデルクラスとデータベースインスタンスを取得
        User, Product, Order, OrderItem, db = get_models_and_db()
        
        # テストデータが存在することを確認
        ensure_test_data(User, Product, Order, OrderItem, db)
        
        results = {}
        
        if query_type == 'sleep':
            # pg_sleepを使った実際の遅延
            logger.info(f"pg_sleep実行: {sleep_duration}秒")
            db.session.execute(text(f"SELECT pg_sleep({sleep_duration})"))
            results['sleep_executed'] = True
            results['sleep_duration'] = sleep_duration
            
        elif query_type == 'complex_join':
            # 複雑なJOINクエリ
            logger.info("複雑なJOINクエリ実行")
            
            # 複数テーブルを結合した重いクエリ
            complex_query = text("""
                SELECT 
                    u.id as user_id,
                    u.username,
                    COUNT(DISTINCT o.id) as order_count,
                    COUNT(DISTINCT oi.id) as order_item_count,
                    COUNT(DISTINCT p.id) as unique_products,
                    SUM(oi.quantity * oi.price) as total_spent,
                    AVG(oi.price) as avg_item_price,
                    MAX(o.created_at) as last_order_date
                FROM users u
                LEFT JOIN orders o ON u.id = o.user_id
                LEFT JOIN order_items oi ON o.id = oi.order_id
                LEFT JOIN products p ON oi.product_id = p.id
                GROUP BY u.id, u.username
                HAVING COUNT(o.id) > 0
                ORDER BY total_spent DESC, order_count DESC
                LIMIT 50
            """)
            
            result = db.session.execute(complex_query)
            complex_results = []
            for row in result:
                complex_results.append({
                    'user_id': row.user_id,
                    'username': row.username,
                    'order_count': row.order_count,
                    'order_item_count': row.order_item_count,
                    'unique_products': row.unique_products,
                    'total_spent': float(row.total_spent) if row.total_spent else 0,
                    'avg_item_price': float(row.avg_item_price) if row.avg_item_price else 0,
                    'last_order_date': row.last_order_date.isoformat() if row.last_order_date else None
                })
            
            results['complex_join_results'] = complex_results
            results['records_processed'] = len(complex_results)
            
        elif query_type == 'cartesian_product':
            # Cartesian Productを発生させる重いクエリ
            logger.info("Cartesian Productクエリ実行")
            
            cartesian_query = text("""
                SELECT 
                    p1.id as product1_id,
                    p1.name as product1_name,
                    p2.id as product2_id,
                    p2.name as product2_name,
                    (p1.price + p2.price) as combined_price
                FROM products p1, products p2
                WHERE p1.id != p2.id 
                AND p1.price > 0 
                AND p2.price > 0
                LIMIT 100
            """)
            
            result = db.session.execute(cartesian_query)
            cartesian_results = []
            for row in result:
                cartesian_results.append({
                    'product1_id': row.product1_id,
                    'product1_name': row.product1_name,
                    'product2_id': row.product2_id,
                    'product2_name': row.product2_name,
                    'combined_price': float(row.combined_price)
                })
            
            results['cartesian_results'] = cartesian_results
            results['combinations_generated'] = len(cartesian_results)
        
        # 追加の遅延（すべてのクエリタイプに適用）
        if sleep_duration > 0:
            additional_sleep = min(sleep_duration * 0.3, 2.0)  # 最大2秒の追加遅延
            db.session.execute(text(f"SELECT pg_sleep({additional_sleep})"))
            results['additional_sleep'] = additional_sleep
        
        execution_time = time.time() - start_time
        
        # ログ出力
        logger.info(f"スロークエリ完了: type={query_type}, 実行時間={execution_time:.3f}秒")
        
        # New RelicにCustom Attributeとして実行情報を追加
        newrelic.agent.add_custom_attribute('execution_time_seconds', execution_time)
        newrelic.agent.add_custom_attribute('slow_query_completed', True)
        
        return jsonify({
            'status': 'success',
            'operation': 'slow_query',
            'user_id': user_id,
            'query_type': query_type,
            'data': results,
            'performance_metrics': {
                'execution_time_seconds': execution_time,
                'sleep_duration': sleep_duration,
                'query_complexity': 'high' if query_type in ['complex_join', 'cartesian_product'] else 'medium'
            }
        })
        
    except Exception as e:
        execution_time = time.time() - start_time
        
        # エラーハンドリング（強化版）
        from error_handler import DistributedServiceErrorHandler
        
        # データベースエラーかどうかを判定
        from sqlalchemy.exc import SQLAlchemyError
        if isinstance(e, SQLAlchemyError):
            response_data, status_code = DistributedServiceErrorHandler.handle_database_error(
                error=e,
                user_id=user_id,
                operation='slow_query',
                context={
                    'execution_time': execution_time,
                    'sleep_duration': data.get('sleep_duration', 3.0),
                    'query_type': data.get('query_type', 'sleep')
                }
            )
        else:
            response_data, status_code = DistributedServiceErrorHandler.handle_general_error(
                error=e,
                user_id=user_id,
                operation='slow_query',
                context={
                    'execution_time': execution_time,
                    'sleep_duration': data.get('sleep_duration', 3.0),
                    'query_type': data.get('query_type', 'sleep')
                }
            )
        
        return jsonify(response_data), status_code


@performance_bp.route('/database-error', methods=['POST'])
@newrelic.agent.function_trace()
def database_error():
    """
    データベースエラーを意図的に発生させるエンドポイント
    
    Request JSON:
    {
        "user_id": 123,
        "error_type": "syntax|constraint|connection|timeout"
    }
    """
    start_time = time.time()
    
    try:
        # 分散トレーシングヘッダーを処理
        process_distributed_trace_headers()
        
        # リクエストデータを取得
        data = request.get_json() or {}
        user_id = data.get('user_id')
        error_type = data.get('error_type', 'syntax')
        
        # Custom Attributeを設定
        set_user_custom_attribute(user_id)
        set_operation_custom_attribute('database_error')
        newrelic.agent.add_custom_attribute('error_type', error_type)
        newrelic.agent.add_custom_attribute('intentional_error', True)
        
        logger.info(f"データベースエラー開始: user_id={user_id}, error_type={error_type}")
        
        # モデルクラスとデータベースインスタンスを取得
        User, Product, Order, OrderItem, db = get_models_and_db()
        
        error_details = {}
        
        if error_type == 'syntax':
            # SQLシンタックスエラーを発生させる
            logger.info("SQLシンタックスエラーを発生させます")
            error_details['attempted_query'] = "SELECT * FROM non_existent_table WHERE invalid_syntax"
            db.session.execute(text("SELECT * FROM non_existent_table WHERE invalid_syntax"))
            
        elif error_type == 'constraint':
            # 制約違反エラーを発生させる
            logger.info("制約違反エラーを発生させます")
            error_details['attempted_operation'] = "Duplicate key insertion"
            
            # 既存のユーザー名で新しいユーザーを作成しようとする（UNIQUE制約違反）
            existing_user = User.query.first()
            if existing_user:
                duplicate_user = User(
                    username=existing_user.username,  # 重複するユーザー名
                    email=f"duplicate_{existing_user.email}",
                    password_hash="dummy_hash"
                )
                db.session.add(duplicate_user)
                db.session.commit()
            else:
                # ユーザーが存在しない場合は、無効な外部キーを使用
                invalid_order = Order(
                    user_id=99999,  # 存在しないユーザーID
                    total_amount=100.00
                )
                db.session.add(invalid_order)
                db.session.commit()
                
        elif error_type == 'connection':
            # 接続エラーをシミュレート（無効なクエリで接続を混乱させる）
            logger.info("接続エラーをシミュレートします")
            error_details['attempted_operation'] = "Connection disruption simulation"
            
            # 非常に長いクエリでタイムアウトを誘発
            db.session.execute(text("""
                SELECT COUNT(*) FROM (
                    SELECT generate_series(1, 1000000) as id
                ) t1 
                CROSS JOIN (
                    SELECT generate_series(1, 1000) as id
                ) t2
            """))
            
        elif error_type == 'timeout':
            # タイムアウトエラーを発生させる
            logger.info("タイムアウトエラーを発生させます")
            error_details['attempted_operation'] = "Long running query timeout"
            
            # 非常に長い処理でタイムアウトを誘発
            db.session.execute(text("SELECT pg_sleep(30)"))  # 30秒の遅延
            
        else:
            # 不明なエラータイプの場合はデフォルトでシンタックスエラー
            logger.info("不明なエラータイプ、デフォルトエラーを発生させます")
            error_details['attempted_query'] = "SELECT invalid_column FROM invalid_table"
            db.session.execute(text("SELECT invalid_column FROM invalid_table"))
        
        # ここに到達することはないはず（エラーが発生するため）
        execution_time = time.time() - start_time
        logger.warning(f"予期しない成功: error_type={error_type}, 実行時間={execution_time:.3f}秒")
        
        return jsonify({
            'status': 'unexpected_success',
            'operation': 'database_error',
            'user_id': user_id,
            'error_type': error_type,
            'message': 'エラーが発生するはずでしたが、処理が成功しました',
            'execution_time': execution_time
        })
        
    except Exception as e:
        execution_time = time.time() - start_time
        error_message = str(e)
        
        logger.error(f"データベースエラー発生（意図的）: {error_message}, 実行時間={execution_time:.3f}秒")
        
        # エラーをNew Relicに報告（Custom Attributeを含む）
        newrelic.agent.add_custom_attribute('database_error_message', error_message)
        newrelic.agent.add_custom_attribute('error_execution_time', execution_time)
        report_error_to_newrelic(e, user_id, 'database_error')
        
        # エラーの種類を判定
        error_category = 'unknown'
        if 'does not exist' in error_message.lower():
            error_category = 'table_not_found'
        elif 'duplicate key' in error_message.lower() or 'unique constraint' in error_message.lower():
            error_category = 'constraint_violation'
        elif 'syntax error' in error_message.lower():
            error_category = 'syntax_error'
        elif 'timeout' in error_message.lower() or 'connection' in error_message.lower():
            error_category = 'connection_error'
        
        newrelic.agent.add_custom_attribute('error_category', error_category)
        
        return jsonify({
            'status': 'error',
            'operation': 'database_error',
            'user_id': user_id,
            'error_type': error_type,
            'error_category': error_category,
            'error_message': error_message,
            'execution_time': execution_time,
            'intentional': True,
            'new_relic_reported': True
        }), 500


@performance_bp.route('/test-all', methods=['POST'])
@newrelic.agent.function_trace()
def test_all_performance_issues():
    """
    すべてのパフォーマンス問題を順次実行するテストエンドポイント
    
    Request JSON:
    {
        "user_id": 123
    }
    """
    start_time = time.time()
    
    try:
        # 分散トレーシングヘッダーを処理
        process_distributed_trace_headers()
        
        # リクエストデータを取得
        data = request.get_json() or {}
        user_id = data.get('user_id')
        
        # Custom Attributeを設定
        set_user_custom_attribute(user_id)
        set_operation_custom_attribute('test_all')
        
        logger.info(f"全パフォーマンステスト開始: user_id={user_id}")
        
        results = {
            'n_plus_one': None,
            'slow_query': None,
            'database_error': None
        }
        
        # モデルクラスとデータベースインスタンスを取得
        User, Product, Order, OrderItem, db = get_models_and_db()
        
        # テストデータが存在することを確認
        ensure_test_data(User, Product, Order, OrderItem, db)
        
        # 1. N+1クエリテスト
        try:
            logger.info("N+1クエリテスト実行中...")
            # 内部的にN+1クエリ関数を呼び出し（簡略版）
            products = Product.query.limit(5).all()
            query_count = 1
            for product in products:
                OrderItem.query.filter_by(product_id=product.id).count()
                query_count += 1
            
            results['n_plus_one'] = {
                'status': 'success',
                'query_count': query_count,
                'products_processed': len(products)
            }
        except Exception as e:
            results['n_plus_one'] = {'status': 'error', 'error': str(e)}
        
        # 2. スロークエリテスト
        try:
            logger.info("スロークエリテスト実行中...")
            db.session.execute(text("SELECT pg_sleep(1)"))  # 短縮版
            results['slow_query'] = {'status': 'success', 'sleep_duration': 1.0}
        except Exception as e:
            results['slow_query'] = {'status': 'error', 'error': str(e)}
        
        # 3. データベースエラーテスト
        try:
            logger.info("データベースエラーテスト実行中...")
            db.session.execute(text("SELECT * FROM non_existent_table_test"))
        except Exception as e:
            results['database_error'] = {
                'status': 'error_as_expected',
                'error': str(e)
            }
        
        execution_time = time.time() - start_time
        
        logger.info(f"全パフォーマンステスト完了: 実行時間={execution_time:.3f}秒")
        
        # New RelicにCustom Attributeとして実行情報を追加
        newrelic.agent.add_custom_attribute('total_execution_time', execution_time)
        newrelic.agent.add_custom_attribute('all_tests_completed', True)
        
        return jsonify({
            'status': 'completed',
            'operation': 'test_all',
            'user_id': user_id,
            'results': results,
            'total_execution_time': execution_time,
            'summary': {
                'n_plus_one_success': results['n_plus_one']['status'] == 'success',
                'slow_query_success': results['slow_query']['status'] == 'success',
                'database_error_triggered': results['database_error']['status'] == 'error_as_expected'
            }
        })
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"全パフォーマンステストエラー: {e}, 実行時間={execution_time:.3f}秒")
        
        # エラーをNew Relicに報告
        report_error_to_newrelic(e, user_id, 'test_all')
        
        return jsonify({
            'status': 'error',
            'operation': 'test_all',
            'user_id': user_id,
            'error': str(e),
            'execution_time': execution_time
        }), 500