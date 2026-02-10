#!/usr/bin/env python3
"""
Seed Firing Up Pizza's full menu into the WONTECH platform.

Populates:
  - Organization settings in master.db
  - Business hours, menu categories, menu items (with sizes),
    modifier groups, modifiers (with per-size prices), and
    item ↔ modifier-group assignments in org_1.db

Idempotent: clears existing menu data before re-seeding so the script
can be safely re-run at any time.

Usage:
    python scripts/seed_firing_up_menu.py
"""

import sys
import os

# Allow imports from the project root (one directory up from scripts/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from db_manager import create_org_database, create_master_db, get_org_db_path, MASTER_DB_PATH


# ═══════════════════════════════════════════════════════════════════════════
#  Helper utilities
# ═══════════════════════════════════════════════════════════════════════════

def slugify(name):
    """Convert a menu item name to a URL-friendly slug."""
    return (
        name.lower()
        .replace('&', 'and')
        .replace("'", '')
        .replace('"', '')
        .replace('/', '-')
        .replace('(', '')
        .replace(')', '')
        .replace(',', '')
        .replace('.', '')
        .replace('  ', ' ')
        .strip()
        .replace(' ', '-')
    )


def add_category(cursor, name, slug, display_order, icon=None, description=None,
                 parent_category_id=None):
    """Insert a menu category and return its id."""
    cursor.execute("""
        INSERT INTO menu_categories (name, slug, description, icon, display_order,
                                     parent_category_id, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (name, slug, description, icon, display_order, parent_category_id))
    return cursor.lastrowid


def add_item(cursor, category_id, name, sizes_dict, is_popular=0,
             description=None, dietary_tags=None, display_order=0):
    """
    Insert a menu item and all of its size variants.

    Args:
        cursor: DB cursor
        category_id: FK to menu_categories
        name: Item display name
        sizes_dict: OrderedDict / dict of {size_name: price}
                    e.g. {'Small 10"': 13.55, 'Large 16"': 17.76}
                    For single-price items: {'Regular': 17.99}
        is_popular: boolean flag
        description: optional description text
        dietary_tags: optional comma-separated tags (e.g. 'vegetarian,gluten-free')
        display_order: sort order inside the category

    Returns:
        (item_id, {size_name: size_id}) tuple
    """
    item_slug = slugify(name)
    cursor.execute("""
        INSERT INTO menu_items (category_id, name, slug, description, dietary_tags,
                                is_popular, is_active, display_order)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
    """, (category_id, name, item_slug, description, dietary_tags,
          is_popular, display_order))
    item_id = cursor.lastrowid

    size_ids = {}
    for idx, (size_name, price) in enumerate(sizes_dict.items()):
        size_code = slugify(size_name)
        is_default = 1 if idx == 0 else 0
        cursor.execute("""
            INSERT INTO menu_item_sizes (menu_item_id, size_name, size_code, price,
                                         is_default, display_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (item_id, size_name, size_code, price, is_default, idx))
        size_ids[size_name] = cursor.lastrowid

    return item_id, size_ids


def add_modifier_group(cursor, name, selection_type, min_sel, max_sel):
    """Insert a modifier group and return its id."""
    cursor.execute("""
        INSERT INTO menu_modifier_groups (name, selection_type, min_selections, max_selections)
        VALUES (?, ?, ?, ?)
    """, (name, selection_type, min_sel, max_sel))
    return cursor.lastrowid


def add_modifier(cursor, group_id, name, default_price, display_order=0):
    """Insert a modifier and return its id."""
    cursor.execute("""
        INSERT INTO menu_modifiers (group_id, name, default_price, display_order, is_active)
        VALUES (?, ?, ?, ?, 1)
    """, (group_id, name, default_price, display_order))
    return cursor.lastrowid


def add_modifier_price(cursor, modifier_id, size_id, price):
    """Insert a per-size price override for a modifier."""
    cursor.execute("""
        INSERT INTO menu_modifier_prices (modifier_id, size_id, price)
        VALUES (?, ?, ?)
    """, (modifier_id, size_id, price))


def link_item_modifier_group(cursor, item_id, group_id, display_order=0):
    """Link a menu item to a modifier group."""
    cursor.execute("""
        INSERT OR IGNORE INTO menu_item_modifier_groups
            (menu_item_id, modifier_group_id, display_order)
        VALUES (?, ?, ?)
    """, (item_id, group_id, display_order))


# ═══════════════════════════════════════════════════════════════════════════
#  Organization settings (master.db)
# ═══════════════════════════════════════════════════════════════════════════

def update_organization():
    """Update the Default Organization row in master.db with Firing Up details."""
    conn = sqlite3.connect(MASTER_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE organizations SET
            organization_name = 'Firing Up Pizza & Grill',
            slug = 'firing-up',
            phone = '(978) 491-5450',
            address = '721 Gloucester Crossing Rd',
            city = 'Gloucester',
            state = 'MA',
            zip_code = '01930',
            tagline = 'Firing up fast and fresh',
            description = 'Your neighborhood pizza and grill, serving Gloucester since day one. From custom pizzas with 30+ toppings to flame-broiled burgers, fresh salads, loaded subs, and homemade pasta — we fire up everything fresh to order. Family-owned, community-driven.',
            website_enabled = 1,
            online_ordering_enabled = 1,
            delivery_enabled = 1,
            pickup_enabled = 1,
            dinein_enabled = 1,
            delivery_fee = 2.50,
            delivery_minimum = 15.00,
            tax_rate = 6.25,
            estimated_pickup_minutes = 20,
            estimated_delivery_minutes = 45,
            primary_color = '#dc2626',
            secondary_color = '#991b1b',
            accent_color = '#f59e0b',
            facebook_url = 'https://www.facebook.com/firinguppizza',
            instagram_url = 'https://www.instagram.com/firinguppizza',
            google_maps_url = 'https://maps.google.com/?q=Firing+Up+Pizza+Gloucester+MA',
            logo_url = '/static/img/firinguplogo.png',
            order_cutoff_minutes = 30
        WHERE id = 1
    """)
    conn.commit()
    conn.close()
    print("[OK] Organization settings updated in master.db")


# ═══════════════════════════════════════════════════════════════════════════
#  Clear existing menu data
# ═══════════════════════════════════════════════════════════════════════════

def clear_menu_data(cursor):
    """Remove existing menu data for a clean re-seed."""
    tables = [
        'menu_modifier_prices',
        'menu_item_modifier_groups',
        'order_item_modifiers',
        'menu_modifiers',
        'menu_modifier_groups',
        'menu_item_sizes',
        'menu_items',
        'menu_categories',
        'business_hours',
    ]
    for table in tables:
        cursor.execute(f'DELETE FROM {table}')
    print("[OK] Cleared existing menu data")


# ═══════════════════════════════════════════════════════════════════════════
#  Business hours
# ═══════════════════════════════════════════════════════════════════════════

def seed_business_hours(cursor):
    """Seed weekly business hours."""
    hours = [
        # (day_of_week, open_time, close_time, is_closed)
        (0, '09:00', '21:30', 0),   # Monday
        (1, '09:00', '21:30', 0),   # Tuesday
        (2, '09:00', '21:30', 0),   # Wednesday
        (3, '09:00', '22:00', 0),   # Thursday
        (4, '09:00', '22:00', 0),   # Friday
        (5, '09:00', '22:00', 0),   # Saturday
        (6, '00:00', '00:00', 1),   # Sunday — CLOSED
    ]
    for day, open_t, close_t, closed in hours:
        cursor.execute("""
            INSERT INTO business_hours (day_of_week, open_time, close_time, is_closed)
            VALUES (?, ?, ?, ?)
        """, (day, open_t, close_t, closed))
    print("[OK] Business hours seeded")


# ═══════════════════════════════════════════════════════════════════════════
#  Menu categories
# ═══════════════════════════════════════════════════════════════════════════

def seed_categories(cursor):
    """Seed all menu categories. Returns dict of slug -> category_id."""
    cats = {}

    cats['pizza'] = add_category(cursor, 'Pizza', 'pizza', 1)
    cats['custom-pizza'] = add_category(cursor, 'Firing Up Pizza Customs', 'custom-pizza', 2)
    cats['calzones'] = add_category(cursor, 'Calzones', 'calzones', 3)
    cats['dinner-plates'] = add_category(cursor, 'Dinner Plates', 'dinner-plates', 4)
    cats['pasta'] = add_category(cursor, 'Pasta', 'pasta', 5)
    cats['rice-plates'] = add_category(cursor, 'Rice Plates', 'rice-plates', 6)
    cats['bowls'] = add_category(cursor, 'Burrito & Fajita Bowls', 'bowls', 7)

    # Appetizers — parent + subcategories
    cats['appetizers'] = add_category(cursor, 'Appetizers & Sides', 'appetizers', 8)
    cats['app-wings'] = add_category(
        cursor, 'Wings & Fingers', 'app-wings', 1,
        parent_category_id=cats['appetizers'])
    cats['app-fried'] = add_category(
        cursor, 'Fried Items', 'app-fried', 2,
        parent_category_id=cats['appetizers'])
    cats['app-fries'] = add_category(
        cursor, 'Fries & Sides', 'app-fries', 3,
        parent_category_id=cats['appetizers'])
    cats['app-specialty'] = add_category(
        cursor, 'Specialty', 'app-specialty', 4,
        parent_category_id=cats['appetizers'])

    cats['salads'] = add_category(cursor, 'Salads', 'salads', 9)
    cats['beverages-desserts'] = add_category(cursor, 'Beverages & Desserts', 'beverages-desserts', 10)
    cats['acai'] = add_category(cursor, 'Acai', 'acai', 11)
    cats['choco-zone'] = add_category(cursor, 'Choco-Zone', 'choco-zone', 12)
    cats['wraps'] = add_category(cursor, 'Wraps', 'wraps', 13)
    cats['sandwiches'] = add_category(cursor, 'Sandwiches & Clubs', 'sandwiches', 14)
    cats['roast-beef'] = add_category(cursor, 'Roast Beef', 'roast-beef', 15)
    cats['hot-subs'] = add_category(cursor, 'Subs - Hot', 'hot-subs', 16)
    cats['cold-subs'] = add_category(cursor, 'Subs - Cold', 'cold-subs', 17)
    cats['omelette-subs'] = add_category(cursor, 'Omelette Subs', 'omelette-subs', 18)
    cats['burgers-dogs'] = add_category(cursor, 'Burgers & Dogs', 'burgers-dogs', 19)
    cats['kids-menu'] = add_category(cursor, "Little Flames' Favorites", 'kids-menu', 20)

    print(f"[OK] {len(cats)} categories seeded")
    return cats


# ═══════════════════════════════════════════════════════════════════════════
#  Modifier groups & modifiers
# ═══════════════════════════════════════════════════════════════════════════

def seed_modifier_groups(cursor):
    """
    Seed all modifier groups and their modifiers.
    Returns dict of group_key -> group_id for use in item assignment.
    """
    groups = {}

    # ------------------------------------------------------------------
    #  Pizza Toppings  (multiple, 0-20)
    # ------------------------------------------------------------------
    gid = add_modifier_group(cursor, 'Pizza Toppings', 'multiple', 0, 20)
    groups['pizza_toppings'] = gid

    # Standard pizza toppings — per-size pricing:
    #   Mini $0.98, Small $1.26, Large $1.78, Party $2.76
    standard_pizza_toppings = [
        'Pepperoni', 'Italian Sausage', 'Bacon', 'Ground Beef', 'Linguica',
        'Ham', 'Meatballs', 'Salami', 'White Onions', 'Green Peppers',
        'Jalapenos', 'Caramelized Onions', 'Roasted Red Peppers', 'Broccoli',
        'Mushrooms', 'Fresh Spinach', 'Garlic', 'Black Olives', 'Tomatoes',
        'Pineapple', 'Breaded Eggplant', 'Artichoke Hearts', 'Extra Cheese',
        'Provolone', 'Feta', 'Ricotta', 'Parmesan',
    ]
    std_prices = {
        'Mini 6"': 0.98, 'Small 10"': 1.26, 'Large 16"': 1.78, 'Party 24sq': 2.76,
    }
    pizza_topping_mods = {}
    for idx, name in enumerate(standard_pizza_toppings):
        mid = add_modifier(cursor, gid, name, default_price=1.26, display_order=idx)
        pizza_topping_mods[name] = mid

    # Special pizza toppings with different per-size pricing
    # Catupiry — flat $4.00 default
    mid = add_modifier(cursor, gid, 'Catupiry', default_price=4.00,
                       display_order=len(standard_pizza_toppings))
    pizza_topping_mods['Catupiry'] = mid

    # Grilled Chicken — Mini $1.26, Small $2.76, Large $3.83, Party $9.16
    mid = add_modifier(cursor, gid, 'Grilled Chicken', default_price=2.76,
                       display_order=len(standard_pizza_toppings) + 1)
    pizza_topping_mods['Grilled Chicken'] = mid

    # Steak & Shrimp — Mini $2.06, Small $3.55, Large $4.53, Party $9.72
    mid = add_modifier(cursor, gid, 'Steak & Shrimp', default_price=3.55,
                       display_order=len(standard_pizza_toppings) + 2)
    pizza_topping_mods['Steak & Shrimp'] = mid

    # Per-size modifier prices are stored in menu_modifier_prices.
    # We'll wire them up AFTER all items are created (we need size_ids).
    # Store references for later.
    groups['_pizza_topping_mods'] = pizza_topping_mods
    groups['_pizza_std_prices'] = std_prices
    groups['_pizza_special_prices'] = {
        'Catupiry': {
            'Mini 6"': 4.00, 'Small 10"': 4.00, 'Large 16"': 4.00, 'Party 24sq': 4.00,
        },
        'Grilled Chicken': {
            'Mini 6"': 1.26, 'Small 10"': 2.76, 'Large 16"': 3.83, 'Party 24sq': 9.16,
        },
        'Steak & Shrimp': {
            'Mini 6"': 2.06, 'Small 10"': 3.55, 'Large 16"': 4.53, 'Party 24sq': 9.72,
        },
    }

    # ------------------------------------------------------------------
    #  Pizza Sauce  (required_single, 1-1)
    # ------------------------------------------------------------------
    gid = add_modifier_group(cursor, 'Pizza Sauce', 'required_single', 1, 1)
    groups['pizza_sauce'] = gid

    sauces = ['Sweet', 'Traditional', 'Alfredo', 'Buffalo', 'Garlic & Olive Oil',
              'BBQ', 'Pesto']
    for idx, name in enumerate(sauces):
        add_modifier(cursor, gid, name, default_price=0.00, display_order=idx)

    # ------------------------------------------------------------------
    #  Wing Sauce  (required_single, 1-1)
    # ------------------------------------------------------------------
    gid = add_modifier_group(cursor, 'Wing Sauce', 'required_single', 1, 1)
    groups['wing_sauce'] = gid

    wing_sauces = ['Buffalo', 'BBQ', 'Honey BBQ', 'Teriyaki', 'Garlic Parmesan', 'Plain']
    for idx, name in enumerate(wing_sauces):
        add_modifier(cursor, gid, name, default_price=0.00, display_order=idx)

    # ------------------------------------------------------------------
    #  Salad Dressing  (required_single, 1-1)
    # ------------------------------------------------------------------
    gid = add_modifier_group(cursor, 'Salad Dressing', 'required_single', 1, 1)
    groups['salad_dressing'] = gid

    dressings = [
        'Creamy Ranch', 'Blue Cheese', 'Caesar', 'Raspberry Vinaigrette',
        'Orange Vinaigrette', 'Vinegar', 'Creamy Italian', 'Light Italian',
        'Extra Virgin Olive Oil', 'Balsamic Vinaigrette',
        'Signature Greek House',
    ]
    for idx, name in enumerate(dressings):
        add_modifier(cursor, gid, name, default_price=0.00, display_order=idx)

    # ------------------------------------------------------------------
    #  Sub Toppings  (multiple, 0-10)
    # ------------------------------------------------------------------
    gid = add_modifier_group(cursor, 'Sub Toppings', 'multiple', 0, 10)
    groups['sub_toppings'] = gid

    sub_tops = [
        ('Cheese',          0.98),
        ('Sauteed Veggies', 1.45),
        ('3-Way Combo',     1.45),
        ('Bacon',           1.45),
        ('Jalapenos',       0.98),
        ('BBQ Sauce',       0.75),
        ('Marinara',        0.75),
        ('Cold Veggies',    0.98),
    ]
    for idx, (name, price) in enumerate(sub_tops):
        add_modifier(cursor, gid, name, default_price=price, display_order=idx)

    # ------------------------------------------------------------------
    #  Wrap Choice  (required_single, 1-1)
    # ------------------------------------------------------------------
    gid = add_modifier_group(cursor, 'Wrap Choice', 'required_single', 1, 1)
    groups['wrap_choice'] = gid

    wrap_types = ['White Wrap', 'Wheat Wrap', 'Spinach Wrap']
    for idx, name in enumerate(wrap_types):
        add_modifier(cursor, gid, name, default_price=0.00, display_order=idx)

    # ------------------------------------------------------------------
    #  Acai Toppings  (multiple, 0-10)
    # ------------------------------------------------------------------
    gid = add_modifier_group(cursor, 'Acai Toppings', 'multiple', 0, 10)
    groups['acai_toppings'] = gid

    acai_tops = [
        ('Blueberry',       0.98),
        ('Mango',           0.98),
        ('Kiwi',            0.98),
        ('Grapes',          0.98),
        ('Pineapple',       0.98),
        ('Whip Cream',      0.98),
        ('Nutella',         0.98),
        ('Condensed Milk',  0.98),
        ('Powdered Milk',   1.26),
    ]
    for idx, (name, price) in enumerate(acai_tops):
        add_modifier(cursor, gid, name, default_price=price, display_order=idx)

    # ------------------------------------------------------------------
    #  Burger/Dog Toppings  (multiple, 0-10)
    # ------------------------------------------------------------------
    gid = add_modifier_group(cursor, 'Burger/Dog Toppings', 'multiple', 0, 10)
    groups['burger_dog_toppings'] = gid

    burger_tops = [
        ('Cheese',          0.98),
        ('Sauteed Veggies', 1.45),
        ('Bacon',           1.45),
        ('Jalapenos',       0.98),
        ('BBQ Sauce',       0.75),
    ]
    for idx, (name, price) in enumerate(burger_tops):
        add_modifier(cursor, gid, name, default_price=price, display_order=idx)

    # ------------------------------------------------------------------
    #  Salad Toppings  (multiple, 0-10) — with per-size pricing
    # ------------------------------------------------------------------
    gid = add_modifier_group(cursor, 'Salad Toppings', 'multiple', 0, 10)
    groups['salad_toppings'] = gid

    # (name, default_price, {size: price})
    salad_tops = [
        ('Cheese',           1.45, {'Mini': 0.98, 'Regular': 1.45, 'Party': 3.60, 'Event': 6.12}),
        ('Avocado',          2.34, {'Mini': 1.45, 'Regular': 2.34, 'Party': 6.12, 'Event': 9.16}),
        ('Dried Cranberries', 1.45, {'Mini': 0.98, 'Regular': 1.45, 'Party': 3.60, 'Event': 6.12}),
        ('Red Onions',       1.45, {'Mini': 0.98, 'Regular': 1.45, 'Party': 3.60, 'Event': 6.12}),
        ('Bacon',            2.34, {'Mini': 1.45, 'Regular': 2.34, 'Party': 6.12, 'Event': 9.16}),
        ('Extra Dressing',   1.45, {'Mini': 0.98, 'Regular': 1.45, 'Party': 3.60, 'Event': 6.12}),
        ('Beets',            1.45, {'Mini': 0.98, 'Regular': 1.45, 'Party': 3.60, 'Event': 6.12}),
        ('Walnuts',          1.45, {'Mini': 0.98, 'Regular': 1.45, 'Party': 3.60, 'Event': 6.12}),
    ]
    salad_topping_mods = {}
    for idx, (name, default, size_prices) in enumerate(salad_tops):
        mid = add_modifier(cursor, gid, name, default_price=default, display_order=idx)
        salad_topping_mods[name] = (mid, size_prices)

    groups['_salad_topping_mods'] = salad_topping_mods

    # ------------------------------------------------------------------
    #  Roast Beef Toppings  (multiple, 0-5)
    # ------------------------------------------------------------------
    gid = add_modifier_group(cursor, 'Roast Beef Toppings', 'multiple', 0, 5)
    groups['roast_beef_toppings'] = gid

    rb_tops = [
        ('3-Way (BBQ, mayo, cheese)', 1.45),
        ('Cheese',                    0.98),
    ]
    for idx, (name, price) in enumerate(rb_tops):
        add_modifier(cursor, gid, name, default_price=price, display_order=idx)

    cursor.execute("SELECT COUNT(*) FROM menu_modifier_groups")
    group_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM menu_modifiers")
    mod_count = cursor.fetchone()[0]
    print(f"[OK] {group_count} modifier groups seeded ({mod_count} modifiers)")

    return groups


# ═══════════════════════════════════════════════════════════════════════════
#  Per-size modifier prices  (wired up after items + modifiers both exist)
# ═══════════════════════════════════════════════════════════════════════════

def seed_modifier_prices(cursor, mod_groups, pizza_items, custom_pizza_items, salad_items):
    """
    Create menu_modifier_prices rows for modifiers that have per-size pricing.

    Pizza toppings prices vary by pizza size.
    Salad toppings prices vary by salad size.
    """

    # ── Pizza topping per-size prices ──
    pizza_mods = mod_groups['_pizza_topping_mods']
    std_prices = mod_groups['_pizza_std_prices']
    special_prices = mod_groups['_pizza_special_prices']

    # Collect all unique pizza size_ids that have matching size_names
    # from both pizza and custom-pizza items.
    all_pizza_items = pizza_items + custom_pizza_items

    for item_id, size_ids in all_pizza_items:
        for mod_name, mod_id in pizza_mods.items():
            if mod_name in special_prices:
                price_map = special_prices[mod_name]
            else:
                price_map = std_prices

            for size_name, size_id in size_ids.items():
                if size_name in price_map:
                    add_modifier_price(cursor, mod_id, size_id, price_map[size_name])

    # ── Salad topping per-size prices ──
    salad_topping_mods = mod_groups['_salad_topping_mods']

    for item_id, size_ids in salad_items:
        for mod_name, (mod_id, size_price_map) in salad_topping_mods.items():
            for size_name, size_id in size_ids.items():
                if size_name in size_price_map:
                    add_modifier_price(cursor, mod_id, size_id, size_price_map[size_name])

    cursor.execute("SELECT COUNT(*) FROM menu_modifier_prices")
    price_count = cursor.fetchone()[0]
    print(f"[OK] {price_count} per-size modifier prices seeded")


# ═══════════════════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  Firing Up Pizza — Full Menu Seed")
    print("=" * 60)
    print()

    # Ensure both master and org schemas are up to date
    create_master_db()
    create_org_database(1)
    print()

    # Update organization settings in master.db
    update_organization()

    # Connect to the org database
    org_db_path = get_org_db_path(1)
    if not org_db_path:
        print("[ERROR] Organization 1 not found in master.db")
        sys.exit(1)

    conn = sqlite3.connect(org_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Enable WAL mode for better concurrent access
    cursor.execute("PRAGMA journal_mode=WAL")

    # Clear existing menu data for idempotent re-runs
    clear_menu_data(cursor)

    # Seed in dependency order
    seed_business_hours(cursor)
    cat_ids = seed_categories(cursor)
    mod_groups = seed_modifier_groups(cursor)

    # Seed all menu items — this function also assigns modifier groups
    # We need to capture pizza/salad items for per-size modifier pricing
    # So we refactor seed_menu_items to return what we need.
    # Actually, we restructure: seed_menu_items does the linking internally,
    # and we add a post-pass for per-size prices.

    # We need the item+size IDs for per-size modifier prices, so we
    # collect them by running the seeding in a way that returns them.
    pizza_items, custom_pizza_items, salad_items_data = \
        _seed_all_items_and_link(cursor, cat_ids, mod_groups)

    # Per-size modifier prices (pizza toppings + salad toppings)
    seed_modifier_prices(cursor, mod_groups, pizza_items, custom_pizza_items,
                         salad_items_data)

    conn.commit()
    conn.close()

    print()
    print("=" * 60)
    print("  Menu seeded successfully!")
    print("=" * 60)


def _seed_all_items_and_link(cursor, cats, mod_groups):
    """
    Seed every menu item, link modifier groups, and return lists of
    (item_id, size_ids) for pizza and salad items so we can wire up
    per-size modifier prices afterwards.

    Returns:
        (pizza_items, custom_pizza_items, salad_items)
        Each is a list of (item_id, {size_name: size_id}) tuples.
    """

    # ------------------------------------------------------------------
    # Accumulators
    # ------------------------------------------------------------------
    pizza_items = []
    custom_pizza_items = []
    wing_items = []
    salad_items = []
    sub_items = []
    wrap_items = []
    acai_items = []
    burger_dog_items = []
    roast_beef_items = []
    dinner_wing_items = []

    mg = mod_groups
    order_num = 0

    # ══════════════════════════════════════════════════════════════════
    #  PIZZA  (Build Your Own)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['pizza']
    order_num = 0

    order_num += 1
    iid, sids = add_item(cursor, cat, 'Original Tomato Sauce Pizza', {
        'Mini 6"': 8.41, 'Small 10"': 13.55, 'Large 16"': 17.76, 'Party 24sq': 36.45,
    }, is_popular=1, display_order=order_num)
    pizza_items.append((iid, sids))

    order_num += 1
    iid, sids = add_item(cursor, cat, 'Sweet Tomato Sauce Pizza', {
        'Mini 6"': 8.41, 'Small 10"': 13.55, 'Large 16"': 17.76, 'Party 24sq': 36.45,
    }, display_order=order_num)
    pizza_items.append((iid, sids))

    order_num += 1
    iid, sids = add_item(cursor, cat, 'Gluten Free 12" Pizza', {
        'Regular': 14.49,
    }, dietary_tags='gluten-free', display_order=order_num)
    pizza_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  FIRING UP PIZZA CUSTOMS  (23 specialty pizzas)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['custom-pizza']
    order_num = 0

    customs = [
        ('Firing Up Special',           {'Small 10"': 17.99, 'Large 16"': 24.53, 'Party 24sq': 50.47}, 1),
        ('Hawaiian',                    {'Small 10"': 16.03, 'Large 16"': 21.26, 'Party 24sq': 41.96}, 0),
        ('Chicken Kabob',               {'Small 10"': 17.99, 'Large 16"': 24.53, 'Party 24sq': 50.47}, 0),
        ('Veggie Max',                  {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 0),
        ('Carnivore Cravers',           {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 1),
        ('Pollo Primavera',             {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 0),
        ('Aegean',                      {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 0),
        ('Chicken Broccoli Alfredo',    {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 1),
        ('Blazing Buffalo Finger',      {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 0),
        ('BBQ Chicken',                 {'Small 10"': 16.54, 'Large 16"': 21.82, 'Party 24sq': 44.99}, 0),
        ("Theo's Creation",             {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 0),
        ('Brazilian Style',             {'Small 10"': 17.99, 'Large 16"': 24.53, 'Party 24sq': 50.47}, 0),
        ('Shrimp Scampi',              {'Small 10"': 17.99, 'Large 16"': 24.53, 'Party 24sq': 50.47}, 0),
        ('Shrimp Alfredo',             {'Small 10"': 17.99, 'Large 16"': 24.53, 'Party 24sq': 50.47}, 0),
        ('Garden Pesto',                {'Small 10"': 16.54, 'Large 16"': 21.82, 'Party 24sq': 44.99}, 0),
        ('Spinach Fresco',              {'Small 10"': 16.54, 'Large 16"': 21.82, 'Party 24sq': 44.99}, 0),
        ('Philly Cheese Steak',         {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 0),
        ('Honolulu Hawaiian',           {'Small 10"': 16.54, 'Large 16"': 21.82, 'Party 24sq': 44.99}, 0),
        ('Coastal Veggie',              {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 0),
        ('Tropical Blaze',              {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 0),
        ('Melanzana Fritta',            {'Small 10"': 16.54, 'Large 16"': 21.82, 'Party 24sq': 44.99}, 0),
        ('Stacked Nacho',               {'Small 10"': 17.29, 'Large 16"': 22.99, 'Party 24sq': 47.43}, 0),
        ("Sideir's Pizza",              {'Small 10"': 17.99, 'Large 16"': 24.53, 'Party 24sq': 50.47}, 0),
    ]
    for name, sizes, popular in customs:
        order_num += 1
        iid, sids = add_item(cursor, cat, name, sizes, is_popular=popular,
                             display_order=order_num)
        custom_pizza_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  CALZONES  (14 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['calzones']
    order_num = 0

    calzones = [
        ('Italian Cold-Cut',    {'Junior': 15.75, 'Small': 21.96, 'Large': 29.53, 'Party': 60.00}),
        ('Steak and Cheese',    {'Junior': 15.75, 'Small': 21.96, 'Large': 29.53, 'Party': 60.00}),
        ('Chicken Parmesan',    {'Junior': 15.75, 'Small': 21.96, 'Large': 29.53, 'Party': 60.00}),
        ('Chicken Kabob',       {'Junior': 16.78, 'Small': 22.99, 'Large': 30.79, 'Party': 61.96}),
        ('Spinach & Feta',      {'Junior': 15.75, 'Small': 21.96, 'Large': 29.53, 'Party': 60.00}),
        ('Vegetable',           {'Junior': 15.75, 'Small': 21.96, 'Large': 29.53, 'Party': 60.00}),
        ('Ham & Cheese',        {'Junior': 14.91, 'Small': 20.98, 'Large': 28.69, 'Party': 58.50}),
        ('Sausage & Cheese',    {'Junior': 14.91, 'Small': 20.98, 'Large': 28.69, 'Party': 58.50}),
        ('Broccoli & Cheese',   {'Junior': 14.91, 'Small': 20.98, 'Large': 28.69, 'Party': 58.50}),
        ('Steak Bomb',          {'Junior': 16.78, 'Small': 22.99, 'Large': 30.79, 'Party': 61.96}),
        ('Chicken & Broccoli',  {'Junior': 15.75, 'Small': 21.96, 'Large': 29.53, 'Party': 60.00}),
        ('Buffalo Finger',      {'Junior': 15.75, 'Small': 21.96, 'Large': 29.53, 'Party': 60.00}),
        ('Pepperoni & Cheese',  {'Junior': 15.75, 'Small': 21.96, 'Large': 29.53, 'Party': 60.00}),
        ('Steak Tip',           {'Junior': 18.13, 'Small': 26.54, 'Large': 35.98, 'Party': 66.45}),
    ]
    for name, sizes in calzones:
        order_num += 1
        add_item(cursor, cat, name + ' Calzone', sizes, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  DINNER PLATES  (10 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['dinner-plates']
    order_num = 0

    dinners = [
        ('Chicken Wings (6 wings)',     17.99),
        ('Chicken Fingers (6 strips)',  17.99),
        ('Chicken Kabob',               17.99),
        ('Roast Beef',                  18.46),
        ('Pastrami',                    18.46),
        ('1/2 lb Cheeseburger',        17.99),
        ('Steak Tips',                  20.79),
        ('Honey BBQ Steak Tips',       20.79),
        ('Fried Haddock',              20.79),
        ('Baked Haddock',              23.36),
    ]
    for name, price in dinners:
        order_num += 1
        iid, sids = add_item(cursor, cat, name + ' Dinner Plate', {'Regular': price},
                             display_order=order_num,
                             description='Served with french fries and coleslaw')
        if 'Wings' in name or 'Fingers' in name:
            dinner_wing_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  PASTA  (14 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['pasta']
    order_num = 0

    pastas = [
        ('Pasta with Marinara',        {'Individual': 9.16, 'Party': 33.97, 'Event': 48.97}, 0),
        ('Chicken Broccoli Ziti',      {'Individual': 13.83, 'Party': 52.99, 'Event': 68.46}, 1),
        ('Baked Ziti',                 {'Individual': 11.40, 'Party': 41.12, 'Event': 52.62}, 0),
        ('Baked Lasagna',              {'Individual': 11.40, 'Party': 41.12, 'Event': 52.62}, 0),
        ('Baked Veggie Lasagna',       {'Party': 43.50, 'Event': 56.73}, 0),
        ('Baked Meat Lasagna',         {'Party': 45.56, 'Event': 58.60}, 0),
        ('Pasta with Meat Sauce',      {'Individual': 11.40, 'Party': 41.12, 'Event': 52.62}, 0),
        ('Chicken Parmesan',           {'Individual': 13.83, 'Party': 52.99, 'Event': 68.46}, 0),
        ('Eggplant Parmesan',          {'Individual': 13.83, 'Party': 52.99, 'Event': 68.46}, 0),
        ('Meatball Parmesan',          {'Individual': 13.83, 'Party': 52.99, 'Event': 68.46}, 0),
        ('Sausage Parmesan',           {'Individual': 13.83, 'Party': 52.99, 'Event': 68.46}, 0),
        ('Shrimp Scampi',             {'Individual': 15.37, 'Party': 55.00, 'Event': 71.50}, 0),
        ('Shrimp Broccoli Alfredo',    {'Individual': 15.37, 'Party': 55.00, 'Event': 71.50}, 0),
        ('Steak Broccoli Alfredo',     {'Individual': 15.37}, 0),
    ]
    for name, sizes, popular in pastas:
        order_num += 1
        add_item(cursor, cat, name, sizes, is_popular=popular, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  RICE PLATES  (6 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['rice-plates']
    order_num = 0

    rice_plates = [
        ('Chicken Kabob Rice Plate',            13.97),
        ('Teriyaki Chicken Kabob Rice Plate',   13.97),
        ('Steak Tips Rice Plate',               17.99),
        ('Honey BBQ Steak Tips Rice Plate',     17.99),
        ('Steak Tips & Chicken Kabob Combo',    18.46),
        ('Chicken Wings Rice Plate',            13.97),
    ]
    for name, price in rice_plates:
        order_num += 1
        add_item(cursor, cat, name, {'Regular': price}, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  BURRITO & FAJITA BOWLS  (8 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['bowls']
    order_num = 0

    bowls = [
        ('Grilled Chicken Burrito Bowl',        13.97),
        ('Steak Tip Burrito Bowl',              17.76),
        ('Seasoned Ground Beef Burrito Bowl',   13.97),
        ('Honey BBQ Steak Tip Burrito Bowl',    17.76),
        ('Grilled Chicken Fajita Bowl',         13.97),
        ('Steak Tip Fajita Bowl',               17.76),
        ('Seasoned Ground Beef Fajita Bowl',    13.97),
        ('Honey BBQ Steak Tip Fajita Bowl',     17.76),
    ]
    for name, price in bowls:
        order_num += 1
        add_item(cursor, cat, name, {'Regular': price}, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  APPETIZERS — Wings & Fingers
    # ══════════════════════════════════════════════════════════════════
    cat = cats['app-wings']
    order_num = 0

    order_num += 1
    iid, sids = add_item(cursor, cat, 'Chicken Wings', {
        '6pc': 9.91, '12pc': 18.97, '18pc': 26.96, '35pc': 46.96, '70pc': 79.95,
    }, is_popular=1, display_order=order_num)
    wing_items.append((iid, sids))

    order_num += 1
    iid, sids = add_item(cursor, cat, 'Boneless Wing Dings', {
        '6pc': 8.41, '12pc': 14.49, '18pc': 24.30, '35pc': 42.24,
    }, display_order=order_num)
    wing_items.append((iid, sids))

    order_num += 1
    iid, sids = add_item(cursor, cat, 'Chicken Fingers', {
        '6pc': 9.49, '12pc': 15.47, '18pc': 21.96, '35pc': 39.95, '70pc': 74.91,
    }, display_order=order_num)
    wing_items.append((iid, sids))

    wing_items.extend(dinner_wing_items)

    # ══════════════════════════════════════════════════════════════════
    #  APPETIZERS — Fried Items
    # ══════════════════════════════════════════════════════════════════
    cat = cats['app-fried']
    order_num = 0

    fried = [
        ('Mozzarella Sticks',     {'6pc': 8.97, '12pc': 14.95, '18pc': 19.95, '35pc': 37.10}),
        ('Jalapeno Poppers',      {'6pc': 8.97, '12pc': 14.95, '18pc': 19.95, '35pc': 37.10}),
        ('Broccoli Cheese Bites', {'6pc': 8.97, '12pc': 14.95, '18pc': 19.95, '35pc': 37.10}),
        ('Breaded Portobellos',   {'6pc': 8.97, '12pc': 14.95, '18pc': 19.95, '35pc': 37.10}),
    ]
    for name, sizes in fried:
        order_num += 1
        add_item(cursor, cat, name, sizes, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  APPETIZERS — Fries & Sides
    # ══════════════════════════════════════════════════════════════════
    cat = cats['app-fries']
    order_num = 0

    fries = [
        ('Onion Rings',       {'Small': 6.45, 'Medium': 7.48, 'Large': 9.49, 'Party': 21.45}, 0),
        ('French Fries',      {'Small': 5.51, 'Medium': 6.54, 'Large': 8.50, 'Party': 19.95}, 1),
        ('Spicy Curly Fries', {'Small': 5.51, 'Medium': 6.54, 'Large': 8.50, 'Party': 19.95}, 0),
        ('Steak Fries',       {'Small': 5.51, 'Medium': 6.54, 'Large': 8.50, 'Party': 19.95}, 0),
    ]
    for name, sizes, popular in fries:
        order_num += 1
        add_item(cursor, cat, name, sizes, is_popular=popular, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  APPETIZERS — Specialty
    # ══════════════════════════════════════════════════════════════════
    cat = cats['app-specialty']
    order_num = 0

    specialties = [
        ('Cheesy Garlic Stix',  10.98),
        ('Crazy Cinnamon Stix', 10.98),
        ('Pizza Roll',          5.51),
        ('Spinach Roll',        5.51),
    ]
    for name, price in specialties:
        order_num += 1
        add_item(cursor, cat, name, {'Regular': price}, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  SALADS  (23 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['salads']
    order_num = 0

    salads = [
        ('Garden Salad',                       {'Mini': 6.96, 'Regular': 9.49, 'Party': 40.00, 'Event': 51.03}, 0),
        ('Greek Salad',                        {'Mini': 7.99, 'Regular': 10.51, 'Party': 45.98, 'Event': 55.00}, 0),
        ('Ultimate Protein Salad',             {'Mini': 11.54, 'Regular': 13.50, 'Party': 55.00, 'Event': 75.00}, 0),
        ('Beet Spring Salad',                  {'Mini': 7.99, 'Regular': 10.51}, 0),
        ('Chef Salad',                         {'Mini': 10.98, 'Regular': 13.50, 'Party': 50.00, 'Event': 70.00}, 0),
        ('Antipasto Salad',                    {'Mini': 10.98, 'Regular': 13.50, 'Party': 50.00, 'Event': 70.00}, 0),
        ('Tuna Salad',                         {'Mini': 10.98, 'Regular': 13.50}, 0),
        ('Seafood Salad',                      {'Mini': 10.98, 'Regular': 13.50}, 0),
        ('Chicken Salad',                      {'Mini': 10.98, 'Regular': 13.50}, 0),
        ('Stacked Nacho Salad',                {'Mini': 10.98, 'Regular': 13.50}, 0),
        ('Tropical Salad',                     {'Mini': 8.50, 'Regular': 11.45, 'Party': 47.99, 'Event': 56.96}, 0),
        ('Honey BBQ Steak Tip Salad',          {'Mini': 14.49, 'Regular': 17.48}, 0),
        ('Steak Tip Salad',                    {'Mini': 14.49, 'Regular': 17.48}, 0),
        ('Steak Tip & Chicken Kabob Salad',    {'Mini': 15.00, 'Regular': 17.99}, 0),
        ('Chicken Kabob Salad',                {'Mini': 11.96, 'Regular': 13.97, 'Party': 60.00, 'Event': 80.00}, 1),
        ('Teriyaki Chicken Kabob Salad',       {'Mini': 11.96, 'Regular': 13.97, 'Party': 60.00, 'Event': 80.00}, 0),
        ('Chicken Caesar Salad',               {'Mini': 11.96, 'Regular': 13.97, 'Party': 60.00, 'Event': 80.00}, 0),
        ('Caesar Salad',                       {'Mini': 7.99, 'Regular': 10.51, 'Party': 45.98, 'Event': 55.00}, 0),
        ('Chicken Finger Salad',               {'Mini': 11.96, 'Regular': 13.97}, 0),
        ('Land & Sea Salad',                   {'Mini': 14.95, 'Regular': 17.99}, 0),
        ('Grilled Shrimp Salad',               {'Mini': 14.95, 'Regular': 17.99}, 0),
        ('Souvlaki Salad',                     {'Mini': 11.96, 'Regular': 13.97}, 0),
        ('Roast Beef Salad',                   {'Mini': 11.96, 'Regular': 13.97}, 0),
    ]
    for name, sizes, popular in salads:
        order_num += 1
        iid, sids = add_item(cursor, cat, name, sizes, is_popular=popular,
                             display_order=order_num)
        salad_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  BEVERAGES & DESSERTS  (6 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['beverages-desserts']
    order_num = 0

    bev_desserts = [
        ('Can Soda',           2.43),
        ('20oz Soda',          2.99),
        ('2-Liter Soda',       3.97),
        ('Whoopie Pies',       2.52),
        ('Assorted Brownies',  2.52),
        ('Assorted Cookies',   2.52),
    ]
    for name, price in bev_desserts:
        order_num += 1
        add_item(cursor, cat, name, {'Regular': price}, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  ACAI  (2 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['acai']
    order_num = 0

    order_num += 1
    iid, sids = add_item(cursor, cat, 'Acai Bowl', {'Regular': 12.66},
                         display_order=order_num)
    acai_items.append((iid, sids))

    order_num += 1
    iid, sids = add_item(cursor, cat, 'Acai Cup', {'Regular': 9.16},
                         display_order=order_num)
    acai_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  CHOCO-ZONE  (5 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['choco-zone']
    order_num = 0

    chocos = [
        ('Milky Way',       10.00),
        ('Smores',          10.98),
        ('Salted Caramel',  10.00),
        ('Chocolate Chip',  10.00),
        ('Fruity',          10.00),
    ]
    for name, price in chocos:
        order_num += 1
        add_item(cursor, cat, name, {'Regular': price}, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  WRAPS  (16 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['wraps']
    order_num = 0

    wraps = [
        ('Chicken Caesar Wrap',          11.68),
        ('Blazing Buffalo Wrap',         12.38),
        ('Turkey Club Wrap',             12.38),
        ('Steak Tip Kabob Wrap',         15.98),
        ('CAVO BLT Wrap',               12.38),
        ('Sizzling Chicken Ranch Wrap',  12.38),
        ('Chicken Burrito Wrap',         12.38),
        ('Steak Tip Burrito Wrap',       15.98),
        ('Ground Beef Burrito Wrap',     12.38),
        ('Chicken Fajita Wrap',          12.38),
        ('Steak Tip Fajita Wrap',        15.98),
        ('Ground Beef Fajita Wrap',      12.38),
        ('Honey BBQ Chicken Finger',     12.38),
        ('Chicken Finger 3 Way',         12.38),
        ('BLT Wrap',                     12.38),
        ('Caesar Wrap',                  8.41),
    ]
    for name, price in wraps:
        order_num += 1
        iid, sids = add_item(cursor, cat, name, {'Regular': price},
                             display_order=order_num)
        wrap_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  SANDWICHES & CLUBS
    # ══════════════════════════════════════════════════════════════════
    cat = cats['sandwiches']
    order_num = 0

    hot_sandwiches = [
        ('Gyro',                         12.71),
        ('Crispy Chicken BLT',           12.10),
        ('Grilled Chicken BLT',          12.10),
        ('Fired Up Chicken',             12.10),
        ('Grilled Chicken Breast',       10.56),
        ('Pastrami Sandwich',            12.10),
        ('Fish Sandwich',                12.71),
        ('BLT Sandwich',                 9.16),
        ('Grilled Cheese',               6.12),
        ('Grilled Cheese with Ham',      7.71),
        ('Grilled Cheese with Bacon',    7.71),
        ('Grilled Cheese with Tomatoes', 7.71),
        ('Tuna Salad Sandwich',          10.56),
        ('Chicken Salad Sandwich',       10.56),
        ('Seafood Salad Sandwich',       10.56),
        ('Egg Salad Sandwich',           10.56),
        ('Roast Turkey Breast',          9.77),
        ('Imported Ham & Cheese',        10.00),
    ]
    for name, price in hot_sandwiches:
        order_num += 1
        add_item(cursor, cat, name, {'Regular': price}, display_order=order_num)

    clubs = [
        ('Imported Ham & Cheese Club',     15.00),
        ('Roast Turkey Club',              15.00),
        ('Grilled Chicken Breast Club',    15.00),
        ('Classic BLT Club',               15.00),
        ('Tuna Salad Club',                15.00),
        ('Cheeseburger Club',              15.51),
        ('White-Meat Chicken Salad Club',  15.00),
        ('Roast Beef Club',                15.51),
    ]
    for name, price in clubs:
        order_num += 1
        add_item(cursor, cat, name, {'Regular': price}, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  ROAST BEEF  (5 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['roast-beef']
    order_num = 0

    roast_beefs = [
        ('Junior Roast Beef',   8.97),
        ('Regular Roast Beef',  9.67),
        ('Super Beef',         10.70),
        ('Roast Beef Sub 8"',  11.26),
        ('Roast Beef Sub 10"', 12.38),
    ]
    for name, price in roast_beefs:
        order_num += 1
        iid, sids = add_item(cursor, cat, name, {'Regular': price},
                             display_order=order_num)
        roast_beef_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  HOT SUBS  (22 items, 8"/10" sizes)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['hot-subs']
    order_num = 0

    hot_subs = [
        ('Steak & Cheese',             {'8"': 11.26, '10"': 12.38}),
        ('Steak Bomb',                 {'8"': 12.38, '10"': 13.60}),
        ('Steak Tip Sub',              {'8"': 13.97, '10"': 15.98}),
        ('Honey BBQ Steak Tip Sub',    {'8"': 13.97, '10"': 15.98}),
        ('Italian Sausage',            {'8"': 11.26, '10"': 12.38}),
        ('Sausage & Meatball Combo',   {'8"': 11.68, '10"': 12.85}),
        ('Meatball Parmesan Sub',      {'8"': 11.68, '10"': 12.85}),
        ('Chicken Parmesan Sub',       {'8"': 11.68, '10"': 12.85}),
        ('Eggplant Parmesan Sub',      {'8"': 11.68, '10"': 12.85}),
        ('Souvlaki Sub',               {'8"': 11.26, '10"': 12.38}),
        ('Linguica Sub',               {'8"': 11.26, '10"': 12.38}),
        ('Linguica Bomb',              {'8"': 12.38, '10"': 13.60}),
        ('Pastrami Sub',               {'8"': 11.26, '10"': 12.38}),
        ('Pastrami Bomb',              {'8"': 12.38, '10"': 13.60}),
        ('BLT Sub',                    {'8"': 11.68, '10"': 12.85}),
        ('Cheeseburger Sub',           {'8"': 11.26, '10"': 12.38}),
        ('Chicken Kabob Sub',          {'8"': 11.68, '10"': 13.60}),
        ('Chicken Teriyaki Kabob Sub', {'8"': 11.68, '10"': 12.85}),
        ('Chicken Kabob Bomb',         {'8"': 12.38, '10"': 13.60}),
        ('Chicken Finger Sub',         {'8"': 11.26, '10"': 12.38}),
        ('Buffalo Finger Sub',         {'8"': 11.26, '10"': 12.38}),
        ('Hot Vegetarian Sub',         {'8"': 10.14, '10"': 11.26}),
    ]
    for name, sizes in hot_subs:
        order_num += 1
        iid, sids = add_item(cursor, cat, name, sizes, display_order=order_num)
        sub_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  COLD SUBS  (10 items, 8"/10" sizes)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['cold-subs']
    order_num = 0

    cold_subs = [
        ('Italian Cold-Cuts',     {'8"': 11.26, '10"': 12.38}),
        ('Genoa Salami',          {'8"': 10.14, '10"': 11.26}),
        ('Imported Ham & Cheese', {'8"': 10.14, '10"': 11.26}),
        ('American Cold-Cuts',    {'8"': 10.14, '10"': 11.26}),
        ('Roast Turkey Breast',   {'8"': 10.14, '10"': 11.26}),
        ('Chicken Salad',         {'8"': 11.26, '10"': 12.38}),
        ('Tuna Salad',            {'8"': 11.26, '10"': 12.38}),
        ('Seafood Salad',         {'8"': 11.26, '10"': 12.38}),
        ('Egg Salad',             {'8"': 11.26, '10"': 12.38}),
        ('Veggie Sub',            {'8"': 9.44, '10"': 10.61}),
    ]
    for name, sizes in cold_subs:
        order_num += 1
        iid, sids = add_item(cursor, cat, name, sizes, display_order=order_num)
        sub_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  OMELETTE SUBS  (11 items, 8"/10" sizes)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['omelette-subs']
    order_num = 0

    omelette_names = [
        'Egg & Cheese',
        'Ham, Egg & Cheese',
        'Bacon, Egg & Cheese',
        'Sausage, Egg & Cheese',
        'Linguica, Egg & Cheese',
        'Steak, Egg & Cheese',
        'Pepper, Egg & Cheese',
        'Potato, Egg & Cheese',
        'Western Omelette',
        'Mediterranean Omelette',
        'Veggie Omelette',
    ]
    omelette_sizes = {'8"': 11.26, '10"': 12.38}
    for name in omelette_names:
        order_num += 1
        iid, sids = add_item(cursor, cat, name, omelette_sizes,
                             display_order=order_num)
        sub_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  BURGERS & DOGS  (3 items)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['burgers-dogs']
    order_num = 0

    burgers = [
        ('Cheeseburger (1/2 lb)', 9.67),
        ('Hamburger (1/2 lb)',    8.97),
        ('Hot Dog',               6.54),
    ]
    for name, price in burgers:
        order_num += 1
        iid, sids = add_item(cursor, cat, name, {'Regular': price},
                             display_order=order_num)
        burger_dog_items.append((iid, sids))

    # ══════════════════════════════════════════════════════════════════
    #  KIDS MENU  (8 items, all $11.87)
    # ══════════════════════════════════════════════════════════════════
    cat = cats['kids-menu']
    order_num = 0

    kids = [
        '4 Mozzarella Sticks & Fries',
        '3 Chicken Fingers & Fries',
        '6 Boneless Wings & Fries',
        '3 Chicken Wings & Fries',
        'Grilled Cheese & Fries',
        'Cheeseburger & Fries',
        'Hot Dog & Fries',
        '6" Mini Pizza & Fries',
    ]
    for name in kids:
        order_num += 1
        add_item(cursor, cat, name, {'Regular': 11.87}, display_order=order_num)

    # ══════════════════════════════════════════════════════════════════
    #  MODIFIER GROUP ASSIGNMENTS
    # ══════════════════════════════════════════════════════════════════

    # Pizza Toppings + Pizza Sauce -> Build Your Own Pizzas
    for item_id, size_ids in pizza_items:
        link_item_modifier_group(cursor, item_id, mg['pizza_toppings'], display_order=1)
        link_item_modifier_group(cursor, item_id, mg['pizza_sauce'], display_order=2)

    # Pizza Toppings -> Firing Up Customs (extra toppings only, sauce is built-in)
    for item_id, size_ids in custom_pizza_items:
        link_item_modifier_group(cursor, item_id, mg['pizza_toppings'], display_order=1)

    # Wing Sauce -> wing/finger items
    for item_id, size_ids in wing_items:
        link_item_modifier_group(cursor, item_id, mg['wing_sauce'], display_order=1)

    # Salad Dressing + Salad Toppings -> all salads
    for item_id, size_ids in salad_items:
        link_item_modifier_group(cursor, item_id, mg['salad_dressing'], display_order=1)
        link_item_modifier_group(cursor, item_id, mg['salad_toppings'], display_order=2)

    # Sub Toppings -> all subs (hot + cold + omelette)
    for item_id, size_ids in sub_items:
        link_item_modifier_group(cursor, item_id, mg['sub_toppings'], display_order=1)

    # Wrap Choice -> all wraps
    for item_id, size_ids in wrap_items:
        link_item_modifier_group(cursor, item_id, mg['wrap_choice'], display_order=1)

    # Acai Toppings -> acai items
    for item_id, size_ids in acai_items:
        link_item_modifier_group(cursor, item_id, mg['acai_toppings'], display_order=1)

    # Burger/Dog Toppings -> burgers & dogs
    for item_id, size_ids in burger_dog_items:
        link_item_modifier_group(cursor, item_id, mg['burger_dog_toppings'], display_order=1)

    # Roast Beef Toppings -> roast beef items
    for item_id, size_ids in roast_beef_items:
        link_item_modifier_group(cursor, item_id, mg['roast_beef_toppings'], display_order=1)

    # Print summary
    cursor.execute("SELECT COUNT(*) FROM menu_items")
    item_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM menu_item_sizes")
    size_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM menu_item_modifier_groups")
    link_count = cursor.fetchone()[0]
    print(f"[OK] {item_count} menu items seeded ({size_count} size variants, {link_count} modifier links)")

    return pizza_items, custom_pizza_items, salad_items


# ═══════════════════════════════════════════════════════════════════════════
#  Entry
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    main()
