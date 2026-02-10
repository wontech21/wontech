"""
POS (Point of Sale) Routes
- Payment processing with Stripe
- Order management
- Receipt generation
"""

from flask import Blueprint, jsonify, request, g, session, current_app
import os
from datetime import datetime

from db_manager import get_org_db
from sales_operations import record_sales_to_db
from middleware import login_required, organization_required

pos_bp = Blueprint('pos', __name__, url_prefix='/api/pos')

# Try to import Stripe, but don't fail if not installed
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    stripe = None


def get_stripe():
    """Initialize Stripe with the secret key from config"""
    if not STRIPE_AVAILABLE:
        return None

    secret_key = current_app.config.get('STRIPE_SECRET_KEY')
    if secret_key:
        stripe.api_key = secret_key
        return stripe
    return None


# ==========================================
# PAYMENT INTENTS
# ==========================================

@pos_bp.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """
    Create a Stripe Payment Intent for card payments

    Expected JSON body:
    {
        "amount": 1099,  // Amount in cents
        "currency": "usd",
        "orderData": {
            "type": "dine-in",
            "items": [...],
            "customer": {...}
        }
    }
    """
    stripe_client = get_stripe()

    if not stripe_client:
        return jsonify({
            'error': 'Stripe is not configured. Please add STRIPE_SECRET_KEY to your configuration.'
        }), 400

    try:
        data = request.get_json()
        amount = data.get('amount')  # Amount in cents
        currency = data.get('currency', 'usd')
        order_data = data.get('orderData', {})

        if not amount or amount < 50:  # Stripe minimum is $0.50
            return jsonify({'error': 'Invalid amount'}), 400

        # Create payment intent
        intent = stripe_client.PaymentIntent.create(
            amount=amount,
            currency=currency,
            automatic_payment_methods={'enabled': True},
            metadata={
                'order_type': order_data.get('type', 'unknown'),
                'customer_name': order_data.get('customer', {}).get('name', ''),
                'customer_phone': order_data.get('customer', {}).get('phone', ''),
                'organization_id': str(g.organization.id) if hasattr(g, 'organization') else ''
            }
        )

        return jsonify({
            'clientSecret': intent.client_secret,
            'paymentIntentId': intent.id
        })

    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@pos_bp.route('/connection-token', methods=['POST'])
def create_connection_token():
    """
    Create a Stripe Terminal connection token for card readers

    Used by Stripe Terminal SDK to authenticate with readers
    """
    stripe_client = get_stripe()

    if not stripe_client:
        return jsonify({
            'error': 'Stripe is not configured'
        }), 400

    try:
        # Create connection token for Stripe Terminal
        token = stripe_client.terminal.ConnectionToken.create()

        return jsonify({
            'secret': token.secret
        })

    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@pos_bp.route('/capture-payment/<payment_intent_id>', methods=['POST'])
def capture_payment(payment_intent_id):
    """
    Capture a previously authorized payment

    Used for terminal payments that require separate capture
    """
    stripe_client = get_stripe()

    if not stripe_client:
        return jsonify({'error': 'Stripe is not configured'}), 400

    try:
        intent = stripe_client.PaymentIntent.capture(payment_intent_id)

        return jsonify({
            'status': intent.status,
            'amount': intent.amount,
            'paymentIntentId': intent.id
        })

    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@pos_bp.route('/refund', methods=['POST'])
def create_refund():
    """
    Create a refund for a payment

    Expected JSON body:
    {
        "paymentIntentId": "pi_xxx",
        "amount": 500  // Optional, in cents. If omitted, full refund
    }
    """
    stripe_client = get_stripe()

    if not stripe_client:
        return jsonify({'error': 'Stripe is not configured'}), 400

    try:
        data = request.get_json()
        payment_intent_id = data.get('paymentIntentId')
        amount = data.get('amount')  # Optional, in cents

        if not payment_intent_id:
            return jsonify({'error': 'Payment intent ID is required'}), 400

        refund_params = {'payment_intent': payment_intent_id}
        if amount:
            refund_params['amount'] = amount

        refund = stripe_client.Refund.create(**refund_params)

        return jsonify({
            'refundId': refund.id,
            'status': refund.status,
            'amount': refund.amount
        })

    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==========================================
# STRIPE TERMINAL (READER MANAGEMENT)
# ==========================================

@pos_bp.route('/readers', methods=['GET'])
def list_readers():
    """List all registered Stripe Terminal readers"""
    stripe_client = get_stripe()

    if not stripe_client:
        return jsonify({'error': 'Stripe is not configured'}), 400

    try:
        readers = stripe_client.terminal.Reader.list(limit=10)

        return jsonify({
            'readers': [{
                'id': r.id,
                'label': r.label,
                'status': r.status,
                'device_type': r.device_type,
                'serial_number': r.serial_number
            } for r in readers.data]
        })

    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@pos_bp.route('/register-reader', methods=['POST'])
def register_reader():
    """
    Register a new Stripe Terminal reader

    Expected JSON body:
    {
        "registrationCode": "xxx",  // From the reader
        "label": "Front Counter"    // Friendly name
    }
    """
    stripe_client = get_stripe()

    if not stripe_client:
        return jsonify({'error': 'Stripe is not configured'}), 400

    try:
        data = request.get_json()
        registration_code = data.get('registrationCode')
        label = data.get('label', 'POS Reader')

        if not registration_code:
            return jsonify({'error': 'Registration code is required'}), 400

        # You need a location ID for reader registration
        # In production, create/manage locations via Stripe Dashboard or API
        location_id = current_app.config.get('STRIPE_TERMINAL_LOCATION')

        if not location_id:
            return jsonify({
                'error': 'Terminal location not configured. Set STRIPE_TERMINAL_LOCATION in config.'
            }), 400

        reader = stripe_client.terminal.Reader.create(
            registration_code=registration_code,
            label=label,
            location=location_id
        )

        return jsonify({
            'readerId': reader.id,
            'label': reader.label,
            'status': reader.status
        })

    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==========================================
# ORDER PERSISTENCE
# ==========================================

def _generate_order_number(cursor):
    """Generate daily sequential order number: ORD-YYYYMMDD-NNN"""
    today = datetime.now().strftime('%Y%m%d')
    prefix = f'ORD-{today}-'

    cursor.execute("""
        SELECT order_number FROM orders
        WHERE order_number LIKE ?
        ORDER BY id DESC LIMIT 1
    """, (f'{prefix}%',))
    row = cursor.fetchone()

    if row:
        last_seq = int(row['order_number'].split('-')[-1])
        seq = last_seq + 1
    else:
        seq = 1

    return f'{prefix}{seq:03d}'


def create_order_core(cursor, data, source='pos', request_ip='POS'):
    """
    Shared order creation pipeline used by both POS and online storefront.
    Inserts order + items + payment + customer profile + sales/inventory.

    Args:
        cursor: Active SQLite cursor (caller manages connection/transaction)
        data: Order data dict with items, payment, customer info, totals
        source: 'pos' or 'online'
        request_ip: IP address for sales audit trail

    Returns:
        dict with order_id, order_number, tracking_token, sales_applied_count
    """
    import uuid

    items = data.get('items', [])
    order_number = _generate_order_number(cursor)
    tracking_token = str(uuid.uuid4()) if source == 'online' else None

    # Insert order header
    cursor.execute("""
        INSERT INTO orders (
            order_number, order_type, status, employee_id,
            customer_name, customer_phone, customer_email, customer_address,
            delivery_distance, delivery_fee,
            subtotal, tax_rate, tax_amount, tip_amount,
            discount_amount, discount_reason, total, notes,
            source, online_tracking_token, scheduled_for, customer_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_number,
        data.get('orderType', 'dine_in'),
        data.get('status', 'confirmed'),
        data.get('employeeId'),
        data.get('customerName'),
        data.get('customerPhone'),
        data.get('customerEmail'),
        data.get('customerAddress'),
        data.get('deliveryDistance'),
        data.get('deliveryFee', 0),
        data.get('subtotal', 0),
        data.get('taxRate', 0),
        data.get('taxAmount', 0),
        data.get('tipAmount', 0),
        data.get('discountAmount', 0),
        data.get('discountReason'),
        data.get('total', 0),
        data.get('notes'),
        source,
        tracking_token,
        data.get('scheduledFor'),
        data.get('customerId'),
    ))
    order_id = cursor.lastrowid

    # Insert order items
    for item in items:
        product_name = item.get('name', '').strip()
        quantity = int(item.get('qty', item.get('quantity', 1)))
        unit_price = float(item.get('price', item.get('unitPrice', 0)))
        line_total = float(item.get('lineTotal', unit_price * quantity))

        # Look up product_id by name
        cursor.execute("""
            SELECT id FROM products WHERE LOWER(product_name) = LOWER(?)
        """, (product_name,))
        product_row = cursor.fetchone()
        product_id = product_row['id'] if product_row else 0

        cursor.execute("""
            INSERT INTO order_items (
                order_id, product_id, product_name, quantity,
                unit_price, modifiers, line_total,
                menu_item_id, size_name, special_instructions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id, product_id, product_name, quantity,
            unit_price, item.get('modifiers'), line_total,
            item.get('menuItemId'), item.get('sizeName'),
            item.get('specialInstructions'),
        ))
        order_item_id = cursor.lastrowid

        # Insert order item modifiers if present
        for mod in item.get('selectedModifiers', []):
            cursor.execute("""
                INSERT INTO order_item_modifiers (
                    order_item_id, modifier_id, modifier_name, price
                ) VALUES (?, ?, ?, ?)
            """, (
                order_item_id,
                mod.get('id'),
                mod.get('name', ''),
                mod.get('price', 0),
            ))

    # Insert payment record
    payment = data.get('payment', {})
    payment_method = payment.get('method', 'cash')
    payment_details = payment.get('details', {})

    cursor.execute("""
        INSERT INTO order_payments (
            order_id, payment_method, amount, tip_amount,
            stripe_payment_intent_id, card_last_four,
            cash_tendered, change_given, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed')
    """, (
        order_id,
        payment_method,
        data.get('total', 0),
        data.get('tipAmount', 0),
        payment_details.get('paymentIntentId'),
        payment_details.get('last4'),
        payment_details.get('amountReceived'),
        payment_details.get('changeGiven'),
    ))

    # Auto-create/update customer profile if phone provided
    customer_phone = data.get('customerPhone', '').strip()
    customer_id = None
    if customer_phone:
        cursor.execute("SELECT id FROM customers WHERE phone = ?", (customer_phone,))
        cust = cursor.fetchone()
        if cust:
            customer_id = cust['id']
            cursor.execute("""
                UPDATE customers SET last_order_at = CURRENT_TIMESTAMP,
                total_orders = total_orders + 1, total_spent = total_spent + ?
                WHERE id = ?
            """, (data.get('total', 0), cust['id']))
            if data.get('customerName'):
                cursor.execute("UPDATE customers SET name = ? WHERE id = ?",
                               (data.get('customerName'), cust['id']))
            if data.get('customerEmail'):
                cursor.execute("UPDATE customers SET email = ? WHERE id = ?",
                               (data.get('customerEmail'), cust['id']))
        else:
            cursor.execute("""
                INSERT INTO customers (name, phone, email, address, first_order_at, last_order_at, total_orders, total_spent)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, ?)
            """, (data.get('customerName'), customer_phone, data.get('customerEmail'),
                  data.get('customerAddress'), data.get('total', 0)))
            customer_id = cursor.lastrowid

        # Link customer to order
        if customer_id:
            cursor.execute("UPDATE orders SET customer_id = ? WHERE id = ?",
                           (customer_id, order_id))

    # Feed the sales pipeline — deduct ingredients + record in sales_history
    now = datetime.now()
    sales_data = []
    for item in items:
        sales_data.append({
            'product_name': item.get('name', ''),
            'quantity': item.get('qty', item.get('quantity', 1)),
            'retail_price': item.get('price', item.get('unitPrice')),
            'sale_time': now.strftime('%H:%M:%S')
        })

    sales_result = record_sales_to_db(
        cursor, sales_data, now.strftime('%Y-%m-%d'),
        sale_time=now.strftime('%H:%M:%S'),
        request_ip=request_ip
    )

    return {
        'order_id': order_id,
        'order_number': order_number,
        'tracking_token': tracking_token,
        'customer_id': customer_id,
        'sales_applied_count': sales_result['applied_count'],
    }


@pos_bp.route('/orders', methods=['POST'])
@login_required
@organization_required
def create_order():
    """
    Create order + items + payment + feed sales pipeline.
    Single atomic transaction — rolls back entirely on failure.
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    items = data.get('items', [])
    if not items:
        return jsonify({'success': False, 'error': 'No items in order'}), 400

    # Use POS session employee, fall back to request body
    data['employeeId'] = session.get('pos_employee_id') or data.get('employeeId')

    conn = None
    try:
        conn = get_org_db()
        cursor = conn.cursor()

        result = create_order_core(cursor, data, source='pos',
                                   request_ip=request.remote_addr or 'POS')

        conn.commit()

        return jsonify({
            'success': True,
            'order': {
                'id': result['order_id'],
                'orderNumber': result['order_number'],
                'total': data.get('total', 0),
                'status': 'closed',
                'salesRecorded': result['sales_applied_count']
            }
        })

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@pos_bp.route('/orders', methods=['GET'])
@login_required
@organization_required
def list_orders():
    """List orders with optional date/status filters. Defaults to today."""
    date_filter = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    status_filter = request.args.get('status')

    try:
        conn = get_org_db()
        cursor = conn.cursor()

        query = """
            SELECT o.id, o.order_number, o.order_type, o.status,
                   o.customer_name, o.customer_phone, o.customer_address,
                   o.subtotal, o.tax_amount,
                   o.tip_amount, o.delivery_fee, o.total,
                   o.created_at,
                   GROUP_CONCAT(oi.quantity || 'x ' || oi.product_name, '; ') as items_summary,
                   COALESCE(SUM(oi.quantity), 0) as item_count
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE DATE(o.created_at) = ?
        """
        params = [date_filter]

        if status_filter:
            query += " AND o.status = ?"
            params.append(status_filter)

        query += " GROUP BY o.id ORDER BY o.created_at DESC"

        cursor.execute(query, params)
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({'success': True, 'orders': orders})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/orders/<int:order_id>', methods=['GET'])
@login_required
@organization_required
def get_order(order_id):
    """Get a single order with items and payments."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        order_dict = dict(order)

        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        order_dict['items'] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT * FROM order_payments WHERE order_id = ?", (order_id,))
        order_dict['payments'] = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return jsonify({'success': True, 'order': order_dict})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/next-order-number', methods=['GET'])
@login_required
@organization_required
def next_order_number():
    """Get the next order number for display (doesn't reserve it)."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        order_number = _generate_order_number(cursor)
        conn.close()

        # Extract the sequence number for display
        seq = int(order_number.split('-')[-1])

        return jsonify({'success': True, 'orderNumber': order_number, 'sequence': seq})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# EMPLOYEE AUTH (Phase 3)
# ==========================================

@pos_bp.route('/employees', methods=['GET'])
@login_required
@organization_required
def list_pos_employees():
    """List active employees for POS employee selection screen."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_pos_can_void_column(cursor)
        cursor.execute("""
            SELECT id, first_name, last_name, position, employee_code,
                   profile_picture, COALESCE(pos_can_void, 0) as pos_can_void
            FROM employees
            WHERE status = 'active'
            ORDER BY first_name, last_name
        """)
        employees = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({'success': True, 'employees': employees})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/employees/<int:employee_id>/void-permission', methods=['POST'])
@login_required
@organization_required
def toggle_void_permission(employee_id):
    """Toggle void permission for an employee. Admin only."""
    if not (g.get('is_super_admin') or g.get('is_organization_admin')):
        return jsonify({'success': False, 'error': 'Admin access required'}), 403

    try:
        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_pos_can_void_column(cursor)

        cursor.execute("SELECT id, COALESCE(pos_can_void, 0) as pos_can_void FROM employees WHERE id = ?", (employee_id,))
        emp = cursor.fetchone()
        if not emp:
            conn.close()
            return jsonify({'success': False, 'error': 'Employee not found'}), 404

        new_val = 0 if emp['pos_can_void'] else 1
        cursor.execute("UPDATE employees SET pos_can_void = ? WHERE id = ?", (new_val, employee_id))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'canVoid': bool(new_val)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/auth', methods=['POST'])
@login_required
@organization_required
def pos_employee_auth():
    """Authenticate an employee by code for POS session."""
    data = request.get_json()
    employee_code = (data.get('employeeCode') or '').strip()

    if not employee_code:
        return jsonify({'success': False, 'error': 'Employee code required'}), 400

    try:
        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_pos_can_void_column(cursor)
        cursor.execute("""
            SELECT id, first_name, last_name, position, employee_code,
                   COALESCE(pos_can_void, 0) as pos_can_void
            FROM employees
            WHERE employee_code = ? AND status = 'active'
        """, (employee_code,))
        employee = cursor.fetchone()
        conn.close()

        if not employee:
            return jsonify({'success': False, 'error': 'Invalid employee code'}), 401

        # Store in session for POS context
        session['pos_employee_id'] = employee['id']
        session['pos_employee_name'] = f"{employee['first_name']} {employee['last_name']}"

        return jsonify({
            'success': True,
            'employee': {
                'id': employee['id'],
                'firstName': employee['first_name'],
                'lastName': employee['last_name'],
                'name': f"{employee['first_name']} {employee['last_name']}",
                'position': employee['position'],
                'canVoid': bool(employee['pos_can_void']),
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/auth/logout', methods=['POST'])
@login_required
def pos_employee_logout():
    """Clear POS employee session (switch employee)."""
    session.pop('pos_employee_id', None)
    session.pop('pos_employee_name', None)
    return jsonify({'success': True})


# ==========================================
# PRODUCT AVAILABILITY (Phase 2)
# ==========================================

def _ensure_pos_86d_column(cursor):
    """Add pos_86d column to products if it doesn't exist."""
    try:
        cursor.execute("SELECT pos_86d FROM products LIMIT 1")
    except Exception:
        cursor.execute("ALTER TABLE products ADD COLUMN pos_86d INTEGER DEFAULT 0")


def _ensure_pos_can_void_column(cursor):
    """Add pos_can_void column to employees if it doesn't exist."""
    try:
        cursor.execute("SELECT pos_can_void FROM employees LIMIT 1")
    except Exception:
        cursor.execute("ALTER TABLE employees ADD COLUMN pos_can_void INTEGER DEFAULT 0")


def _check_void_permission(cursor):
    """Check if current POS employee or logged-in user can void orders.
    Returns (allowed: bool, reason: str)."""
    # Org admins and super admins always can void
    if g.get('is_super_admin') or g.get('is_organization_admin'):
        return True, 'admin'

    emp_id = session.get('pos_employee_id')
    if not emp_id:
        return False, 'No employee authenticated'

    _ensure_pos_can_void_column(cursor)
    cursor.execute("SELECT COALESCE(pos_can_void, 0) as pos_can_void FROM employees WHERE id = ?", (emp_id,))
    emp = cursor.fetchone()
    if emp and emp['pos_can_void']:
        return True, 'employee_permitted'

    return False, 'Void permission required'


@pos_bp.route('/product-availability', methods=['GET'])
@login_required
@organization_required
def product_availability():
    """Check which products can be made based on current ingredient stock + manual 86."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_pos_86d_column(cursor)

        # Get all products with their recipes and current stock
        cursor.execute("""
            SELECT p.id as product_id, p.product_name,
                   COALESCE(p.pos_86d, 0) as pos_86d,
                   r.ingredient_id, r.quantity_needed,
                   i.ingredient_name, i.quantity_on_hand, i.reorder_level
            FROM products p
            LEFT JOIN recipes r ON r.product_id = p.id
            LEFT JOIN ingredients i ON r.ingredient_id = i.id
            ORDER BY p.id
        """)
        rows = cursor.fetchall()
        conn.close()

        # Build per-product availability
        products = {}
        for row in rows:
            pid = row['product_id']
            if pid not in products:
                products[pid] = {
                    'productId': pid,
                    'productName': row['product_name'],
                    'available': True,
                    'manual86': bool(row['pos_86d']),
                    'lowStock': False,
                    'missingIngredients': [],
                    'lowIngredients': []
                }
                # Manual 86 overrides everything
                if row['pos_86d']:
                    products[pid]['available'] = False

            # Skip if no recipe or orphaned recipe (ingredient was deleted)
            if row['ingredient_id'] is None or row['ingredient_name'] is None:
                continue

            on_hand = row['quantity_on_hand'] or 0
            needed = row['quantity_needed'] or 0
            reorder = row['reorder_level'] or 0

            if on_hand < needed:
                products[pid]['available'] = False
                products[pid]['missingIngredients'].append(row['ingredient_name'])
            elif reorder > 0 and on_hand <= reorder:
                products[pid]['lowStock'] = True
                products[pid]['lowIngredients'].append(row['ingredient_name'])

        return jsonify({
            'success': True,
            'availability': list(products.values())
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/86/<int:product_id>', methods=['POST'])
@login_required
@organization_required
def toggle_86(product_id):
    """Toggle manual 86 on a product."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_pos_86d_column(cursor)

        cursor.execute("SELECT id, product_name, COALESCE(pos_86d, 0) as pos_86d FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        if not product:
            conn.close()
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        new_val = 0 if product['pos_86d'] else 1
        cursor.execute("UPDATE products SET pos_86d = ? WHERE id = ?", (new_val, product_id))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'productId': product_id,
            'productName': product['product_name'],
            'is86d': bool(new_val)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/product-ingredients', methods=['GET'])
@login_required
@organization_required
def product_ingredients():
    """Return ingredient names per product for search-by-ingredient."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.product_id, i.ingredient_name
            FROM recipes r
            JOIN ingredients i ON r.ingredient_id = i.id
            ORDER BY r.product_id
        """)
        rows = cursor.fetchall()
        conn.close()

        mapping = {}
        for row in rows:
            pid = str(row['product_id'])
            if pid not in mapping:
                mapping[pid] = []
            mapping[pid].append(row['ingredient_name'])

        return jsonify({'success': True, 'ingredients': mapping})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# 86 GROUPS — Batch 86/un-86 by named group
# ==========================================

def _ensure_86_groups_tables(cursor):
    """Create 86 group tables if they don't exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pos_86_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            group_type TEXT NOT NULL DEFAULT 'custom',
            source_category TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pos_86_group_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            FOREIGN KEY (group_id) REFERENCES pos_86_groups(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            UNIQUE(group_id, product_id)
        )
    """)


def _get_group_products(cursor, group):
    """Return list of product dicts for a group (category or custom)."""
    if group['group_type'] == 'category' and group['source_category']:
        cursor.execute(
            "SELECT id as product_id, product_name, COALESCE(pos_86d, 0) as pos_86d FROM products WHERE category = ?",
            (group['source_category'],)
        )
    else:
        cursor.execute("""
            SELECT p.id as product_id, p.product_name, COALESCE(p.pos_86d, 0) as pos_86d
            FROM products p
            JOIN pos_86_group_products gp ON gp.product_id = p.id
            WHERE gp.group_id = ?
        """, (group['id'],))
    return cursor.fetchall()


@pos_bp.route('/86-groups', methods=['GET'])
@login_required
@organization_required
def list_86_groups():
    """List all 86 groups with their products and status."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_86_groups_tables(cursor)
        _ensure_pos_86d_column(cursor)

        cursor.execute("SELECT * FROM pos_86_groups ORDER BY group_type, group_name")
        groups = cursor.fetchall()

        result = []
        for g in groups:
            products = _get_group_products(cursor, g)
            count_86d = sum(1 for p in products if p['pos_86d'])
            total = len(products)
            result.append({
                'id': g['id'],
                'groupName': g['group_name'],
                'groupType': g['group_type'],
                'sourceCategory': g['source_category'],
                'products': [{'productId': p['product_id'], 'productName': p['product_name'], 'is86d': bool(p['pos_86d'])} for p in products],
                'all86d': total > 0 and count_86d == total,
                'count86d': count_86d,
                'totalProducts': total
            })

        conn.close()
        return jsonify({'success': True, 'groups': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/86-groups', methods=['POST'])
@login_required
@organization_required
def create_86_group():
    """Create a custom 86 group."""
    try:
        data = request.get_json()
        name = (data.get('name') or '').strip()
        product_ids = data.get('productIds', [])

        if not name:
            return jsonify({'success': False, 'error': 'Group name is required'}), 400

        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_86_groups_tables(cursor)

        cursor.execute(
            "INSERT INTO pos_86_groups (group_name, group_type) VALUES (?, 'custom')",
            (name,)
        )
        group_id = cursor.lastrowid

        for pid in product_ids:
            cursor.execute(
                "INSERT OR IGNORE INTO pos_86_group_products (group_id, product_id) VALUES (?, ?)",
                (group_id, pid)
            )

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'groupId': group_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/86-groups/<int:group_id>', methods=['PUT'])
@login_required
@organization_required
def update_86_group(group_id):
    """Update an 86 group (rename and/or change products for custom groups)."""
    try:
        data = request.get_json()
        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_86_groups_tables(cursor)

        cursor.execute("SELECT * FROM pos_86_groups WHERE id = ?", (group_id,))
        group = cursor.fetchone()
        if not group:
            conn.close()
            return jsonify({'success': False, 'error': 'Group not found'}), 404

        name = (data.get('name') or '').strip()
        if name:
            cursor.execute(
                "UPDATE pos_86_groups SET group_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (name, group_id)
            )

        # Only allow product edits on custom groups
        if group['group_type'] == 'custom' and 'productIds' in data:
            cursor.execute("DELETE FROM pos_86_group_products WHERE group_id = ?", (group_id,))
            for pid in data['productIds']:
                cursor.execute(
                    "INSERT OR IGNORE INTO pos_86_group_products (group_id, product_id) VALUES (?, ?)",
                    (group_id, pid)
                )

        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/86-groups/<int:group_id>', methods=['DELETE'])
@login_required
@organization_required
def delete_86_group(group_id):
    """Delete a custom 86 group. Category groups cannot be deleted."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_86_groups_tables(cursor)

        cursor.execute("SELECT * FROM pos_86_groups WHERE id = ?", (group_id,))
        group = cursor.fetchone()
        if not group:
            conn.close()
            return jsonify({'success': False, 'error': 'Group not found'}), 404
        if group['group_type'] == 'category':
            conn.close()
            return jsonify({'success': False, 'error': 'Cannot delete category groups'}), 400

        cursor.execute("DELETE FROM pos_86_group_products WHERE group_id = ?", (group_id,))
        cursor.execute("DELETE FROM pos_86_groups WHERE id = ?", (group_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/86-groups/<int:group_id>/toggle', methods=['POST'])
@login_required
@organization_required
def toggle_86_group(group_id):
    """Bulk 86 or un-86 all products in a group."""
    try:
        data = request.get_json() or {}
        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_86_groups_tables(cursor)
        _ensure_pos_86d_column(cursor)

        cursor.execute("SELECT * FROM pos_86_groups WHERE id = ?", (group_id,))
        group = cursor.fetchone()
        if not group:
            conn.close()
            return jsonify({'success': False, 'error': 'Group not found'}), 404

        products = _get_group_products(cursor, group)
        if not products:
            conn.close()
            return jsonify({'success': True, 'toggled': 0})

        # Determine action: explicit or auto-detect
        action = data.get('action')
        if not action:
            all_86d = all(p['pos_86d'] for p in products)
            action = 'un86' if all_86d else '86'

        new_val = 1 if action == '86' else 0
        pids = [p['product_id'] for p in products]
        placeholders = ','.join('?' * len(pids))
        cursor.execute(f"UPDATE products SET pos_86d = ? WHERE id IN ({placeholders})", [new_val] + pids)
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'action': action, 'toggled': len(pids)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/86-groups/sync-categories', methods=['POST'])
@login_required
@organization_required
def sync_category_groups():
    """Auto-create category groups from distinct product categories."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        _ensure_86_groups_tables(cursor)

        cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''")
        categories = [row['category'] for row in cursor.fetchall()]

        created = 0
        for cat in categories:
            cursor.execute(
                "SELECT id FROM pos_86_groups WHERE group_type = 'category' AND source_category = ?",
                (cat,)
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO pos_86_groups (group_name, group_type, source_category) VALUES (?, 'category', ?)",
                    (cat, cat)
                )
                created += 1

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'created': created, 'totalCategories': len(categories)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# ORDER LIFECYCLE (Phase 4)
# ==========================================

@pos_bp.route('/orders/<int:order_id>/status', methods=['PATCH'])
@login_required
@organization_required
def update_order_status(order_id):
    """Update order status with timestamp."""
    data = request.get_json()
    new_status = data.get('status')

    valid_statuses = ['new', 'confirmed', 'preparing', 'ready',
                      'picked_up', 'delivered', 'served', 'closed', 'voided']
    if new_status not in valid_statuses:
        return jsonify({'success': False, 'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400

    try:
        conn = get_org_db()
        cursor = conn.cursor()

        # Permission check for void
        if new_status == 'voided':
            override_code = data.get('overrideCode')
            if override_code:
                # Manager override — verify the code belongs to a void-permitted employee or admin
                _ensure_pos_can_void_column(cursor)
                cursor.execute("""
                    SELECT id, COALESCE(pos_can_void, 0) as pos_can_void
                    FROM employees WHERE employee_code = ? AND status = 'active'
                """, (override_code,))
                override_emp = cursor.fetchone()
                if not override_emp or not override_emp['pos_can_void']:
                    # Also check if the logged-in user is admin (override always allowed)
                    if not (g.get('is_super_admin') or g.get('is_organization_admin')):
                        conn.close()
                        return jsonify({'success': False, 'error': 'Override code does not have void permission'}), 403
            else:
                allowed, reason = _check_void_permission(cursor)
                if not allowed:
                    conn.close()
                    return jsonify({'success': False, 'error': reason, 'needsOverride': True}), 403

        cursor.execute("SELECT id, status, order_number, created_at FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [new_status]

        if new_status == 'ready':
            updates.append("actual_ready_time = CURRENT_TIMESTAMP")
        elif new_status == 'voided':
            updates.append("voided_at = CURRENT_TIMESTAMP")
            if session.get('pos_employee_id'):
                updates.append("voided_by = ?")
                params.append(session['pos_employee_id'])

        params.append(order_id)
        cursor.execute(f"UPDATE orders SET {', '.join(updates)} WHERE id = ?", params)

        # Reverse inventory deductions when voiding
        if new_status == 'voided' and order['status'] != 'voided':
            cursor.execute("SELECT product_id, product_name, quantity FROM order_items WHERE order_id = ?", (order_id,))
            items = cursor.fetchall()
            for item in items:
                cursor.execute("""
                    SELECT r.ingredient_id, r.quantity_needed
                    FROM recipes r
                    WHERE r.product_id = ?
                """, (item['product_id'],))
                recipe = cursor.fetchall()
                for ing in recipe:
                    restore_qty = ing['quantity_needed'] * item['quantity']
                    cursor.execute("""
                        UPDATE ingredients
                        SET quantity_on_hand = quantity_on_hand + ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (restore_qty, ing['ingredient_id']))

            # Mark related sales_history records as voided
            order_date = order['created_at'].split('T')[0] if 'T' in (order['created_at'] or '') else (order['created_at'] or '').split(' ')[0]
            for item in items:
                cursor.execute("""
                    UPDATE sales_history
                    SET notes = 'VOIDED'
                    WHERE product_id = ? AND sale_date = ?
                    AND id IN (
                        SELECT id FROM sales_history
                        WHERE product_id = ? AND sale_date = ?
                        AND (notes IS NULL OR notes != 'VOIDED')
                        ORDER BY id DESC LIMIT ?
                    )
                """, (item['product_id'], order_date,
                      item['product_id'], order_date, item['quantity']))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'order': {'id': order_id, 'status': new_status}})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/kitchen', methods=['GET'])
@login_required
@organization_required
def kitchen_orders():
    """Get active orders for kitchen display (confirmed + preparing)."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT o.id, o.order_number, o.order_type, o.status,
                   o.customer_name, o.notes, o.created_at,
                   o.estimated_ready_time,
                   GROUP_CONCAT(oi.quantity || 'x ' || oi.product_name, '||') as items_list
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE o.status IN ('confirmed', 'preparing')
              AND DATE(o.created_at) = DATE('now')
            GROUP BY o.id
            ORDER BY o.created_at ASC
        """)
        orders = []
        for row in cursor.fetchall():
            order = dict(row)
            order['items'] = row['items_list'].split('||') if row['items_list'] else []
            del order['items_list']
            orders.append(order)

        conn.close()
        return jsonify({'success': True, 'orders': orders})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# PHASE 6: REGISTER MANAGEMENT
# ==========================================

@pos_bp.route('/register/open', methods=['POST'])
@login_required
@organization_required
def open_register():
    """Start a register session with opening cash count."""
    data = request.get_json()
    opening_cash = data.get('openingCash', 0)
    employee_id = session.get('pos_employee_id') or data.get('employeeId')

    if not employee_id:
        return jsonify({'success': False, 'error': 'No employee authenticated'}), 400

    try:
        conn = get_org_db()
        cursor = conn.cursor()

        # Check for already-open session
        cursor.execute("""
            SELECT id FROM register_sessions
            WHERE employee_id = ? AND closed_at IS NULL
        """, (employee_id,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Register already open for this employee'}), 400

        cursor.execute("""
            INSERT INTO register_sessions (employee_id, opening_cash)
            VALUES (?, ?)
        """, (employee_id, opening_cash))
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'sessionId': session_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/register/close', methods=['POST'])
@login_required
@organization_required
def close_register():
    """Close register session with closing cash count and reconciliation."""
    data = request.get_json()
    closing_cash = data.get('closingCash', 0)
    notes = data.get('notes', '')
    employee_id = session.get('pos_employee_id') or data.get('employeeId')

    try:
        conn = get_org_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, opened_at, opening_cash FROM register_sessions
            WHERE employee_id = ? AND closed_at IS NULL
            ORDER BY id DESC LIMIT 1
        """, (employee_id,))
        reg = cursor.fetchone()
        if not reg:
            conn.close()
            return jsonify({'success': False, 'error': 'No open register session found'}), 404

        # Calculate expected totals from orders during this session
        cursor.execute("""
            SELECT
                COUNT(DISTINCT o.id) as order_count,
                COALESCE(SUM(o.total), 0) as total_sales,
                COALESCE(SUM(CASE WHEN op.payment_method = 'cash' THEN op.amount ELSE 0 END), 0) as total_cash_sales,
                COALESCE(SUM(CASE WHEN op.payment_method != 'cash' THEN op.amount ELSE 0 END), 0) as total_card_sales,
                COALESCE(SUM(op.tip_amount), 0) as total_tips,
                COALESCE(SUM(CASE WHEN op.status = 'refunded' THEN op.refund_amount ELSE 0 END), 0) as total_refunds
            FROM orders o
            LEFT JOIN order_payments op ON op.order_id = o.id
            WHERE o.created_at >= ? AND o.status != 'voided'
        """, (reg['opened_at'],))
        totals = cursor.fetchone()

        expected_cash = reg['opening_cash'] + totals['total_cash_sales'] - totals['total_refunds']
        cash_variance = closing_cash - expected_cash

        cursor.execute("""
            UPDATE register_sessions SET
                closed_at = CURRENT_TIMESTAMP,
                closing_cash = ?,
                expected_cash = ?,
                cash_variance = ?,
                total_sales = ?,
                total_cash_sales = ?,
                total_card_sales = ?,
                total_tips = ?,
                total_refunds = ?,
                order_count = ?,
                notes = ?
            WHERE id = ?
        """, (
            closing_cash, expected_cash, cash_variance,
            totals['total_sales'], totals['total_cash_sales'],
            totals['total_card_sales'], totals['total_tips'],
            totals['total_refunds'], totals['order_count'],
            notes, reg['id']
        ))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'summary': {
                'sessionId': reg['id'],
                'openingCash': reg['opening_cash'],
                'closingCash': closing_cash,
                'expectedCash': round(expected_cash, 2),
                'cashVariance': round(cash_variance, 2),
                'totalSales': round(totals['total_sales'], 2),
                'totalCashSales': round(totals['total_cash_sales'], 2),
                'totalCardSales': round(totals['total_card_sales'], 2),
                'totalTips': round(totals['total_tips'], 2),
                'totalRefunds': round(totals['total_refunds'], 2),
                'orderCount': totals['order_count']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/register/current', methods=['GET'])
@login_required
@organization_required
def current_register():
    """Get active register session with running totals."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM register_sessions
            WHERE closed_at IS NULL
            ORDER BY opened_at DESC LIMIT 1
        """)
        reg = cursor.fetchone()
        if not reg:
            conn.close()
            return jsonify({'success': True, 'session': None})

        # Running totals since session opened
        cursor.execute("""
            SELECT
                COUNT(DISTINCT o.id) as order_count,
                COALESCE(SUM(o.total), 0) as total_sales,
                COALESCE(SUM(CASE WHEN op.payment_method = 'cash' THEN op.amount ELSE 0 END), 0) as cash_sales,
                COALESCE(SUM(CASE WHEN op.payment_method != 'cash' THEN op.amount ELSE 0 END), 0) as card_sales,
                COALESCE(SUM(op.tip_amount), 0) as tips
            FROM orders o
            LEFT JOIN order_payments op ON op.order_id = o.id
            WHERE o.created_at >= ? AND o.status != 'voided'
        """, (reg['opened_at'],))
        totals = cursor.fetchone()
        conn.close()

        return jsonify({
            'success': True,
            'session': {
                'id': reg['id'],
                'employeeId': reg['employee_id'],
                'openedAt': reg['opened_at'],
                'openingCash': reg['opening_cash'],
                'orderCount': totals['order_count'],
                'totalSales': round(totals['total_sales'], 2),
                'cashSales': round(totals['cash_sales'], 2),
                'cardSales': round(totals['card_sales'], 2),
                'tips': round(totals['tips'], 2),
                'expectedCash': round(reg['opening_cash'] + totals['cash_sales'], 2)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# PHASE 7: RECEIPTS
# ==========================================

def _build_receipt_html(order, items, payments, org_name=''):
    """Generate receipt HTML for email or print."""
    items_html = ''.join(
        f'<tr><td>{i["quantity"]}x {i["product_name"]}</td><td style="text-align:right">${i["line_total"]:.2f}</td></tr>'
        for i in items
    )
    payment_method = payments[0]['payment_method'].title() if payments else 'N/A'

    return f"""
    <div style="font-family: 'Courier New', monospace; max-width: 400px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0;">
        <div style="text-align: center; margin-bottom: 16px;">
            <h2 style="margin: 0;">{org_name or 'Receipt'}</h2>
            <p style="margin: 4px 0; font-size: 12px;">Order #{order['order_number']}</p>
            <p style="margin: 4px 0; font-size: 12px;">{order['created_at']}</p>
            <p style="margin: 4px 0; font-size: 12px;">{(order.get('order_type') or '').replace('_', ' ').title()}</p>
        </div>
        <hr style="border: none; border-top: 1px dashed #999;">
        <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
            {items_html}
        </table>
        <hr style="border: none; border-top: 1px dashed #999;">
        <table style="width: 100%; font-size: 14px;">
            <tr><td>Subtotal</td><td style="text-align:right">${order['subtotal']:.2f}</td></tr>
            <tr><td>Tax</td><td style="text-align:right">${order['tax_amount']:.2f}</td></tr>
            {'<tr><td>Delivery Fee</td><td style="text-align:right">$' + f"{order['delivery_fee']:.2f}" + '</td></tr>' if order.get('delivery_fee') else ''}
            {'<tr><td>Tip</td><td style="text-align:right">$' + f"{order['tip_amount']:.2f}" + '</td></tr>' if order.get('tip_amount') else ''}
            <tr style="font-weight: bold; font-size: 16px;"><td>Total</td><td style="text-align:right">${order['total']:.2f}</td></tr>
        </table>
        <hr style="border: none; border-top: 1px dashed #999;">
        <p style="text-align: center; font-size: 12px;">Paid: {payment_method}</p>
        {f'<p style="text-align:center;font-size:12px;">Customer: {order["customer_name"]}</p>' if order.get('customer_name') else ''}
        <p style="text-align: center; font-size: 12px; margin-top: 12px;">Thank you!</p>
    </div>
    """


@pos_bp.route('/orders/<int:order_id>/receipt', methods=['GET'])
@login_required
@organization_required
def get_receipt(order_id):
    """Get receipt data for an order (for printing)."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM order_payments WHERE order_id = ?", (order_id,))
        payments = [dict(r) for r in cursor.fetchall()]

        conn.close()

        org_name = g.organization.get('organization_name', '') if hasattr(g, 'organization') and g.organization else ''
        html = _build_receipt_html(dict(order), items, payments, org_name)

        return jsonify({
            'success': True,
            'receipt': {
                'html': html,
                'order': dict(order),
                'items': items,
                'payments': payments
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/orders/<int:order_id>/receipt/email', methods=['POST'])
@login_required
@organization_required
def email_receipt(order_id):
    """Email receipt to customer."""
    data = request.get_json() or {}
    to_email = data.get('email', '').strip()
    if not to_email:
        return jsonify({'success': False, 'error': 'Email address required'}), 400

    try:
        from routes.share_routes import get_email_service

        service_type, service_config = get_email_service()
        if not service_type:
            return jsonify({'success': False, 'error': 'Email service not configured'}), 503

        conn = get_org_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT * FROM order_payments WHERE order_id = ?", (order_id,))
        payments = [dict(r) for r in cursor.fetchall()]
        conn.close()

        org_name = g.organization.get('organization_name', '') if hasattr(g, 'organization') and g.organization else ''
        html = _build_receipt_html(dict(order), items, payments, org_name)

        subject = f"Receipt - Order #{order['order_number']}"

        if service_type == 'sendgrid':
            import sendgrid as sg_module
            from sendgrid.helpers.mail import Mail
            sg = sg_module.SendGridAPIClient(api_key=service_config)
            from_email = current_app.config.get('EMAIL_FROM', 'receipts@wontech.app')
            mail = Mail(from_email=from_email, to_emails=to_email, subject=subject, html_content=html)
            sg.send(mail)
        else:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            msg = MIMEMultipart()
            msg['From'] = service_config['from_email']
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(html, 'html'))
            with smtplib.SMTP(service_config['host'], service_config['port']) as server:
                server.starttls()
                if service_config.get('user') and service_config.get('password'):
                    server.login(service_config['user'], service_config['password'])
                server.send_message(msg)

        return jsonify({'success': True, 'sentTo': to_email})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/orders/<int:order_id>/receipt/sms', methods=['POST'])
@login_required
@organization_required
def sms_receipt(order_id):
    """Text receipt summary to customer."""
    data = request.get_json() or {}
    to_phone = data.get('phone', '').strip()
    if not to_phone:
        return jsonify({'success': False, 'error': 'Phone number required'}), 400

    try:
        from routes.share_routes import get_sms_service, send_via_twilio

        service_type, service_config = get_sms_service()
        if not service_type:
            return jsonify({'success': False, 'error': 'SMS service not configured'}), 503

        conn = get_org_db()
        cursor = conn.cursor()
        cursor.execute("SELECT order_number, total, order_type FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        cursor.execute("SELECT quantity, product_name FROM order_items WHERE order_id = ?", (order_id,))
        items = cursor.fetchall()
        conn.close()

        org_name = g.organization['name'] if hasattr(g, 'organization') and g.organization else 'Your order'
        items_text = ', '.join(f"{i['quantity']}x {i['product_name']}" for i in items)
        message = f"{org_name} - Order #{order['order_number']}\n{items_text}\nTotal: ${order['total']:.2f}\nThank you!"

        send_via_twilio(service_config, to_phone, message)

        return jsonify({'success': True, 'sentTo': to_phone})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# PHASE 8: CUSTOMER PROFILES
# ==========================================

@pos_bp.route('/customers/lookup', methods=['GET'])
@login_required
@organization_required
def customer_lookup():
    """Look up customer by phone number."""
    phone = request.args.get('phone', '').strip()
    if not phone:
        return jsonify({'success': False, 'error': 'Phone number required'}), 400

    try:
        conn = get_org_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM customers WHERE phone = ?", (phone,))
        customer = cursor.fetchone()

        if not customer:
            conn.close()
            return jsonify({'success': True, 'customer': None})

        # Get recent orders
        cursor.execute("""
            SELECT o.id, o.order_number, o.order_type, o.total, o.created_at,
                   GROUP_CONCAT(oi.quantity || 'x ' || oi.product_name, '; ') as items_summary
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE o.customer_phone = ? AND o.status != 'voided'
            GROUP BY o.id
            ORDER BY o.created_at DESC LIMIT 5
        """, (phone,))
        recent_orders = [dict(r) for r in cursor.fetchall()]
        conn.close()

        return jsonify({
            'success': True,
            'customer': {
                'id': customer['id'],
                'name': customer['name'],
                'phone': customer['phone'],
                'email': customer['email'],
                'address': customer['address'],
                'notes': customer['notes'],
                'totalOrders': customer['total_orders'],
                'totalSpent': round(customer['total_spent'], 2),
                'lastOrderAt': customer['last_order_at'],
                'recentOrders': recent_orders
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/customers', methods=['POST'])
@login_required
@organization_required
def create_or_update_customer():
    """Create or update a customer profile. Called automatically on order completion."""
    data = request.get_json()
    phone = (data.get('phone') or '').strip()
    if not phone:
        return jsonify({'success': False, 'error': 'Phone required'}), 400

    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    address = (data.get('address') or '').strip()
    order_total = data.get('orderTotal', 0)

    try:
        conn = get_org_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM customers WHERE phone = ?", (phone,))
        existing = cursor.fetchone()

        if existing:
            updates = ["last_order_at = CURRENT_TIMESTAMP",
                        "total_orders = total_orders + 1",
                        "total_spent = total_spent + ?"]
            params = [order_total]
            if name:
                updates.append("name = ?")
                params.append(name)
            if email:
                updates.append("email = ?")
                params.append(email)
            if address:
                updates.append("address = ?")
                params.append(address)
            params.append(existing['id'])
            cursor.execute(f"UPDATE customers SET {', '.join(updates)} WHERE id = ?", params)
            customer_id = existing['id']
        else:
            cursor.execute("""
                INSERT INTO customers (name, phone, email, address, first_order_at, last_order_at, total_orders, total_spent)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, ?)
            """, (name, phone, email, address, order_total))
            customer_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'customerId': customer_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pos_bp.route('/customers/<int:customer_id>/notes', methods=['PUT'])
@login_required
@organization_required
def update_customer_notes(customer_id):
    """Update customer notes (allergies, preferences, etc.)."""
    data = request.get_json()
    notes = data.get('notes', '')

    try:
        conn = get_org_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE customers SET notes = ? WHERE id = ?", (notes, customer_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
