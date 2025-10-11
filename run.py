# New Relic initialization is handled by newrelic-admin in start.sh
# Do not initialize here to avoid double initialization

from app import create_app, db
from app.models import User, Product, Order, OrderItem, CartItem

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Product': Product,
        'Order': Order,
        'OrderItem': OrderItem,
        'CartItem': CartItem
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
