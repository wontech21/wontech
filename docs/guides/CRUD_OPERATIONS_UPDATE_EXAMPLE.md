# Updating crud_operations.py for Multi-Tenant Support

This document shows how to update your existing `crud_operations.py` file to support multi-tenant permissions.

## Changes Required

1. Import middleware decorators
2. Add decorators to each route
3. Add `organization_id` filter to all queries
4. Add `organization_id` when creating records

---

## Step 1: Update Imports

**Add these imports at the top of `crud_operations.py`:**

```python
"""
CRUD Operations for Ingredients, Products, and Recipes
"""
from flask import request, jsonify, g  # Add g
from datetime import datetime
import sqlite3

# NEW: Import middleware decorators
from middleware import (
    login_required,
    organization_required,
    permission_required,
    log_audit
)

INVENTORY_DB = 'inventory.db'
```

---

## Step 2: Update Each Route

### Example 1: Create Ingredient (BEFORE)

```python
@app.route('/api/ingredients', methods=['POST'])
def create_ingredient():
    """Create a new ingredient"""
    data = request.json

    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO ingredients (
                ingredient_code, ingredient_name, category, unit_of_measure,
                quantity_on_hand, unit_cost, supplier_name, brand,
                reorder_level, storage_location, active, is_composite, batch_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('ingredient_code'),
            data.get('ingredient_name'),
            # ... rest of parameters
        ))

        ingredient_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'ingredient_id': ingredient_id,
            'message': 'Ingredient created successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

### Example 1: Create Ingredient (AFTER)

```python
@app.route('/api/ingredients', methods=['POST'])
@login_required                           # NEW: Must be logged in
@organization_required                    # NEW: Must have organization context
@permission_required('inventory.create')  # NEW: Must have permission
def create_ingredient():
    """Create a new ingredient"""
    data = request.json

    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO ingredients (
                organization_id,                    -- NEW: Add organization_id
                ingredient_code, ingredient_name, category, unit_of_measure,
                quantity_on_hand, unit_cost, supplier_name, brand,
                reorder_level, storage_location, active, is_composite, batch_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)  -- One more ?
        """, (
            g.organization['id'],                   -- NEW: Set from context
            data.get('ingredient_code'),
            data.get('ingredient_name'),
            data.get('category', 'Uncategorized'),
            data.get('unit_of_measure'),
            data.get('quantity_on_hand', 0),
            data.get('unit_cost', 0),
            data.get('supplier_name', ''),
            data.get('brand', ''),
            data.get('reorder_level', 0),
            data.get('storage_location', ''),
            data.get('active', 1),
            data.get('is_composite', 0),
            data.get('batch_size', None)
        ))

        ingredient_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # NEW: Log audit trail
        log_audit('created_ingredient', 'ingredient', ingredient_id, {
            'ingredient_name': data.get('ingredient_name')
        })

        return jsonify({
            'success': True,
            'ingredient_id': ingredient_id,
            'message': 'Ingredient created successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

### Example 2: Get Ingredient (BEFORE)

```python
@app.route('/api/ingredients/<int:ingredient_id>', methods=['GET'])
def get_ingredient(ingredient_id):
    """Get a single ingredient by ID"""
    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM ingredients WHERE id = ?
        """, (ingredient_id,))

        ingredient = cursor.fetchone()
        conn.close()

        if ingredient:
            return jsonify(dict(ingredient))
        else:
            return jsonify({'error': 'Ingredient not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Example 2: Get Ingredient (AFTER)

```python
@app.route('/api/ingredients/<int:ingredient_id>', methods=['GET'])
@login_required                           # NEW
@organization_required                    # NEW
@permission_required('inventory.view')    # NEW
def get_ingredient(ingredient_id):
    """Get a single ingredient by ID"""
    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        # NEW: Add organization_id filter for security
        cursor.execute("""
            SELECT * FROM ingredients
            WHERE id = ? AND organization_id = ?
        """, (ingredient_id, g.organization['id']))

        ingredient = cursor.fetchone()
        conn.close()

        if ingredient:
            return jsonify(dict(ingredient))
        else:
            return jsonify({'error': 'Ingredient not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

### Example 3: Update Ingredient (BEFORE)

```python
@app.route('/api/ingredients/<int:ingredient_id>', methods=['PUT'])
def update_ingredient(ingredient_id):
    """Update an existing ingredient"""
    data = request.json

    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE ingredients SET
                ingredient_code = ?,
                ingredient_name = ?,
                category = ?,
                unit_of_measure = ?,
                quantity_on_hand = ?,
                unit_cost = ?,
                supplier_name = ?,
                brand = ?,
                reorder_level = ?,
                storage_location = ?,
                active = ?
            WHERE id = ?
        """, (
            data.get('ingredient_code'),
            data.get('ingredient_name'),
            # ... rest of parameters
            ingredient_id
        ))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Ingredient updated'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

### Example 3: Update Ingredient (AFTER)

```python
@app.route('/api/ingredients/<int:ingredient_id>', methods=['PUT'])
@login_required                          # NEW
@organization_required                   # NEW
@permission_required('inventory.edit')   # NEW
def update_ingredient(ingredient_id):
    """Update an existing ingredient"""
    data = request.json

    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        # NEW: Verify ownership before updating
        cursor.execute("""
            UPDATE ingredients SET
                ingredient_code = ?,
                ingredient_name = ?,
                category = ?,
                unit_of_measure = ?,
                quantity_on_hand = ?,
                unit_cost = ?,
                supplier_name = ?,
                brand = ?,
                reorder_level = ?,
                storage_location = ?,
                active = ?
            WHERE id = ? AND organization_id = ?  -- NEW: Add organization check
        """, (
            data.get('ingredient_code'),
            data.get('ingredient_name'),
            data.get('category'),
            data.get('unit_of_measure'),
            data.get('quantity_on_hand'),
            data.get('unit_cost'),
            data.get('supplier_name'),
            data.get('brand'),
            data.get('reorder_level'),
            data.get('storage_location'),
            data.get('active'),
            ingredient_id,
            g.organization['id']  -- NEW: Filter by organization
        ))

        # Check if any rows were updated
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Ingredient not found or access denied'}), 404

        conn.commit()
        conn.close()

        # NEW: Log audit trail
        log_audit('updated_ingredient', 'ingredient', ingredient_id, data)

        return jsonify({'success': True, 'message': 'Ingredient updated'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

### Example 4: Delete Ingredient (BEFORE)

```python
@app.route('/api/ingredients/<int:ingredient_id>', methods=['DELETE'])
def delete_ingredient(ingredient_id):
    """Delete an ingredient"""
    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM ingredients WHERE id = ?", (ingredient_id,))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Ingredient deleted'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

### Example 4: Delete Ingredient (AFTER)

```python
@app.route('/api/ingredients/<int:ingredient_id>', methods=['DELETE'])
@login_required                            # NEW
@organization_required                     # NEW
@permission_required('inventory.delete')   # NEW
def delete_ingredient(ingredient_id):
    """Delete an ingredient"""
    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        # NEW: Verify ownership before deleting
        cursor.execute("""
            DELETE FROM ingredients
            WHERE id = ? AND organization_id = ?
        """, (ingredient_id, g.organization['id']))

        # Check if any rows were deleted
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Ingredient not found or access denied'}), 404

        conn.commit()
        conn.close()

        # NEW: Log audit trail
        log_audit('deleted_ingredient', 'ingredient', ingredient_id)

        return jsonify({'success': True, 'message': 'Ingredient deleted'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

### Example 5: List All Ingredients (BEFORE)

```python
@app.route('/api/ingredients', methods=['GET'])
def list_ingredients():
    """Get all ingredients"""
    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM ingredients ORDER BY ingredient_name")

        ingredients = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({'ingredients': ingredients})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Example 5: List All Ingredients (AFTER)

```python
@app.route('/api/ingredients', methods=['GET'])
@login_required                          # NEW
@organization_required                   # NEW
@permission_required('inventory.view')   # NEW
def list_ingredients():
    """Get all ingredients for current organization"""
    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        # NEW: Filter by organization_id
        cursor.execute("""
            SELECT * FROM ingredients
            WHERE organization_id = ?
            ORDER BY ingredient_name
        """, (g.organization['id'],))

        ingredients = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({'ingredients': ingredients})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## Summary of Changes

For EVERY route in `crud_operations.py`, you need to:

### 1. Add Decorators
```python
@login_required          # User must be logged in
@organization_required   # Organization context must be set
@permission_required('permission.name')  # User must have specific permission
```

### 2. Add organization_id to INSERT
```python
# BEFORE
INSERT INTO table (field1, field2) VALUES (?, ?)

# AFTER
INSERT INTO table (organization_id, field1, field2) VALUES (?, ?, ?)
                   # ^^^^^^^^^^^^^^                            ^
```

### 3. Add organization_id filter to SELECT
```python
# BEFORE
SELECT * FROM table WHERE id = ?

# AFTER
SELECT * FROM table WHERE id = ? AND organization_id = ?
                                     # ^^^^^^^^^^^^^^^^^^^
```

### 4. Add organization_id filter to UPDATE
```python
# BEFORE
UPDATE table SET field = ? WHERE id = ?

# AFTER
UPDATE table SET field = ? WHERE id = ? AND organization_id = ?
                                            # ^^^^^^^^^^^^^^^^^^^
```

### 5. Add organization_id filter to DELETE
```python
# BEFORE
DELETE FROM table WHERE id = ?

# AFTER
DELETE FROM table WHERE id = ? AND organization_id = ?
                                   # ^^^^^^^^^^^^^^^^^^^
```

### 6. Add audit logging
```python
# After successful create/update/delete
log_audit('action_name', 'entity_type', entity_id, changes_dict)
```

---

## Permission Mapping

Use these permissions for each type of operation:

| Operation | Permission |
|-----------|-----------|
| GET (view) | `entity.view` |
| POST (create) | `entity.create` |
| PUT (update) | `entity.edit` |
| DELETE | `entity.delete` |

For example:
- Ingredients: `inventory.view`, `inventory.create`, `inventory.edit`, `inventory.delete`
- Products: `products.view`, `products.create`, `products.edit`, `products.delete`
- Sales: `sales.view`, `sales.create`, `sales.edit`, `sales.delete`
- Employees: `employees.view`, `employees.create`, `employees.edit`, `employees.delete`

---

## Testing Checklist

After updating each route, test:

- [ ] Super admin can access the route
- [ ] Organization admin can access the route (if they have permission)
- [ ] Employee CANNOT access the route (if they don't have permission)
- [ ] Users from Organization A cannot see Organization B's data
- [ ] Creating records sets correct organization_id
- [ ] Updating records verifies organization_id ownership
- [ ] Deleting records verifies organization_id ownership
- [ ] Audit log captures the action

---

## Next Steps

1. Update all ingredient routes in `crud_operations.py`
2. Update all product routes in `crud_operations.py`
3. Update all recipe routes in `crud_operations.py`
4. Update all sales routes
5. Update all invoice routes
6. Test with multiple organizations
7. Test with different user roles
