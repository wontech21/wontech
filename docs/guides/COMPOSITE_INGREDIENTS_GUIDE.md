# Composite Ingredients System

## Overview
The system now supports **composite ingredients** - ingredients that are made from other base ingredients. For example, Pizza Sauce is a composite ingredient made from tomato paste, garlic, oregano, basil, salt, and olive oil.

## Database Structure

### New Table: `ingredient_recipes`
Stores recipes for composite ingredients:
- `composite_ingredient_id` - The ingredient being made
- `base_ingredient_id` - The raw ingredient used to make it
- `quantity_needed` - How much of the base ingredient is needed
- `unit_of_measure` - Unit for the base ingredient
- `notes` - Optional notes

### New Column: `ingredients.is_composite`
Flag indicating if an ingredient is composite (1) or raw/base (0)

## Current Composite Ingredients

### 1. Pizza Sauce (128 oz batch)
**Ingredient Code:** SAUCE-PIZ
**Cost per oz:** $0.1641

**Recipe:**
- Tomato Paste: 96 oz (6 cans)
- Olive Oil: 8 oz
- Garlic Minced: 4 oz
- Oregano Dried: 16 tsp
- Basil Dried: 16 tsp
- Salt: 8 tsp

**Total Batch Cost:** $21.00

### 2. House Made Meatballs (20 meatballs)
**Ingredient Code:** MEATBALL-HOUSE
**Cost per meatball:** $0.5990

**Recipe:**
- Ground Beef 80/20: 2 lb
- Italian Bread Crumbs: 1 cup
- Whole Eggs: 2 each
- Parmesan Cheese Grated: 0.5 cup
- Garlic Minced: 1 oz
- Oregano Dried: 2 tsp
- Salt: 2 tsp

**Total Batch Cost:** $11.98

## How It Works

### In Product Recipes
When you expand a product's recipe in the dashboard, composite ingredients are:
1. Highlighted with a yellow background
2. Show a "🔧 Composite" badge
3. Display their sub-recipe showing all base ingredients

### Cost Calculation
- Composite ingredients have their unit cost automatically calculated from base ingredients
- When calculating product costs, the system uses the composite ingredient's total cost
- The breakdown is available for transparency

## API Endpoints

### Get Product Recipe with Composite Breakdown
```
GET /api/recipes/by-product/<product_name>
```
Returns recipe with `is_composite` flag and `sub_recipe` array for composite ingredients.

### Get Composite Ingredient Recipe
```
GET /api/ingredients/composite/<ingredient_id>
```
Returns the recipe for a specific composite ingredient.

## Creating New Composite Ingredients

To add a new composite ingredient:

1. **Add the composite ingredient to `ingredients` table:**
   ```sql
   INSERT INTO ingredients
   (ingredient_code, ingredient_name, category, unit_of_measure,
    quantity_on_hand, unit_cost, brand, active, is_composite)
   VALUES ('YOUR-CODE', 'Your Ingredient', 'Category', 'unit',
           100, 0, 'Brand', 1, 1);
   ```

2. **Add base ingredients (if they don't exist):**
   Make sure all raw ingredients are in the `ingredients` table with `is_composite = 0`

3. **Create the recipe in `ingredient_recipes` table:**
   ```sql
   INSERT INTO ingredient_recipes
   (composite_ingredient_id, base_ingredient_id, quantity_needed,
    unit_of_measure, notes)
   VALUES (composite_id, base_id, quantity, 'unit', 'notes');
   ```

4. **Calculate and update the unit cost:**
   ```python
   total_cost = sum(quantity * base_ingredient.unit_cost for each base ingredient)
   unit_cost = total_cost / batch_size
   ```

## Example: Pizza Using Composite Ingredients

When you view "Cheese Pizza - Small (10")" in the dashboard:

**Main Recipe:**
- 10" Pizza Box: 1 each ($0.0035)
- Mozzarella Cheese Shredded: 0.25 lb ($0.0438)
- Pizza Dough Ball: 1 each ($0.0250)
- **Pizza Sauce: 4 oz ($0.0025)** 🔧 Composite
  - ↳ Made from:
    - Tomato Paste: 96 oz
    - Olive Oil: 8 oz
    - Garlic Minced: 4 oz
    - Oregano Dried: 16 tsp
    - Basil Dried: 16 tsp
    - Salt: 8 tsp

**Total Ingredient Cost:** $0.0748

## Benefits

1. **Accurate Costing** - Know the true cost of house-made items
2. **Recipe Transparency** - See exactly what goes into composite ingredients
3. **Inventory Tracking** - Track both composite items and their base ingredients
4. **Scalability** - Easily add new composite ingredients as your menu grows

## Future Enhancements

- UI for creating composite ingredients without SQL
- Multi-level composite ingredients (composites made from other composites)
- Batch scaling calculator
- Composite ingredient production tracking
