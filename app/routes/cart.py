from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import CartItem, Product, Order, OrderItem

bp = Blueprint('cart', __name__, url_prefix='/cart')

@bp.route('/')
@login_required
def view_cart():
    current_app.logger.info(f'Cart viewed by user {current_user.id}', extra={
        'event_type': 'page_view',
        'page': 'cart',
        'user_id': current_user.id
    })

    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)

    current_app.logger.info(f'Cart contains {len(cart_items)} items, total: ¥{total}', extra={
        'event_type': 'cart_viewed',
        'user_id': current_user.id,
        'item_count': len(cart_items),
        'total_amount': float(total)
    })

    return render_template('cart.html', cart_items=cart_items, total=total)

@bp.route('/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = request.form.get('quantity', 1, type=int)

    current_app.logger.info(f'User {current_user.id} adding product {product_id} to cart', extra={
        'event_type': 'cart_add',
        'user_id': current_user.id,
        'product_id': product_id,
        'product_name': product.name,
        'quantity': quantity,
        'price': float(product.price)
    })

    cart_item = CartItem.query.filter_by(
        user_id=current_user.id,
        product_id=product_id
    ).first()

    if cart_item:
        old_quantity = cart_item.quantity
        cart_item.quantity += quantity
        current_app.logger.info(f'Updated cart item quantity from {old_quantity} to {cart_item.quantity}')
    else:
        cart_item = CartItem(
            user_id=current_user.id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)
        current_app.logger.info('New cart item created')

    db.session.commit()

    current_app.logger.info('Product successfully added to cart', extra={
        'event_type': 'cart_add_success',
        'user_id': current_user.id,
        'product_id': product_id
    })

    flash('Product added to cart!')
    return redirect(url_for('cart.view_cart'))

@bp.route('/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.user_id != current_user.id:
        flash('Unauthorized')
        return redirect(url_for('cart.view_cart'))

    db.session.delete(cart_item)
    db.session.commit()
    flash('Item removed from cart')
    return redirect(url_for('cart.view_cart'))

@bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    current_app.logger.info(f'Checkout initiated by user {current_user.id}', extra={
        'event_type': 'checkout_start',
        'user_id': current_user.id
    })

    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()

    if not cart_items:
        current_app.logger.warning(f'Checkout attempted with empty cart', extra={
            'event_type': 'checkout_error',
            'user_id': current_user.id,
            'error': 'empty_cart'
        })
        flash('Cart is empty')
        return redirect(url_for('cart.view_cart'))

    total = sum(item.product.price * item.quantity for item in cart_items)

    current_app.logger.info(f'Creating order for user {current_user.id}', extra={
        'event_type': 'order_create',
        'user_id': current_user.id,
        'item_count': len(cart_items),
        'total_amount': float(total)
    })

    order = Order(user_id=current_user.id, total_amount=total)
    db.session.add(order)

    for cart_item in cart_items:
        order_item = OrderItem(
            order=order,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            price=cart_item.product.price
        )
        db.session.add(order_item)
        current_app.logger.debug(f'Added order item: {cart_item.product.name} x{cart_item.quantity}')
        db.session.delete(cart_item)

    db.session.commit()

    current_app.logger.info(f'Order placed successfully', extra={
        'event_type': 'order_success',
        'user_id': current_user.id,
        'order_id': order.id,
        'total_amount': float(total)
    })

    flash('Order placed successfully!')
    return redirect(url_for('main.index'))
