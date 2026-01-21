# 🚀 LAYER 4: QUICK START GUIDE

**Status:** ✅ LIVE & READY TO USE

---

## ⚡ 30-SECOND START

1. **Open your browser** → Navigate to your dashboard
2. **Click "💰 Sales" tab** in the top navigation
3. **Paste your CSV** or manually enter sales
4. **Click "🔍 Parse & Preview"**
5. **Review the preview** (Revenue, Cost, Profit, Deductions)
6. **Click "✓ Apply to Inventory"**
7. **Done!** Inventory automatically updated ✓

---

## 📋 CSV FORMAT

```
Product Name, Quantity
Cheese Pizza, 100
Beef Tacos, 250
Chicken Burrito, 175
Caesar Salad, 50
```

**Rules:**
- Product names must match your database (case-insensitive)
- Quantities can be decimal (e.g., 12.5)
- One product per line
- Comma-separated

---

## 🎯 WHAT YOU'LL SEE

### Preview Cards (Color-Coded):
- **💰 Purple** - Total Revenue
- **💵 Pink** - Total Cost
- **📊 Blue** - Gross Profit

### Matched Products (Green):
- Product name
- Quantity sold
- Revenue, Cost, Profit
- Click "📋 Ingredient Deductions" to expand
  - See exact quantities being deducted
  - Current → New inventory levels

### Warnings (Yellow):
- ⚠️ Low stock alerts
- ⚠️ Negative inventory warnings
- ⚠️ Items below reorder level

### Unmatched Products (Red):
- Products not found in database
- Won't be processed
- Check product name spelling

---

## ✅ WHAT LAYER 4 DOES

### Automatically:
1. ✓ Parses your sales CSV
2. ✓ Matches products by name
3. ✓ Looks up recipes for each product
4. ✓ Calculates ingredient deductions (recipe × quantity)
5. ✓ Shows preview with totals
6. ✓ Deducts ingredients from inventory
7. ✓ Records sales in history
8. ✓ Tracks revenue, cost, and profit

### Safety Features:
- Preview before applying (no accidents!)
- Transaction safety (rollback on error)
- Unmatched product detection
- Low stock warnings
- Negative inventory alerts

---

## 🎨 UI FEATURES

### Two Input Methods:
1. **📋 Paste CSV** - Fast bulk entry from POS export
2. **✏️ Manual Entry** - Add sales one at a time

### Interactive Elements:
- Tab switching (CSV ↔ Manual)
- Product dropdown (auto-populated)
- Date picker (defaults to today)
- Manual sales list (add/remove items)
- Expandable ingredient details
- Scrollable sales history

### Professional Styling:
- Purple gradient theme (matches dashboard)
- Smooth animations and transitions
- Hover effects on all interactive elements
- Mobile responsive design
- Color-coded cards for quick scanning

---

## 📊 SALES HISTORY

**Location:** Bottom of Sales tab

**Shows:**
- Date of sale
- Product name
- Quantity sold
- Revenue
- Cost of goods
- Gross profit (in green)

**Features:**
- Displays 20 most recent sales
- Sortable columns
- Hover highlighting
- Alternating row colors for readability

---

## 🔄 TYPICAL WORKFLOW

### Daily Sales Entry:
```
Morning:
1. Export sales CSV from POS system
2. Copy CSV data

Afternoon:
3. Open Dashboard → Sales tab
4. Paste CSV data
5. Click "Parse & Preview"
6. Review totals and warnings
7. Click "Apply to Inventory"
8. Check sales history

Done! Inventory updated, profit tracked ✓
```

---

## ⚠️ COMMON ISSUES & FIXES

### "Product not found in database"
**Cause:** Product name in CSV doesn't match database
**Fix:**
- Check spelling
- Make sure product exists in Products tab
- Case doesn't matter ("CHEESE PIZZA" = "Cheese Pizza")

### "Preview failed"
**Cause:** Product doesn't have a recipe defined
**Fix:**
- Go to Products tab
- Click "View Recipe" for the product
- Add ingredients if missing

### "Negative inventory warning"
**Cause:** Not enough inventory to fulfill sales
**Fix:**
- Check physical inventory
- Investigate discrepancy
- Update inventory count if needed
- Create purchase order

### Preview doesn't show
**Cause:** CSV parsing failed or empty data
**Fix:**
- Check CSV format (Product, Quantity)
- Ensure there's data entered
- Try manual entry instead

---

## 🎯 EXAMPLE: FIRST SALE

**Scenario:** You sold 10 Cheese Pizzas

### Option 1: CSV
```
1. Click Sales tab
2. Paste: "Cheese Pizza, 10"
3. Click "Parse & Preview"
4. See preview:
   - Revenue: $129.90 (10 × $12.99)
   - Cost: $37.00
   - Profit: $92.90
   - Deductions:
     • Mozzarella: -5 lbs
     • Pizza Dough: -3 lbs
     • Tomato Sauce: -2 lbs
5. Click "Apply to Inventory"
6. Success! ✓
```

### Option 2: Manual
```
1. Click "Manual Entry" tab
2. Select "Cheese Pizza" from dropdown
3. Enter quantity: 10
4. Click "+ Add"
5. Click "Preview"
6. (Same preview as above)
7. Click "Apply to Inventory"
8. Success! ✓
```

---

## 📈 VIEWING RESULTS

### Immediate Effects:
1. **Inventory Tab** - Ingredient quantities decreased
2. **Sales History** - New entry appears
3. **Success Message** - Confirmation displayed

### Check Inventory:
```
1. Go to Inventory tab
2. Find "Mozzarella"
3. Quantity should be 5 lbs less
4. Check other ingredients too
```

### Check History:
```
1. Scroll to "Recent Sales" section
2. See your sale listed:
   - Date: Today
   - Product: Cheese Pizza
   - Quantity: 10
   - Revenue: $129.90
   - Cost: $37.00
   - Profit: $92.90
```

---

## 🎓 PRO TIPS

### Efficiency:
- Process sales once daily (end of day)
- Keep CSV export button handy in POS
- Review warnings before applying
- Check history weekly for trends

### Accuracy:
- Verify product names match exactly
- Update recipes when menu changes
- Investigate negative inventory warnings
- Cross-check with physical counts

### Best Practices:
- Always preview before applying
- Read warning messages carefully
- Keep sales history for accounting
- Update reorder levels based on trends

---

## 🔧 TECHNICAL NOTES

### What's Running:
- **Server:** Flask on port 5001 ✓
- **Database:** SQLite (inventory.db) ✓
- **Frontend:** layer4_sales.js loaded ✓
- **Styling:** CSS fully applied ✓

### Files:
- Backend: `sales_operations.py`
- Routes: `app.py` (sales endpoints)
- Frontend: `static/js/layer4_sales.js`
- Styles: `static/css/style.css`
- HTML: `templates/dashboard.html` (sales tab)

### Tested:
- ✓ All 8 backend tests passing
- ✓ CSV parsing validated
- ✓ Preview calculations verified
- ✓ Inventory deductions confirmed
- ✓ Transaction safety tested
- ✓ Error handling validated

---

## 🎉 YOU'RE READY!

**Everything is configured and working.**

Just open your dashboard and go to the **💰 Sales** tab to start!

**Need help?** Check `LAYER4_COMPLETE.md` for full documentation.

---

**Happy selling!** 🚀
