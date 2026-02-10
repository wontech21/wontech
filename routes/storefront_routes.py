"""
Public Storefront Routes — Customer-facing website + online ordering.

No authentication required. Resolves organization from:
1. Custom domain (Host header) → g.storefront_org
2. Path prefix /s/<slug>/ → g.storefront_org

All routes check g.storefront_org (set by middleware) and serve
the appropriate org's public content.
"""

from flask import (
    Blueprint, jsonify, request, g, render_template,
    abort, redirect, url_for
)
import sqlite3
import json
from datetime import datetime, time

from db_manager import get_org_db

storefront_bp = Blueprint('storefront', __name__)


# ===========================================================================
#  Helpers
# ===========================================================================

def _get_sf_org():
    """Get the resolved storefront org or abort 404."""
    org = getattr(g, 'storefront_org', None)
    if not org:
        abort(404)
    return org


def _get_sf_db():
    """Get a connection to the storefront org's database."""
    db_path = getattr(g, 'storefront_db_path', None)
    if not db_path:
        abort(404)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _sf_context(org):
    """Base template context for storefront pages."""
    return {
        'org': org,
        'slug': org.get('slug', ''),
        'is_custom_domain': _is_custom_domain(),
    }


def _is_custom_domain():
    """Check if the current request arrived via a custom domain (not /s/<slug>/)."""
    return not request.path.startswith('/s/')


def _url_for_sf(page, slug=None):
    """Generate storefront URL respecting custom domain vs slug path."""
    if _is_custom_domain():
        return f'/{page}' if page else '/'
    slug = slug or getattr(g, 'storefront_org', {}).get('slug', '')
    return f'/s/{slug}/{page}' if page else f'/s/{slug}/'


def _get_business_hours(conn):
    """Get business hours from DB."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM business_hours ORDER BY day_of_week")
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


def _is_currently_open(conn):
    """Check if the business is currently open based on business_hours."""
    now = datetime.now()
    day_of_week = now.weekday()  # 0=Monday

    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM business_hours WHERE day_of_week = ?",
        (day_of_week,)
    )
    row = cursor.fetchone()

    if not row or row['is_closed']:
        return False

    try:
        open_time = datetime.strptime(row['open_time'], '%H:%M').time()
        close_time = datetime.strptime(row['close_time'], '%H:%M').time()
        current_time = now.time()

        if close_time < open_time:
            # Spans midnight
            return current_time >= open_time or current_time <= close_time
        return open_time <= current_time <= close_time
    except (ValueError, TypeError):
        return False


def _get_menu_tree(conn):
    """
    Build the full menu tree: categories → items → sizes → modifier groups → modifiers.
    Returns list of category dicts with nested items.
    """
    cursor = conn.cursor()

    # Categories
    cursor.execute("""
        SELECT * FROM menu_categories
        WHERE is_active = 1
        ORDER BY display_order, name
    """)
    categories = [dict(r) for r in cursor.fetchall()]

    # Items
    cursor.execute("""
        SELECT * FROM menu_items
        WHERE is_active = 1
        ORDER BY display_order, name
    """)
    items = [dict(r) for r in cursor.fetchall()]

    # Sizes
    cursor.execute("""
        SELECT * FROM menu_item_sizes
        ORDER BY display_order, price
    """)
    sizes = [dict(r) for r in cursor.fetchall()]

    # Modifier group assignments (item ↔ group junction)
    cursor.execute("""
        SELECT * FROM menu_item_modifier_groups
        ORDER BY display_order
    """)
    item_mod_groups = [dict(r) for r in cursor.fetchall()]

    # Modifier groups
    cursor.execute("SELECT * FROM menu_modifier_groups")
    mod_groups = {r['id']: dict(r) for r in cursor.fetchall()}

    # Modifiers
    cursor.execute("""
        SELECT * FROM menu_modifiers
        WHERE is_active = 1
        ORDER BY display_order, name
    """)
    modifiers = [dict(r) for r in cursor.fetchall()]

    # Per-size modifier prices
    cursor.execute("SELECT * FROM menu_modifier_prices")
    mod_prices = [dict(r) for r in cursor.fetchall()]

    # Build modifier price lookup: (modifier_id, size_id) → price
    mod_price_map = {}
    for mp in mod_prices:
        mod_price_map[(mp['modifier_id'], mp['size_id'])] = mp['price']

    # Attach modifiers to groups
    group_modifiers = {}
    for mod in modifiers:
        gid = mod['group_id']
        if gid not in group_modifiers:
            group_modifiers[gid] = []

        # Attach per-size prices
        mod['size_prices'] = {
            sp['size_id']: sp['price']
            for sp in mod_prices if sp['modifier_id'] == mod['id']
        }
        group_modifiers[gid].append(mod)

    # Build item lookup with sizes and modifier groups
    item_map = {}
    for item in items:
        item['sizes'] = []
        item['modifier_groups'] = []
        if item.get('dietary_tags'):
            try:
                item['dietary_tags'] = json.loads(item['dietary_tags'])
            except (json.JSONDecodeError, TypeError):
                item['dietary_tags'] = []
        else:
            item['dietary_tags'] = []
        item_map[item['id']] = item

    # Attach sizes to items
    for size in sizes:
        iid = size['menu_item_id']
        if iid in item_map:
            item_map[iid]['sizes'].append(size)

    # Attach modifier groups to items
    for img in item_mod_groups:
        iid = img['menu_item_id']
        gid = img['modifier_group_id']
        if iid in item_map and gid in mod_groups:
            group = dict(mod_groups[gid])
            group['modifiers'] = group_modifiers.get(gid, [])
            item_map[iid]['modifier_groups'].append(group)

    # Calculate starting price for each item
    for item in item_map.values():
        if item['sizes']:
            item['starting_price'] = min(s['price'] for s in item['sizes'])
        else:
            item['starting_price'] = 0

    # Build category tree
    for cat in categories:
        cat['items'] = [
            item_map[item['id']]
            for item in items
            if item['category_id'] == cat['id'] and item['id'] in item_map
        ]

    return categories


def _get_popular_items(conn, limit=8):
    """Get popular menu items for homepage."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT mi.*, mc.name as category_name
        FROM menu_items mi
        JOIN menu_categories mc ON mc.id = mi.category_id
        WHERE mi.is_popular = 1 AND mi.is_active = 1 AND mc.is_active = 1
        ORDER BY mi.display_order
        LIMIT ?
    """, (limit,))
    items = [dict(r) for r in cursor.fetchall()]

    # Attach starting prices
    for item in items:
        cursor.execute("""
            SELECT MIN(price) as min_price FROM menu_item_sizes
            WHERE menu_item_id = ?
        """, (item['id'],))
        row = cursor.fetchone()
        item['starting_price'] = row['min_price'] if row and row['min_price'] else 0
        if item.get('dietary_tags'):
            try:
                item['dietary_tags'] = json.loads(item['dietary_tags'])
            except (json.JSONDecodeError, TypeError):
                item['dietary_tags'] = []
        else:
            item['dietary_tags'] = []

    return items


# ===========================================================================
#  Page Routes — /s/<slug>/ pattern
# ===========================================================================

@storefront_bp.route('/s/<slug>/')
def sf_home(slug):
    org = _get_sf_org()
    conn = _get_sf_db()
    try:
        hours = _get_business_hours(conn)
        popular = _get_popular_items(conn)
        is_open = _is_currently_open(conn)
        ctx = _sf_context(org)
        ctx.update({
            'hours': hours,
            'popular_items': popular,
            'is_open': is_open,
            'page': 'home',
        })
        return render_template('storefront/home.html', **ctx)
    finally:
        conn.close()


@storefront_bp.route('/s/<slug>/menu')
def sf_menu(slug):
    org = _get_sf_org()
    conn = _get_sf_db()
    try:
        menu = _get_menu_tree(conn)
        ctx = _sf_context(org)
        ctx.update({'categories': menu, 'page': 'menu'})
        return render_template('storefront/menu.html', **ctx)
    finally:
        conn.close()


@storefront_bp.route('/s/<slug>/order')
def sf_order(slug):
    org = _get_sf_org()
    if not org.get('online_ordering_enabled'):
        abort(404)
    conn = _get_sf_db()
    try:
        is_open = _is_currently_open(conn)
        ctx = _sf_context(org)
        ctx.update({'is_open': is_open, 'page': 'order'})
        return render_template('storefront/order.html', **ctx)
    finally:
        conn.close()


@storefront_bp.route('/s/<slug>/order/track/<token>')
def sf_order_track(slug, token):
    org = _get_sf_org()
    ctx = _sf_context(org)
    ctx.update({'token': token, 'page': 'track'})
    return render_template('storefront/order_track.html', **ctx)


@storefront_bp.route('/s/<slug>/contact')
def sf_contact(slug):
    org = _get_sf_org()
    conn = _get_sf_db()
    try:
        hours = _get_business_hours(conn)
        ctx = _sf_context(org)
        ctx.update({'hours': hours, 'page': 'contact'})
        return render_template('storefront/contact.html', **ctx)
    finally:
        conn.close()


@storefront_bp.route('/s/<slug>/about')
def sf_about(slug):
    org = _get_sf_org()
    ctx = _sf_context(org)
    ctx.update({'page': 'about'})
    return render_template('storefront/about.html', **ctx)


# ===========================================================================
#  Custom Domain Routes — same pages, no /s/<slug>/ prefix
# ===========================================================================

@storefront_bp.route('/', endpoint='sf_home_custom')
def sf_home_custom():
    org = getattr(g, 'storefront_org', None)
    if not org:
        return redirect('/login')  # Not a storefront domain, fall through to app
    conn = _get_sf_db()
    try:
        hours = _get_business_hours(conn)
        popular = _get_popular_items(conn)
        is_open = _is_currently_open(conn)
        ctx = _sf_context(org)
        ctx.update({
            'hours': hours,
            'popular_items': popular,
            'is_open': is_open,
            'page': 'home',
        })
        return render_template('storefront/home.html', **ctx)
    finally:
        conn.close()


@storefront_bp.route('/menu', endpoint='sf_menu_custom')
def sf_menu_custom():
    org = getattr(g, 'storefront_org', None)
    if not org:
        abort(404)
    conn = _get_sf_db()
    try:
        menu = _get_menu_tree(conn)
        ctx = _sf_context(org)
        ctx.update({'categories': menu, 'page': 'menu'})
        return render_template('storefront/menu.html', **ctx)
    finally:
        conn.close()


@storefront_bp.route('/order', endpoint='sf_order_custom')
def sf_order_custom():
    org = getattr(g, 'storefront_org', None)
    if not org or not org.get('online_ordering_enabled'):
        abort(404)
    conn = _get_sf_db()
    try:
        is_open = _is_currently_open(conn)
        ctx = _sf_context(org)
        ctx.update({'is_open': is_open, 'page': 'order'})
        return render_template('storefront/order.html', **ctx)
    finally:
        conn.close()


@storefront_bp.route('/order/track/<token>', endpoint='sf_track_custom')
def sf_track_custom(token):
    org = getattr(g, 'storefront_org', None)
    if not org:
        abort(404)
    ctx = _sf_context(org)
    ctx.update({'token': token, 'page': 'track'})
    return render_template('storefront/order_track.html', **ctx)


@storefront_bp.route('/contact', endpoint='sf_contact_custom')
def sf_contact_custom():
    org = getattr(g, 'storefront_org', None)
    if not org:
        abort(404)
    conn = _get_sf_db()
    try:
        hours = _get_business_hours(conn)
        ctx = _sf_context(org)
        ctx.update({'hours': hours, 'page': 'contact'})
        return render_template('storefront/contact.html', **ctx)
    finally:
        conn.close()


@storefront_bp.route('/about', endpoint='sf_about_custom')
def sf_about_custom():
    org = getattr(g, 'storefront_org', None)
    if not org:
        abort(404)
    ctx = _sf_context(org)
    ctx.update({'page': 'about'})
    return render_template('storefront/about.html', **ctx)


# ===========================================================================
#  API Routes — JSON, no auth
# ===========================================================================

@storefront_bp.route('/s/<slug>/api/storefront/menu')
@storefront_bp.route('/api/storefront/menu', endpoint='sf_api_menu_custom')
def sf_api_menu(slug=None):
    """Full menu tree: categories → items → sizes → modifier groups → modifiers."""
    org = _get_sf_org()
    conn = _get_sf_db()
    try:
        menu = _get_menu_tree(conn)
        return jsonify({'success': True, 'categories': menu})
    finally:
        conn.close()


@storefront_bp.route('/s/<slug>/api/storefront/info')
@storefront_bp.route('/api/storefront/info', endpoint='sf_api_info_custom')
def sf_api_info(slug=None):
    """Org name, hours, address, branding, social links."""
    org = _get_sf_org()
    conn = _get_sf_db()
    try:
        hours = _get_business_hours(conn)
        is_open = _is_currently_open(conn)

        return jsonify({
            'success': True,
            'info': {
                'name': org.get('organization_name'),
                'slug': org.get('slug'),
                'phone': org.get('phone'),
                'address': org.get('address'),
                'city': org.get('city'),
                'state': org.get('state'),
                'zip_code': org.get('zip_code'),
                'tagline': org.get('tagline'),
                'description': org.get('description'),
                'logo_url': org.get('logo_url'),
                'primary_color': org.get('primary_color'),
                'secondary_color': org.get('secondary_color'),
                'accent_color': org.get('accent_color'),
                'facebook_url': org.get('facebook_url'),
                'instagram_url': org.get('instagram_url'),
                'google_maps_url': org.get('google_maps_url'),
                'hero_image_url': org.get('hero_image_url'),
                'delivery_enabled': bool(org.get('delivery_enabled')),
                'pickup_enabled': bool(org.get('pickup_enabled')),
                'dinein_enabled': bool(org.get('dinein_enabled')),
                'delivery_fee': org.get('delivery_fee', 0),
                'delivery_minimum': org.get('delivery_minimum', 0),
                'tax_rate': org.get('tax_rate', 0),
                'estimated_pickup_minutes': org.get('estimated_pickup_minutes', 20),
                'estimated_delivery_minutes': org.get('estimated_delivery_minutes', 45),
                'is_open': is_open,
                'hours': hours,
            }
        })
    finally:
        conn.close()


@storefront_bp.route('/s/<slug>/api/storefront/is-open')
@storefront_bp.route('/api/storefront/is-open', endpoint='sf_api_is_open_custom')
def sf_api_is_open(slug=None):
    """Current open/closed status."""
    _get_sf_org()
    conn = _get_sf_db()
    try:
        is_open = _is_currently_open(conn)
        return jsonify({'success': True, 'is_open': is_open})
    finally:
        conn.close()


@storefront_bp.route('/s/<slug>/api/storefront/order', methods=['POST'])
@storefront_bp.route('/api/storefront/order', methods=['POST'], endpoint='sf_api_order_custom')
def sf_api_order(slug=None):
    """
    Submit an online order.
    Validates items, recalculates prices server-side, creates order through
    the shared POS pipeline.
    """
    from routes.pos_routes import create_order_core

    org = _get_sf_org()
    if not org.get('online_ordering_enabled'):
        return jsonify({'success': False, 'error': 'Online ordering is not available'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    cart_items = data.get('items', [])
    if not cart_items:
        return jsonify({'success': False, 'error': 'Cart is empty'}), 400

    conn = _get_sf_db()
    try:
        cursor = conn.cursor()

        # Check business hours
        if not _is_currently_open(conn) and not data.get('scheduledFor'):
            return jsonify({'success': False, 'error': 'We are currently closed'}), 400

        # Validate & recalculate prices server-side
        validated_items = []
        subtotal = 0

        for cart_item in cart_items:
            menu_item_id = cart_item.get('menuItemId')
            size_id = cart_item.get('sizeId')
            quantity = int(cart_item.get('quantity', 1))
            modifier_ids = cart_item.get('modifierIds', [])

            if not menu_item_id or not size_id:
                return jsonify({'success': False, 'error': 'Invalid item in cart'}), 400

            # Validate menu item exists and is active
            cursor.execute("""
                SELECT mi.id, mi.name, mi.is_active, mc.is_active as cat_active
                FROM menu_items mi
                JOIN menu_categories mc ON mc.id = mi.category_id
                WHERE mi.id = ?
            """, (menu_item_id,))
            item_row = cursor.fetchone()
            if not item_row or not item_row['is_active'] or not item_row['cat_active']:
                return jsonify({
                    'success': False,
                    'error': f'Item not available: {cart_item.get("name", "Unknown")}'
                }), 400

            # Validate size and get server-side price
            cursor.execute("""
                SELECT * FROM menu_item_sizes WHERE id = ? AND menu_item_id = ?
            """, (size_id, menu_item_id))
            size_row = cursor.fetchone()
            if not size_row:
                return jsonify({'success': False, 'error': f'Invalid size for {item_row["name"]}'}), 400

            item_price = size_row['price']
            selected_modifiers = []

            # Validate modifiers and get server-side prices
            for mod_id in modifier_ids:
                cursor.execute("SELECT * FROM menu_modifiers WHERE id = ? AND is_active = 1", (mod_id,))
                mod_row = cursor.fetchone()
                if not mod_row:
                    continue

                # Check for per-size price override
                cursor.execute("""
                    SELECT price FROM menu_modifier_prices
                    WHERE modifier_id = ? AND size_id = ?
                """, (mod_id, size_id))
                price_row = cursor.fetchone()
                mod_price = price_row['price'] if price_row else mod_row['default_price']

                item_price += mod_price
                selected_modifiers.append({
                    'id': mod_row['id'],
                    'name': mod_row['name'],
                    'price': mod_price,
                })

            line_total = round(item_price * quantity, 2)
            subtotal += line_total

            # Build modifier text for display
            mod_text = ', '.join(m['name'] for m in selected_modifiers) if selected_modifiers else None

            validated_items.append({
                'name': f"{item_row['name']} ({size_row['size_name']})",
                'menuItemId': menu_item_id,
                'sizeName': size_row['size_name'],
                'quantity': quantity,
                'price': item_price,
                'unitPrice': item_price,
                'lineTotal': line_total,
                'modifiers': mod_text,
                'selectedModifiers': selected_modifiers,
                'specialInstructions': cart_item.get('specialInstructions'),
            })

        # Calculate totals server-side
        tax_rate = org.get('tax_rate', 0)
        tax_amount = round(subtotal * tax_rate / 100, 2) if tax_rate else 0
        delivery_fee = 0
        if data.get('orderType') == 'delivery':
            delivery_fee = org.get('delivery_fee', 0)
            if org.get('delivery_minimum') and subtotal < org.get('delivery_minimum', 0):
                return jsonify({
                    'success': False,
                    'error': f'Minimum order for delivery is ${org["delivery_minimum"]:.2f}'
                }), 400

        total = round(subtotal + tax_amount + delivery_fee, 2)

        # Build order data for shared pipeline
        order_data = {
            'items': validated_items,
            'orderType': data.get('orderType', 'pickup'),
            'status': 'confirmed',
            'subtotal': subtotal,
            'taxRate': tax_rate,
            'taxAmount': tax_amount,
            'deliveryFee': delivery_fee,
            'total': total,
            'customerName': data.get('customerName'),
            'customerPhone': data.get('customerPhone'),
            'customerEmail': data.get('customerEmail'),
            'customerAddress': data.get('customerAddress'),
            'notes': data.get('notes'),
            'scheduledFor': data.get('scheduledFor'),
            'payment': data.get('payment', {'method': 'cash', 'details': {}}),
        }

        result = create_order_core(
            cursor, order_data, source='online',
            request_ip=request.remote_addr or 'online'
        )

        conn.commit()

        return jsonify({
            'success': True,
            'order': {
                'id': result['order_id'],
                'orderNumber': result['order_number'],
                'trackingToken': result['tracking_token'],
                'subtotal': subtotal,
                'taxAmount': tax_amount,
                'deliveryFee': delivery_fee,
                'total': total,
            }
        })

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@storefront_bp.route('/s/<slug>/api/storefront/order/<token>/status')
@storefront_bp.route('/api/storefront/order/<token>/status', endpoint='sf_api_order_status_custom')
def sf_api_order_status(token, slug=None):
    """Public order tracking by token."""
    _get_sf_org()
    conn = _get_sf_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.id, o.order_number, o.order_type, o.status,
                   o.subtotal, o.tax_amount, o.delivery_fee, o.tip_amount, o.total,
                   o.estimated_ready_time, o.actual_ready_time,
                   o.created_at, o.notes
            FROM orders o
            WHERE o.online_tracking_token = ?
        """, (token,))
        order = cursor.fetchone()

        if not order:
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        order_dict = dict(order)

        # Get items
        cursor.execute("""
            SELECT product_name, quantity, unit_price, line_total,
                   size_name, special_instructions, modifiers
            FROM order_items WHERE order_id = ?
        """, (order_dict['id'],))
        order_dict['items'] = [dict(r) for r in cursor.fetchall()]

        return jsonify({'success': True, 'order': order_dict})
    finally:
        conn.close()


@storefront_bp.route('/s/<slug>/api/storefront/customer/lookup', methods=['POST'])
@storefront_bp.route('/api/storefront/customer/lookup', methods=['POST'], endpoint='sf_api_customer_custom')
def sf_api_customer_lookup(slug=None):
    """Phone-based returning customer lookup."""
    _get_sf_org()
    data = request.get_json()
    phone = (data or {}).get('phone', '').strip()
    if not phone:
        return jsonify({'success': False, 'error': 'Phone required'}), 400

    conn = _get_sf_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, phone, email, address, total_orders, total_spent
            FROM customers WHERE phone = ?
        """, (phone,))
        customer = cursor.fetchone()

        if not customer:
            return jsonify({'success': True, 'customer': None})

        return jsonify({'success': True, 'customer': dict(customer)})
    finally:
        conn.close()
