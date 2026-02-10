# Sales CSV Format - Simplified

## Overview

The sales system uses a simple CSV format with retail price as the primary pricing field.

**CSV Format:** `Product, Quantity, Retail_Price, Time`

## Key Principle

**Revenue = Retail_Price × Quantity**

Simple and straightforward - no complex tax or discount calculations.

---

## How It Works

### Database Price (Reference Price)
- The price stored in the `products` table
- The "regular" or "list" price
- Used as fallback if no retail_price is provided in CSV

### Retail Price (Actual Sale Price)
- The actual price the customer was charged
- Provided in CSV or defaults to database price
- **This is what drives revenue calculations**

### Revenue Formula
```
Revenue = Retail_Price × Quantity
```

---

## CSV Format Details

### With Headers (Recommended)
```csv
Product, Quantity, Retail_Price, Time
Cheese Pizza, 100, 14.99, 14:30:00
Beef Tacos, 250, 9.99, 14:35:00
Chicken Burrito, 75, 11.99, 15:00:00
```

### Without Headers (Positional)
```csv
Margherita Pizza, 50, 13.99, 16:00:00
Veggie Burrito, 30, , 16:15:00
```

### Optional Fields
- **Retail_Price:** If blank/missing, uses database price
- **Time:** If blank/missing, uses default time set in UI

---

## Implementation Details

### Backend (`sales_operations.py`)

**Revenue Calculation:**
```python
# Use retail_price if provided, otherwise use database price
actual_retail_price = retail_price if retail_price is not None else original_price

# Revenue = retail_price × quantity
actual_revenue = actual_retail_price * quantity_sold

# Sale price is the retail price
sale_price = actual_retail_price
```

**Discount Tracking:**
```python
# Calculate discount info (if sale price differs from database price)
discount_amount = (original_price - sale_price) * quantity_sold
discount_percent = ((original_price - sale_price) / original_price * 100) if original_price > 0 else 0
```

If retail_price < database price, the system automatically tracks it as a discount.

### Database Schema

**`sales_history` table columns:**
- `original_price` - Database/list price (reference)
- `sale_price` - Actual retail price charged
- `discount_amount` - Auto-calculated if sale_price < original_price
- `discount_percent` - Percentage difference
- `revenue` - **Calculated from sale_price × quantity**
- `cost_of_goods` - Ingredient costs
- `gross_profit` - Revenue - Cost

---

## Use Cases

### 1. Regular Sale (No Discount)
```csv
Product, Quantity, Retail_Price, Time
Cheese Pizza, 100, 15.00, 14:30:00
```
**Result:**
- Database Price: $15.00
- Retail Price: $15.00
- Revenue: $15.00 × 100 = $1,500.00
- Discount: $0.00

### 2. Sale with Custom Price (Discount)
```csv
Product, Quantity, Retail_Price, Time
Cheese Pizza, 100, 12.99, 14:30:00
```
**Result:**
- Database Price: $15.00
- Retail Price: $12.99
- Revenue: $12.99 × 100 = $1,299.00
- Discount: $2.01 per unit ($201.00 total)

### 3. Using Database Price (Blank Retail_Price)
```csv
Product, Quantity, Retail_Price, Time
Cheese Pizza, 100, , 14:30:00
```
**Result:**
- Database Price: $15.00
- Retail Price: $15.00 (uses database price)
- Revenue: $15.00 × 100 = $1,500.00
- Discount: $0.00

---

## Financial Reporting

### Accurate Revenue Tracking
- Reports reflect actual money received
- Discounts are automatically tracked when retail_price < database price
- Profit margins are accurate
- No manual reconciliation needed

### Profit Calculation
```
Gross Profit = Revenue - Cost of Goods
             = (Retail_Price × Quantity) - (Ingredient Costs)
```

This ensures profit reflects the ACTUAL transaction price.

---

## Best Practices

1. **Always provide retail_price for accuracy:** Even if it matches database price
2. **Leave blank to use database price:** System defaults automatically
3. **Use consistent time format:** HH:MM:SS (e.g., 14:30:00)
4. **Include headers:** Makes CSV more readable and flexible
5. **Reconcile daily:** Revenue totals should match POS/register totals

---

## Summary

✅ **Retail Price determines Revenue**
✅ **Database Price is just a reference**
✅ **System automatically tracks discounts**
✅ **Simple, clean CSV format**
✅ **Reports reflect actual transactions**
