import sqlite3
from datetime import datetime

INVENTORY_DB = 'inventory.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def adjust_inventory_to_realistic_levels():
    """
    Adjust inventory to realistic levels for a $100k/month revenue business.
    Target: ~$15-20k total inventory (1-2 weeks of COGS at 30% food cost)
    """

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get current inventory
    cursor.execute("""
        SELECT id, ingredient_name, category, quantity_on_hand, unit_of_measure,
               average_unit_price
        FROM ingredients
        WHERE active = 1
    """)

    ingredients = cursor.fetchall()

    print(f"\n{'='*70}")
    print("ADJUSTING INVENTORY TO REALISTIC LEVELS")
    print(f"{'='*70}\n")

    # Calculate current total value
    current_value = sum(float(ing['quantity_on_hand']) * float(ing['average_unit_price'])
                       for ing in ingredients)
    print(f"Current inventory value: ${current_value:,.2f}")

    # Category-based reduction factors
    # Different categories need different inventory levels
    category_factors = {
        'Spices & Seasonings': 0.02,      # Very low - spices last long, need small amounts
        'Oils & Fats': 0.05,               # Low - one or two cases
        'Dairy': 0.03,                     # Very low - highly perishable
        'Produce': 0.02,                   # Very low - highly perishable
        'Proteins': 0.03,                  # Low - perishable, order frequently
        'Meat': 0.03,                      # Low - perishable
        'Poultry': 0.03,                   # Low - perishable
        'Seafood': 0.02,                   # Very low - most perishable
        'Baking': 0.06,                    # Moderate - staples
        'Grains & Pasta': 0.06,            # Moderate - dry goods, can stock more
        'Sauces & Condiments': 0.04,       # Low-moderate
        'Beverages': 0.05,                 # Low-moderate
        'Canned Goods': 0.05,              # Low-moderate
        'Frozen': 0.04,                    # Low
        'Paper Products': 0.05,            # Low-moderate
        'Cleaning Supplies': 0.03,         # Low
    }

    updates = []
    new_value = 0

    for ing in ingredients:
        category = ing['category']
        current_qty = float(ing['quantity_on_hand'])
        price = float(ing['average_unit_price'])

        # Get reduction factor for category, default to 0.04 (4%)
        factor = category_factors.get(category, 0.04)

        # Calculate new quantity
        new_qty = current_qty * factor

        # Set minimum quantities based on unit of measure
        uom = ing['unit_of_measure']
        if uom in ['lb', 'kg']:
            min_qty = 2.0  # At least 2 lbs/kg
        elif uom in ['gal', 'liter']:
            min_qty = 1.0  # At least 1 gallon/liter
        elif uom in ['oz', 'ml']:
            min_qty = 8.0  # At least 8 oz/ml
        elif uom == 'each':
            min_qty = 1.0  # At least 1 each
        elif uom == 'case':
            min_qty = 0.5  # At least half a case
        else:
            min_qty = 1.0

        # Don't go below minimum
        new_qty = max(new_qty, min_qty)

        # Round to reasonable precision
        if new_qty < 10:
            new_qty = round(new_qty, 1)
        else:
            new_qty = round(new_qty)

        new_item_value = new_qty * price
        new_value += new_item_value

        updates.append({
            'id': ing['id'],
            'name': ing['ingredient_name'],
            'category': category,
            'old_qty': current_qty,
            'new_qty': new_qty,
            'uom': uom,
            'price': price,
            'old_value': current_qty * price,
            'new_value': new_item_value
        })

    print(f"Target inventory value: $15,000 - $20,000")
    print(f"Calculated new value: ${new_value:,.2f}")
    print(f"Reduction: {((current_value - new_value) / current_value * 100):.1f}%\n")

    # Show sample adjustments
    print("Sample adjustments by category:")
    print(f"{'Category':<25} {'Ingredient':<30} {'Old Qty':<12} {'New Qty':<12} {'Value'}")
    print("-" * 100)

    by_category = {}
    for upd in updates:
        cat = upd['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(upd)

    for cat in sorted(by_category.keys()):
        items = by_category[cat][:2]  # Show first 2 items per category
        for item in items:
            print(f"{cat:<25} {item['name']:<30} "
                  f"{item['old_qty']:.1f} {item['uom']:<8} "
                  f"{item['new_qty']:.1f} {item['uom']:<8} "
                  f"${item['new_value']:,.2f}")

    # Apply updates
    print("\nApplying inventory adjustments...")
    for upd in updates:
        cursor.execute("""
            UPDATE ingredients
            SET quantity_on_hand = ?
            WHERE id = ?
        """, (upd['new_qty'], upd['id']))

    # Log the adjustment in audit_log
    cursor.execute("""
        INSERT INTO audit_log (action_type, entity_type, entity_id, details, user)
        VALUES (?, ?, ?, ?, ?)
    """, (
        'INVENTORY_ADJUSTMENT',
        'ingredients',
        0,
        f"Adjusted all inventory quantities to realistic levels. Old value: ${current_value:,.2f}, New value: ${new_value:,.2f}",
        'system'
    ))

    conn.commit()
    conn.close()

    print(f"\n✓ Inventory adjusted successfully!")
    print(f"✓ New total inventory value: ${new_value:,.2f}")
    print(f"✓ Audit log entry created\n")

    # Show category breakdown
    print("\nInventory value by category:")
    print(f"{'Category':<25} {'Value':<15} {'% of Total'}")
    print("-" * 50)

    category_values = {}
    for upd in by_category:
        cat_value = sum(item['new_value'] for item in by_category[upd])
        category_values[upd] = cat_value

    for cat in sorted(category_values.keys(), key=lambda x: category_values[x], reverse=True):
        value = category_values[cat]
        pct = (value / new_value * 100) if new_value > 0 else 0
        print(f"{cat:<25} ${value:>12,.2f}  {pct:>5.1f}%")

    print(f"\n{'TOTAL':<25} ${new_value:>12,.2f}  100.0%")

if __name__ == '__main__':
    adjust_inventory_to_realistic_levels()
