# WONTECH Business Management Dashboard Guide

## Access the Dashboard

**URL:** http://localhost:5001

The dashboard is now running on your local machine and accessible from any browser.

## Dashboard Features

### 📊 Show All (Aggregated View) - Default Tab

**What it shows:**
- Total quantities across all brands/suppliers
- Average unit costs
- Total inventory value
- Number of brands for each ingredient
- List of all brands and suppliers

**Category Summary Cards:**
- Visual breakdown by category
- Total value per category
- Item count per category

**Use cases:**
- "How much ground beef do I have in total?"
- "What's my total inventory value?"
- "Which categories have the most value?"

### 📋 Detailed View Tab

**What it shows:**
- Individual entries for each brand/supplier combination
- Detailed tracking information (lot numbers, expiration dates)
- Storage locations
- Individual costs and values

**Filtering:**
- **Supplier dropdown:** Filter by specific supplier (e.g., "Sysco Foods")
- **Brand dropdown:** Filter by specific brand (e.g., "Premium Angus")
- **Category dropdown:** Filter by category (e.g., "Meat")
- **"All" option:** Default - shows everything

**Use cases:**
- "Show me only Sysco Foods inventory"
- "What Premium Angus items do I have?"
- "Show all meat products"
- "What's expiring soon?"

### 🍔 Products Tab

**What it shows:**
- All finished products
- Ingredient cost per product
- Selling price
- Gross profit
- Profit margin percentage

**Color coding:**
- Green margins: Profitable products
- Red margins: Losing money (e.g., bulk sides sold below cost)

**Use cases:**
- "Which products are most profitable?"
- "What are my product costs?"
- "Should I adjust pricing?"

### 📄 Invoices Tab

**Unreconciled Invoices Section:**
- Invoices that haven't been added to inventory yet
- Shows supplier, dates, amounts, payment status
- Red badges indicate items need attention

**Recent Invoices Section:**
- Last 10 invoices
- Payment status (PAID/UNPAID)
- Reconciliation status (YES/NO)
- Quick overview of recent activity

**Use cases:**
- "Which invoices need reconciling?"
- "What's unpaid?"
- "Recent purchase history"

## How to Use

### Starting the Dashboard

```bash
cd /Users/dell/WONTECH
source venv/bin/activate
python3 app.py
```

Then open: http://localhost:5001

### Stopping the Dashboard

Press `CTRL+C` in the terminal where it's running

Or if running in background:
```bash
# Find the process
lsof -ti:5001 | xargs kill
```

### Restarting the Dashboard

```bash
cd /Users/dell/WONTECH
source venv/bin/activate
python3 app.py
```

## Dashboard Features

✅ **Real-time data** - Always shows current database state
✅ **Multi-brand support** - Aggregates across brands automatically
✅ **Smart filtering** - Dropdown menus for suppliers, brands, categories
✅ **Category summaries** - Visual cards showing value by category
✅ **Product analysis** - Costs and margins calculated automatically
✅ **Invoice tracking** - See what needs reconciling
✅ **Responsive design** - Works on desktop, tablet, and mobile
✅ **Auto-refresh** - Switch tabs to reload data

## API Endpoints

The dashboard uses these API endpoints (available for other tools):

- `GET /api/inventory/aggregated` - Aggregated inventory totals
- `GET /api/inventory/detailed` - Detailed inventory with filters
- `GET /api/inventory/summary` - Summary statistics
- `GET /api/filters/suppliers` - List of suppliers
- `GET /api/filters/brands` - List of brands
- `GET /api/filters/categories` - List of categories
- `GET /api/products/costs` - Product cost analysis
- `GET /api/invoices/unreconciled` - Unreconciled invoices
- `GET /api/invoices/recent` - Recent invoices

## Accessing from Other Devices

The server runs on `0.0.0.0` which means it's accessible from other devices on your network.

Find your local IP:
```bash
ipconfig getifaddr en0
```

Then access from another device:
```
http://YOUR_IP:5001
```

Example: `http://192.168.1.100:5001`

## File Structure

```
WONTECH/
├── app.py                          # Flask application
├── templates/
│   └── dashboard.html              # Main dashboard template
├── static/
│   ├── css/
│   │   └── style.css              # Dashboard styling
│   └── js/
│       └── dashboard.js           # Dashboard JavaScript
├── venv/                          # Python virtual environment
├── inventory.db                   # Main inventory database
└── invoices.db                    # Invoices database
```

## Troubleshooting

### Port Already in Use

If you see "Address already in use", either:

1. Change the port in `app.py`:
   ```python
   app.run(debug=True, host='0.0.0.0', port=5002)
   ```

2. Or kill the process on port 5001:
   ```bash
   lsof -ti:5001 | xargs kill
   ```

### Can't Connect to Database

Make sure you're in the WONTECH directory:
```bash
cd /Users/dell/WONTECH
python3 app.py
```

### Virtual Environment Not Activated

```bash
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

## Tips

- **Bookmark the URL** - Add http://localhost:5001 to your browser bookmarks
- **Keep terminal open** - Don't close the terminal running the server
- **Refresh data** - Click between tabs to reload data
- **Use filters** - Try different filter combinations in Detailed View
- **Check invoices regularly** - Reconcile invoices promptly for accurate inventory

## Next Steps

- **Add invoices** - Use the invoice reconciliation script
- **Update inventory** - Reconciled invoices automatically update the dashboard
- **Monitor margins** - Check Products tab regularly
- **Track expiration** - Use Detailed View to see expiring items
