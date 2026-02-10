"""
Menu Administration Routes — CRUD for storefront menu management.

Used by org admins from the dashboard to manage:
- Menu categories, items, sizes
- Modifier groups and modifiers
- Business hours
- Website/storefront settings
"""

from flask import Blueprint, jsonify, request, g
import json
from db_manager import get_org_db, get_master_db
from middleware.tenant_context_separate_db import (
    login_required, organization_required, organization_admin_required
)

menu_admin_bp = Blueprint('menu_admin', __name__, url_prefix='/api/menu-admin')


# ===========================================================================
#  Business Hours
# ===========================================================================

@menu_admin_bp.route('/hours', methods=['GET'])
@login_required
@organization_required
@organization_admin_required
def get_hours():
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM business_hours ORDER BY day_of_week")
    hours = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'success': True, 'hours': hours})


@menu_admin_bp.route('/hours', methods=['PUT'])
@login_required
@organization_required
@organization_admin_required
def update_hours():
    """Bulk update business hours. Expects array of 7 day objects."""
    data = request.get_json()
    hours_list = data.get('hours', [])

    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM business_hours")

    for h in hours_list:
        cursor.execute("""
            INSERT INTO business_hours (day_of_week, open_time, close_time, is_closed)
            VALUES (?, ?, ?, ?)
        """, (h['day_of_week'], h.get('open_time', '09:00'),
              h.get('close_time', '21:00'), h.get('is_closed', 0)))

    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ===========================================================================
#  Website Settings (org-level fields in master.db)
# ===========================================================================

@menu_admin_bp.route('/settings', methods=['GET'])
@login_required
@organization_required
@organization_admin_required
def get_settings():
    """Get storefront-related org settings."""
    org = g.organization
    conn = get_master_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM organizations WHERE id = ?", (org['id'],))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'success': False, 'error': 'Organization not found'}), 404

    org_dict = dict(row)
    # Return only storefront-relevant fields
    fields = [
        'tagline', 'description', 'website_enabled', 'online_ordering_enabled',
        'delivery_enabled', 'pickup_enabled', 'dinein_enabled',
        'delivery_fee', 'delivery_minimum', 'tax_rate',
        'estimated_pickup_minutes', 'estimated_delivery_minutes',
        'facebook_url', 'instagram_url', 'google_maps_url',
        'hero_image_url', 'order_cutoff_minutes',
        'primary_color', 'secondary_color', 'accent_color',
        'custom_domain',
    ]
    settings = {k: org_dict.get(k) for k in fields}
    return jsonify({'success': True, 'settings': settings})


@menu_admin_bp.route('/settings', methods=['PUT'])
@login_required
@organization_required
@organization_admin_required
def update_settings():
    """Update storefront-related org settings."""
    data = request.get_json()
    org = g.organization

    allowed = {
        'tagline', 'description', 'website_enabled', 'online_ordering_enabled',
        'delivery_enabled', 'pickup_enabled', 'dinein_enabled',
        'delivery_fee', 'delivery_minimum', 'tax_rate',
        'estimated_pickup_minutes', 'estimated_delivery_minutes',
        'facebook_url', 'instagram_url', 'google_maps_url',
        'hero_image_url', 'order_cutoff_minutes',
        'primary_color', 'secondary_color', 'accent_color',
        'custom_domain',
    }

    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({'success': False, 'error': 'No valid fields'}), 400

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [org['id']]

    conn = get_master_db()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE organizations SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()

    return jsonify({'success': True})


# ===========================================================================
#  Menu Categories
# ===========================================================================

@menu_admin_bp.route('/categories', methods=['GET'])
@login_required
@organization_required
@organization_admin_required
def list_categories():
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM menu_categories ORDER BY display_order, name")
    categories = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'success': True, 'categories': categories})


@menu_admin_bp.route('/categories', methods=['POST'])
@login_required
@organization_required
@organization_admin_required
def create_category():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Name required'}), 400

    slug = data.get('slug') or _slugify(name)

    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO menu_categories (name, slug, description, image_url, icon,
                                     display_order, parent_category_id, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, slug, data.get('description'), data.get('image_url'),
          data.get('icon'), data.get('display_order', 0),
          data.get('parent_category_id'), data.get('is_active', 1)))
    cat_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': cat_id}), 201


@menu_admin_bp.route('/categories/<int:cat_id>', methods=['PUT'])
@login_required
@organization_required
@organization_admin_required
def update_category(cat_id):
    data = request.get_json()
    conn = get_org_db()
    cursor = conn.cursor()

    fields = ['name', 'slug', 'description', 'image_url', 'icon',
              'display_order', 'parent_category_id', 'is_active']
    updates = {k: data[k] for k in fields if k in data}
    if not updates:
        conn.close()
        return jsonify({'success': False, 'error': 'No fields to update'}), 400

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [cat_id]
    cursor.execute(f"UPDATE menu_categories SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@menu_admin_bp.route('/categories/<int:cat_id>', methods=['DELETE'])
@login_required
@organization_required
@organization_admin_required
def delete_category(cat_id):
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu_categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ===========================================================================
#  Menu Items
# ===========================================================================

@menu_admin_bp.route('/items', methods=['GET'])
@login_required
@organization_required
@organization_admin_required
def list_items():
    cat_id = request.args.get('category_id')
    conn = get_org_db()
    cursor = conn.cursor()

    if cat_id:
        cursor.execute("""
            SELECT mi.*, mc.name as category_name
            FROM menu_items mi
            JOIN menu_categories mc ON mc.id = mi.category_id
            WHERE mi.category_id = ?
            ORDER BY mi.display_order, mi.name
        """, (cat_id,))
    else:
        cursor.execute("""
            SELECT mi.*, mc.name as category_name
            FROM menu_items mi
            JOIN menu_categories mc ON mc.id = mi.category_id
            ORDER BY mc.display_order, mi.display_order, mi.name
        """)

    items = [dict(r) for r in cursor.fetchall()]

    # Attach sizes
    for item in items:
        cursor.execute("""
            SELECT * FROM menu_item_sizes WHERE menu_item_id = ? ORDER BY display_order, price
        """, (item['id'],))
        item['sizes'] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify({'success': True, 'items': items})


@menu_admin_bp.route('/items', methods=['POST'])
@login_required
@organization_required
@organization_admin_required
def create_item():
    data = request.get_json()
    name = data.get('name', '').strip()
    category_id = data.get('category_id')
    if not name or not category_id:
        return jsonify({'success': False, 'error': 'Name and category required'}), 400

    slug = data.get('slug') or _slugify(name)
    dietary_tags = json.dumps(data.get('dietary_tags', []))

    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO menu_items (category_id, name, slug, description, image_url,
                                dietary_tags, is_popular, is_active, display_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (category_id, name, slug, data.get('description'), data.get('image_url'),
          dietary_tags, data.get('is_popular', 0), data.get('is_active', 1),
          data.get('display_order', 0)))
    item_id = cursor.lastrowid

    # Create sizes if provided
    for size in data.get('sizes', []):
        cursor.execute("""
            INSERT INTO menu_item_sizes (menu_item_id, size_name, size_code, price,
                                         is_default, product_id, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (item_id, size['size_name'], size.get('size_code', _slugify(size['size_name'])),
              size['price'], size.get('is_default', 0), size.get('product_id'),
              size.get('display_order', 0)))

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': item_id}), 201


@menu_admin_bp.route('/items/<int:item_id>', methods=['PUT'])
@login_required
@organization_required
@organization_admin_required
def update_item(item_id):
    data = request.get_json()
    conn = get_org_db()
    cursor = conn.cursor()

    fields = ['category_id', 'name', 'slug', 'description', 'image_url',
              'is_popular', 'is_active', 'display_order']
    updates = {k: data[k] for k in fields if k in data}

    if 'dietary_tags' in data:
        updates['dietary_tags'] = json.dumps(data['dietary_tags'])

    if updates:
        set_clause = ', '.join(f'{k} = ?' for k in updates)
        values = list(updates.values()) + [item_id]
        cursor.execute(f"UPDATE menu_items SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)

    conn.commit()
    conn.close()
    return jsonify({'success': True})


@menu_admin_bp.route('/items/<int:item_id>', methods=['DELETE'])
@login_required
@organization_required
@organization_admin_required
def delete_item(item_id):
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu_item_sizes WHERE menu_item_id = ?", (item_id,))
    cursor.execute("DELETE FROM menu_item_modifier_groups WHERE menu_item_id = ?", (item_id,))
    cursor.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ===========================================================================
#  Menu Item Sizes
# ===========================================================================

@menu_admin_bp.route('/items/<int:item_id>/sizes', methods=['POST'])
@login_required
@organization_required
@organization_admin_required
def add_size(item_id):
    data = request.get_json()
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO menu_item_sizes (menu_item_id, size_name, size_code, price,
                                     is_default, product_id, display_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (item_id, data['size_name'], data.get('size_code', _slugify(data['size_name'])),
          data['price'], data.get('is_default', 0), data.get('product_id'),
          data.get('display_order', 0)))
    size_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': size_id}), 201


@menu_admin_bp.route('/sizes/<int:size_id>', methods=['PUT'])
@login_required
@organization_required
@organization_admin_required
def update_size(size_id):
    data = request.get_json()
    conn = get_org_db()
    cursor = conn.cursor()

    fields = ['size_name', 'size_code', 'price', 'is_default', 'product_id', 'display_order']
    updates = {k: data[k] for k in fields if k in data}
    if not updates:
        conn.close()
        return jsonify({'success': False, 'error': 'No fields'}), 400

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [size_id]
    cursor.execute(f"UPDATE menu_item_sizes SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@menu_admin_bp.route('/sizes/<int:size_id>', methods=['DELETE'])
@login_required
@organization_required
@organization_admin_required
def delete_size(size_id):
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu_modifier_prices WHERE size_id = ?", (size_id,))
    cursor.execute("DELETE FROM menu_item_sizes WHERE id = ?", (size_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ===========================================================================
#  Modifier Groups
# ===========================================================================

@menu_admin_bp.route('/modifier-groups', methods=['GET'])
@login_required
@organization_required
@organization_admin_required
def list_modifier_groups():
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM menu_modifier_groups ORDER BY name")
    groups = [dict(r) for r in cursor.fetchall()]

    for group in groups:
        cursor.execute("""
            SELECT * FROM menu_modifiers WHERE group_id = ? ORDER BY display_order, name
        """, (group['id'],))
        group['modifiers'] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify({'success': True, 'groups': groups})


@menu_admin_bp.route('/modifier-groups', methods=['POST'])
@login_required
@organization_required
@organization_admin_required
def create_modifier_group():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Name required'}), 400

    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO menu_modifier_groups (name, selection_type, min_selections, max_selections)
        VALUES (?, ?, ?, ?)
    """, (name, data.get('selection_type', 'multiple'),
          data.get('min_selections', 0), data.get('max_selections', 10)))
    group_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': group_id}), 201


@menu_admin_bp.route('/modifier-groups/<int:group_id>', methods=['PUT'])
@login_required
@organization_required
@organization_admin_required
def update_modifier_group(group_id):
    data = request.get_json()
    conn = get_org_db()
    cursor = conn.cursor()

    fields = ['name', 'selection_type', 'min_selections', 'max_selections']
    updates = {k: data[k] for k in fields if k in data}
    if not updates:
        conn.close()
        return jsonify({'success': False, 'error': 'No fields'}), 400

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [group_id]
    cursor.execute(f"UPDATE menu_modifier_groups SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@menu_admin_bp.route('/modifier-groups/<int:group_id>', methods=['DELETE'])
@login_required
@organization_required
@organization_admin_required
def delete_modifier_group(group_id):
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu_modifier_prices WHERE modifier_id IN (SELECT id FROM menu_modifiers WHERE group_id = ?)", (group_id,))
    cursor.execute("DELETE FROM menu_modifiers WHERE group_id = ?", (group_id,))
    cursor.execute("DELETE FROM menu_item_modifier_groups WHERE modifier_group_id = ?", (group_id,))
    cursor.execute("DELETE FROM menu_modifier_groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ===========================================================================
#  Modifiers
# ===========================================================================

@menu_admin_bp.route('/modifiers', methods=['POST'])
@login_required
@organization_required
@organization_admin_required
def create_modifier():
    data = request.get_json()
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO menu_modifiers (group_id, name, default_price, ingredient_id, display_order, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (data['group_id'], data['name'], data.get('default_price', 0),
          data.get('ingredient_id'), data.get('display_order', 0), data.get('is_active', 1)))
    mod_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': mod_id}), 201


@menu_admin_bp.route('/modifiers/<int:mod_id>', methods=['PUT'])
@login_required
@organization_required
@organization_admin_required
def update_modifier(mod_id):
    data = request.get_json()
    conn = get_org_db()
    cursor = conn.cursor()

    fields = ['name', 'default_price', 'ingredient_id', 'display_order', 'is_active']
    updates = {k: data[k] for k in fields if k in data}
    if not updates:
        conn.close()
        return jsonify({'success': False, 'error': 'No fields'}), 400

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [mod_id]
    cursor.execute(f"UPDATE menu_modifiers SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@menu_admin_bp.route('/modifiers/<int:mod_id>', methods=['DELETE'])
@login_required
@organization_required
@organization_admin_required
def delete_modifier(mod_id):
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu_modifier_prices WHERE modifier_id = ?", (mod_id,))
    cursor.execute("DELETE FROM menu_modifiers WHERE id = ?", (mod_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ===========================================================================
#  Modifier Per-Size Pricing
# ===========================================================================

@menu_admin_bp.route('/modifier-prices', methods=['POST'])
@login_required
@organization_required
@organization_admin_required
def set_modifier_price():
    """Set or update per-size modifier price."""
    data = request.get_json()
    modifier_id = data.get('modifier_id')
    size_id = data.get('size_id')
    price = data.get('price')

    if not all([modifier_id, size_id, price is not None]):
        return jsonify({'success': False, 'error': 'modifier_id, size_id, and price required'}), 400

    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO menu_modifier_prices (modifier_id, size_id, price)
        VALUES (?, ?, ?)
        ON CONFLICT(modifier_id, size_id) DO UPDATE SET price = excluded.price
    """, (modifier_id, size_id, price))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@menu_admin_bp.route('/modifier-prices/bulk', methods=['POST'])
@login_required
@organization_required
@organization_admin_required
def bulk_set_modifier_prices():
    """Bulk set per-size modifier prices. Expects array of {modifier_id, size_id, price}."""
    data = request.get_json()
    prices = data.get('prices', [])

    conn = get_org_db()
    cursor = conn.cursor()
    for p in prices:
        cursor.execute("""
            INSERT INTO menu_modifier_prices (modifier_id, size_id, price)
            VALUES (?, ?, ?)
            ON CONFLICT(modifier_id, size_id) DO UPDATE SET price = excluded.price
        """, (p['modifier_id'], p['size_id'], p['price']))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'count': len(prices)})


# ===========================================================================
#  Item ↔ Modifier Group Assignments
# ===========================================================================

@menu_admin_bp.route('/items/<int:item_id>/modifier-groups', methods=['GET'])
@login_required
@organization_required
@organization_admin_required
def get_item_modifier_groups(item_id):
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT img.*, mg.name as group_name, mg.selection_type
        FROM menu_item_modifier_groups img
        JOIN menu_modifier_groups mg ON mg.id = img.modifier_group_id
        WHERE img.menu_item_id = ?
        ORDER BY img.display_order
    """, (item_id,))
    groups = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'success': True, 'modifier_groups': groups})


@menu_admin_bp.route('/items/<int:item_id>/modifier-groups', methods=['POST'])
@login_required
@organization_required
@organization_admin_required
def assign_modifier_group(item_id):
    data = request.get_json()
    group_id = data.get('modifier_group_id')
    if not group_id:
        return jsonify({'success': False, 'error': 'modifier_group_id required'}), 400

    conn = get_org_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO menu_item_modifier_groups (menu_item_id, modifier_group_id, display_order)
            VALUES (?, ?, ?)
        """, (item_id, group_id, data.get('display_order', 0)))
        conn.commit()
    except Exception:
        conn.close()
        return jsonify({'success': False, 'error': 'Already assigned'}), 409
    conn.close()
    return jsonify({'success': True}), 201


@menu_admin_bp.route('/items/<int:item_id>/modifier-groups/<int:group_id>', methods=['DELETE'])
@login_required
@organization_required
@organization_admin_required
def unassign_modifier_group(item_id, group_id):
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM menu_item_modifier_groups
        WHERE menu_item_id = ? AND modifier_group_id = ?
    """, (item_id, group_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ===========================================================================
#  Helpers
# ===========================================================================

def _slugify(text):
    """Simple slug generator."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')
