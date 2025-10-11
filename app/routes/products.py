from flask import Blueprint, render_template, request, current_app
from app.models import Product

bp = Blueprint('products', __name__, url_prefix='/products')

@bp.route('/')
def list_products():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category')

    current_app.logger.info(f'Products list requested', extra={
        'event_type': 'page_view',
        'page': 'products_list',
        'page_number': page,
        'category': category or 'all'
    })

    query = Product.query
    if category:
        query = query.filter_by(category=category)
        current_app.logger.info(f'Filtering products by category: {category}')

    products = query.paginate(page=page, per_page=12, error_out=False)

    current_app.logger.info(f'Displaying products page {page}', extra={
        'event_type': 'data_loaded',
        'product_count': len(products.items),
        'total_pages': products.pages
    })

    return render_template('products.html', products=products)

@bp.route('/<int:product_id>')
def product_detail(product_id):
    current_app.logger.info(f'Product detail requested: {product_id}', extra={
        'event_type': 'page_view',
        'page': 'product_detail',
        'product_id': product_id
    })

    product = Product.query.get_or_404(product_id)

    current_app.logger.info(f'Product found: {product.name}', extra={
        'event_type': 'product_viewed',
        'product_id': product.id,
        'product_name': product.name,
        'price': float(product.price),
        'stock': product.stock
    })

    return render_template('product_detail.html', product=product)
