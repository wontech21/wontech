-- Firing Up Food Production Inventory Database Schema
-- Created: 2026-01-10

-- Raw ingredients and materials table
-- SUPPORTS INGREDIENT CLUSTERING: Multiple brands/suppliers for same ingredient_name
CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_code TEXT UNIQUE NOT NULL, -- Unique per brand/supplier combo
    ingredient_name TEXT NOT NULL, -- Cluster name (e.g., "Ground Beef 80/20")
    brand TEXT, -- Brand name (e.g., "Premium Angus")
    category TEXT NOT NULL, -- 'Produce', 'Dairy', 'Meat', 'Dry Goods', 'Spices', 'Packaging', etc.
    unit_of_measure TEXT NOT NULL, -- 'lbs', 'oz', 'gallons', 'units', 'cases', etc.
    quantity_on_hand REAL NOT NULL DEFAULT 0,
    unit_cost REAL NOT NULL, -- Cost per unit
    supplier_name TEXT,
    supplier_contact TEXT,
    reorder_level REAL DEFAULT 0,
    reorder_quantity REAL,
    storage_location TEXT,
    expiration_date TEXT,
    lot_number TEXT,
    date_received TEXT,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Finished products (what you sell)
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code TEXT UNIQUE NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit_of_measure TEXT NOT NULL, -- 'each', 'dozen', 'lbs', etc.
    quantity_on_hand REAL NOT NULL DEFAULT 0,
    selling_price REAL NOT NULL,
    shelf_life_days INTEGER,
    storage_requirements TEXT,
    date_added TEXT DEFAULT CURRENT_TIMESTAMP,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Recipes/Formulas - defines what goes into each product
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,
    quantity_needed REAL NOT NULL, -- Amount of ingredient per batch/unit of product
    unit_of_measure TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
);

-- Production batches - tracking when products are made
CREATE TABLE IF NOT EXISTS production_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    batch_size REAL NOT NULL, -- How many units produced
    production_date TEXT DEFAULT CURRENT_TIMESTAMP,
    expiration_date TEXT,
    batch_notes TEXT,
    produced_by TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Ingredient transactions (purchases, usage, waste, adjustments)
CREATE TABLE IF NOT EXISTS ingredient_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL,
    transaction_type TEXT NOT NULL, -- 'PURCHASE', 'USAGE', 'WASTE', 'ADJUSTMENT'
    quantity_change REAL NOT NULL,
    unit_cost REAL,
    transaction_date TEXT DEFAULT CURRENT_TIMESTAMP,
    related_batch_id INTEGER, -- Links to production_batches if used in production
    notes TEXT,
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id),
    FOREIGN KEY (related_batch_id) REFERENCES production_batches(id)
);

-- Product transactions (sales, production additions, waste)
CREATE TABLE IF NOT EXISTS product_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    transaction_type TEXT NOT NULL, -- 'SALE', 'PRODUCTION', 'WASTE', 'ADJUSTMENT'
    quantity_change REAL NOT NULL,
    transaction_date TEXT DEFAULT CURRENT_TIMESTAMP,
    related_batch_id INTEGER,
    notes TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (related_batch_id) REFERENCES production_batches(id)
);

-- Suppliers table
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT UNIQUE NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    payment_terms TEXT,
    notes TEXT
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_ingredient_code ON ingredients(ingredient_code);
CREATE INDEX IF NOT EXISTS idx_ingredient_category ON ingredients(category);
CREATE INDEX IF NOT EXISTS idx_product_code ON products(product_code);
CREATE INDEX IF NOT EXISTS idx_recipe_product ON recipes(product_id);
CREATE INDEX IF NOT EXISTS idx_recipe_ingredient ON recipes(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_batch_product ON production_batches(product_id);

-- Trigger to update ingredients last_updated timestamp
CREATE TRIGGER IF NOT EXISTS update_ingredient_timestamp
AFTER UPDATE ON ingredients
BEGIN
    UPDATE ingredients SET last_updated = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Trigger to update products last_updated timestamp
CREATE TRIGGER IF NOT EXISTS update_product_timestamp
AFTER UPDATE ON products
BEGIN
    UPDATE products SET last_updated = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- View: Current ingredient inventory with total value
CREATE VIEW IF NOT EXISTS ingredient_inventory_value AS
SELECT
    ingredient_code,
    ingredient_name,
    category,
    quantity_on_hand,
    unit_of_measure,
    unit_cost,
    (quantity_on_hand * unit_cost) as total_value,
    supplier_name,
    reorder_level
FROM ingredients
ORDER BY category, ingredient_name;

-- View: Low stock ingredients
CREATE VIEW IF NOT EXISTS low_stock_ingredients AS
SELECT
    ingredient_code,
    ingredient_name,
    quantity_on_hand,
    unit_of_measure,
    reorder_level,
    reorder_quantity,
    supplier_name
FROM ingredients
WHERE quantity_on_hand <= reorder_level
ORDER BY category, ingredient_name;

-- View: Recipe cost calculation
CREATE VIEW IF NOT EXISTS recipe_costs AS
SELECT
    p.product_code,
    p.product_name,
    i.ingredient_name,
    r.quantity_needed,
    r.unit_of_measure,
    i.unit_cost,
    (r.quantity_needed * i.unit_cost) as ingredient_cost
FROM recipes r
JOIN products p ON r.product_id = p.id
JOIN ingredients i ON r.ingredient_id = i.id
ORDER BY p.product_name, i.ingredient_name;
