from flask import Blueprint, render_template, current_app
from app.models import Product

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    current_app.logger.info('Home page accessed', extra={
        'event_type': 'page_view',
        'page': 'home'
    })

    products = Product.query.limit(12).all()

    current_app.logger.info(f'Displaying {len(products)} products on home page', extra={
        'event_type': 'data_loaded',
        'product_count': len(products)
    })

    return render_template('index.html', products=products)

@bp.route('/health')
def health():
    current_app.logger.debug('Health check endpoint called')
    return {'status': 'healthy'}, 200
