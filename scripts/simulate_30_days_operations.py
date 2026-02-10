#!/usr/bin/env python3
"""
30-Day Operations Simulation
Simulates realistic restaurant operations including:
- Daily sales processing
- Inventory depletion through sales
- Restocking via invoices
- Inventory count adjustments
- Waste tracking
"""

import sqlite3
import random
from datetime import datetime, timedelta

INVENTORY_DB = 'inventory.db'

class OperationsSimulator:
    def __init__(self):
        self.conn = sqlite3.connect(INVENTORY_DB)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.start_date = datetime.now() - timedelta(days=30)

    def get_all_products(self):
        """Get all products with recipes"""
        self.cursor.execute("""
            SELECT DISTINCT p.id, p.product_name, p.selling_price
            FROM products p
            JOIN recipes r ON p.id = r.product_id
            WHERE p.product_name NOT LIKE '%Test%'
            ORDER BY p.product_name
        """)
        return self.cursor.fetchall()

    def get_product_recipe(self, product_id):
        """Get recipe for a product"""
        self.cursor.execute("""
            SELECT
                r.ingredient_id,
                r.quantity_needed,
                r.unit_of_measure,
                i.ingredient_name,
                i.unit_cost,
                i.quantity_on_hand
            FROM recipes r
            JOIN ingredients i ON r.ingredient_id = i.id
            WHERE r.product_id = ?
        """, (product_id,))
        return self.cursor.fetchall()

    def generate_daily_sales(self, day_num, products):
        """Generate realistic sales for one day"""
        sales_data = []
        current_date = self.start_date + timedelta(days=day_num)

        # Weekends have higher sales
        is_weekend = current_date.weekday() >= 5
        base_multiplier = 1.5 if is_weekend else 1.0

        # Different times of day
        peak_hours = ['11:30:00', '12:00:00', '12:30:00', '13:00:00',
                     '18:00:00', '18:30:00', '19:00:00', '19:30:00']
        off_hours = ['10:00:00', '14:00:00', '15:30:00', '17:00:00', '20:30:00']

        for product in products:
            # Not all products sold every day
            if random.random() < 0.7:  # 70% chance product is sold
                # Generate 1-5 sales transactions for this product throughout the day
                num_transactions = random.randint(1, 5)

                for _ in range(num_transactions):
                    # Peak hours = more sales
                    if random.random() < 0.6:
                        sale_time = random.choice(peak_hours)
                        qty_multiplier = 1.5
                    else:
                        sale_time = random.choice(off_hours)
                        qty_multiplier = 0.8

                    # Quantity varies by product price (cheaper = more units)
                    base_qty = int(100 / float(product['selling_price']))
                    quantity = max(1, int(base_qty * base_multiplier * qty_multiplier * random.uniform(0.5, 1.5)))

                    # Sometimes items sell at discount
                    retail_price = float(product['selling_price'])
                    if random.random() < 0.15:  # 15% chance of discount
                        discount_pct = random.choice([0.10, 0.15, 0.20])  # 10-20% off
                        retail_price = round(retail_price * (1 - discount_pct), 2)

                    sales_data.append({
                        'product_id': product['id'],
                        'product_name': product['product_name'],
                        'quantity': quantity,
                        'retail_price': retail_price,
                        'original_price': float(product['selling_price']),
                        'time': sale_time
                    })

        return sales_data

    def create_sales_csv(self, day_num, sales_data):
        """Create CSV file for day's sales"""
        filename = f'day_{day_num + 1:02d}_sales.csv'

        with open(filename, 'w') as f:
            f.write('Product, Quantity, Retail_Price, Time\n')
            for sale in sales_data:
                f.write(f"{sale['product_name']}, {sale['quantity']}, {sale['retail_price']}, {sale['time']}\n")

        return filename

    def process_sale(self, sale, sale_date):
        """Process a single sale (deduct inventory, record sale)"""
        product_id = sale['product_id']
        quantity_sold = sale['quantity']
        retail_price = sale['retail_price']
        original_price = sale['original_price']
        sale_time = sale['time']

        # Get recipe
        recipe = self.get_product_recipe(product_id)

        # Calculate cost and deduct ingredients
        product_cost = 0
        for ingredient in recipe:
            quantity_needed = ingredient['quantity_needed'] * quantity_sold
            ingredient_cost = ingredient['unit_cost'] * quantity_needed
            product_cost += ingredient_cost

            # Deduct from inventory
            self.cursor.execute("""
                UPDATE ingredients
                SET quantity_on_hand = quantity_on_hand - ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (quantity_needed, ingredient['ingredient_id']))

        # Calculate revenue and profit
        revenue = retail_price * quantity_sold
        gross_profit = revenue - product_cost

        # Calculate discount
        discount_amount = (original_price - retail_price) * quantity_sold
        discount_percent = ((original_price - retail_price) / original_price * 100) if original_price > 0 else 0

        # Record sale
        self.cursor.execute("""
            INSERT INTO sales_history (
                sale_date, sale_time, product_id, product_name, quantity_sold,
                revenue, cost_of_goods, gross_profit,
                original_price, sale_price, discount_amount, discount_percent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sale_date,
            sale_time,
            product_id,
            sale['product_name'],
            quantity_sold,
            revenue,
            product_cost,
            gross_profit,
            original_price,
            retail_price,
            discount_amount,
            discount_percent
        ))

        return revenue, gross_profit

    def process_daily_sales(self, sales_data, sale_date):
        """Process all sales for a day"""
        total_revenue = 0
        total_profit = 0
        processed = 0

        for sale in sales_data:
            try:
                revenue, profit = self.process_sale(sale, sale_date)
                total_revenue += revenue
                total_profit += profit
                processed += 1
            except Exception as e:
                print(f"      ❌ Error processing sale: {e}")

        self.conn.commit()
        return processed, total_revenue, total_profit

    def check_and_restock(self, day_num):
        """Check inventory levels and create purchase transactions if needed"""
        print(f"  🔍 Checking inventory levels...")

        # Get ingredients that are low
        self.cursor.execute("""
            SELECT id, ingredient_name, quantity_on_hand, unit_of_measure,
                   unit_cost, reorder_level
            FROM ingredients
            WHERE quantity_on_hand < 50  -- Low threshold
            ORDER BY quantity_on_hand ASC
            LIMIT 10
        """)

        low_stock = self.cursor.fetchall()

        if low_stock:
            print(f"    ⚠️  Found {len(low_stock)} ingredients below threshold")

            purchase_date = (self.start_date + timedelta(days=day_num)).strftime('%Y-%m-%d')
            vendor = random.choice([
                'Sysco Foods', 'US Foods', 'Restaurant Depot',
                'Gordon Food Service', 'Performance Foodservice'
            ])

            total_cost = 0

            for ingredient in low_stock:
                # Calculate restock quantity (bring back to healthy level)
                target_qty = max(200, float(ingredient['reorder_level'] or 100))
                restock_qty = target_qty - float(ingredient['quantity_on_hand'])
                restock_qty = max(50, restock_qty)  # Minimum order

                item_cost = float(ingredient['unit_cost']) * restock_qty
                total_cost += item_cost

                # Record purchase transaction
                self.cursor.execute("""
                    INSERT INTO ingredient_transactions (
                        ingredient_id, transaction_type, quantity_change,
                        unit_cost, transaction_date, notes
                    ) VALUES (?, 'PURCHASE', ?, ?, ?, ?)
                """, (ingredient['id'], restock_qty, ingredient['unit_cost'],
                      purchase_date, f"Restock from {vendor}"))

                # Update ingredient stock
                self.cursor.execute("""
                    UPDATE ingredients
                    SET quantity_on_hand = quantity_on_hand + ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (restock_qty, ingredient['id']))

                print(f"      📦 {ingredient['ingredient_name']}: +{restock_qty:.1f} {ingredient['unit_of_measure']}")

            self.conn.commit()
            print(f"    ✅ Purchase order from {vendor}: ${total_cost:,.2f}")
            return total_cost
        else:
            print(f"    ✓ All inventory levels OK")
            return 0

    def simulate_inventory_adjustments(self, day_num):
        """Simulate random inventory adjustments (waste, spoilage, etc.)"""
        # Only do this occasionally (every 7-10 days)
        if day_num % random.randint(7, 10) != 0:
            return

        print(f"  📋 Performing inventory adjustments...")

        # Get random ingredients
        self.cursor.execute("""
            SELECT id, ingredient_name, quantity_on_hand, unit_of_measure
            FROM ingredients
            WHERE quantity_on_hand > 10
            ORDER BY RANDOM()
            LIMIT 5
        """)

        ingredients = self.cursor.fetchall()
        adjustment_date = (self.start_date + timedelta(days=day_num)).strftime('%Y-%m-%d')

        for ingredient in ingredients:
            current_qty = float(ingredient['quantity_on_hand'])

            # Simulate small discrepancies (spoilage, waste, counting errors)
            adjustment_type = random.choice(['waste', 'spoilage', 'counting_error', 'none'])

            if adjustment_type == 'waste':
                # Small waste (1-5% of stock)
                waste_qty = -current_qty * random.uniform(0.01, 0.05)
                reason = 'Waste'
                trans_type = 'WASTE'
            elif adjustment_type == 'spoilage':
                # Spoilage (2-8% of stock)
                waste_qty = -current_qty * random.uniform(0.02, 0.08)
                reason = 'Spoilage'
                trans_type = 'WASTE'
            elif adjustment_type == 'counting_error':
                # Counting error (could be + or -)
                waste_qty = current_qty * random.uniform(-0.03, 0.03)
                reason = 'Count Adjustment'
                trans_type = 'ADJUSTMENT'
            else:
                continue

            # Record transaction
            self.cursor.execute("""
                INSERT INTO ingredient_transactions (
                    ingredient_id, transaction_type, quantity_change,
                    transaction_date, notes
                ) VALUES (?, ?, ?, ?, ?)
            """, (ingredient['id'], trans_type, waste_qty, adjustment_date, reason))

            # Update quantity
            new_qty = current_qty + waste_qty
            self.cursor.execute("""
                UPDATE ingredients
                SET quantity_on_hand = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_qty, ingredient['id']))

            sign = '+' if waste_qty >= 0 else ''
            print(f"    🔢 {ingredient['ingredient_name']}: {current_qty:.1f} → {new_qty:.1f} "
                  f"({sign}{waste_qty:.1f} {ingredient['unit_of_measure']}) - {reason}")

        self.conn.commit()

    def run_simulation(self):
        """Run complete 30-day simulation"""
        print("\n" + "="*70)
        print("🚀 Starting 30-Day Operations Simulation")
        print("="*70 + "\n")

        products = self.get_all_products()
        print(f"📦 Found {len(products)} products with recipes\n")

        success_count = 0
        total_revenue_all = 0
        total_profit_all = 0
        total_purchase_cost = 0

        for day_num in range(30):
            current_date = self.start_date + timedelta(days=day_num)
            date_str = current_date.strftime('%Y-%m-%d')
            day_name = current_date.strftime('%A')

            print(f"\n{'='*70}")
            print(f"📅 Day {day_num + 1}/30: {day_name}, {date_str}")
            print('='*70)

            # Generate sales
            print(f"  🎲 Generating sales data...")
            sales_data = self.generate_daily_sales(day_num, products)
            print(f"    ✓ Generated {len(sales_data)} transactions")

            # Create CSV
            csv_filename = self.create_sales_csv(day_num, sales_data)
            print(f"    ✓ Created {csv_filename}")

            # Process sales
            print(f"  📤 Processing sales...")
            processed, revenue, profit = self.process_daily_sales(sales_data, date_str)
            print(f"    ✅ Processed {processed} sales")
            print(f"       💰 Revenue: ${revenue:,.2f}")
            print(f"       📊 Profit: ${profit:,.2f}")

            success_count += 1
            total_revenue_all += revenue
            total_profit_all += profit

            # Check inventory and restock if needed
            purchase_cost = self.check_and_restock(day_num)
            total_purchase_cost += purchase_cost

            # Simulate inventory adjustments
            self.simulate_inventory_adjustments(day_num)

        print("\n" + "="*70)
        print("✅ Simulation Complete!")
        print("="*70)
        print(f"Successfully processed: {success_count}/30 days")
        print(f"\n📊 Summary:")

        # Get final stats
        self.cursor.execute("SELECT COUNT(*) as count FROM sales_history")
        total_sales = self.cursor.fetchone()['count']

        self.cursor.execute("SELECT SUM(revenue) as revenue FROM sales_history")
        total_revenue = self.cursor.fetchone()['revenue'] or 0

        self.cursor.execute("SELECT SUM(gross_profit) as profit FROM sales_history")
        total_profit = self.cursor.fetchone()['profit'] or 0

        self.cursor.execute("""
            SELECT COUNT(*) as count FROM ingredient_transactions
            WHERE transaction_type = 'PURCHASE'
        """)
        total_purchases = self.cursor.fetchone()['count']

        self.cursor.execute("""
            SELECT SUM(quantity_change * unit_cost) as cost
            FROM ingredient_transactions
            WHERE transaction_type = 'PURCHASE'
        """)
        purchase_cost = self.cursor.fetchone()['cost'] or 0

        self.cursor.execute("""
            SELECT COUNT(*) as count FROM ingredient_transactions
            WHERE transaction_type IN ('WASTE', 'ADJUSTMENT')
        """)
        total_adjustments = self.cursor.fetchone()['count']

        print(f"  💰 Total Sales Transactions: {total_sales:,}")
        print(f"  💵 Total Revenue: ${total_revenue:,.2f}")
        print(f"  📈 Total Gross Profit: ${total_profit:,.2f}")
        print(f"  📦 Purchase Transactions: {total_purchases}")
        print(f"  💸 Purchase Costs: ${purchase_cost:,.2f}")
        print(f"  📋 Waste/Adjustment Transactions: {total_adjustments}")
        print(f"  🎯 Net Profit (before overhead): ${total_profit - purchase_cost:,.2f}")
        print()

        self.conn.close()


if __name__ == '__main__':
    simulator = OperationsSimulator()
    simulator.run_simulation()
