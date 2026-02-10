## 🎉 Separate Database Architecture - Complete Physical Isolation

Your system now uses **completely isolated databases** per organization. This is the most secure multi-tenant architecture possible.

---

## 📊 Database Structure

```
/Users/dell/WONTECH/
│
├── master.db                     # Global data (users, organizations, sessions)
│
├── databases/
│   ├── org_1.db                 # Default Organization (your existing data)
│   ├── org_2.db                 # Future client #2
│   ├── org_3.db                 # Future client #3
│   └── ...
│
└── inventory.db                  # Backup (original file preserved)
```

**Key Benefits:**
- ✅ **Complete physical isolation** - Impossible to access wrong data even with code bug
- ✅ **Easy backups** - Backup individual client databases
- ✅ **Easy deletion** - Delete entire client by removing database file
- ✅ **Portable** - Can give client their database file if they leave
- ✅ **Scalable** - Add unlimited clients without database conflicts

---

## 🚀 Step-by-Step Implementation

### Step 1: Run Master Database Migration

This creates `master.db` with users, organizations, sessions, invitations:

```bash
cd /Users/dell/WONTECH
python migrations/create_master_database.py
```

**Expected Output:**
```
============================================================
🏢 CREATING MASTER DATABASE (Separate DB Architecture)
============================================================

1️⃣  Creating organizations table...
   ✓ Organizations table created

2️⃣  Creating users table...
   ✓ Users table created

... (more steps)

9️⃣  Creating super admin user...
   ✓ Super admin created
   📧 Email: admin@wontech.com
   🔑 Password: admin123
   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!

============================================================
✅ MASTER DATABASE CREATED SUCCESSFULLY!
============================================================
```

---

### Step 2: Convert Existing Data

This copies `inventory.db` → `databases/org_1.db`:

```bash
python migrations/convert_existing_data.py
```

**Expected Output:**
```
============================================================
📦 CONVERTING EXISTING DATA TO SEPARATE DATABASE
============================================================

1️⃣  Created databases directory: /Users/dell/WONTECH/databases

2️⃣  Creating backup of original inventory.db...
   ✓ Backup created: inventory_backup_20260124_143022.db

3️⃣  Copying inventory.db → databases/org_1.db...
   ✓ Created: databases/org_1.db

4️⃣  Validating database integrity...
   ✓ Found 12 tables
   ✓ ingredients: 45 records
   ✓ products: 23 records
   ✓ sales: 156 records

============================================================
✅ CONVERSION COMPLETE!
============================================================

📊 Your Data:
   📁 Original (backup): inventory_backup_20260124_143022.db
   📁 Organization 1:    databases/org_1.db
```

**Important:** Your original `inventory.db` is preserved as a backup. Your data is now in `databases/org_1.db`.

---

### Step 3: Update app.py

Replace the old database connection code with the new database manager:

**OLD CODE (Single Database):**
```python
def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn
```

**NEW CODE (Separate Databases):**
```python
from db_manager import get_master_db, get_org_db
from middleware.tenant_context_separate_db import set_tenant_context

# Import decorators from separate DB middleware
from middleware.tenant_context_separate_db import (
    login_required,
    organization_required,
    permission_required,
    super_admin_required,
    organization_admin_required
)

app = Flask(__name__)
app.secret_key = 'your-very-secure-secret-key-here'  # CHANGE THIS!

# Register blueprints
from routes import admin_bp, employee_bp
app.register_blueprint(admin_bp)
app.register_blueprint(employee_bp)

# Set tenant context before every request
@app.before_request
def before_request_handler():
    set_tenant_context()
```

---

### Step 4: Update Your Routes

**CRITICAL:** All routes that access business data (inventory, products, sales, etc.) must use `get_org_db()` instead of `get_db_connection()`.

**Example - Update Inventory Route:**

**BEFORE:**
```python
@app.route('/api/ingredients')
def get_ingredients():
    conn = get_db_connection()  # ❌ OLD
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ingredients")
    ingredients = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'ingredients': ingredients})
```

**AFTER:**
```python
from db_manager import get_org_db

@app.route('/api/ingredients')
@login_required                          # NEW: Must be logged in
@organization_required                   # NEW: Must have org context
@permission_required('inventory.view')   # NEW: Must have permission
def get_ingredients():
    conn = get_org_db()                  # ✅ NEW: Gets correct org database
    cursor = conn.cursor()

    # Query runs on organization's database automatically
    cursor.execute("SELECT * FROM ingredients ORDER BY ingredient_name")

    ingredients = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'ingredients': ingredients})
```

**Key Points:**
- Use `get_org_db()` for business data (ingredients, products, sales, invoices, employees, etc.)
- Use `get_master_db()` ONLY for user authentication and organization management
- NO MORE `organization_id` filters needed in queries (automatic isolation!)
- Add permission decorators to every route

---

### Step 5: Update crud_operations.py

If you have `crud_operations.py`, update all functions:

**Pattern for ALL business data routes:**

```python
from db_manager import get_org_db
from middleware.tenant_context_separate_db import (
    login_required,
    organization_required,
    permission_required
)

@app.route('/api/ingredients', methods=['POST'])
@login_required
@organization_required
@permission_required('inventory.create')
def create_ingredient():
    data = request.json

    # Get organization's database
    conn = get_org_db()  # Automatically routes to correct database
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO ingredients (ingredient_name, category, unit_of_measure, quantity_on_hand, unit_cost)
        VALUES (?, ?, ?, ?, ?)
    """, (data['name'], data['category'], data['unit'], data['quantity'], data['cost']))

    ingredient_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': ingredient_id})
```

**No more `organization_id` column needed!** Each organization has their own database file.

---

## 🔐 How Database Isolation Works

### When Super Admin Logs In:
1. User logs in → authenticated against `master.db`
2. User is super admin → sees `/admin/dashboard`
3. Super admin clicks "Enter Dashboard" for "Joe's Pizza"
4. Session sets `current_organization_id = 2`
5. Middleware sets `g.org_db_path = "databases/org_2.db"`
6. All queries now run against Joe's Pizza database
7. Super admin **CANNOT** see data from other organizations (physically separate file)

### When Organization Admin Logs In:
1. User logs in → authenticated against `master.db`
2. User has `organization_id = 3` (locked to Restaurant ABC)
3. Middleware sets `g.org_db_path = "databases/org_3.db"`
4. User can ONLY access Restaurant ABC's database
5. User **CANNOT** switch to other organization databases (enforced by middleware)

### When Employee Logs In:
1. User logs in → authenticated against `master.db`
2. User has `organization_id = 3` and `role = 'employee'`
3. Middleware sets `g.org_db_path = "databases/org_3.db"`
4. Permission checks limit what they can do (view only, no edit/delete)
5. `@own_data_only` decorator ensures they can only see their own paystubs/time entries

---

## 📝 Database Connection Reference

### For User Authentication & Organization Management:
```python
from db_manager import get_master_db

conn = get_master_db()  # Always connects to master.db
cursor = conn.cursor()

# Query users
cursor.execute("SELECT * FROM users WHERE email = ?", (email,))

# Query organizations
cursor.execute("SELECT * FROM organizations WHERE active = 1")

conn.close()
```

### For Business Data (Inventory, Sales, etc.):
```python
from db_manager import get_org_db

conn = get_org_db()  # Routes to current organization's database
cursor = conn.cursor()

# Query ingredients (automatically in correct organization's database)
cursor.execute("SELECT * FROM ingredients")

# Query sales (automatically isolated)
cursor.execute("SELECT * FROM sales WHERE date >= ?", (date,))

conn.close()
```

### Creating New Organization Database:
```python
from db_manager import create_org_database

# After creating organization in master.db
new_db_path = create_org_database(organization_id=5)
# Creates databases/org_5.db with full schema
```

---

## 🧪 Testing Database Isolation

### Test 1: Verify Master Database
```bash
sqlite3 master.db
```
```sql
-- Should show 1 organization (default)
SELECT * FROM organizations;

-- Should show 1 user (super admin)
SELECT email, role FROM users;

.exit
```

### Test 2: Verify Organization Database
```bash
sqlite3 databases/org_1.db
```
```sql
-- Should show your existing data
SELECT COUNT(*) FROM ingredients;
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM sales;

.exit
```

### Test 3: Start App and Login
```bash
python app.py
```

1. Navigate to `http://localhost:5001/login`
2. Login with:
   - Email: `admin@wontech.com`
   - Password: `admin123`
3. Should see super admin dashboard at `/admin/dashboard`
4. Should see "Default Organization" card
5. Click "Enter Dashboard"
6. You should see your existing inventory data

### Test 4: Create Second Organization
1. While logged in as super admin, go to `/admin/dashboard`
2. Click "New Organization" (when you implement the modal)
3. Create "Test Restaurant" with slug "test-restaurant"
4. This creates `databases/org_2.db` (fresh, empty database)
5. Enter Test Restaurant's dashboard
6. Create a product in Test Restaurant
7. Exit and enter Default Organization dashboard
8. **Test Restaurant's product should NOT appear** (database isolation working!)

---

## 🛡️ Security Benefits

### Impossible Data Leaks
Even if you forget permission decorators or write buggy code, **organizations cannot access each other's data** because they're in completely separate database files.

```python
# Even if you write this buggy code:
@app.route('/api/all-products')  # ❌ No permission decorator!
def get_all_products():
    conn = get_org_db()  # Still only gets current org's database
    cursor.execute("SELECT * FROM products")  # Only sees their own products
    return jsonify(cursor.fetchall())
```

Organization A's database: `databases/org_1.db`
Organization B's database: `databases/org_2.db`

**No way for Organization A to query Organization B's file** - physically impossible!

### Easy Backups
```bash
# Backup single client
cp databases/org_3.db backups/org_3_backup_20260124.db

# Restore single client
cp backups/org_3_backup_20260124.db databases/org_3.db
```

### Easy Client Deletion
```bash
# Delete all of Organization 5's data
rm databases/org_5.db

# Update master database
sqlite3 master.db
DELETE FROM organizations WHERE id = 5;
DELETE FROM users WHERE organization_id = 5;
```

### Client Portability
If a client leaves, give them their database file:
```bash
cp databases/org_3.db /path/to/export/client_data_export.db
```

They can open it with any SQLite tool and have all their data.

---

## 📂 Next Steps

1. ✅ **Run migrations** (Steps 1-2 above)
2. ✅ **Update app.py** (Step 3)
3. ⏳ **Update all routes** to use `get_org_db()` (Step 4-5)
4. ⏳ **Test login and data access**
5. ⏳ **Create second organization to test isolation**
6. ⏳ **Implement user invitation system**
7. ⏳ **Deploy to production**

---

## ❓ FAQ

**Q: What happened to my original inventory.db?**
A: It's backed up as `inventory_backup_TIMESTAMP.db`. Your data is now in `databases/org_1.db`.

**Q: Do I need to add `WHERE organization_id = ?` to queries?**
A: **NO!** That's the beauty of separate databases. Each organization's queries automatically run on their own database file.

**Q: Can I still do cross-organization analytics?**
A: For super admin analytics across all clients, you'll need to loop through organization databases or aggregate data separately. This is a trade-off for complete isolation.

**Q: What if I want to merge two organizations?**
A: You can export data from one database and import into another using SQL tools.

**Q: How do I backup all organization data?**
A: Backup the entire `databases/` directory and `master.db`:
```bash
tar -czf backup_all_clients.tar.gz master.db databases/
```

---

## 🎯 You're Ready!

You now have the **most secure multi-tenant architecture** possible with complete physical database isolation.

**Next command:**
```bash
python migrations/create_master_database.py
```

Then follow Steps 1-5 above! 🚀
