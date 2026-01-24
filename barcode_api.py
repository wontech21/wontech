"""
Barcode API Integration Module
Queries multiple free barcode databases in parallel and aggregates results
"""

import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import sqlite3
from typing import Dict, List, Optional


class BarcodeAPI:
    """Handles barcode lookups across multiple free APIs"""

    # Free tier API endpoints
    OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    UPC_ITEMDB_URL = "https://api.upcitemdb.com/prod/trial/lookup"
    BARCODE_LOOKUP_URL = "https://api.barcodelookup.com/v3/products"

    # Daily limits for free tiers
    DAILY_LIMITS = {
        'upcitemdb': 100,
        'barcodelookup': 100,
        'openfoodfacts': 999999  # Unlimited
    }

    def __init__(self, db_connection):
        self.conn = db_connection

    def check_api_limit(self, api_name: str) -> bool:
        """Check if we've hit the daily limit for an API"""
        today = datetime.now().strftime('%Y-%m-%d')
        cursor = self.conn.execute("""
            SELECT request_count FROM barcode_api_usage
            WHERE api_name = ? AND request_date = ?
        """, (api_name, today))

        result = cursor.fetchone()
        if result:
            return result[0] < self.DAILY_LIMITS.get(api_name, 100)
        return True

    def increment_api_usage(self, api_name: str):
        """Increment API usage counter for today"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.conn.execute("""
            INSERT INTO barcode_api_usage (api_name, request_date, request_count)
            VALUES (?, ?, 1)
            ON CONFLICT(api_name, request_date)
            DO UPDATE SET request_count = request_count + 1
        """, (api_name, today))
        self.conn.commit()

    def query_open_food_facts(self, barcode: str) -> Optional[Dict]:
        """Query Open Food Facts database (unlimited, best for food)"""
        try:
            response = requests.get(
                self.OPEN_FOOD_FACTS_URL.format(barcode=barcode),
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 1:  # Product found
                    product = data.get('product', {})

                    # Cache the result
                    self._cache_result(barcode, 'openfoodfacts', product)
                    self.increment_api_usage('openfoodfacts')

                    return {
                        'source': 'Open Food Facts',
                        'product_name': product.get('product_name') or product.get('product_name_en'),
                        'brand': product.get('brands'),
                        'category': product.get('categories'),
                        'quantity': product.get('quantity'),
                        'image_url': product.get('image_url') or product.get('image_front_url'),
                        'ingredients': product.get('ingredients_text'),
                        'nutrition_grade': product.get('nutrition_grade_fr'),
                        'confidence': 'high' if product.get('product_name') else 'medium',
                        'raw_data': product
                    }
        except Exception as e:
            print(f"Open Food Facts error: {e}")

        return None

    def query_upc_itemdb(self, barcode: str) -> Optional[Dict]:
        """Query UPCitemdb (100 requests/day free)"""
        if not self.check_api_limit('upcitemdb'):
            print("UPCitemdb daily limit reached")
            return None

        try:
            response = requests.get(
                self.UPC_ITEMDB_URL,
                params={'upc': barcode},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('items'):
                    item = data['items'][0]

                    # Cache the result
                    self._cache_result(barcode, 'upcitemdb', item)
                    self.increment_api_usage('upcitemdb')

                    return {
                        'source': 'UPC Item DB',
                        'product_name': item.get('title'),
                        'brand': item.get('brand'),
                        'category': item.get('category'),
                        'quantity': None,
                        'image_url': ' '.join(item.get('images', [])) if item.get('images') else None,
                        'description': item.get('description'),
                        'confidence': 'high' if item.get('title') else 'low',
                        'raw_data': item
                    }
        except Exception as e:
            print(f"UPCitemdb error: {e}")

        return None

    def query_barcode_lookup(self, barcode: str, api_key: Optional[str] = None) -> Optional[Dict]:
        """
        Query Barcode Lookup API (100 requests/day free with API key)
        Note: Requires free API key from https://www.barcodelookup.com/
        Set environment variable: BARCODE_LOOKUP_API_KEY
        """
        if not api_key:
            # Try to get from environment or skip
            import os
            api_key = os.environ.get('BARCODE_LOOKUP_API_KEY')
            if not api_key:
                print("Barcode Lookup API key not configured (optional)")
                return None

        if not self.check_api_limit('barcodelookup'):
            print("Barcode Lookup daily limit reached")
            return None

        try:
            response = requests.get(
                self.BARCODE_LOOKUP_URL,
                params={'barcode': barcode, 'key': api_key},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('products'):
                    product = data['products'][0]

                    # Cache the result
                    self._cache_result(barcode, 'barcodelookup', product)
                    self.increment_api_usage('barcodelookup')

                    return {
                        'source': 'Barcode Lookup',
                        'product_name': product.get('product_name') or product.get('title'),
                        'brand': product.get('brand'),
                        'category': product.get('category'),
                        'quantity': None,
                        'image_url': ' '.join(product.get('images', [])) if product.get('images') else None,
                        'manufacturer': product.get('manufacturer'),
                        'confidence': 'high' if product.get('product_name') else 'medium',
                        'raw_data': product
                    }
        except Exception as e:
            print(f"Barcode Lookup error: {e}")

        return None

    def _cache_result(self, barcode: str, source: str, raw_data: Dict):
        """Cache API result to reduce future lookups"""
        try:
            self.conn.execute("""
                INSERT INTO barcode_cache
                (barcode, data_source, product_name, brand, category,
                 quantity, image_url, raw_data, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(barcode, data_source)
                DO UPDATE SET
                    product_name = excluded.product_name,
                    brand = excluded.brand,
                    category = excluded.category,
                    quantity = excluded.quantity,
                    image_url = excluded.image_url,
                    raw_data = excluded.raw_data,
                    last_updated = CURRENT_TIMESTAMP
            """, (
                barcode,
                source,
                raw_data.get('product_name') or raw_data.get('title'),
                raw_data.get('brand') or raw_data.get('brands'),
                raw_data.get('category') or raw_data.get('categories'),
                raw_data.get('quantity'),
                raw_data.get('image_url') or raw_data.get('image_front_url'),
                json.dumps(raw_data)
            ))
            self.conn.commit()
        except Exception as e:
            print(f"Cache error: {e}")

    def get_cached_results(self, barcode: str) -> List[Dict]:
        """Get cached results for a barcode"""
        cursor = self.conn.execute("""
            SELECT data_source, product_name, brand, category,
                   quantity, image_url, raw_data, last_updated
            FROM barcode_cache
            WHERE barcode = ?
            ORDER BY last_updated DESC
        """, (barcode,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'source': row[0],
                'product_name': row[1],
                'brand': row[2],
                'category': row[3],
                'quantity': row[4],
                'image_url': row[5],
                'cached': True,
                'cached_date': row[7],
                'raw_data': json.loads(row[6]) if row[6] else {}
            })

        return results

    def lookup_all_sources(self, barcode: str, use_cache: bool = True) -> Dict:
        """
        Query all available barcode databases in parallel
        Returns aggregated results from all sources
        """
        # Check local inventory first
        local_results = self._check_local_inventory(barcode)

        # Check cache
        cached_results = []
        if use_cache:
            cached_results = self.get_cached_results(barcode)

        # Query all external APIs in parallel
        external_results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.query_open_food_facts, barcode): 'openfoodfacts',
                executor.submit(self.query_upc_itemdb, barcode): 'upcitemdb',
                executor.submit(self.query_barcode_lookup, barcode): 'barcodelookup'
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        external_results.append(result)
                except Exception as e:
                    print(f"API query error: {e}")

        # Aggregate all results
        return {
            'barcode': barcode,
            'found_in_inventory': len(local_results) > 0,
            'inventory_items': local_results,
            'external_sources': len(external_results),
            'cached_sources': len(cached_results),
            'results': external_results + cached_results,
            'best_match': self._determine_best_match(external_results + cached_results)
        }

    def _check_local_inventory(self, barcode: str) -> List[Dict]:
        """Check if barcode exists in local ingredients or products"""
        results = []

        # Check ingredients
        cursor = self.conn.execute("""
            SELECT id, ingredient_code, ingredient_name, category,
                   unit_of_measure, quantity_on_hand, unit_cost, brand
            FROM ingredients
            WHERE barcode = ? AND active = 1
        """, (barcode,))

        for row in cursor.fetchall():
            results.append({
                'type': 'ingredient',
                'id': row[0],
                'code': row[1],
                'name': row[2],
                'category': row[3],
                'unit_of_measure': row[4],
                'quantity_on_hand': row[5],
                'unit_cost': row[6],
                'brand': row[7]
            })

        # Check products
        cursor = self.conn.execute("""
            SELECT id, product_code, product_name, category,
                   unit_of_measure, quantity_on_hand, selling_price
            FROM products
            WHERE barcode = ?
        """, (barcode,))

        for row in cursor.fetchall():
            results.append({
                'type': 'product',
                'id': row[0],
                'code': row[1],
                'name': row[2],
                'category': row[3],
                'unit_of_measure': row[4],
                'quantity_on_hand': row[5],
                'selling_price': row[6]
            })

        return results

    def _determine_best_match(self, results: List[Dict]) -> Optional[Dict]:
        """Determine the most reliable result from multiple sources"""
        if not results:
            return None

        # Priority: High confidence, has image, most complete data
        scored_results = []
        for result in results:
            score = 0

            # Confidence score
            if result.get('confidence') == 'high':
                score += 3
            elif result.get('confidence') == 'medium':
                score += 2

            # Has image
            if result.get('image_url'):
                score += 2

            # Has brand
            if result.get('brand'):
                score += 1

            # Has category
            if result.get('category'):
                score += 1

            # Open Food Facts is generally most accurate for food
            if result.get('source') == 'Open Food Facts':
                score += 1

            scored_results.append((score, result))

        # Return highest scoring result
        scored_results.sort(reverse=True, key=lambda x: x[0])
        return scored_results[0][1]
