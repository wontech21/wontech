# 💰 SALES TAB: HOW TO USE

## 🐛 BUG FIXED!
**Issue:** Preview button wasn't working
**Cause:** Typo in HTML (`id="saleDate Manual"` had a space)
**Fixed:** Changed to `id="saleDateManual"`

---

## 📋 TWO WAYS TO ENTER SALES

### Method 1: CSV Paste (Recommended for bulk sales)

1. **Click the "📋 Paste CSV" tab** (should be active by default)

2. **Paste your CSV data** into the text area:
   ```
   Product Name, Quantity
   Cheese Pizza - Large (16"), 5
   Supreme Pizza - Large (16"), 3
   ```

3. **Select the sale date** (defaults to today)

4. **Click "🔍 Parse & Preview"**

5. **Review the preview:**
   - Total revenue, cost, profit (colorful cards)
   - Each product with detailed calculations
   - Ingredient deductions (expandable)
   - Warnings if any (negative inventory, low stock)

6. **Click "✓ Apply to Inventory"** to confirm

---

### Method 2: Manual Entry (For individual sales)

1. **Click the "✏️ Manual Entry" tab**

2. **Select a product** from the dropdown

3. **Enter quantity** (e.g., 5)

4. **Click "+ Add"**
   - Product appears in the list below
   - You can add multiple products

5. **Click "🔍 Preview"** (below the list)

6. **Review the preview** (same as CSV method)

7. **Click "✓ Apply to Inventory"** to confirm

---

## 🔍 DEBUGGING (if still not working)

### Open Browser Console (F12)

You should see these messages when using the Sales tab:

```
✓ Layer 4: Sales Processing Ready
New functions available:
  - parseSalesCSV()
  - applySales()
  ...
✓ Sales tab initialized
```

### When you click "Parse & Preview" (CSV):
```
📝 parseSalesCSV called
Parsing CSV (67 chars), date: 2026-01-19
Parse result: {success: true, count: 2, sales_data: Array(2)}
🎨 displaySalesPreview called {matched: Array(2), unmatched: Array(0), ...}
Preview section shown
```

### When you click "+ Add" (Manual):
```
➕ addManualSale called
Product: Cheese Pizza - Large (16") (ID: 12), Quantity: 5
Manual sale added. Total: 1
```

### When you click "🔍 Preview" (Manual):
```
👁️ previewManualSales called
Manual entries count: 2, date: 2026-01-19
🎨 displaySalesPreview called ...
Preview section shown
```

---

## ❌ ERRORS TO LOOK FOR

### If you see this error:
```
preview-section element not found!
```
**Solution:** The HTML elements are missing. Refresh the page.

### If you see this error:
```
Cannot read property 'value' of null
```
**Solution:** An HTML element ID is wrong. This should be fixed now.

### If you see this error:
```
Failed to fetch
```
**Solution:** Flask server is not running. Start it with:
```bash
cd /Users/dell/WONTECH
python3 app.py
```

---

## 📊 WHAT HAPPENS WHEN YOU APPLY

1. **Inventory is deducted** based on recipes
   - Example: Sell 5 Cheese Pizzas
   - Deducts: 10 dough balls, 40 oz sauce, 2.5 lb cheese, 5 boxes

2. **Sale is recorded** in sales_history table
   - Date, product, quantity, revenue, cost, profit

3. **You can view history** below (automatically refreshes)

4. **Dashboard inventory updates** (refresh to see new quantities)

---

## 🧪 TEST WITH SAMPLE DATA

**Copy and paste this:**
```
Product Name, Quantity
Cheese Pizza - Large (16"), 5
Supreme Pizza - Large (16"), 3
```

**Expected result:**
- Total Revenue: ~$147.92
- Total Cost: ~$51.35
- Total Profit: ~$96.57
- ⚠️ WARNING: Pizza Sauce will go NEGATIVE (-14.00 oz)

This warning means you don't have enough sauce in inventory!

---

## 🎯 WORKFLOW SUMMARY

```
CSV Method:
┌─────────────┐
│ Paste CSV   │
└──────┬──────┘
       ↓
┌─────────────┐
│ Parse       │ ← Validates format
└──────┬──────┘
       ↓
┌─────────────┐
│ Preview     │ ← Shows calculations, warnings
└──────┬──────┘
       ↓
┌─────────────┐
│ Apply       │ ← Actually updates inventory
└──────┬──────┘
       ↓
┌─────────────┐
│ History     │ ← Shows all sales
└─────────────┘
```

```
Manual Method:
┌─────────────┐
│ Select      │
│ Product     │
└──────┬──────┘
       ↓
┌─────────────┐
│ Enter       │
│ Quantity    │
└──────┬──────┘
       ↓
┌─────────────┐
│ Add (+)     │ ← Adds to list (can add more)
└──────┬──────┘
       ↓
┌─────────────┐
│ Preview     │ ← Shows calculations for ALL items in list
└──────┬──────┘
       ↓
┌─────────────┐
│ Apply       │ ← Updates inventory
└─────────────┘
```

---

## 🚀 NEXT: REFRESH THE PAGE

1. **Refresh your browser** (Ctrl+R or Cmd+R)
2. **Open the Sales tab**
3. **Check the console** (F12) for the "Layer 4 Ready" message
4. **Try adding a sale** using either method

The bug is fixed! It should work now. 🎉
