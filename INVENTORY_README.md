# Firing Up Food Production Inventory Database

SQLite database for managing food production inventory - tracking ingredients, finished products, recipes, and production batches.

## Database Files

- `inventory.db` - Main SQLite database file
- `inventory_schema.sql` - Database schema/structure
- `sample_data.sql` - Sample ingredient, product, and recipe data

## Database Structure

### Core Tables

**ingredients** - Raw materials and supplies purchased
- Ingredient details: code, name, category, unit of measure
- Inventory: quantity on hand, unit cost, storage location
- Supplier info: supplier name, contact
- Reordering: reorder level, reorder quantity
- Tracking: expiration dates, lot numbers, date received

**products** - Finished items you sell
- Product details: code, name, category, selling price
- Inventory: quantity on hand
- Food safety: shelf life, storage requirements

**recipes** - Formulas showing what ingredients go into each product
- Links products to ingredients
- Specifies quantity needed per batch/unit

**production_batches** - Track production runs
- When products were made
- Batch size, expiration dates, who produced it

**ingredient_transactions** - Purchase, usage, waste tracking for ingredients

**product_transactions** - Sales, production, waste tracking for products

**suppliers** - Supplier contact and payment information

### Built-in Views

**ingredient_inventory_value** - Shows total value of ingredient inventory
**low_stock_ingredients** - Shows ingredients at or below reorder level
**recipe_costs** - Calculates ingredient costs for each product

## Common Queries

### View all ingredients
```sql
sqlite3 inventory.db "SELECT ingredient_code, ingredient_name, category,
quantity_on_hand, unit_of_measure, unit_cost, storage_location
FROM ingredients ORDER BY category, ingredient_name;"
```

### Check ingredient inventory value
```sql
sqlite3 inventory.db "SELECT * FROM ingredient_inventory_value;"
```

### Check low stock ingredients
```sql
sqlite3 inventory.db "SELECT * FROM low_stock_ingredients;"
```

### View recipe for a product
```sql
sqlite3 inventory.db "SELECT p.product_name, i.ingredient_name,
r.quantity_needed, r.unit_of_measure, r.notes
FROM recipes r
JOIN products p ON r.product_id = p.id
JOIN ingredients i ON r.ingredient_id = i.id
WHERE p.product_code = 'PRD-TAC-001';"
```

### Calculate total cost of a product
```sql
sqlite3 inventory.db "SELECT p.product_name,
SUM(r.quantity_needed * i.unit_cost) as total_ingredient_cost,
p.selling_price,
(p.selling_price - SUM(r.quantity_needed * i.unit_cost)) as gross_profit
FROM recipes r
JOIN products p ON r.product_id = p.id
JOIN ingredients i ON r.ingredient_id = i.id
WHERE p.product_code = 'PRD-TAC-001'
GROUP BY p.product_name, p.selling_price;"
```

### View all recipe costs
```sql
sqlite3 inventory.db "SELECT * FROM recipe_costs;"
```

### Add new ingredient
```sql
sqlite3 inventory.db "INSERT INTO ingredients
(ingredient_code, ingredient_name, category, unit_of_measure,
quantity_on_hand, unit_cost, supplier_name, reorder_level, storage_location)
VALUES ('ING-NEW-001', 'Ingredient Name', 'Category', 'lbs',
50, 2.99, 'Supplier Name', 20, 'Storage Location');"
```

### Record ingredient purchase
```sql
sqlite3 inventory.db "
UPDATE ingredients SET quantity_on_hand = quantity_on_hand + 50
WHERE ingredient_code = 'ING-TOM-001';

INSERT INTO ingredient_transactions
(ingredient_id, transaction_type, quantity_change, unit_cost, notes)
SELECT id, 'PURCHASE', 50, 2.50, 'Weekly delivery'
FROM ingredients WHERE ingredient_code = 'ING-TOM-001';"
```

### Record ingredient usage in production
```sql
sqlite3 inventory.db "
UPDATE ingredients SET quantity_on_hand = quantity_on_hand - 10
WHERE ingredient_code = 'ING-BEF-001';

INSERT INTO ingredient_transactions
(ingredient_id, transaction_type, quantity_change, notes)
SELECT id, 'USAGE', -10, 'Used in taco production'
FROM ingredients WHERE ingredient_code = 'ING-BEF-001';"
```

### Add a new product
```sql
sqlite3 inventory.db "INSERT INTO products
(product_code, product_name, category, unit_of_measure,
quantity_on_hand, selling_price, shelf_life_days, storage_requirements)
VALUES ('PRD-NEW-001', 'Product Name', 'Category', 'each',
0, 14.99, 2, 'Refrigerate 41°F or below');"
```

### Create a recipe for a product
```sql
sqlite3 inventory.db "
-- Get the product_id and ingredient_id first
SELECT id FROM products WHERE product_code = 'PRD-TAC-001';
SELECT id FROM ingredients WHERE ingredient_code = 'ING-TOM-001';

-- Then insert recipe entry
INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure, notes)
VALUES (1, 1, 0.25, 'lbs', 'Diced tomatoes');"
```

### Record a production batch
```sql
sqlite3 inventory.db "
-- Record the production batch
INSERT INTO production_batches (product_id, batch_size, production_date, batch_notes)
SELECT id, 20, CURRENT_TIMESTAMP, 'Morning batch'
FROM products WHERE product_code = 'PRD-TAC-001';

-- Update product inventory
UPDATE products SET quantity_on_hand = quantity_on_hand + 20
WHERE product_code = 'PRD-TAC-001';

-- Record product transaction
INSERT INTO product_transactions (product_id, transaction_type, quantity_change, notes)
SELECT id, 'PRODUCTION', 20, 'Morning batch - 20 units produced'
FROM products WHERE product_code = 'PRD-TAC-001';"
```

### Record a product sale
```sql
sqlite3 inventory.db "
UPDATE products SET quantity_on_hand = quantity_on_hand - 1
WHERE product_code = 'PRD-BUR-001';

INSERT INTO product_transactions (product_id, transaction_type, quantity_change, notes)
SELECT id, 'SALE', -1, 'Customer order'
FROM products WHERE product_code = 'PRD-BUR-001';"
```

### View transaction history for an ingredient
```sql
sqlite3 inventory.db "SELECT i.ingredient_name, t.transaction_type,
t.quantity_change, t.transaction_date, t.notes
FROM ingredient_transactions t
JOIN ingredients i ON t.ingredient_id = i.id
WHERE i.ingredient_code = 'ING-TOM-001'
ORDER BY t.transaction_date DESC;"
```

### Calculate total inventory investment
```sql
sqlite3 inventory.db "SELECT
SUM(quantity_on_hand * unit_cost) as total_ingredient_value
FROM ingredients;"
```

## Managing the Database

### Backup database
```bash
cp inventory.db inventory_backup_$(date +%Y%m%d).db
```

### Reset database with fresh schema
```bash
rm inventory.db
sqlite3 inventory.db < inventory_schema.sql
```

### Interactive mode
```bash
sqlite3 inventory.db
```

Then you can run queries directly:
```sql
.tables
.schema ingredients
SELECT * FROM low_stock_ingredients;
.exit
```

## Sample Data

The database includes sample data:
- 22 ingredients across categories (Produce, Meat, Dairy, Dry Goods, Spices, Packaging)
- 6 finished products (tacos, burritos, burgers, sides, sauces)
- 36 recipe entries showing how ingredients combine to make products
- 5 suppliers
- Sample transaction history

## Notes

- Ingredients track unit cost (what you pay wholesale)
- Products track selling price (what customers pay)
- Recipes link them together to calculate profit margins
- All transactions are logged for audit and analysis
- The database automatically updates timestamps when records change
- Use views for quick reporting without complex queries
