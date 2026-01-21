#!/usr/bin/env python3
"""
Setup analytics infrastructure - create widget tables and populate with default widgets
"""

import sqlite3

INVENTORY_DB = 'inventory.db'

# All 20 analytics widgets
WIDGETS = [
    # Original 10
    {
        'widget_key': 'vendor_spend',
        'widget_name': 'Vendor Spend Distribution',
        'widget_type': 'chart',
        'chart_type': 'doughnut',
        'category': 'supplier',
        'description': 'Percentage of total spend by supplier',
        'icon': '🏢',
        'default_enabled': 1,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'price_trends',
        'widget_name': 'Price Trend Analysis',
        'widget_type': 'chart',
        'chart_type': 'line',
        'category': 'cost',
        'description': 'Price changes over time for selected ingredients',
        'icon': '📈',
        'default_enabled': 1,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'product_profitability',
        'widget_name': 'Product Profitability',
        'widget_type': 'chart',
        'chart_type': 'bar',
        'category': 'profitability',
        'description': 'Margin % and profit per product',
        'icon': '💰',
        'default_enabled': 1,
        'requires_recipe_data': 1
    },
    {
        'widget_key': 'category_spending',
        'widget_name': 'Category Spending Trends',
        'widget_type': 'chart',
        'chart_type': 'area',
        'category': 'cost',
        'description': 'Monthly spending by category over time',
        'icon': '📊',
        'default_enabled': 1,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'inventory_value',
        'widget_name': 'Inventory Value Distribution',
        'widget_type': 'chart',
        'chart_type': 'bar',
        'category': 'inventory',
        'description': 'Top items by total inventory value',
        'icon': '📦',
        'default_enabled': 1,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'supplier_performance',
        'widget_name': 'Supplier Performance',
        'widget_type': 'table',
        'chart_type': 'radar',
        'category': 'supplier',
        'description': 'Multi-metric supplier comparison',
        'icon': '⭐',
        'default_enabled': 1,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'price_volatility',
        'widget_name': 'Price Volatility Index',
        'widget_type': 'chart',
        'chart_type': 'bar',
        'category': 'cost',
        'description': 'Coefficient of variation for ingredients',
        'icon': '📉',
        'default_enabled': 1,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'invoice_activity',
        'widget_name': 'Invoice Activity Timeline',
        'widget_type': 'chart',
        'chart_type': 'line',
        'category': 'supplier',
        'description': 'Invoice count and value over time',
        'icon': '📅',
        'default_enabled': 1,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'cost_variance',
        'widget_name': 'Cost Variance Alerts',
        'widget_type': 'table',
        'chart_type': None,
        'category': 'cost',
        'description': 'Items with significant price changes',
        'icon': '⚠️',
        'default_enabled': 1,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'usage_forecast',
        'widget_name': 'Usage & Forecast',
        'widget_type': 'chart',
        'chart_type': 'line',
        'category': 'forecasting',
        'description': 'Historical usage with regression forecast',
        'icon': '🔮',
        'default_enabled': 1,
        'requires_recipe_data': 0
    },
    # Additional 10
    {
        'widget_key': 'recipe_cost_trajectory',
        'widget_name': 'Recipe Cost Trajectory',
        'widget_type': 'chart',
        'chart_type': 'line',
        'category': 'profitability',
        'description': 'COGS trend with regression prediction',
        'icon': '📉',
        'default_enabled': 0,
        'requires_recipe_data': 1
    },
    {
        'widget_key': 'substitution_opportunities',
        'widget_name': 'Ingredient Substitution',
        'widget_type': 'table',
        'chart_type': None,
        'category': 'cost',
        'description': 'Compare prices of similar ingredients',
        'icon': '🔄',
        'default_enabled': 0,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'dead_stock',
        'widget_name': 'Dead Stock Analysis',
        'widget_type': 'table',
        'chart_type': None,
        'category': 'inventory',
        'description': 'Items with zero usage',
        'icon': '💀',
        'default_enabled': 0,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'eoq_optimizer',
        'widget_name': 'Order Frequency Optimizer',
        'widget_type': 'table',
        'chart_type': None,
        'category': 'inventory',
        'description': 'Economic Order Quantity analysis',
        'icon': '🎯',
        'default_enabled': 0,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'seasonal_patterns',
        'widget_name': 'Seasonal Demand Patterns',
        'widget_type': 'chart',
        'chart_type': 'line',
        'category': 'forecasting',
        'description': 'Monthly usage with year-over-year overlay',
        'icon': '🌡️',
        'default_enabled': 0,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'menu_engineering',
        'widget_name': 'Menu Engineering Matrix',
        'widget_type': 'chart',
        'chart_type': 'scatter',
        'category': 'profitability',
        'description': 'BCG matrix for product portfolio',
        'icon': '🎨',
        'default_enabled': 0,
        'requires_recipe_data': 1
    },
    {
        'widget_key': 'waste_shrinkage',
        'widget_name': 'Waste & Shrinkage',
        'widget_type': 'chart',
        'chart_type': 'bar',
        'category': 'inventory',
        'description': 'Expected vs actual inventory variance',
        'icon': '🗑️',
        'default_enabled': 0,
        'requires_recipe_data': 1
    },
    {
        'widget_key': 'price_correlation',
        'widget_name': 'Supplier Price Correlation',
        'widget_type': 'chart',
        'chart_type': 'heatmap',
        'category': 'cost',
        'description': 'Correlation matrix of supplier pricing',
        'icon': '🔗',
        'default_enabled': 0,
        'requires_recipe_data': 0
    },
    {
        'widget_key': 'breakeven_analysis',
        'widget_name': 'Break-Even Analysis',
        'widget_type': 'table',
        'chart_type': None,
        'category': 'profitability',
        'description': 'Units needed to break even per product',
        'icon': '⚖️',
        'default_enabled': 0,
        'requires_recipe_data': 1
    },
    {
        'widget_key': 'cost_drivers',
        'widget_name': 'Cost Driver Analysis',
        'widget_type': 'table',
        'chart_type': None,
        'category': 'cost',
        'description': 'Multi-variable regression on cost factors',
        'icon': '🔬',
        'default_enabled': 0,
        'requires_recipe_data': 0
    }
]

def setup_analytics_tables():
    """Create analytics tables in inventory database"""
    conn = sqlite3.connect(INVENTORY_DB)
    cursor = conn.cursor()

    print("=" * 70)
    print("🔧 SETTING UP ANALYTICS INFRASTRUCTURE")
    print("=" * 70)
    print()

    # Create analytics_widgets table
    print("📊 Creating analytics_widgets table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics_widgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            widget_key TEXT UNIQUE NOT NULL,
            widget_name TEXT NOT NULL,
            widget_type TEXT NOT NULL,
            chart_type TEXT,
            category TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            default_enabled INTEGER DEFAULT 1,
            requires_recipe_data INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create user_widget_preferences table
    print("⚙️ Creating user_widget_preferences table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_widget_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            widget_key TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            position INTEGER,
            size TEXT DEFAULT 'medium',
            custom_settings TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (widget_key) REFERENCES analytics_widgets(widget_key)
        )
    """)

    # Create widget_data_cache table
    print("💾 Creating widget_data_cache table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS widget_data_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            widget_key TEXT NOT NULL,
            cache_key TEXT NOT NULL,
            data TEXT NOT NULL,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT
        )
    """)

    # Create index on cache
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_widget_cache
        ON widget_data_cache(widget_key, cache_key, expires_at)
    """)

    conn.commit()

    # Populate widgets
    print("📝 Populating analytics widgets...")
    for widget in WIDGETS:
        cursor.execute("""
            INSERT OR IGNORE INTO analytics_widgets (
                widget_key, widget_name, widget_type, chart_type, category,
                description, icon, default_enabled, requires_recipe_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            widget['widget_key'],
            widget['widget_name'],
            widget['widget_type'],
            widget['chart_type'],
            widget['category'],
            widget['description'],
            widget['icon'],
            widget['default_enabled'],
            widget['requires_recipe_data']
        ))

    conn.commit()

    # Create default user preferences for enabled widgets
    print("👤 Setting up default widget preferences...")
    cursor.execute("DELETE FROM user_widget_preferences WHERE user_id = 'default'")

    position = 0
    for widget in WIDGETS:
        if widget['default_enabled']:
            # Determine size based on widget type
            if widget['chart_type'] in ['scatter', 'heatmap']:
                size = 'large'
            elif widget['widget_type'] == 'table':
                size = 'full-width'
            else:
                size = 'medium'

            cursor.execute("""
                INSERT INTO user_widget_preferences (
                    user_id, widget_key, enabled, position, size
                ) VALUES ('default', ?, 1, ?, ?)
            """, (widget['widget_key'], position, size))
            position += 1

    conn.commit()

    # Summary
    print()
    print("=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)

    cursor.execute("SELECT COUNT(*) FROM analytics_widgets")
    total_widgets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM analytics_widgets WHERE default_enabled = 1")
    enabled_widgets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM user_widget_preferences")
    user_prefs = cursor.fetchone()[0]

    print(f"📊 Total Widgets: {total_widgets}")
    print(f"✅ Default Enabled: {enabled_widgets}")
    print(f"⚙️ User Preferences: {user_prefs}")
    print()

    print("Widget Categories:")
    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM analytics_widgets
        GROUP BY category
        ORDER BY count DESC
    """)

    for row in cursor.fetchall():
        print(f"  • {row[0]}: {row[1]} widgets")

    print()
    print("=" * 70)
    print("✅ ANALYTICS SETUP COMPLETE!")
    print("=" * 70)

    conn.close()

if __name__ == '__main__':
    setup_analytics_tables()
