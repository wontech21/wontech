# Multi-Tenant Implementation Guide

This guide shows how to integrate the three-tier access control system into your existing FIRINGup application.

## Table of Contents
1. [Run Database Migration](#1-run-database-migration)
2. [Update app.py](#2-update-apppy)
3. [Add Permission Checks to Existing Routes](#3-add-permission-checks-to-existing-routes)
4. [Update Dashboard Template](#4-update-dashboard-template)
5. [Create Authentication Routes](#5-create-authentication-routes)
6. [Testing the System](#6-testing-the-system)

---

## 1. Run Database Migration

First, run the multi-tenancy migration to set up the database schema:

```bash
cd /Users/dell/FIRINGup
python migrations/add_multi_tenancy.py
```

This will:
- Create organizations, users, permissions tables
- Add organization_id to all existing tables
- Create default organization and super admin user
- Set up three-tier role system

**Default super admin credentials:**
- Email: `admin@firingup.com`
- Password: `admin123`
- **⚠️ CHANGE THIS IMMEDIATELY AFTER FIRST LOGIN!**

---

## 2. Update app.py

Add these imports and modifications to your existing `app.py`:

### Add Imports (Top of file)

```python
from flask import Flask, g, session, request
from middleware import set_tenant_context, login_required, permission_required
from routes import admin_bp

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure random key

# Register admin blueprint
app.register_blueprint(admin_bp)
```

### Add Before Request Hook

```python
@app.before_request
def before_request_handler():
    """Run before every request - sets up tenant context and user"""
    set_tenant_context()
```

### Example: Update an Existing Route

**Before (no permissions):**
```python
@app.route('/api/products')
def get_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()
    return jsonify(products)
```

**After (with multi-tenant support and permissions):**
```python
@app.route('/api/products')
@login_required
@organization_required
@permission_required('products.view')
def get_products():
    conn = get_db_connection()
    cursor = conn.cursor()

    # CRITICAL: Filter by organization_id
    cursor.execute("""
        SELECT * FROM products
        WHERE organization_id = ?
        ORDER BY name ASC
    """, (g.organization['id'],))

    products = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'products': products})
```

**Key Changes:**
1. Added `@login_required` - User must be logged in
2. Added `@organization_required` - Organization context must be set
3. Added `@permission_required('products.view')` - User must have this permission
4. Added `WHERE organization_id = ?` - Filter by current organization
5. Use `g.organization['id']` - Access current organization from Flask's g object

---

## 3. Add Permission Checks to Existing Routes

Update all your existing routes following this pattern:

### Inventory Routes

```python
# View inventory
@app.route('/api/ingredients')
@login_required
@organization_required
@permission_required('inventory.view')
def get_ingredients():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM ingredients
        WHERE organization_id = ?
    """, (g.organization['id'],))
    ingredients = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'ingredients': ingredients})

# Create inventory item
@app.route('/api/ingredients', methods=['POST'])
@login_required
@organization_required
@permission_required('inventory.create')
def create_ingredient():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    # CRITICAL: Set organization_id when creating
    cursor.execute("""
        INSERT INTO ingredients (organization_id, name, category, unit, quantity, cost_per_unit)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (g.organization['id'], data['name'], data['category'], data['unit'], data['quantity'], data['cost_per_unit']))

    conn.commit()
    ingredient_id = cursor.lastrowid
    conn.close()

    return jsonify({'success': True, 'id': ingredient_id})

# Edit inventory item
@app.route('/api/ingredients/<int:id>', methods=['PUT'])
@login_required
@organization_required
@permission_required('inventory.edit')
def update_ingredient(id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    # CRITICAL: Verify ownership before updating
    cursor.execute("""
        UPDATE ingredients
        SET name = ?, category = ?, unit = ?, quantity = ?, cost_per_unit = ?
        WHERE id = ? AND organization_id = ?
    """, (data['name'], data['category'], data['unit'], data['quantity'], data['cost_per_unit'], id, g.organization['id']))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

# Delete inventory item
@app.route('/api/ingredients/<int:id>', methods=['DELETE'])
@login_required
@organization_required
@permission_required('inventory.delete')
def delete_ingredient(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # CRITICAL: Verify ownership before deleting
    cursor.execute("""
        DELETE FROM ingredients
        WHERE id = ? AND organization_id = ?
    """, (id, g.organization['id']))

    conn.commit()
    conn.close()

    return jsonify({'success': True})
```

### Sales Routes

```python
@app.route('/api/sales', methods=['POST'])
@login_required
@organization_required
@permission_required('sales.create')
def record_sale():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sales (organization_id, product_id, quantity, sale_price, date)
        VALUES (?, ?, ?, ?, ?)
    """, (g.organization['id'], data['product_id'], data['quantity'], data['sale_price'], data['date']))

    conn.commit()
    sale_id = cursor.lastrowid
    conn.close()

    return jsonify({'success': True, 'id': sale_id})
```

### Products & Recipes Routes

```python
@app.route('/api/products')
@login_required
@organization_required
@permission_required('products.view')
def get_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM products
        WHERE organization_id = ?
    """, (g.organization['id'],))
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'products': products})

@app.route('/api/products', methods=['POST'])
@login_required
@organization_required
@permission_required('products.create')
def create_product():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products (organization_id, name, selling_price)
        VALUES (?, ?, ?)
    """, (g.organization['id'], data['name'], data['selling_price']))

    product_id = cursor.lastrowid

    # Add recipe items (if any)
    if 'recipe' in data:
        for item in data['recipe']:
            cursor.execute("""
                INSERT INTO recipes (organization_id, product_id, ingredient_id, quantity)
                VALUES (?, ?, ?, ?)
            """, (g.organization['id'], product_id, item['ingredient_id'], item['quantity']))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': product_id})
```

---

## 4. Update Dashboard Template

Add the tenant switcher component to your main dashboard template:

**In `templates/dashboard.html`**, add this at the top of the `<body>` tag:

```html
<body>
    <!-- Include tenant switcher for super admin -->
    {% include 'components/tenant_switcher.html' %}

    <!-- Rest of your dashboard HTML -->
    <div class="dashboard-container">
        ...
    </div>
</body>
```

Also add the admin CSS to the `<head>`:

```html
<head>
    <meta charset="UTF-8">
    <title>Dashboard - FIRINGup</title>
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="stylesheet" href="/static/css/admin.css">
</head>
```

---

## 5. Create Authentication Routes

Add these authentication routes to `app.py`:

```python
import hashlib
import secrets

def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def verify_password(password, password_hash):
    """Verify password against hash"""
    try:
        salt, pwd_hash = password_hash.split('$')
        test_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return test_hash == pwd_hash
    except:
        return False

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    data = request.json
    email = data.get('email')
    password = data.get('password')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, organization_id, password_hash, role, active
        FROM users
        WHERE email = ?
    """, (email,))

    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user['active']:
        return jsonify({'error': 'Account is inactive'}), 403

    if not verify_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid credentials'}), 401

    # Set session
    session['user_id'] = user['id']

    # For non-super admin, set organization context immediately
    if user['role'] != 'super_admin':
        session['current_organization_id'] = user['organization_id']

    return jsonify({
        'success': True,
        'redirect': '/admin/dashboard' if user['role'] == 'super_admin' else '/dashboard'
    })

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
def index():
    """Redirect to appropriate dashboard based on user role"""
    if 'user_id' not in session:
        return redirect('/login')

    if g.is_super_admin:
        return redirect('/admin/dashboard')
    else:
        return redirect('/dashboard')
```

---

## 6. Testing the System

### Step 1: Run Migration

```bash
python migrations/add_multi_tenancy.py
```

### Step 2: Start Flask Application

```bash
python app.py
```

### Step 3: Login as Super Admin

1. Navigate to `http://localhost:5001/login`
2. Login with:
   - Email: `admin@firingup.com`
   - Password: `admin123`
3. You should be redirected to `/admin/dashboard`

### Step 4: Create a Test Organization

1. Click "New Organization" button
2. Fill in:
   - Organization Name: "Test Restaurant"
   - Slug: "test-restaurant"
   - Owner Name: "John Doe"
   - Owner Email: "john@test.com"
   - Plan Type: "basic"
3. Create organization

### Step 5: Invite Organization Admin

1. Find the "Test Restaurant" card
2. Click "Enter Dashboard"
3. You should now be viewing Test Restaurant's dashboard
4. Notice the breadcrumb: "Super Admin → Test Restaurant"
5. Notice the tenant switcher in top-right corner

### Step 6: Test Organization Isolation

1. Create a product in Test Restaurant
2. Exit organization (click "Exit Organization" button)
3. Create another organization "Restaurant 2"
4. Enter Restaurant 2's dashboard
5. You should NOT see Test Restaurant's products (data isolation working!)

### Step 7: Test Permission System

To test permissions, you'll need to create users with different roles.

**Create Organization Admin User:**
```sql
INSERT INTO users
(organization_id, email, password_hash, first_name, last_name, role, permissions, active)
VALUES
(1, 'admin@testrestaurant.com', 'HASH_HERE', 'Jane', 'Admin', 'organization_admin',
 '["inventory.*", "employees.*", "payroll.*", "sales.*", "products.*", "invoices.*", "reports.*", "settings.*", "users.*"]', 1);
```

**Create Employee User:**
```sql
INSERT INTO users
(organization_id, email, password_hash, first_name, last_name, role, permissions, active)
VALUES
(1, 'employee@testrestaurant.com', 'HASH_HERE', 'Bob', 'Employee', 'employee',
 '["inventory.view", "inventory.count", "timeclock.clockin", "payroll.view_own"]', 1);
```

Then logout and login with each user to verify permissions are enforced.

---

## Permission Matrix

| Permission | Super Admin | Org Admin | Employee |
|------------|-------------|-----------|----------|
| `inventory.view` | ✅ | ✅ | ✅ |
| `inventory.create` | ✅ | ✅ | ❌ |
| `inventory.edit` | ✅ | ✅ | ❌ |
| `inventory.delete` | ✅ | ✅ | ❌ |
| `inventory.count` | ✅ | ✅ | ✅ |
| `employees.view` | ✅ | ✅ | ❌ |
| `employees.create` | ✅ | ✅ | ❌ |
| `employees.view_own` | ✅ | ✅ | ✅ |
| `payroll.process` | ✅ | ✅ | ❌ |
| `payroll.view_own` | ✅ | ✅ | ✅ |
| `sales.create` | ✅ | ✅ | ✅ |
| `sales.delete` | ✅ | ✅ | ❌ |
| `products.view` | ✅ | ✅ | ✅ |
| `products.create` | ✅ | ✅ | ❌ |
| `users.create` | ✅ | ✅ | ❌ |
| `settings.edit` | ✅ | ✅ | ❌ |

---

## Common Patterns

### Pattern 1: Simple View Route
```python
@app.route('/api/entity')
@login_required
@organization_required
@permission_required('entity.view')
def get_entities():
    cursor.execute("SELECT * FROM entity WHERE organization_id = ?", (g.organization['id'],))
```

### Pattern 2: Create Route
```python
@app.route('/api/entity', methods=['POST'])
@login_required
@organization_required
@permission_required('entity.create')
def create_entity():
    cursor.execute(
        "INSERT INTO entity (organization_id, ...) VALUES (?, ...)",
        (g.organization['id'], ...)
    )
```

### Pattern 3: Update/Delete Route
```python
@app.route('/api/entity/<int:id>', methods=['PUT'])
@login_required
@organization_required
@permission_required('entity.edit')
def update_entity(id):
    cursor.execute(
        "UPDATE entity SET ... WHERE id = ? AND organization_id = ?",
        (..., id, g.organization['id'])
    )
```

### Pattern 4: Employee Self-Service Route
```python
from middleware import own_data_only

@app.route('/api/employees/<int:id>/paystubs')
@login_required
@organization_required
@permission_required('payroll.view_own')
@own_data_only('employee', 'id')
def get_own_paystubs(id):
    # Employee can only access if id matches their employee record
    cursor.execute("""
        SELECT * FROM paychecks
        WHERE employee_id = ? AND organization_id = ?
    """, (id, g.organization['id']))
```

---

## Security Checklist

Before deploying to production:

- [ ] Change super admin password from default
- [ ] Use strong, random `app.secret_key`
- [ ] Enable HTTPS/SSL
- [ ] Set up proper session timeout
- [ ] Review all queries include `organization_id` filter
- [ ] Test permission enforcement for all roles
- [ ] Set up audit logging for sensitive actions
- [ ] Configure proper CORS headers
- [ ] Enable rate limiting for API routes
- [ ] Set up monitoring for failed login attempts

---

## Troubleshooting

### Issue: "Organization context required" error
**Solution:** Make sure route has `@organization_required` decorator and user has selected an organization.

### Issue: User can see data from other organizations
**Solution:** You forgot to add `WHERE organization_id = ?` filter to a query. Review all database queries.

### Issue: Super admin can't switch organizations
**Solution:** Verify user has `can_switch_organizations = 1` in database.

### Issue: Employee can access admin features
**Solution:** Check permission decorators are applied to routes and user's `permissions` field in database.

---

## Next Steps

1. **Employee Portal**: Build self-service portal for employees (clock in/out, view paystubs)
2. **Invitation System**: Allow organization admins to invite users
3. **Payroll Integration**: Integrate with Gusto for tax filing
4. **Subdomain Routing**: Configure wildcard DNS and SSL for `*.firingup.com`
5. **Mobile App**: Build mobile app for barcode scanning and inventory management
6. **Reporting Dashboard**: Add organization-specific analytics and reports

---

## Support

For questions or issues, refer to:
- Database schema: `/Users/dell/FIRINGup/migrations/add_multi_tenancy.py`
- Middleware: `/Users/dell/FIRINGup/middleware/tenant_context.py`
- Admin routes: `/Users/dell/FIRINGup/routes/admin_routes.py`
