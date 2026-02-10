#!/usr/bin/env python3
"""
Fix Recipe References
Removes recipe items that reference non-existent ingredients
"""
import sqlite3

INVENTORY_DB = 'inventory.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def fix_recipe_references():
    """Remove recipe items with invalid ingredient references"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    print("=" * 60)
    print("FIXING RECIPE REFERENCES")
    print("=" * 60)

    # Find recipes with null ingredient references
    cursor.execute("""
        SELECT r.id, r.product_id, p.product_name, r.ingredient_id, r.source_type
        FROM recipes r
        JOIN products p ON r.product_id = p.id
        LEFT JOIN ingredients i ON r.ingredient_id = i.id AND r.source_type = 'ingredient'
        WHERE r.source_type = 'ingredient' AND i.id IS NULL
    """)

    broken_recipes = cursor.fetchall()

    if not broken_recipes:
        print("\n✓ No broken recipe references found!")
        conn.close()
        return

    print(f"\n⚠️  Found {len(broken_recipes)} broken recipe references:")
    print()

    # Group by product
    by_product = {}
    for recipe in broken_recipes:
        product_name = recipe['product_name']
        if product_name not in by_product:
            by_product[product_name] = []
        by_product[product_name].append(recipe)

    for product_name, recipes in by_product.items():
        print(f"  • {product_name}: {len(recipes)} invalid ingredients")

    print()
    response = input("Delete these broken recipe items? (yes/no): ")

    if response.lower() != 'yes':
        print("\nCancelled. No changes made.")
        conn.close()
        return

    # Delete broken recipe items
    recipe_ids = [recipe['id'] for recipe in broken_recipes]
    placeholders = ','.join('?' * len(recipe_ids))
    cursor.execute(f"DELETE FROM recipes WHERE id IN ({placeholders})", recipe_ids)

    conn.commit()

    print(f"\n✓ Deleted {len(broken_recipes)} broken recipe items")
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()
    print("The following products now have incomplete recipes:")
    print("You should edit them in the Products tab to add the correct ingredients:")
    print()
    for product_name in by_product.keys():
        print(f"  • {product_name}")
    print()
    print("=" * 60)

    conn.close()

if __name__ == '__main__':
    fix_recipe_references()
