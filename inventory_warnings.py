"""
Universal Inventory Warning System
====================================

This module provides warning checks for ALL inventory modification operations.
It prevents negative inventory and provides clear warnings before changes are applied.

Usage:
    from inventory_warnings import check_inventory_warnings, format_warning_message
"""

def check_inventory_warnings(deductions_list, conn, low_stock_threshold=0.1):
    """
    Universal warning checker for inventory changes.

    Args:
        deductions_list: List of dicts with keys:
            - ingredient_id (int)
            - ingredient_name (str)
            - ingredient_code (str)
            - current_qty (float)
            - new_qty (float)
            - deduction (float) - amount being deducted (negative for additions)
            - unit (str)
        conn: Database connection
        low_stock_threshold: Percentage (0.1 = 10%) for low stock warning

    Returns:
        list of warning dicts with keys:
            - type: 'negative', 'low_stock', 'zero'
            - ingredient_name, ingredient_code, ingredient_id
            - current_qty, new_qty, deduction, unit
            - message: formatted warning message
            - severity: 'critical', 'warning', 'info'
    """
    warnings = []
    cursor = conn.cursor()

    for item in deductions_list:
        ingredient_id = item.get('ingredient_id')
        ingredient_name = item.get('ingredient_name')
        ingredient_code = item.get('ingredient_code')
        current_qty = float(item.get('current_qty', 0))
        new_qty = float(item.get('new_qty', 0))
        deduction = float(item.get('deduction', 0))
        unit = item.get('unit', 'ea')

        # CRITICAL: Will go negative
        if new_qty < 0:
            warnings.append({
                'type': 'negative',
                'severity': 'critical',
                'ingredient_id': ingredient_id,
                'ingredient_name': ingredient_name,
                'ingredient_code': ingredient_code,
                'current_qty': current_qty,
                'new_qty': new_qty,
                'deduction': deduction,
                'unit': unit,
                'message': f"❌ {ingredient_name} will go NEGATIVE ({new_qty:.2f} {unit})"
            })

        # WARNING: Will hit zero
        elif new_qty == 0:
            warnings.append({
                'type': 'zero',
                'severity': 'warning',
                'ingredient_id': ingredient_id,
                'ingredient_name': ingredient_name,
                'ingredient_code': ingredient_code,
                'current_qty': current_qty,
                'new_qty': new_qty,
                'deduction': deduction,
                'unit': unit,
                'message': f"⚠️ {ingredient_name} will hit ZERO ({unit})"
            })

        # INFO: Low stock (within threshold %)
        elif current_qty > 0 and new_qty > 0 and new_qty < (current_qty * low_stock_threshold):
            pct_remaining = (new_qty / current_qty) * 100
            warnings.append({
                'type': 'low_stock',
                'severity': 'info',
                'ingredient_id': ingredient_id,
                'ingredient_name': ingredient_name,
                'ingredient_code': ingredient_code,
                'current_qty': current_qty,
                'new_qty': new_qty,
                'deduction': deduction,
                'unit': unit,
                'pct_remaining': pct_remaining,
                'message': f"ℹ️ {ingredient_name} will be low ({new_qty:.2f} {unit}, {pct_remaining:.0f}% remaining)"
            })

    return warnings


def format_warning_message(warnings):
    """
    Format warnings list into a human-readable summary.

    Args:
        warnings: List of warning dicts from check_inventory_warnings()

    Returns:
        dict with keys:
            - has_warnings (bool)
            - critical_count (int) - negative inventory warnings
            - warning_count (int) - zero/low stock warnings
            - messages (list) - formatted message strings
            - blocking (bool) - should prevent operation
    """
    if not warnings:
        return {
            'has_warnings': False,
            'critical_count': 0,
            'warning_count': 0,
            'info_count': 0,
            'messages': [],
            'blocking': False
        }

    critical = [w for w in warnings if w['severity'] == 'critical']
    warning = [w for w in warnings if w['severity'] == 'warning']
    info = [w for w in warnings if w['severity'] == 'info']

    messages = []

    # Critical messages first
    for w in critical:
        messages.append(w['message'])

    # Then warnings
    for w in warning:
        messages.append(w['message'])

    # Then info
    for w in info:
        messages.append(w['message'])

    return {
        'has_warnings': True,
        'critical_count': len(critical),
        'warning_count': len(warning),
        'info_count': len(info),
        'messages': messages,
        'warnings': warnings,
        'blocking': len(critical) > 0  # Block if any critical (negative) warnings
    }


def get_ingredient_current_quantity(ingredient_id, conn):
    """
    Get current quantity for an ingredient.

    Args:
        ingredient_id: Ingredient ID
        conn: Database connection

    Returns:
        dict with keys: quantity_on_hand, unit_of_measure, ingredient_name
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT quantity_on_hand, unit_of_measure, ingredient_name, ingredient_code
        FROM ingredients
        WHERE id = ?
    """, (ingredient_id,))

    row = cursor.fetchone()

    if not row:
        return None

    return {
        'quantity_on_hand': row['quantity_on_hand'],
        'unit_of_measure': row['unit_of_measure'],
        'ingredient_name': row['ingredient_name'],
        'ingredient_code': row['ingredient_code']
    }


def preview_quantity_change(ingredient_id, new_quantity, conn):
    """
    Preview a single ingredient quantity change and return warnings.

    Args:
        ingredient_id: Ingredient ID
        new_quantity: New quantity value
        conn: Database connection

    Returns:
        dict with:
            - current (dict): current ingredient info
            - new_qty (float): proposed new quantity
            - deduction (float): change amount (negative = addition)
            - warnings (list): warning messages
    """
    current = get_ingredient_current_quantity(ingredient_id, conn)

    if not current:
        return {
            'success': False,
            'error': 'Ingredient not found'
        }

    current_qty = current['quantity_on_hand']
    deduction = current_qty - new_quantity  # Positive = deduction, negative = addition

    deductions_list = [{
        'ingredient_id': ingredient_id,
        'ingredient_name': current['ingredient_name'],
        'ingredient_code': current['ingredient_code'],
        'current_qty': current_qty,
        'new_qty': new_quantity,
        'deduction': deduction,
        'unit': current['unit_of_measure']
    }]

    warnings = check_inventory_warnings(deductions_list, conn)
    warning_summary = format_warning_message(warnings)

    return {
        'success': True,
        'current': current,
        'new_qty': new_quantity,
        'deduction': deduction,
        'change_type': 'deduction' if deduction > 0 else 'addition',
        'warnings': warning_summary
    }


def preview_count_changes(count_items, conn):
    """
    Preview physical count changes and return warnings for all items.

    Args:
        count_items: List of dicts with keys:
            - ingredient_code (str)
            - quantity_counted (float)
        conn: Database connection

    Returns:
        dict with:
            - items (list): each item with current/new/warnings
            - summary_warnings (dict): overall warning summary
    """
    cursor = conn.cursor()
    items = []
    all_deductions = []

    for item in count_items:
        ingredient_code = item['ingredient_code']
        quantity_counted = float(item['quantity_counted'])

        # Look up current inventory
        cursor.execute("""
            SELECT id, quantity_on_hand, unit_of_measure, ingredient_name
            FROM ingredients
            WHERE ingredient_code = ?
        """, (ingredient_code,))

        row = cursor.fetchone()

        if row:
            current_qty = row['quantity_on_hand']
            variance = quantity_counted - current_qty

            item_info = {
                'ingredient_id': row['id'],
                'ingredient_code': ingredient_code,
                'ingredient_name': row['ingredient_name'],
                'current_qty': current_qty,
                'quantity_counted': quantity_counted,
                'new_qty': quantity_counted,
                'variance': variance,
                'variance_type': 'increase' if variance > 0 else 'decrease' if variance < 0 else 'no_change',
                'unit': row['unit_of_measure'],
                'exists': True
            }

            # Add to deductions list for warning check
            all_deductions.append({
                'ingredient_id': row['id'],
                'ingredient_name': row['ingredient_name'],
                'ingredient_code': ingredient_code,
                'current_qty': current_qty,
                'new_qty': quantity_counted,
                'deduction': variance,  # Negative = addition
                'unit': row['unit_of_measure']
            })
        else:
            # New ingredient discovered in count
            item_info = {
                'ingredient_code': ingredient_code,
                'ingredient_name': item.get('ingredient_name', 'Unknown'),
                'current_qty': 0,
                'quantity_counted': quantity_counted,
                'new_qty': quantity_counted,
                'variance': quantity_counted,
                'variance_type': 'new_item',
                'unit': item.get('unit_of_measure', 'ea'),
                'exists': False
            }

        items.append(item_info)

    # Check warnings for all items
    warnings = check_inventory_warnings(all_deductions, conn)
    summary_warnings = format_warning_message(warnings)

    return {
        'success': True,
        'items': items,
        'total_items': len(items),
        'items_with_variance': len([i for i in items if i['variance'] != 0]),
        'new_items': len([i for i in items if not i['exists']]),
        'warnings': summary_warnings
    }
