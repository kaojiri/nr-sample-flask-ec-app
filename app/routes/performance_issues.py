"""
Performance Issues Routes - FOR DEMO/TESTING PURPOSES ONLY

This module contains intentionally problematic endpoints to demonstrate
New Relic's monitoring and detection capabilities.

WARNING: Do NOT use these routes in production!
"""
from flask import Blueprint, render_template, jsonify, current_app
from app import db
from app.models import Product, Order, OrderItem
from sqlalchemy import text, func
import time
import random

bp = Blueprint('performance', __name__, url_prefix='/performance')


@bp.route('/')
def index():
    """Index page listing all performance issue demos"""
    current_app.logger.info('Performance demo index accessed', extra={
        'event_type': 'demo_page_view',
        'page': 'performance_index'
    })
    return render_template('performance/index.html')


@bp.route('/slow')
def slow_endpoint():
    """
    Intentionally slow endpoint (3-5 seconds)

    New Relic will detect:
    - High transaction time
    - Low Apdex score
    - Slow transaction traces
    """
    delay = random.uniform(3.0, 5.0)
    current_app.logger.warning(f'Slow endpoint accessed - will delay for {delay:.2f} seconds', extra={
        'event_type': 'slow_transaction_start',
        'delay_seconds': delay
    })

    # Simulate slow external API call
    current_app.logger.info('Simulating slow external API call')
    time.sleep(delay)
    current_app.logger.info('External API call completed')

    # Simulate heavy computation
    current_app.logger.info('Starting heavy computation')
    result = 0
    for i in range(1000000):
        result += i ** 2
    current_app.logger.info(f'Heavy computation completed: result={result}')

    # Another slow operation
    current_app.logger.info('Additional slow operation')
    time.sleep(1.5)

    products = Product.query.limit(10).all()

    current_app.logger.warning(f'Slow endpoint completed - total time: {delay + 1.5:.2f}s', extra={
        'event_type': 'slow_transaction_complete',
        'total_time': delay + 1.5
    })

    return render_template('performance/slow.html',
                         products=products,
                         computation_result=result)


@bp.route('/n-plus-one')
def n_plus_one_problem():
    """
    N+1 Query Problem

    New Relic will detect:
    - High number of database queries
    - Multiple similar SQL queries
    - Database performance issues
    """
    # Bad: N+1 query problem
    products = Product.query.limit(20).all()  # 1 query

    product_data = []
    for product in products:
        # N queries - one for each product
        order_count = db.session.query(OrderItem)\
            .filter(OrderItem.product_id == product.id)\
            .count()

        # Another query per product
        total_revenue = db.session.query(db.func.sum(OrderItem.price * OrderItem.quantity))\
            .filter(OrderItem.product_id == product.id)\
            .scalar() or 0

        product_data.append({
            'product': product,
            'order_count': order_count,
            'revenue': total_revenue
        })

    return render_template('performance/n_plus_one.html',
                         product_data=product_data)


@bp.route('/n-plus-one-fixed')
def n_plus_one_fixed():
    """
    Fixed version using proper joins

    This shows the correct way to avoid N+1 queries
    for comparison in New Relic
    """
    # Good: Single query with join
    from sqlalchemy import func

    product_data = db.session.query(
        Product,
        func.count(OrderItem.id).label('order_count'),
        func.sum(OrderItem.price * OrderItem.quantity).label('revenue')
    ).outerjoin(OrderItem, Product.id == OrderItem.product_id)\
     .group_by(Product.id)\
     .limit(20)\
     .all()

    formatted_data = [{
        'product': product,
        'order_count': order_count or 0,
        'revenue': revenue or 0
    } for product, order_count, revenue in product_data]

    return render_template('performance/n_plus_one.html',
                         product_data=formatted_data)


@bp.route('/bad-vitals')
def bad_core_web_vitals():
    """
    Page with poor Core Web Vitals

    New Relic Browser will detect:
    - High LCP (Largest Contentful Paint)
    - High INP (Interaction to Next Paint)
    - High CLS (Cumulative Layout Shift)
    """
    products = Product.query.limit(50).all()

    return render_template('performance/bad_vitals.html',
                         products=products)


@bp.route('/memory-intensive')
def memory_intensive():
    """
    Memory-intensive operation

    New Relic will detect:
    - High memory usage
    - Potential memory leaks
    """
    # Create large data structures
    large_list = []
    for i in range(100000):
        large_list.append({
            'id': i,
            'data': 'x' * 1000,  # 1KB per item = 100MB total
            'nested': {
                'value': i ** 2,
                'description': 'Memory intensive operation ' * 10
            }
        })

    # Sleep to keep memory allocated
    time.sleep(2)

    return jsonify({
        'status': 'completed',
        'items_processed': len(large_list),
        'memory_note': 'This endpoint uses ~100MB of memory'
    })


@bp.route('/error')
def trigger_error():
    """
    Endpoint that always raises an error

    New Relic will detect:
    - Error rate increase
    - Exception details
    - Stack traces
    """
    current_app.logger.error('Intentional error endpoint accessed', extra={
        'event_type': 'error_demo',
        'error_type': 'intentional'
    })

    # Intentional error
    raise Exception("This is a demo error for New Relic monitoring")


@bp.route('/random-error')
def random_error():
    """
    Endpoint with 30% error rate

    New Relic will detect:
    - Fluctuating error rate
    - Error patterns
    """
    if random.random() < 0.3:  # 30% chance of error
        raise Exception("Random error occurred (30% probability)")

    return jsonify({'status': 'success', 'message': 'No error this time'})


@bp.route('/database-timeout')
def database_timeout():
    """
    Simulates a database timeout

    New Relic will detect:
    - Database performance issues
    - Slow queries
    """
    # Simulate a very slow query
    time.sleep(5)

    # Execute a query after the delay
    products = Product.query.limit(5).all()

    return jsonify({
        'status': 'completed',
        'products_count': len(products),
        'note': 'This query took 5+ seconds'
    })


@bp.route('/high-cpu')
def high_cpu():
    """
    CPU-intensive operation

    New Relic will detect:
    - High CPU usage
    - Long-running transactions
    """
    # CPU-intensive calculation
    result = 0
    for i in range(10000000):  # 10 million iterations
        result += (i ** 2) % 997

    # More CPU work
    fibonacci = [0, 1]
    for i in range(100000):
        fibonacci.append(fibonacci[-1] + fibonacci[-2])

    return jsonify({
        'status': 'completed',
        'result': result,
        'fibonacci_length': len(fibonacci)
    })


@bp.route('/js-errors')
def js_errors():
    """
    JavaScript errors demo page

    New Relic Browser will detect:
    - JavaScript errors and stack traces
    - Unhandled promise rejections
    - Network errors
    - Custom errors with attributes
    """
    current_app.logger.info('JavaScript errors demo page accessed', extra={
        'event_type': 'demo_page_view',
        'page': 'js_errors'
    })
    return render_template('performance/js_errors.html')


@bp.route('/js-error/null-reference')
def js_error_null():
    """Page that triggers null reference error"""
    return render_template('performance/js_error_null.html')


@bp.route('/js-error/undefined-function')
def js_error_undefined():
    """Page that triggers undefined function error"""
    return render_template('performance/js_error_undefined.html')


@bp.route('/js-error/promise-rejection')
def js_error_promise():
    """Page that triggers unhandled promise rejection"""
    return render_template('performance/js_error_promise.html')


@bp.route('/js-error/async-error')
def js_error_async():
    """Page that triggers async error"""
    return render_template('performance/js_error_async.html')


@bp.route('/js-error/network-error')
def js_error_network():
    """Page that triggers network error"""
    return render_template('performance/js_error_network.html')


@bp.route('/api/fail')
def api_fail():
    """API endpoint that always fails for testing network errors"""
    current_app.logger.error('API endpoint intentionally failed', extra={
        'event_type': 'api_error_demo'
    })
    return jsonify({'error': 'This endpoint always fails'}), 500


@bp.route('/slow-query')
def slow_query_index():
    """
    Slow Query demo page

    New Relic will detect:
    - Slow database queries
    - Query execution time
    - Explain plans
    - Database performance issues
    """
    current_app.logger.info('Slow query demo page accessed', extra={
        'event_type': 'demo_page_view',
        'page': 'slow_query'
    })
    return render_template('performance/slow_query.html')


@bp.route('/slow-query/sleep')
def slow_query_sleep():
    """
    Intentionally slow query using pg_sleep()

    New Relic will detect:
    - Query taking 3-5 seconds
    - High database time in transaction traces
    - SQL statement with pg_sleep
    """
    sleep_duration = random.uniform(3.0, 5.0)
    current_app.logger.warning(f'Executing slow query with pg_sleep({sleep_duration:.2f})', extra={
        'event_type': 'slow_query_demo',
        'query_type': 'pg_sleep',
        'duration': sleep_duration
    })

    # Execute slow query using pg_sleep
    db.session.execute(text(f"SELECT pg_sleep({sleep_duration})"))
    db.session.commit()

    # Get some products
    products = Product.query.limit(10).all()

    current_app.logger.info(f'Slow query completed: {len(products)} products retrieved', extra={
        'event_type': 'slow_query_complete',
        'product_count': len(products)
    })

    return render_template('performance/slow_query_result.html',
                         query_type='pg_sleep',
                         duration=sleep_duration,
                         result_count=len(products),
                         description='PostgreSQL pg_sleep()を使った意図的な遅延クエリ')


@bp.route('/slow-query/full-scan')
def slow_query_full_scan():
    """
    Slow query with full table scan (no index)

    New Relic will detect:
    - Full table scan
    - High query execution time
    - LIKE query without index
    """
    current_app.logger.warning('Executing slow query with full table scan', extra={
        'event_type': 'slow_query_demo',
        'query_type': 'full_scan'
    })

    start_time = time.time()

    # Moderately heavy database query - balanced for Slow Query detection
    # Window functions + full table scan, but without O(N²) subqueries
    result = db.session.execute(text("""
        SELECT
            p.id,
            p.name,
            p.description,
            p.price,
            p.category,
            -- Window functions - moderately expensive operations
            ROW_NUMBER() OVER (ORDER BY p.price DESC) as price_rank,
            DENSE_RANK() OVER (PARTITION BY p.category ORDER BY p.created_at DESC) as category_rank,
            -- String operations - CPU intensive
            LENGTH(p.description) as desc_length,
            UPPER(p.name) as upper_name,
            LOWER(p.category) as lower_category
        FROM products p
        WHERE
            -- LIKE with leading wildcard - forces full table scan
            p.description LIKE '%商品%' OR
            p.description LIKE '%説明%' OR
            p.name LIKE '%品%' OR
            LENGTH(p.description) > 100
        ORDER BY
            LENGTH(p.description) DESC,
            p.price DESC,
            p.created_at DESC
        LIMIT 10000
    """))

    # Fetch only count to minimize Python processing
    result_list = result.fetchall()
    result_count = len(result_list)

    duration = time.time() - start_time

    current_app.logger.warning(f'Full table scan completed in {duration:.2f}s', extra={
        'event_type': 'slow_query_complete',
        'query_type': 'full_scan',
        'duration': duration,
        'result_count': result_count
    })

    return render_template('performance/slow_query_result.html',
                         query_type='full_scan',
                         duration=duration,
                         result_count=result_count,
                         description='LIKE句 + ウィンドウ関数によるフルテーブルスキャン（データベースレベルで遅い）')


@bp.route('/slow-query/complex-join')
def slow_query_complex_join():
    """
    Slow query with complex JOINs and aggregations

    New Relic will detect:
    - Multiple JOIN operations
    - Complex GROUP BY and HAVING clauses
    - Aggregation functions
    """
    current_app.logger.warning('Executing slow query with complex JOINs', extra={
        'event_type': 'slow_query_demo',
        'query_type': 'complex_join'
    })

    start_time = time.time()

    # Complex query with multiple aggregations
    # REMOVED LIMIT - process all products to make it truly slow
    # Added description field (large TEXT field) to increase data transfer
    result = db.session.query(
        Product.id,
        Product.name,
        Product.description,  # Large field - increases data transfer time
        Product.category,
        func.count(OrderItem.id).label('order_count'),
        func.sum(OrderItem.quantity).label('total_sold'),
        func.avg(OrderItem.price).label('avg_price'),
        func.max(OrderItem.price).label('max_price'),
        func.min(OrderItem.price).label('min_price'),
        func.sum(OrderItem.price * OrderItem.quantity).label('total_revenue')
    ).outerjoin(OrderItem, Product.id == OrderItem.product_id)\
     .group_by(Product.id, Product.name, Product.description, Product.category)\
     .having(func.count(OrderItem.id) >= 0)\
     .order_by(func.count(OrderItem.id).desc(), func.sum(OrderItem.price * OrderItem.quantity).desc())\
     .all()  # NO LIMIT - scan and aggregate all products

    duration = time.time() - start_time

    current_app.logger.warning(f'Complex JOIN query completed in {duration:.2f}s', extra={
        'event_type': 'slow_query_complete',
        'query_type': 'complex_join',
        'duration': duration,
        'result_count': len(result)
    })

    return render_template('performance/slow_query_result.html',
                         query_type='complex_join',
                         duration=duration,
                         result_count=len(result),
                         description='複数のJOINと集計関数を使った複雑なクエリ')


@bp.route('/slow-query/cartesian')
def slow_query_cartesian():
    """
    Slow query with Cartesian product (missing JOIN condition)

    New Relic will detect:
    - Cartesian product (cross join)
    - Extremely high row count
    - Missing JOIN condition warning
    """
    current_app.logger.warning('Executing slow query with Cartesian product', extra={
        'event_type': 'slow_query_demo',
        'query_type': 'cartesian_product'
    })

    start_time = time.time()

    # Intentional Cartesian product - missing JOIN condition
    # This will create product_count × order_count rows
    # INCREASED LIMIT to 50000 to make it much slower (was 100)
    # WARNING: This can generate millions of rows!
    result = db.session.query(Product.id, Product.name, Product.price, Order.id, Order.status)\
        .select_from(Product)\
        .join(Order, text('1=1'))\
        .limit(50000)\
        .all()

    duration = time.time() - start_time

    current_app.logger.warning(f'Cartesian product query completed in {duration:.2f}s', extra={
        'event_type': 'slow_query_complete',
        'query_type': 'cartesian_product',
        'duration': duration,
        'result_count': len(result)
    })

    return render_template('performance/slow_query_result.html',
                         query_type='cartesian',
                         duration=duration,
                         result_count=len(result),
                         description='JOIN条件のないCartesian Product（直積結合）')


@bp.route('/slow-query/no-limit')
def slow_query_no_limit():
    """
    Query without LIMIT - fetches all records

    New Relic will detect:
    - Large result set
    - High memory usage
    - Long data transfer time
    """
    current_app.logger.warning('Executing query without LIMIT', extra={
        'event_type': 'slow_query_demo',
        'query_type': 'no_limit'
    })

    start_time = time.time()

    # Fetch all products without limit
    # Added sorting to make it slower (requires sorting large dataset)
    products = Product.query\
        .order_by(Product.description.desc(), Product.price.desc(), Product.created_at.desc())\
        .all()  # No LIMIT - fetch everything

    duration = time.time() - start_time

    current_app.logger.warning(f'No-limit query completed in {duration:.2f}s', extra={
        'event_type': 'slow_query_complete',
        'query_type': 'no_limit',
        'duration': duration,
        'result_count': len(products)
    })

    return render_template('performance/slow_query_result.html',
                         query_type='no_limit',
                         duration=duration,
                         result_count=len(products),
                         description='LIMIT句なしで全レコードを取得')


@bp.route('/slow-query/sequential-scan')
def slow_query_sequential_scan():
    """
    Sequential scan with string operations and functions

    New Relic will detect:
    - Full sequential scan
    - String function overhead
    - No index usage
    """
    current_app.logger.warning('Executing sequential scan with string operations', extra={
        'event_type': 'slow_query_demo',
        'query_type': 'sequential_scan'
    })

    start_time = time.time()

    # String operations that prevent index usage
    products = db.session.query(
        Product.id,
        Product.name,
        Product.description,
        func.length(Product.description).label('desc_length'),
        func.upper(Product.name).label('upper_name'),
        func.lower(Product.category).label('lower_category')
    ).filter(
        db.or_(
            Product.description.like('%商品%'),
            func.length(Product.description) > 100,
            func.upper(Product.name).like('%品%')
        )
    ).order_by(func.length(Product.description).desc()).all()

    duration = time.time() - start_time

    current_app.logger.warning(f'Sequential scan completed in {duration:.2f}s', extra={
        'event_type': 'slow_query_complete',
        'query_type': 'sequential_scan',
        'duration': duration,
        'result_count': len(products)
    })

    return render_template('performance/slow_query_result.html',
                         query_type='sequential_scan',
                         duration=duration,
                         result_count=len(products),
                         description='文字列関数を含むSequential Scan（インデックス使用不可）')


@bp.route('/generate-test-data')
def generate_test_data_page():
    """
    Test data generation page
    """
    # Get current counts
    product_count = Product.query.count()
    order_count = Order.query.count()
    order_item_count = OrderItem.query.count()

    return render_template('performance/generate_test_data.html',
                         product_count=product_count,
                         order_count=order_count,
                         order_item_count=order_item_count)


@bp.route('/generate-test-data/execute', methods=['POST'])
def generate_test_data_execute():
    """
    Generate large amount of test data

    This will make slow queries actually slow:
    - Products: 10,000 records
    - Orders: 5,000 records
    - OrderItems: 20,000 records
    """
    from flask import request
    from app.models import User

    num_products = int(request.form.get('num_products', 10000))
    num_orders = int(request.form.get('num_orders', 5000))
    num_order_items = int(request.form.get('num_order_items', 20000))

    current_app.logger.info(f'Starting test data generation: {num_products} products, {num_orders} orders, {num_order_items} order items')

    start_time = time.time()
    results = {
        'products_created': 0,
        'orders_created': 0,
        'order_items_created': 0
    }

    try:
        # Get or create test user (check both username and email to avoid UniqueViolation)
        test_user = User.query.filter(
            (User.email == 'testuser@example.com') |
            (User.username == 'testuser')
        ).first()

        if not test_user:
            test_user = User(username='testuser', email='testuser@example.com')
            test_user.set_password('password')
            db.session.add(test_user)
            db.session.commit()

        # Generate Products
        current_app.logger.info(f'Generating {num_products} products...')
        categories = ['Electronics', 'Books', 'Clothing', 'Food', 'Toys', 'Sports', 'Home', 'Beauty']

        existing_products = Product.query.count()
        products_to_create = []

        for i in range(num_products):
            product = Product(
                name=f'商品 {existing_products + i + 1} - {random.choice(["高品質", "お買い得", "人気", "新作", "限定"])}',
                description=f'これは商品番号 {existing_products + i + 1} の説明です。' * random.randint(1, 5),
                price=round(random.uniform(100, 50000), 2),
                stock=random.randint(0, 1000),
                category=random.choice(categories)
            )
            products_to_create.append(product)

            # Batch insert every 1000 records
            if len(products_to_create) >= 1000:
                db.session.bulk_save_objects(products_to_create)
                db.session.commit()
                results['products_created'] += len(products_to_create)
                current_app.logger.info(f'Inserted {results["products_created"]} products...')
                products_to_create = []

        # Insert remaining
        if products_to_create:
            db.session.bulk_save_objects(products_to_create)
            db.session.commit()
            results['products_created'] += len(products_to_create)

        current_app.logger.info(f'Products created: {results["products_created"]}')

        # Generate Orders and OrderItems
        current_app.logger.info(f'Generating {num_orders} orders with {num_order_items} order items...')

        all_products = Product.query.all()
        if not all_products:
            raise Exception("No products available to create orders")

        statuses = ['pending', 'processing', 'shipped', 'delivered']

        for i in range(num_orders):
            # Check if we've reached the order items limit
            if results['order_items_created'] >= num_order_items:
                current_app.logger.info(f'Reached order items limit. Created {results["orders_created"]} orders.')
                break

            order = Order(
                user_id=test_user.id,
                total_amount=0,
                status=random.choice(statuses)
            )
            db.session.add(order)
            db.session.flush()  # Get order.id

            # Calculate remaining order items that can be created
            remaining_items = num_order_items - results['order_items_created']

            # Skip if no items remaining (safety check)
            if remaining_items <= 0:
                current_app.logger.warning(f'No remaining items at order {i+1}. Breaking.')
                break

            # Create 1-10 order items per order (or remaining items if less than 10)
            items_in_order = random.randint(1, min(10, remaining_items))
            order_total = 0

            current_app.logger.debug(f'Order {i+1}: creating {items_in_order} items (remaining: {remaining_items})')

            for _ in range(items_in_order):
                if results['order_items_created'] >= num_order_items:
                    break

                product = random.choice(all_products)
                quantity = random.randint(1, 5)
                price = product.price

                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    price=price
                )
                db.session.add(order_item)
                order_total += float(price) * quantity
                results['order_items_created'] += 1

            order.total_amount = order_total
            results['orders_created'] += 1

            # Commit every 100 orders
            if (i + 1) % 100 == 0:
                db.session.commit()
                current_app.logger.info(f'Created {results["orders_created"]} orders, {results["order_items_created"]} order items...')

        db.session.commit()

        duration = time.time() - start_time

        current_app.logger.info(f'Test data generation completed in {duration:.2f}s', extra={
            'event_type': 'test_data_generated',
            **results
        })

        return render_template('performance/generate_test_data_result.html',
                             success=True,
                             duration=duration,
                             **results)

    except Exception as e:
        db.session.rollback()

        # Explicitly report error to New Relic
        # Note: Caught exceptions are NOT automatically reported by New Relic
        # We must use notice_error() to ensure they appear in Errors Inbox
        try:
            import newrelic.agent
            newrelic.agent.notice_error(
                error=(type(e), e, e.__traceback__),
                attributes={
                    'error_type': 'test_data_generation_failed',
                    'num_products_requested': num_products,
                    'num_orders_requested': num_orders,
                    'num_order_items_requested': num_order_items,
                    'products_created': results['products_created'],
                    'orders_created': results['orders_created'],
                    'order_items_created': results['order_items_created'],
                    'error_message': str(e)
                }
            )
        except ImportError:
            # New Relic is not installed or not running
            pass

        current_app.logger.error(f'Test data generation failed: {str(e)}', extra={
            'event_type': 'test_data_generation_failed',
            'error': str(e),
            'products_created': results['products_created'],
            'orders_created': results['orders_created'],
            'order_items_created': results['order_items_created']
        })

        # Return 500 status code to indicate server error
        return render_template('performance/generate_test_data_result.html',
                             success=False,
                             error=str(e),
                             **results), 500
