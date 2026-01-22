# 🔥 FIRINGup Inventory Management System

A comprehensive restaurant inventory and sales tracking application built with Flask and vanilla JavaScript.

## Features

### 📦 Inventory Management
- Track ingredients with multiple variants (brands, suppliers)
- Consolidated and detailed inventory views
- Automatic reorder level warnings
- Storage location tracking
- Date received and lot number management
- Composite ingredients support (recipes within ingredients)

### 🍔 Products & Recipes
- Create products with ingredient recipes
- Products-as-ingredients support (nested recipes up to 2 levels)
- Automatic cost calculation from ingredient costs
- Recipe validation (circular dependency detection, depth limits)
- Real-time profit margin calculations

### 💰 Sales Analytics
- Sales dashboard with 7-day, monthly, and custom date ranges
- Revenue, profit, and cost of goods tracking
- Top products analysis
- Sales trend charts and hourly distribution
- CSV export for all sales records

### 📄 Invoice Management
- Upload and process invoices
- Automatic inventory reconciliation
- Invoice history and tracking
- Supplier and brand management

### 🔢 Inventory Counts
- Perform physical inventory counts
- Automatic variance detection
- Count history tracking

## Technology Stack

- **Backend:** Python 3.11, Flask 3.1.2
- **Database:** SQLite3
- **Frontend:** Vanilla JavaScript (ES6+), HTML5, CSS3
- **Charts:** Chart.js 4.4.0
- **Deployment:** Docker, Docker Compose

## Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/wontech21/firingup-inventory.git
cd firingup-inventory

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py

# Open browser to http://localhost:5001
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Project Structure

```
FIRINGup/
├── app.py                      # Main Flask application
├── crud_operations.py          # CRUD API endpoints
├── sales_operations.py         # Sales processing logic
├── sales_analytics.py          # Analytics endpoints
├── inventory.db                # SQLite database
├── templates/
│   └── dashboard.html          # Main UI template
├── static/
│   ├── css/
│   │   └── style.css          # Application styles
│   ├── js/
│   │   ├── dashboard.js       # Main dashboard logic
│   │   ├── sales_analytics.js # Sales charts & analytics
│   │   └── layer4_sales.js    # CSV processing
│   └── icons/                 # PWA app icons
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Service orchestration
└── requirements.txt            # Python dependencies
```

## API Endpoints

### Inventory
- `GET /api/inventory/aggregated` - Get consolidated inventory
- `GET /api/inventory/detailed` - Get detailed variants
- `POST /api/ingredients` - Create ingredient
- `PUT /api/ingredients/<id>` - Update ingredient
- `DELETE /api/ingredients/<id>` - Delete ingredient

### Products
- `GET /api/products/all` - List all products
- `POST /api/products` - Create product
- `PUT /api/products/<id>` - Update product
- `DELETE /api/products/<id>` - Delete product
- `GET /api/products/<id>/recipe` - Get product recipe
- `GET /api/products/<id>/ingredient-cost` - Calculate ingredient cost

### Sales
- `GET /api/analytics/sales-overview` - Sales dashboard data
- `GET /api/sales/history` - Sales records with pagination
- `POST /api/sales/parse-csv` - Parse CSV sales data
- `POST /api/sales/apply` - Process and save sales

### Invoices
- `GET /api/invoices` - List invoices
- `POST /api/invoices/upload` - Upload invoice
- `DELETE /api/invoices/delete/<number>` - Delete invoice

## Database Schema

### Main Tables
- `ingredients` - Ingredient master data
- `products` - Product definitions
- `recipes` - Product recipes (links products to ingredients/other products)
- `sales_history` - Sales transaction records
- `invoices` - Invoice master data
- `invoice_items` - Invoice line items
- `inventory_counts` - Physical count records

### Key Features
- Products can use other products as ingredients (with validation)
- Automatic cost rollup for nested products
- Circular dependency prevention
- Audit trails with timestamps

## Contributing

This is a private project. If you have access and want to contribute:

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## License

Private - All rights reserved

## Author

wontech21

## Support

For issues or questions, please open an issue on GitHub.
