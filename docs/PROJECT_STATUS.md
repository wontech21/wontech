# WONTECH Project Status

**Last Updated:** 2026-01-21

## Current State

### ✅ Completed Features
1. **Inventory Management**
   - Consolidated and detailed views
   - Multiple variants per ingredient
   - Edit/delete functionality (fixed modal closing issue)
   - Date filtering with apply buttons

2. **Products & Recipes**
   - Products-as-ingredients support
   - Circular dependency validation
   - Depth limit enforcement (2 levels)
   - Cost calculation for nested products

3. **Sales Analytics**
   - Dashboard with multiple time periods (Last 7 Days default)
   - CSV export with date filtering
   - Revenue, profit, and COGS tracking
   - Charts and visualizations

4. **Infrastructure**
   - Git version control (16 commits)
   - Docker containerization
   - GitHub repository: https://github.com/wontech21/wontech
   - Cloud deployment: https://wontech.onrender.com/
   - Automatic deployment pipeline (git push → Render auto-deploys)
   - PWA installed on iPad

5. **Background Customization & Glassmorphism**
   - 10 gradient themes (Default, Sunset, Ocean, Forest, Lavender, Fire, Midnight, Cherry, Mint, Gold)
   - Custom image upload (JPEG, PNG, GIF up to 5MB)
   - Live preview for uploaded images
   - Preferences saved in localStorage
   - Reset to default option
   - **Minimal Glassmorphism UI**: Main container has frosted glass overlay
   - Backdrop blur filters (20px on main container only)
   - All other UI elements are bold and opaque for readability
   - Table headers, tabs, and modals have bold purple gradient
   - Background shows through main container only

6. **CSV Import**
   - Sales CSV import in Sales tab
   - File upload and copy/paste support
   - Comprehensive format guide with examples
   - Preview before applying changes
   - Validation and error handling
   - Full audit logging to System History

7. **System History / Audit Trail**
   - Complete audit log of all system actions
   - Sales tracking (SALE_RECORDED)
   - Invoice operations
   - Inventory counts
   - Item/Brand/Supplier changes
   - Filterable by action type and entity
   - Date range filtering

### 🚧 In Progress
- None currently

### 📋 Pending
- Optional: Set up Render Disk for persistent database
- Optional: Upgrade to Starter plan ($7/month) for always-on

### 🐛 Known Issues
- None currently

### 🔧 Recently Fixed
- Sales CSV imports now properly log to System History tab (audit_log)
- Missing saleTime field causing Parse & Preview to fail

### ⚙️ Settings & Customization
- Brand management (rename across all items)
- Supplier management (rename across all items)
- Background customization (10 gradients + custom images)

---

## Quick Commands

### Local Development
```bash
# Start Docker container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop container
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

### Git Operations
```bash
# Check status
git status

# Commit changes (I'll do this when you request changes)
git add . && git commit -m "Description" && git push
```

### Access URLs
- **Local:** http://localhost:5001
- **Cloud:** https://wontech.onrender.com/
- **GitHub:** https://github.com/wontech21/wontech
- **Render Dashboard:** https://dashboard.render.com/

---

## Key Files

### Application
- `app.py` - Main Flask application
- `crud_operations.py` - CRUD API endpoints
- `sales_operations.py` - Sales processing
- `sales_analytics.py` - Analytics endpoints
- `templates/dashboard.html` - Main UI
- `static/js/dashboard.js` - Dashboard logic
- `static/js/sales_analytics.js` - Sales charts

### Infrastructure
- `Dockerfile` - Container definition
- `docker-compose.yml` - Service orchestration
- `requirements.txt` - Python dependencies
- `.gitignore` - Git exclusions
- `.dockerignore` - Docker build exclusions

### Documentation
- `README.md` - Project overview
- `RENDER_DEPLOYMENT.md` - Cloud deployment guide
- `DOCKER_SETUP_GUIDE.md` - Docker instructions
- `PROJECT_STATUS.md` - This file

---

## Recent Changes

### 2026-01-21 (Session 1)
1. Added CSV export for sales records
2. Fixed variant edit/delete modal closing issue
3. Completed Phase 1: Git setup
4. Completed Phase 2: Docker containerization
5. Completed Phase 3: Cloud deployment to Render.com
6. PWA installed on iPad - full mobile access enabled
7. Added CSV import to Sales tab with comprehensive format guide
8. Fixed CSV import Parse & Preview button not working (missing saleTime field)
9. Added comprehensive audit logging for sales CSV imports
10. Sales now appear in System History tab with full details
11. Removed timezone settings (simplified to local time)
12. Added background customization with 10 gradient themes and custom image upload
13. Implemented comprehensive glassmorphism (frosted glass) effect across entire dashboard

### 2026-01-22 (Session 2)
1. **REVERSED comprehensive glassmorphism** - User feedback: text was washed out and unreadable
2. **Kept minimal glass effect** - Only main container has frosted glass overlay
3. **Fixed perpetually loading header stats** - Removed orphaned timezone function calls from DOMContentLoaded
4. **Applied bold opaque colors to all UI elements**:
   - Active tabs now have purple gradient background with white text
   - All table headers have bold purple gradient with white text
   - Modal headers have purple gradient with white text
   - Close buttons updated for dark backgrounds
5. **Removed all remaining timezone code** - Cleaned up unused timezone functions
6. **Ensured proper contrast** - All text elements now have good readability
7. **Implemented dynamic theming** - UI elements now match background color scheme:
   - CSS variables control theme colors across all UI elements
   - Header, tabs, table headers, modals, and stat boxes sync with background gradient
   - When user selects Sunset gradient, all themed elements use sunset colors
   - When user selects Ocean gradient, all themed elements use ocean colors
   - Custom images keep default purple theme for UI elements
   - 10 color-coordinated themes available
8. **Comprehensive theme color sweep** - All hardcoded colors now use CSS variables:
   - Replaced 50+ instances of hardcoded #667eea, #764ba2, #ff6b6b colors
   - Updated all border-color, color, background, and accent-color properties
   - Converted rgba() colors to use CSS variable RGB values for transparency
   - Tab hover states, button active states, focus borders all sync with theme
   - Form element accents (dropdowns, inputs, checkboxes) match theme
   - Box shadows with theme colors now adapt to selected gradient
   - Sales preview details, product items, variant dropdowns themed
   - Complete visual coherence across all UI elements
9. **Fixed inline styles preventing theme sync** - Removed hardcoded inline styles from HTML:
   - Fixed line-items-table column headers (were stuck on gray)
   - Replaced inline gradient styles on Format Guide button
   - Replaced inline border colors on CSV date/time inputs
   - Replaced inline gradient on Parse & Preview button
   - Replaced inline gradient on CSV upload button
   - Created new CSS classes: btn-format-guide, format-guide-box, btn-upload-csv, csv-date-input, btn-parse-csv
   - All previously stubborn elements now sync perfectly with selected theme

### 2026-01-23 (Session 3)
1. **Fixed header gradient not updating with theme changes**:
   - Discovered browser limitation: CSS variables referencing other variables don't auto-recalculate
   - Explicitly calculate gradient string in JavaScript and set all CSS variables
   - Header background now properly syncs with selected theme
2. **Rebranded to "WONTECH Data Center"**:
   - Changed dashboard title from "WONTECH Inventory Dashboard"
   - Added company logo image (firinguplogo.png) to header
   - Logo displays inline with title using flexbox
   - Responsive logo sizing with clamp() for all screen sizes
   - Updated page title tag to match new branding
3. **Disabled auto-refresh for analytics**:
   - Removed 60-second auto-refresh interval
   - Analytics now only load when user manually clicks Analytics tab
   - Manual refresh still available via Refresh button
4. **Analytics dashboard cleanup** - Removed 7 widgets and improved UX:
   - **Deleted widgets**: Usage & Forecast, Ingredient Substitution, Recipe Cost Trajectory, Break-Even Analysis, Menu Engineering Matrix, Seasonal Demand Patterns, Order Frequency Optimizer (EOQ)
   - **Category Spending improvements**: Changed from area chart to pie chart showing total spending distribution by category; removed category filter UI for simpler visualization
   - **Date filter additions**: Supplier Performance and Cost Variance now respect date range filters
   - **Remaining analytics**: Vendor Spend Distribution, Category Spending Distribution (pie), Price Trend Analysis, Supplier Performance (with date filter), Invoice Activity, Cost Variance (with date filter), Product Profitability, Inventory Value Distribution, Price Volatility Index, Dead Stock Analysis, Waste & Shrinkage, Supplier Price Correlation, Cost Driver Analysis
5. **Fixed category spending to show ALL categories**:
   - Was limited to only 5 categories, now shows all 18 categories with spending data
   - Optimized query from multiple category queries to single aggregation
   - Extended color palette from 10 to 20 colors with dynamic cycling
   - Pie chart now provides complete spending visibility across all categories
6. **Completely rebuilt Price Trend Analysis widget**:
   - Simplified from complex multi-item (max 5) to single-item focused view
   - Added search bar for efficient filtering across 900+ inventory items
   - Shows ALL brand/supplier variants in searchable dropdown
   - Added dedicated date range filters (From/To) independent of global analytics filter
   - Default timeframe: last 90 days
   - Chart auto-scales both axes based on actual price data and selected date range
   - Removed confusing "purchase frequency" categorization
   - Cleaner single-line chart for better price trend visualization
7. **Fixed Price Trend Analysis loading error**:
   - Updated to use correct endpoint `/api/inventory/detailed?status=active`
   - Previous endpoint `/api/inventory/list?status=active` didn't exist
   - Dropdown now successfully loads all inventory items with brand/supplier info
8. **Converted Analytics dashboard to match Sales section layout**:
   - Replaced dropdown time selector with button-based period selection
   - Added period buttons: Today, Last 7 Days, This Week, This Month, Last 30 Days (default), Last Quarter, Last Year, All Time, Custom Range
   - Custom range shows date picker inputs with Apply button
   - Current period displayed prominently above widgets
   - All 7 references to old dropdown replaced with new date variables
   - All analytics widgets now use new period selection system
9. **Added purchase frequency filter to Price Trend Analysis**:
   - New radio button filters: All, Daily (<3 days), Weekly (3-10 days), Monthly (>10 days)
   - Frequency calculated based on average days between purchases from invoice data
   - Backend endpoint `/api/analytics/purchase-frequency` calculates frequency for all items
   - Dropdown dynamically filters items by both search term and frequency category
   - Helps users quickly find items based on how often they're purchased
10. **Improved Price Trend Analysis widget layout and size**:
   - Widget now spans full width of analytics dashboard for better visibility
   - Added `size` column to `analytics_widgets` table
   - Restructured controls into 3 clear rows: Frequency filters, Item selection, Date range
   - Date filters now prominently displayed on dedicated row
   - Auto-update chart when changing item selection or dates
   - Increased font sizes and padding for better readability
11. **Redesigned Price Trend Analysis search with autocomplete dropdown**:
   - Search results now appear in dropdown directly below search input (autocomplete pattern)
   - No more hidden results in separate dropdown - all results visible as you type
   - Dropdown shows up to 50 filtered results with hover highlighting
   - Selected item displayed prominently next to search box
   - Click outside dropdown to close it
   - Modern, intuitive UX - type to search, click to select
   - Search filters combine with frequency filter for targeted results
12. **Completely redesigned Price Trend Analysis widget layout**:
   - **Reordered widgets**: Moved Price Trends down to position 8 (after Cost Variance, before unused widgets)
   - **Side-by-side layout**: Chart on left (~60% width), controls on right (~40% width)
   - **Expanded chart**: Fills full height (~500px min) and width of container with maintainAspectRatio: false
   - **Right-side control panel**: Organized vertically with theme-styled background
   - **Prioritized controls by function**:
     1. Purchase Frequency Filter (radio buttons in white box)
     2. Search & Select Item (autocomplete with selected item display)
     3. Date Range (from/to in white box)
     4. Update Chart button (full-width, gradient, prominent)
   - **Visual theme integration**: Gradient background, themed borders, hover effects
   - **Better visibility**: Larger chart, organized controls, clear visual hierarchy
13. **Generated comprehensive historical data (90 days)**:
   - **Sales data**: 30,814 transactions totaling $626,306 in revenue
     * Generated backward from 2026-01-23 to 2025-10-25
     * Focused on top 15 products based on recipe complexity
     * Day-of-week patterns (weekends busier, Mondays slower)
     * Random discounts (10% chance of 5-15% off)
     * Realistic timing (11 AM - 10 PM)
     * Top seller: Beef Tacos (16,846 units, $216,689 revenue)
     * Last 30 days: 10,524 sales transactions
   - **Invoice data**: 59 invoices totaling $275,814 from 10 suppliers
     * Deliveries every 2-3 days throughout entire 90-day period
     * 50 unique ingredients ordered based on sales usage
     * Price variations (±10% realistic market fluctuations)
     * **Last 30 days**: 32 invoices, $79,003 (realistic monthly cycle)
     * Top recent suppliers: Shamrock Foods ($19,741), Cheney Brothers ($17,371)
     * Lot numbers and expiration dates included
     * Distribution: Oct ($19k), Nov ($35k), Dec ($179k), Jan ($43k)
   - **Inventory counts**: 26 count sessions (twice weekly)
     * All 970 active ingredients counted each session (25,220 total line items)
     * Realistic variances: 80% minor (±2%), 10% moderate loss (3-8%), 5% significant loss (10-20%), 5% exact
     * Variance reasons: Spillage (1,258), Expired items (1,326), Waste (1,212), Theft (633), Damaged goods (637)
     * Average loss per count: -1.56 units
   - **Scripts**:
     * `generate_historical_data.py` - Full 90-day data generation
     * `generate_recent_invoices.py` - Supplement with recent invoice data
14. **Fixed Price Trend Analysis "no price history" issue**:
   - Problem: Dropdown showed all 970 ingredients but only ~50 had invoice data
   - Solution: Filter dropdown to only show ingredients with actual price history
   - New endpoint: `/api/analytics/ingredients-with-price-history` returns list of ingredient codes with invoice data
   - Widget now loads 3 data sources in parallel: inventory, frequency, and price history filter
   - Dropdown only displays items that have historical pricing data
   - User can now successfully view price trends for any item in the dropdown
15. **Added pagination to Supplier and Category Management tables**:
   - Both tables now show 10 items per page (previously showed all)
   - Pagination controls: Previous/Next buttons with page numbers
   - Shows "Showing X-Y of Z" counter
   - Improves performance for large datasets
   - Consistent UX across all tables in the system
16. **Backfilled audit logs for all simulated historical data**:
   - Created `backfill_audit_logs.py` script
   - Added 30,814 sales audit entries (SALE_RECORDED)
   - Added 105 invoice audit entries (INVOICE_CREATED + payment status)
   - Added 26 inventory count audit entries (COUNT_CREATED)
   - Total audit log entries: 32,113
   - System History tab now shows complete activity from Oct 25, 2025 to present
   - All simulated data now visible in audit trail for analysis
17. **Enhanced System History stat card labels**:
   - Made stat labels more visible and prominent
   - Increased font weight to 600 (semi-bold)
   - Added uppercase text transform with letter spacing
   - Forced white color and full opacity for better visibility
   - Added explicit display:block to prevent layout issues
   - Labels now clearly show "TOTAL EVENTS" and "LAST 7 DAYS"

---

## Next Session Checklist

When resuming work:
1. ✅ Check if Docker container is running: `docker ps`
2. ✅ If not running: `docker-compose up -d`
3. ✅ Verify local app: http://localhost:5001
4. ✅ Verify cloud app: https://wontech.onrender.com/
5. ✅ Check git status: `git status`

---

## Database Info

### Local
- `inventory.db` - 970 items, 134 ingredients, 15 products
- `invoices.db` - Invoice data

### Schema
- Products can use other products as ingredients (validated)
- Source type tracking (ingredient vs product)
- Sales history with pricing and discount data

---

## Deployment Pipeline

```
Local Changes → Git Commit → Push to GitHub → Render Auto-Deploy (2-3 min)
```

**Automatic:** When I push to GitHub, Render detects and deploys automatically.

---

## How to Resume Next Session

Tell Claude:
- "Continue where we left off"
- "What's our current status?"
- "Resume the WONTECH project"

Claude will read this file and the conversation history to get back up to speed.
