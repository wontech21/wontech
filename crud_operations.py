"""
CRUD Operations for Ingredients, Products, and Recipes
"""
from flask import request, jsonify
from datetime import datetime
import sqlite3

INVENTORY_DB = 'inventory.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def register_crud_routes(app):
    """Register CRUD routes with Flask app"""

    # ========== INGREDIENT CRUD ==========

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

            return jsonify({
                'success': True,
                'ingredient_id': ingredient_id,
                'message': 'Ingredient created successfully'
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

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
                    active = ?,
                    is_composite = ?,
                    batch_size = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
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
                data.get('active', 1),
                data.get('is_composite', 0),
                data.get('batch_size'),
                ingredient_id
            ))

            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': 'Ingredient updated successfully'
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/ingredients/<int:ingredient_id>', methods=['DELETE'])
    def delete_ingredient(ingredient_id):
        """Delete an ingredient"""
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            # Check if ingredient exists
            cursor.execute("SELECT ingredient_name FROM ingredients WHERE id = ?", (ingredient_id,))
            ingredient = cursor.fetchone()

            if not ingredient:
                conn.close()
                return jsonify({'success': False, 'error': 'Ingredient not found'}), 404

            ingredient_name = ingredient['ingredient_name']

            # Delete associated composite recipe entries first (if any)
            cursor.execute("DELETE FROM ingredient_recipes WHERE composite_ingredient_id = ?", (ingredient_id,))

            # Delete the ingredient
            cursor.execute("DELETE FROM ingredients WHERE id = ?", (ingredient_id,))

            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': f'Ingredient "{ingredient_name}" deleted successfully'
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/ingredients/<int:ingredient_id>/recipe', methods=['POST'])
    def save_composite_recipe(ingredient_id):
        """Save or update composite ingredient recipe"""
        data = request.json
        base_ingredients = data.get('base_ingredients', [])

        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            # Delete existing recipe
            cursor.execute("DELETE FROM ingredient_recipes WHERE composite_ingredient_id = ?", (ingredient_id,))

            # Insert new recipe items
            for item in base_ingredients:
                cursor.execute("""
                    INSERT INTO ingredient_recipes (
                        composite_ingredient_id, base_ingredient_id,
                        quantity_needed, unit_of_measure, notes
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    ingredient_id,
                    item['ingredient_id'],
                    item['quantity_needed'],
                    item['unit_of_measure'],
                    item.get('notes', '')
                ))

            # Calculate and update unit cost based on base ingredients
            cursor.execute("""
                SELECT SUM(ir.quantity_needed * bi.unit_cost) as total_cost
                FROM ingredient_recipes ir
                JOIN ingredients bi ON ir.base_ingredient_id = bi.id
                WHERE ir.composite_ingredient_id = ?
            """, (ingredient_id,))

            result = cursor.fetchone()
            total_cost = result['total_cost'] if result else 0

            # Get batch size
            cursor.execute("SELECT batch_size FROM ingredients WHERE id = ?", (ingredient_id,))
            batch_result = cursor.fetchone()
            batch_size = batch_result['batch_size'] if batch_result and batch_result['batch_size'] else 1

            unit_cost = total_cost / batch_size if batch_size > 0 else 0

            # Update composite ingredient unit cost
            cursor.execute("UPDATE ingredients SET unit_cost = ? WHERE id = ?", (unit_cost, ingredient_id))

            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'unit_cost': unit_cost,
                'message': 'Composite recipe saved successfully'
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/ingredients/<int:ingredient_id>/recipe', methods=['GET'])
    def get_composite_recipe(ingredient_id):
        """Get composite ingredient recipe"""
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            # Get recipe items
            cursor.execute("""
                SELECT ir.id, ir.base_ingredient_id, ir.quantity_needed,
                       ir.unit_of_measure, ir.notes,
                       i.ingredient_name, i.ingredient_code, i.unit_cost
                FROM ingredient_recipes ir
                JOIN ingredients i ON ir.base_ingredient_id = i.id
                WHERE ir.composite_ingredient_id = ?
                ORDER BY ir.id
            """, (ingredient_id,))

            recipe_items = cursor.fetchall()
            conn.close()

            return jsonify({
                'success': True,
                'recipe_items': [dict(row) for row in recipe_items]
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ========== PRODUCT CRUD ==========

    @app.route('/api/products', methods=['POST'])
    def create_product():
        """Create a new product with recipe (integrated as one entity)"""
        data = request.json
        conn = None

        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            # Insert product
            cursor.execute("""
                INSERT INTO products (
                    product_code, product_name, category, unit_of_measure,
                    quantity_on_hand, selling_price, shelf_life_days, storage_requirements
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('product_code'),
                data.get('product_name'),
                data.get('category', 'Uncategorized'),
                data.get('unit_of_measure', 'each'),
                data.get('quantity_on_hand', 0),
                data.get('selling_price', 0),
                data.get('shelf_life_days'),
                data.get('storage_requirements', '')
            ))

            product_id = cursor.lastrowid

            # Insert recipe ingredients (if provided)
            recipe = data.get('recipe', [])
            if recipe:
                for ingredient in recipe:
                    cursor.execute("""
                        INSERT INTO recipes (
                            product_id, ingredient_id, quantity_needed, unit_of_measure, source_type
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        product_id,
                        ingredient.get('source_id', ingredient.get('ingredient_id')),  # Support both formats
                        ingredient.get('quantity_needed'),
                        ingredient.get('unit_of_measure', 'unit'),
                        ingredient.get('source_type', 'ingredient')  # Default to 'ingredient' for backward compatibility
                    ))

            conn.commit()

            return jsonify({
                'success': True,
                'product_id': product_id,
                'message': f'Product created successfully with {len(recipe)} ingredients'
            })

        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn:
                conn.close()

    @app.route('/api/products/<int:product_id>', methods=['PUT'])
    def update_product(product_id):
        """Update an existing product with recipe (integrated as one entity)"""
        data = request.json
        conn = None

        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            # Update product details
            cursor.execute("""
                UPDATE products SET
                    product_code = ?,
                    product_name = ?,
                    category = ?,
                    unit_of_measure = ?,
                    quantity_on_hand = ?,
                    selling_price = ?,
                    shelf_life_days = ?,
                    storage_requirements = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                data.get('product_code'),
                data.get('product_name'),
                data.get('category'),
                data.get('unit_of_measure'),
                data.get('quantity_on_hand', 0),
                data.get('selling_price'),
                data.get('shelf_life_days'),
                data.get('storage_requirements'),
                product_id
            ))

            # Delete existing recipe
            cursor.execute("DELETE FROM recipes WHERE product_id = ?", (product_id,))

            # Insert updated recipe ingredients
            recipe = data.get('recipe', [])
            if recipe:
                for ingredient in recipe:
                    cursor.execute("""
                        INSERT INTO recipes (
                            product_id, ingredient_id, quantity_needed, unit_of_measure, source_type
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        product_id,
                        ingredient.get('source_id', ingredient.get('ingredient_id')),  # Support both formats
                        ingredient.get('quantity_needed'),
                        ingredient.get('unit_of_measure', 'unit'),
                        ingredient.get('source_type', 'ingredient')  # Default to 'ingredient' for backward compatibility
                    ))

            conn.commit()

            return jsonify({
                'success': True,
                'message': f'Product updated successfully with {len(recipe)} ingredients'
            })

        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn:
                conn.close()

    @app.route('/api/products/<int:product_id>', methods=['GET'])
    def get_product(product_id):
        """Get a single product with its recipe (integrated as one entity)"""
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            # Get product details
            cursor.execute("""
                SELECT * FROM products WHERE id = ?
            """, (product_id,))
            product = dict(cursor.fetchone())

            # Get recipe ingredients
            cursor.execute("""
                SELECT
                    r.ingredient_id,
                    r.quantity_needed,
                    r.unit_of_measure,
                    i.ingredient_name
                FROM recipes r
                JOIN ingredients i ON r.ingredient_id = i.id
                WHERE r.product_id = ?
            """, (product_id,))
            recipe = [dict(row) for row in cursor.fetchall()]

            conn.close()

            # Integrate recipe into product
            product['recipe'] = recipe

            return jsonify(product)

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/products/<int:product_id>', methods=['DELETE'])
    def delete_product(product_id):
        """Delete a product and its recipe (integrated as one entity)"""
        conn = None
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            # Delete recipe first (foreign key dependency)
            cursor.execute("DELETE FROM recipes WHERE product_id = ?", (product_id,))

            # Delete product
            cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))

            conn.commit()

            return jsonify({
                'success': True,
                'message': 'Product and recipe deleted successfully'
            })

        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn:
                conn.close()

    # ========== RECIPE CRUD (Legacy - now integrated with products) ==========

    @app.route('/api/products/<int:product_id>/recipe', methods=['GET', 'POST'])
    def product_recipe(product_id):
        """Get or save product recipe"""

        if request.method == 'GET':
            # Get recipe for a product
            try:
                conn = get_db_connection(INVENTORY_DB)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT r.id, r.ingredient_id as source_id, r.source_type,
                           CASE
                               WHEN r.source_type = 'ingredient' THEN i.ingredient_name
                               WHEN r.source_type = 'product' THEN p.product_name
                           END as name,
                           r.quantity_needed, r.unit_of_measure, r.notes
                    FROM recipes r
                    LEFT JOIN ingredients i ON r.ingredient_id = i.id AND r.source_type = 'ingredient'
                    LEFT JOIN products p ON r.ingredient_id = p.id AND r.source_type = 'product'
                    WHERE r.product_id = ?
                    ORDER BY r.source_type, name
                """, (product_id,))
                recipe = [dict(row) for row in cursor.fetchall()]
                conn.close()
                return jsonify(recipe)
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        else:  # POST - Save or update product recipe
            data = request.json
            ingredients = data.get('ingredients', [])

            try:
                conn = get_db_connection(INVENTORY_DB)
                cursor = conn.cursor()

                # Delete existing recipe
                cursor.execute("DELETE FROM recipes WHERE product_id = ?", (product_id,))

                # Insert new recipe items
                for item in ingredients:
                    cursor.execute("""
                        INSERT INTO recipes (
                            product_id, ingredient_id, quantity_needed,
                            unit_of_measure, notes, source_type
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        product_id,
                        item.get('source_id', item.get('ingredient_id')),  # Support both formats
                        item['quantity_needed'],
                        item['unit_of_measure'],
                        item.get('notes', ''),
                        item.get('source_type', 'ingredient')  # Default to 'ingredient' for backward compatibility
                    ))

                conn.commit()
                conn.close()

                return jsonify({
                    'success': True,
                    'message': 'Recipe saved successfully'
                })

            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/products/<int:product_id>/recipe/<int:ingredient_id>', methods=['DELETE'])
    def remove_recipe_ingredient(product_id, ingredient_id):
        """Remove an ingredient from a product recipe"""
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM recipes
                WHERE product_id = ? AND ingredient_id = ?
            """, (product_id, ingredient_id))

            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': 'Ingredient removed from recipe'
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ========== GET ALL INGREDIENTS (for dropdowns) ==========

    @app.route('/api/ingredients/list')
    def get_all_ingredients():
        """Get all active ingredients for dropdowns"""
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, ingredient_code, ingredient_name, unit_of_measure,
                       unit_cost, is_composite, category
                FROM ingredients
                WHERE active = 1
                ORDER BY ingredient_name
            """)

            ingredients = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return jsonify(ingredients)

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/products/list')
    def get_all_products():
        """Get all products for dropdowns"""
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, product_code, product_name, category,
                       unit_of_measure, selling_price
                FROM products
                ORDER BY product_name
            """)

            products = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return jsonify(products)

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/ingredients-and-products/list')
    def get_ingredients_and_products_for_recipe():
        """Get both ingredients and products for recipe dropdown with type differentiation"""
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            # Get ingredients
            cursor.execute("""
                SELECT id, ingredient_code as code, ingredient_name as name,
                       unit_of_measure, unit_cost, 'ingredient' as source_type,
                       is_composite, category
                FROM ingredients
                WHERE active = 1
                ORDER BY ingredient_name
            """)
            ingredients = [dict(row) for row in cursor.fetchall()]

            # Get products (exclude current product if product_id provided in query params)
            exclude_product_id = request.args.get('exclude_product_id', type=int)

            if exclude_product_id:
                cursor.execute("""
                    SELECT id, product_code as code, product_name as name,
                           unit_of_measure, 'product' as source_type, category
                    FROM products
                    WHERE id != ?
                    ORDER BY product_name
                """, (exclude_product_id,))
            else:
                cursor.execute("""
                    SELECT id, product_code as code, product_name as name,
                           unit_of_measure, 'product' as source_type, category
                    FROM products
                    ORDER BY product_name
                """)

            products = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return jsonify({
                'ingredients': ingredients,
                'products': products
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/products/<int:product_id>/ingredient-cost')
    def get_product_ingredient_cost(product_id):
        """Calculate total ingredient cost for a product (recursive for nested products)"""
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            def calculate_cost(pid, visited=None):
                """Recursively calculate product cost"""
                if visited is None:
                    visited = set()

                # Prevent infinite recursion
                if pid in visited:
                    return 0
                visited.add(pid)

                cursor.execute("""
                    SELECT source_type, ingredient_id as source_id, quantity_needed
                    FROM recipes
                    WHERE product_id = ?
                """, (pid,))

                recipe_items = cursor.fetchall()
                total_cost = 0

                for item in recipe_items:
                    source_type = item['source_type']
                    source_id = item['source_id']
                    quantity = item['quantity_needed']

                    if source_type == 'ingredient':
                        # Get ingredient cost
                        cursor.execute("""
                            SELECT COALESCE(unit_cost, 0) as unit_cost
                            FROM ingredients WHERE id = ?
                        """, (source_id,))
                        result = cursor.fetchone()
                        if result:
                            total_cost += quantity * result['unit_cost']

                    elif source_type == 'product':
                        # Recursively get product cost
                        nested_cost = calculate_cost(source_id, visited.copy())
                        total_cost += quantity * nested_cost

                return total_cost

            total_cost = calculate_cost(product_id)
            conn.close()

            return jsonify({
                'product_id': product_id,
                'total_ingredient_cost': total_cost
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/products/validate-recipe', methods=['POST'])
    def validate_product_recipe():
        """
        Validate product recipe for:
        1. Circular dependencies
        2. Nesting depth (max 2 levels)
        3. Self-reference
        """
        data = request.json
        product_id = data.get('product_id')  # Can be None for new products
        recipe_items = data.get('recipe_items', [])

        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            def check_circular_dependency(pid, target_pid, visited=None):
                """Check if target_pid exists in pid's recipe tree"""
                if visited is None:
                    visited = set()

                if pid in visited:
                    return False
                visited.add(pid)

                cursor.execute("""
                    SELECT source_type, ingredient_id as source_id
                    FROM recipes
                    WHERE product_id = ? AND source_type = 'product'
                """, (pid,))

                for row in cursor.fetchall():
                    nested_product_id = row['source_id']
                    if nested_product_id == target_pid:
                        return True
                    if check_circular_dependency(nested_product_id, target_pid, visited.copy()):
                        return True

                return False

            def check_depth(pid, current_depth=0):
                """Check maximum nesting depth"""
                if current_depth >= 2:
                    return current_depth

                cursor.execute("""
                    SELECT source_type, ingredient_id as source_id
                    FROM recipes
                    WHERE product_id = ? AND source_type = 'product'
                """, (pid,))

                max_depth = current_depth
                for row in cursor.fetchall():
                    nested_product_id = row['source_id']
                    depth = check_depth(nested_product_id, current_depth + 1)
                    max_depth = max(max_depth, depth)

                return max_depth

            errors = []

            # Validate each recipe item
            for item in recipe_items:
                if item.get('source_type') == 'product':
                    source_product_id = item.get('source_id')

                    # Check self-reference
                    if product_id and source_product_id == product_id:
                        cursor.execute("SELECT product_name FROM products WHERE id = ?", (product_id,))
                        result = cursor.fetchone()
                        product_name = result['product_name'] if result else 'this product'
                        errors.append(f"Cannot add '{product_name}' to its own recipe (self-reference)")
                        continue

                    # Check circular dependency
                    if product_id and check_circular_dependency(source_product_id, product_id):
                        cursor.execute("SELECT product_name FROM products WHERE id = ?", (source_product_id,))
                        result = cursor.fetchone()
                        nested_name = result['product_name'] if result else 'unknown product'
                        errors.append(f"Circular dependency detected with '{nested_name}'")
                        continue

                    # Check depth limit
                    depth = check_depth(source_product_id, current_depth=1)
                    if depth >= 2:
                        cursor.execute("SELECT product_name FROM products WHERE id = ?", (source_product_id,))
                        result = cursor.fetchone()
                        nested_name = result['product_name'] if result else 'unknown product'
                        errors.append(f"'{nested_name}' exceeds maximum nesting depth (2 levels)")

            conn.close()

            return jsonify({
                'valid': len(errors) == 0,
                'errors': errors
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ========== BRAND CRUD ==========
    # Note: Supplier endpoints already exist in app.py at /api/suppliers/all and /api/suppliers/create

    @app.route('/api/brands/list')
    def get_all_brands():
        """Get all brands for dropdowns"""
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, brand_name
                FROM brands
                ORDER BY brand_name
            """)

            brands = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return jsonify(brands)

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/brands', methods=['POST'])
    def create_brand():
        """Create a new brand"""
        data = request.json
        conn = None

        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO brands (brand_name, notes)
                VALUES (?, ?)
            """, (
                data.get('brand_name'),
                data.get('notes', '')
            ))

            brand_id = cursor.lastrowid
            conn.commit()

            return jsonify({
                'success': True,
                'brand_id': brand_id,
                'message': 'Brand created successfully'
            })

        except sqlite3.IntegrityError:
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'error': 'Brand name already exists'}), 400
        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn:
                conn.close()

    return app
