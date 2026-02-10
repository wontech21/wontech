# Inventory Clustering System - Brand & Supplier Management

## Overview

The inventory system now supports **ingredient clustering** - multiple brands and suppliers for the same ingredient. This allows you to:
- Track different brands of the same product (e.g., Premium Angus beef vs. Certified Angus beef)
- Track the same product from different suppliers
- View total quantities across all brands/suppliers
- Filter inventory by specific brands or suppliers
- Automatically reconcile invoices to the correct brand/supplier combination

## How It Works

### Ingredient Clustering

**Same Ingredient, Different Brands:**
- Ingredient Name: "Ground Beef 80/20"
  - Brand 1: Premium Angus (Sysco Foods) - 150 lbs
  - Brand 2: Certified Angus (US Foods) - 75 lbs
  - **TOTAL: 225 lbs across all brands**

### Database Structure

Each ingredient entry now includes:
- `ingredient_code` - Unique per brand/supplier combo (e.g., ING-BEF-001, ING-BEF-002)
- `ingredient_name` - Cluster name (e.g., "Ground Beef 80/20")
- `brand` - Brand name (e.g., "Premium Angus")
- `supplier_name` - Supplier (e.g., "Sysco Foods")

## Views and Queries

### 1. Aggregated View (Show All - Default)

View total quantities across all brands/suppliers:

```sql
sqlite3 inventory.db "SELECT * FROM inventory_aggregated;"
```

Shows:
- ingredient_name
- total_quantity (summed across all brands)
- avg_unit_cost
- total_value
- brand_count (how many brands/suppliers)
- brands (list of all brands)
- suppliers (list of all suppliers)

**Example Output:**
```
Ground Beef 80/20 | 225.0 lbs | $4.38 avg | $993.75 | 2 brands | Premium Angus,Certified Angus
```

### 2. Detailed View (All Brands/Suppliers)

View each brand/supplier combination separately:

```sql
sqlite3 inventory.db "SELECT * FROM inventory_detailed;"
```

Shows every unique brand/supplier combination with individual quantities.

**Example Output:**
```
ING-BEF-001 | Ground Beef 80/20 | Premium Angus | Sysco Foods | 150.0 lbs
ING-BEF-002 | Ground Beef 80/20 | Certified Angus | US Foods | 75.0 lbs
```

### 3. Filter by Supplier

Show inventory from a specific supplier:

```sql
sqlite3 inventory.db "SELECT * FROM inventory_detailed WHERE supplier_name = 'Sysco Foods';"
```

### 4. Filter by Brand

Show inventory from a specific brand:

```sql
sqlite3 inventory.db "SELECT * FROM inventory_detailed WHERE brand = 'Premium Angus';"
```

### 5. Filter by Ingredient Name

Show all brands/suppliers for a specific ingredient:

```sql
sqlite3 inventory.db "SELECT * FROM inventory_detailed WHERE ingredient_name = 'Ground Beef 80/20';"
```

### 6. Filter by Brand AND Supplier

```sql
sqlite3 inventory.db "SELECT * FROM inventory_detailed WHERE brand = 'Premium Angus' AND supplier_name = 'Sysco Foods';"
```

### 7. Ingredient Clusters

Show unique ingredient names (cluster list):

```sql
sqlite3 inventory.db "SELECT * FROM ingredient_clusters;"
```

### 8. Supplier Dropdown List

Get list of all suppliers for dropdown menus:

```sql
sqlite3 inventory.db "SELECT * FROM supplier_list;"
```

### 9. Brand Dropdown List

Get list of all brands for dropdown menus:

```sql
sqlite3 inventory.db "SELECT * FROM brand_list;"
```

## Invoice Reconciliation with Clustering

### How It Works

When an invoice is reconciled:
1. The system reads the brand and supplier from the invoice line items
2. It matches to the inventory entry with matching:
   - ingredient_code OR ingredient_name
   - **AND** brand
   - **AND** supplier
3. Updates only that specific brand/supplier combination
4. The aggregated view automatically shows the new total across all brands

### Using the Updated Reconciliation Script

```bash
# Use the new v2 script that supports brand/supplier matching
python3 reconcile_invoice_v2.py INV-2024-004
```

The v2 script:
- ✓ Matches by ingredient_code + brand + supplier
- ✓ Falls back to ingredient_name + brand + supplier if code doesn't match
- ✓ Shows brand info in reconciliation output
- ✓ Warns if brand/supplier combination doesn't exist in inventory

### Adding New Brand/Supplier Combinations

If an invoice contains a brand/supplier you don't have in inventory yet, you need to add it first:

```sql
INSERT INTO ingredients
(ingredient_code, ingredient_name, brand, supplier_name, category,
unit_of_measure, quantity_on_hand, unit_cost, storage_location, reorder_level)
VALUES
('ING-BEF-003', 'Ground Beef 80/20', 'Black Angus', 'Restaurant Depot',
'Meat', 'lbs', 0, 4.75, 'Walk-in Cooler B', 40);
```

Then reconcile the invoice - it will update this new entry.

## CSV Exports with Filters

### Export All (Show All - Default)

```bash
sqlite3 inventory.db << 'EOF'
.headers on
.mode csv
.output inventory_all_brands.csv
SELECT * FROM inventory_aggregated;
EOF
```

### Export Detailed (All Brand/Supplier Combos)

```bash
sqlite3 inventory.db << 'EOF'
.headers on
.mode csv
.output inventory_detailed_all.csv
SELECT * FROM inventory_detailed;
EOF
```

### Export Filtered by Supplier

```bash
sqlite3 inventory.db << 'EOF'
.headers on
.mode csv
.output inventory_sysco_only.csv
SELECT * FROM inventory_detailed WHERE supplier_name = 'Sysco Foods';
EOF
```

### Export Filtered by Brand

```bash
sqlite3 inventory.db << 'EOF'
.headers on
.mode csv
.output inventory_premium_angus.csv
SELECT * FROM inventory_detailed WHERE brand = 'Premium Angus';
EOF
```

## Multi-Brand Examples in Database

Current examples of clustered ingredients:

1. **Ground Beef 80/20** (2 brands)
   - Premium Angus (Sysco Foods): 150 lbs
   - Certified Angus (US Foods): 75 lbs
   - Total: 225 lbs

2. **Chicken Breast** (2 brands)
   - Farm Fresh (Sysco Foods): 100 lbs
   - Perdue (Restaurant Depot): 50 lbs
   - Total: 150 lbs

3. **Roma Tomatoes** (2 brands)
   - Fresh Farms (Fresh Produce Wholesalers): 75 lbs
   - Organic Valley (US Foods): 30 lbs
   - Total: 105 lbs

4. **Cheddar Cheese** (2 brands)
   - Tillamook (US Foods): 25 lbs
   - Cabot (Restaurant Depot): 15 lbs
   - Total: 40 lbs

5. **All-Purpose Flour** (2 brands)
   - King Arthur (Restaurant Depot): 200 lbs
   - Gold Medal (Sysco Foods): 100 lbs
   - Total: 300 lbs

## Common Use Cases

### "Show me all my inventory"
```sql
SELECT * FROM inventory_aggregated;
```
Default view - shows totals across all brands/suppliers.

### "Show me what I have from Sysco"
```sql
SELECT * FROM inventory_detailed WHERE supplier_name = 'Sysco Foods';
```

### "How much Premium Angus beef do I have?"
```sql
SELECT * FROM inventory_detailed
WHERE ingredient_name = 'Ground Beef 80/20' AND brand = 'Premium Angus';
```

### "Show me all the different brands of cheese I carry"
```sql
SELECT * FROM inventory_detailed WHERE category = 'Dairy' AND ingredient_name LIKE '%Cheese%';
```

### "What's my total ground beef across all brands?"
```sql
SELECT * FROM inventory_aggregated WHERE ingredient_name = 'Ground Beef 80/20';
```

## Benefits of Clustering

✓ **Total visibility** - See combined quantities across brands
✓ **Brand tracking** - Know exactly which brands you have
✓ **Supplier tracking** - Track which supplier provides what
✓ **Price comparison** - Compare unit costs across brands
✓ **Automatic aggregation** - Totals update automatically
✓ **Invoice flexibility** - Reconcile any brand/supplier combination
✓ **No duplicate ingredient names** - Same name, different codes

## Notes

- Each brand/supplier combination is a separate inventory entry
- Use "show all" (aggregated view) to see totals
- Use filtered views to see specific brands/suppliers
- Always specify brand and supplier when reconciling invoices
- The reconciliation script (v2) handles brand/supplier matching automatically
