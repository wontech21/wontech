"""
Setup Composite Ingredients System
Allows ingredients to be made from other base ingredients
"""
import sqlite3
from datetime import datetime

INVENTORY_DB = 'inventory.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def create_composite_ingredients_table():
    """Create table to store ingredient recipes (ingredients made from other ingredients)"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Create ingredient_recipes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingredient_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            composite_ingredient_id INTEGER NOT NULL,
            base_ingredient_id INTEGER NOT NULL,
            quantity_needed REAL NOT NULL,
            unit_of_measure TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (composite_ingredient_id) REFERENCES ingredients(id),
            FOREIGN KEY (base_ingredient_id) REFERENCES ingredients(id)
        )
    """)

    # Add composite flag to ingredients if it doesn't exist
    try:
        cursor.execute("ALTER TABLE ingredients ADD COLUMN is_composite INTEGER DEFAULT 0")
        print("✓ Added is_composite column to ingredients table")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("✓ is_composite column already exists")
        else:
            raise

    conn.commit()
    conn.close()
    print("✓ Composite ingredients table structure ready")

def add_tomato_sauce_composite():
    """Add pizza sauce as a composite ingredient made from base ingredients"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Check if we already have pizza sauce
    cursor.execute("SELECT id FROM ingredients WHERE ingredient_code = ?", ('SAUCE-PIZ',))
    existing = cursor.fetchone()

    if existing:
        print(f"✓ Pizza sauce already exists (id: {existing[0]})")
        sauce_id = existing[0]
    else:
        print("Creating pizza sauce ingredient...")
        cursor.execute("""
            INSERT INTO ingredients
            (ingredient_code, ingredient_name, category, unit_of_measure,
             quantity_on_hand, unit_cost, brand, active, is_composite)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('SAUCE-PIZ', 'Pizza Sauce', 'Prepared Foods', 'oz', 100, 0.00625, 'House Made', 1, 1))
        sauce_id = cursor.lastrowid
        print(f"✓ Created pizza sauce (id: {sauce_id})")

    # Mark pizza sauce as composite
    cursor.execute("UPDATE ingredients SET is_composite = 1 WHERE id = ?", (sauce_id,))

    # Add base ingredients for pizza sauce recipe
    base_ingredients = [
        ('TOMATO-PASTE', 'Tomato Paste', 'Produce', 'oz', 500, 0.15, 'Hunt\'s'),
        ('GARLIC-MINCED', 'Garlic Minced', 'Produce', 'oz', 50, 0.25, 'Fresh'),
        ('OREGANO-DRIED', 'Oregano Dried', 'Spices', 'tsp', 100, 0.10, 'McCormick'),
        ('BASIL-DRIED', 'Basil Dried', 'Spices', 'tsp', 100, 0.10, 'McCormick'),
        ('SALT', 'Salt', 'Spices', 'tsp', 500, 0.02, 'Morton'),
        ('OLIVE-OIL', 'Olive Oil', 'Oils', 'oz', 200, 0.30, 'Bertolli'),
    ]

    ingredient_ids = {}

    for code, name, category, unit, qty, cost, brand in base_ingredients:
        cursor.execute("SELECT id FROM ingredients WHERE ingredient_code = ?", (code,))
        existing = cursor.fetchone()

        if existing:
            ingredient_ids[code] = existing[0]
            print(f"✓ Using existing ingredient: {name}")
        else:
            cursor.execute("""
                INSERT INTO ingredients
                (ingredient_code, ingredient_name, category, unit_of_measure,
                 quantity_on_hand, unit_cost, brand, active, is_composite)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, name, category, unit, qty, cost, brand, 1, 0))
            ingredient_ids[code] = cursor.lastrowid
            print(f"✓ Created base ingredient: {name}")

    # Delete existing pizza sauce recipe if any
    cursor.execute("DELETE FROM ingredient_recipes WHERE composite_ingredient_id = ?", (sauce_id,))

    # Create pizza sauce recipe (makes 128 oz = 1 gallon of sauce)
    sauce_recipe = [
        (ingredient_ids['TOMATO-PASTE'], 96, 'oz', 'Main ingredient'),  # 6 cans
        (ingredient_ids['OLIVE-OIL'], 8, 'oz', 'For sautéing'),
        (ingredient_ids['GARLIC-MINCED'], 4, 'oz', 'Flavor'),
        (ingredient_ids['OREGANO-DRIED'], 16, 'tsp', 'Herb'),
        (ingredient_ids['BASIL-DRIED'], 16, 'tsp', 'Herb'),
        (ingredient_ids['SALT'], 8, 'tsp', 'Seasoning'),
    ]

    total_cost = 0
    for base_id, qty, unit, notes in sauce_recipe:
        cursor.execute("""
            INSERT INTO ingredient_recipes
            (composite_ingredient_id, base_ingredient_id, quantity_needed, unit_of_measure, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (sauce_id, base_id, qty, unit, notes))

        # Calculate cost
        cursor.execute("SELECT unit_cost FROM ingredients WHERE id = ?", (base_id,))
        unit_cost = cursor.fetchone()[0]
        total_cost += qty * unit_cost

    # Update pizza sauce unit cost (per oz)
    sauce_unit_cost = total_cost / 128  # 128 oz per batch
    cursor.execute("UPDATE ingredients SET unit_cost = ? WHERE id = ?", (sauce_unit_cost, sauce_id))

    print(f"\n✓ Pizza Sauce Recipe Created:")
    print(f"  Batch size: 128 oz (1 gallon)")
    print(f"  Total batch cost: ${total_cost:.2f}")
    print(f"  Cost per oz: ${sauce_unit_cost:.4f}")

    conn.commit()
    conn.close()

def add_house_made_meatballs():
    """Add house-made meatballs as another composite ingredient example"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Create meatballs as composite ingredient
    cursor.execute("SELECT id FROM ingredients WHERE ingredient_code = ?", ('MEATBALL-HOUSE',))
    existing = cursor.fetchone()

    if existing:
        print(f"\n✓ House meatballs already exists (id: {existing[0]})")
        meatball_id = existing[0]
    else:
        cursor.execute("""
            INSERT INTO ingredients
            (ingredient_code, ingredient_name, category, unit_of_measure,
             quantity_on_hand, unit_cost, brand, active, is_composite)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('MEATBALL-HOUSE', 'House Made Meatballs', 'Prepared Foods', 'each', 200, 0.50, 'House Made', 1, 1))
        meatball_id = cursor.lastrowid
        print(f"\n✓ Created house meatballs (id: {meatball_id})")

    # Mark as composite
    cursor.execute("UPDATE ingredients SET is_composite = 1 WHERE id = ?", (meatball_id,))

    # Add base ingredients for meatballs
    base_ingredients = [
        ('BEEF-GROUND', 'Ground Beef 80/20', 'Meat', 'lb', 100, 4.99, 'Local Butcher'),
        ('BREADCRUMBS', 'Italian Bread Crumbs', 'Dry Goods', 'cup', 50, 0.50, 'Progresso'),
        ('EGG-WHOLE', 'Whole Eggs', 'Dairy', 'each', 60, 0.25, 'Farm Fresh'),
        ('PARMESAN-GRATED', 'Parmesan Cheese Grated', 'Dairy', 'cup', 20, 2.00, 'Kraft'),
    ]

    ingredient_ids = {}

    for code, name, category, unit, qty, cost, brand in base_ingredients:
        cursor.execute("SELECT id FROM ingredients WHERE ingredient_code = ?", (code,))
        existing = cursor.fetchone()

        if existing:
            ingredient_ids[code] = existing[0]
        else:
            cursor.execute("""
                INSERT INTO ingredients
                (ingredient_code, ingredient_name, category, unit_of_measure,
                 quantity_on_hand, unit_cost, brand, active, is_composite)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, name, category, unit, qty, cost, brand, 1, 0))
            ingredient_ids[code] = cursor.lastrowid

    # Delete existing meatball recipe if any
    cursor.execute("DELETE FROM ingredient_recipes WHERE composite_ingredient_id = ?", (meatball_id,))

    # Meatball recipe (makes 20 meatballs)
    meatball_recipe = [
        (ingredient_ids['BEEF-GROUND'], 2, 'lb', 'Main protein'),
        (ingredient_ids['BREADCRUMBS'], 1, 'cup', 'Binder'),
        (ingredient_ids['EGG-WHOLE'], 2, 'each', 'Binder'),
        (ingredient_ids['PARMESAN-GRATED'], 0.5, 'cup', 'Flavor'),
        (ingredient_ids.get('GARLIC-MINCED', None), 1, 'oz', 'Flavor') if 'GARLIC-MINCED' in ingredient_ids else None,
        (ingredient_ids.get('OREGANO-DRIED', None), 2, 'tsp', 'Seasoning') if 'OREGANO-DRIED' in ingredient_ids else None,
        (ingredient_ids.get('SALT', None), 2, 'tsp', 'Seasoning') if 'SALT' in ingredient_ids else None,
    ]

    meatball_recipe = [r for r in meatball_recipe if r is not None]

    total_cost = 0
    for base_id, qty, unit, notes in meatball_recipe:
        cursor.execute("""
            INSERT INTO ingredient_recipes
            (composite_ingredient_id, base_ingredient_id, quantity_needed, unit_of_measure, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (meatball_id, base_id, qty, unit, notes))

        cursor.execute("SELECT unit_cost FROM ingredients WHERE id = ?", (base_id,))
        unit_cost = cursor.fetchone()[0]
        total_cost += qty * unit_cost

    # Update meatball unit cost (per meatball)
    meatball_unit_cost = total_cost / 20  # 20 meatballs per batch
    cursor.execute("UPDATE ingredients SET unit_cost = ? WHERE id = ?", (meatball_unit_cost, meatball_id))

    print(f"✓ House Meatball Recipe Created:")
    print(f"  Batch size: 20 meatballs")
    print(f"  Total batch cost: ${total_cost:.2f}")
    print(f"  Cost per meatball: ${meatball_unit_cost:.4f}")

    conn.commit()
    conn.close()

def main():
    print("=" * 60)
    print("Setting Up Composite Ingredients System")
    print("=" * 60)

    create_composite_ingredients_table()
    add_tomato_sauce_composite()
    add_house_made_meatballs()

    print("\n" + "=" * 60)
    print("✓ Composite Ingredients Setup Complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()
