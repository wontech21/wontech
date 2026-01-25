"""
Barcode Scanner API Routes
Endpoints for barcode scanning, lookup, and inventory integration
Multi-Tenant Support: Uses organization-specific databases
"""

from flask import jsonify, request
from barcode_api import BarcodeAPI
import json

# Multi-tenant database manager
from db_manager import get_org_db


def register_barcode_routes(app, get_db_connection=None, inventory_db=None):
    """Register barcode-related API routes (multi-tenant enabled)"""

    @app.route('/api/barcode/lookup/<barcode>', methods=['GET'])
    def lookup_barcode(barcode):
        """
        Lookup barcode across all sources (local inventory + external APIs)
        Returns aggregated results from all available databases
        """
        use_cache = request.args.get('use_cache', 'true').lower() == 'true'

        conn = get_org_db()
        barcode_api = BarcodeAPI(conn)

        try:
            results = barcode_api.lookup_all_sources(barcode, use_cache=use_cache)
            conn.close()

            return jsonify({
                'success': True,
                **results
            })

        except Exception as e:
            conn.close()
            return jsonify({
                'success': False,
                'error': str(e),
                'barcode': barcode
            }), 500

    @app.route('/api/barcode/lookup-batch', methods=['POST'])
    def lookup_barcode_batch():
        """
        Lookup multiple barcodes at once
        Useful for bulk scanning operations
        """
        data = request.json
        barcodes = data.get('barcodes', [])

        if not barcodes or not isinstance(barcodes, list):
            return jsonify({
                'success': False,
                'error': 'Barcodes array required'
            }), 400

        conn = get_org_db()
        barcode_api = BarcodeAPI(conn)

        results = []
        for barcode in barcodes:
            try:
                result = barcode_api.lookup_all_sources(barcode)
                results.append(result)
            except Exception as e:
                results.append({
                    'barcode': barcode,
                    'error': str(e),
                    'found_in_inventory': False
                })

        conn.close()

        return jsonify({
            'success': True,
            'count': len(results),
            'results': results
        })

    @app.route('/api/barcode/add-to-count', methods=['POST'])
    def add_to_count_by_barcode():
        """
        Add item to inventory count via barcode scan
        Creates count line item if ingredient exists, otherwise returns create prompt
        """
        data = request.json
        count_id = data.get('count_id')
        barcode = data.get('barcode')
        quantity = data.get('quantity', 1)

        if not count_id or not barcode:
            return jsonify({
                'success': False,
                'error': 'count_id and barcode required'
            }), 400

        # Normalize barcode (remove leading zero from EAN-13)
        barcode = BarcodeAPI.normalize_barcode(barcode)

        conn = get_org_db()
        cursor = conn.cursor()

        # Check if ingredient exists with this barcode
        cursor.execute("""
            SELECT id, ingredient_code, ingredient_name, unit_of_measure,
                   quantity_on_hand, category, brand
            FROM ingredients
            WHERE barcode = ? AND active = 1
        """, (barcode,))

        ingredient = cursor.fetchone()

        if not ingredient:
            # Not in inventory - return prompt to create
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Ingredient not found in inventory',
                'prompt_create': True,
                'barcode': barcode
            }), 404

        # Ingredient exists - add to count
        try:
            variance = quantity - ingredient['quantity_on_hand']

            cursor.execute("""
                INSERT INTO count_line_items
                (count_id, ingredient_code, ingredient_name, quantity_counted,
                 quantity_expected, variance, unit_of_measure, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                count_id,
                ingredient['ingredient_code'],
                ingredient['ingredient_name'],
                quantity,
                ingredient['quantity_on_hand'],
                variance,
                ingredient['unit_of_measure'],
                f"Added via barcode scan: {barcode}"
            ))

            line_item_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'line_item_id': line_item_id,
                'item': {
                    'id': ingredient['id'],
                    'code': ingredient['ingredient_code'],
                    'name': ingredient['ingredient_name'],
                    'category': ingredient['category'],
                    'brand': ingredient['brand'],
                    'unit_of_measure': ingredient['unit_of_measure'],
                    'quantity_expected': ingredient['quantity_on_hand'],
                    'quantity_counted': quantity,
                    'variance': variance
                }
            })

        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/barcode/create-ingredient', methods=['POST'])
    def create_ingredient_from_barcode():
        """
        Create new ingredient with barcode pre-filled from external API data
        """
        data = request.json

        required_fields = ['ingredient_code', 'ingredient_name', 'category',
                          'unit_of_measure', 'unit_cost', 'barcode']

        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing)}'
            }), 400

        # Normalize barcode (remove leading zero from EAN-13)
        data['barcode'] = BarcodeAPI.normalize_barcode(data['barcode'])

        conn = get_org_db()
        cursor = conn.cursor()

        try:
            # Check if barcode already exists
            cursor.execute("""
                SELECT id, ingredient_name FROM ingredients
                WHERE barcode = ?
            """, (data['barcode'],))

            existing = cursor.fetchone()
            if existing:
                conn.close()
                return jsonify({
                    'success': False,
                    'error': f'Barcode already exists for: {existing["ingredient_name"]}',
                    'existing_id': existing['id']
                }), 409

            # Insert new ingredient
            cursor.execute("""
                INSERT INTO ingredients
                (ingredient_code, ingredient_name, category, unit_of_measure,
                 quantity_on_hand, unit_cost, barcode, brand, supplier_name,
                 reorder_level, storage_location)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['ingredient_code'],
                data['ingredient_name'],
                data['category'],
                data['unit_of_measure'],
                data.get('quantity_on_hand', 0),
                data['unit_cost'],
                data['barcode'],
                data.get('brand', ''),
                data.get('supplier_name', ''),
                data.get('reorder_level', 0),
                data.get('storage_location', '')
            ))

            ingredient_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'id': ingredient_id,
                'message': f'Ingredient created: {data["ingredient_name"]}'
            })

        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/barcode/update-ingredient-barcode', methods=['PUT'])
    def update_ingredient_barcode():
        """
        Add/update barcode for existing ingredient
        """
        data = request.json
        ingredient_id = data.get('ingredient_id')
        barcode = data.get('barcode')

        if not ingredient_id or not barcode:
            return jsonify({
                'success': False,
                'error': 'ingredient_id and barcode required'
            }), 400

        # Normalize barcode (remove leading zero from EAN-13)
        barcode = BarcodeAPI.normalize_barcode(barcode)

        conn = get_org_db()
        cursor = conn.cursor()

        try:
            # Check if barcode already exists on different ingredient
            cursor.execute("""
                SELECT id, ingredient_name FROM ingredients
                WHERE barcode = ? AND id != ?
            """, (barcode, ingredient_id))

            existing = cursor.fetchone()
            if existing:
                conn.close()
                return jsonify({
                    'success': False,
                    'error': f'Barcode already assigned to: {existing["ingredient_name"]}',
                    'existing_id': existing['id']
                }), 409

            # Update barcode
            cursor.execute("""
                UPDATE ingredients
                SET barcode = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (barcode, ingredient_id))

            if cursor.rowcount == 0:
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'Ingredient not found'
                }), 404

            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': 'Barcode updated successfully'
            })

        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/barcode/api-usage', methods=['GET'])
    def get_api_usage():
        """
        Get current API usage statistics for free tier limits
        """
        conn = get_org_db()
        cursor = conn.cursor()

        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')

        cursor.execute("""
            SELECT api_name, request_count
            FROM barcode_api_usage
            WHERE request_date = ?
        """, (today,))

        usage = {}
        for row in cursor.fetchall():
            usage[row['api_name']] = row['request_count']

        conn.close()

        # Add limits
        limits = BarcodeAPI.DAILY_LIMITS

        return jsonify({
            'success': True,
            'date': today,
            'apis': [
                {
                    'name': 'Open Food Facts',
                    'key': 'openfoodfacts',
                    'used': usage.get('openfoodfacts', 0),
                    'limit': limits['openfoodfacts'],
                    'unlimited': True
                },
                {
                    'name': 'UPC Item DB',
                    'key': 'upcitemdb',
                    'used': usage.get('upcitemdb', 0),
                    'limit': limits['upcitemdb'],
                    'unlimited': False
                },
                {
                    'name': 'Barcode Lookup',
                    'key': 'barcodelookup',
                    'used': usage.get('barcodelookup', 0),
                    'limit': limits['barcodelookup'],
                    'unlimited': False
                }
            ]
        })

    @app.route('/api/barcode/clear-cache', methods=['DELETE'])
    def clear_barcode_cache():
        """
        Clear barcode cache (useful for testing or forcing fresh lookups)
        """
        barcode = request.args.get('barcode')

        conn = get_org_db()
        cursor = conn.cursor()

        try:
            if barcode:
                # Clear specific barcode
                cursor.execute("DELETE FROM barcode_cache WHERE barcode = ?", (barcode,))
                message = f'Cache cleared for barcode: {barcode}'
            else:
                # Clear all cache
                cursor.execute("DELETE FROM barcode_cache")
                message = 'All barcode cache cleared'

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': message,
                'deleted_count': deleted_count
            })

        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
