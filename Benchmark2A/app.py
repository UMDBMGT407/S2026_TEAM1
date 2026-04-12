# =========================
# FELICIA PART OF APP.PY
# =========================

# =========================
# IMPORTS
# =========================
from flask import Flask, request, render_template, redirect, url_for, abort, jsonify
from flask_mysqldb import MySQL
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
    UserMixin
)
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps


# =========================
# CREATE FLASK APP
# =========================
app = Flask(__name__)
app.secret_key = '407TEAM1'


# =========================
# MYSQL CONFIGURATION
# =========================
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '407TEAM1'
app.config['MYSQL_DB'] = 'kft_inventory'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)


# =========================
# FLASK-LOGIN SETUP
# =========================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# =========================
# USER CLASS
# =========================
class User(UserMixin):
    def __init__(self, id, name, email, password, role):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.role = role


# =========================
# ROLE CHECK DECORATOR
# =========================
def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                return abort(403)
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper


# =========================
# LOAD USER FROM SESSION
# =========================
@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id, name, email, password, role FROM users WHERE id = %s",
        (user_id,)
    )
    user_data = cur.fetchone()
    cur.close()

    if user_data:
        return User(**user_data)
    return None


# =========================
# HELPER FUNCTIONS
# =========================
def get_latest_approved_audit():
    """
    Get the most recent approved audit in the system.
    Conducted by can be either manager or shift lead.
    """
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT a.id,
               a.status,
               a.created_at,
               a.submitted_at,
               a.approved_at,
               a.conducted_by,
               a.approved_by,
               conductor.name AS conducted_by_name,
               conductor.role AS conducted_by_role,
               approver.name AS approved_by_name
        FROM audits a
        JOIN users conductor ON a.conducted_by = conductor.id
        LEFT JOIN users approver ON a.approved_by = approver.id
        WHERE a.status = 'Approved'
        ORDER BY COALESCE(a.approved_at, a.created_at) DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    cur.close()
    return row


def get_user_draft_audit(user_id):
    """Get the current user's latest draft audit."""
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT id, status, created_at, submitted_at, approved_at
        FROM audits
        WHERE conducted_by = %s
          AND status = 'Draft'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,)
    )
    row = cur.fetchone()
    cur.close()
    return row


def delete_user_draft_audit(user_id):
    """
    Delete all draft audits for this user before creating a new one.
    audit_items will also be deleted because of ON DELETE CASCADE.
    """
    cur = mysql.connection.cursor()
    cur.execute(
        """
        DELETE FROM audits
        WHERE conducted_by = %s
          AND status = 'Draft'
        """,
        (user_id,)
    )
    mysql.connection.commit()
    cur.close()


def get_latest_user_visible_audit(user_id):
    """
    Get the current user's most recent audit that is either
    Submitted or Approved. Draft audits are excluded.
    """
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT a.id,
               a.status,
               a.created_at,
               a.submitted_at,
               a.approved_at,
               u.name AS conducted_by_name
        FROM audits a
        JOIN users u ON a.conducted_by = u.id
        WHERE a.conducted_by = %s
          AND a.status IN ('Submitted', 'Approved')
        ORDER BY COALESCE(a.submitted_at, a.approved_at, a.created_at) DESC
        LIMIT 1
        """,
        (user_id,)
    )
    row = cur.fetchone()
    cur.close()
    return row


def get_pending_submitted_audit():
    """Get the oldest submitted audit waiting for manager approval."""
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT a.id,
               a.status,
               a.created_at,
               a.submitted_at,
               conductor.name AS conducted_by_name,
               conductor.role AS conducted_by_role
        FROM audits a
        JOIN users conductor ON a.conducted_by = conductor.id
        WHERE a.status = 'Submitted'
        ORDER BY COALESCE(a.submitted_at, a.created_at) ASC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    cur.close()
    return row


def create_audit(user_id):
    """Create a new draft audit and copy all inventory items into it."""
    cur = mysql.connection.cursor()

    cur.execute(
        "INSERT INTO audits (conducted_by, status) VALUES (%s, 'Draft')",
        (user_id,)
    )
    audit_id = cur.lastrowid

    cur.execute("SELECT id, system_qty FROM inventory_items ORDER BY item_name")
    inventory_rows = cur.fetchall()

    for item in inventory_rows:
        cur.execute(
            """
            INSERT INTO audit_items (audit_id, inventory_item_id, system_qty, physical_count)
            VALUES (%s, %s, %s, %s)
            """,
            (audit_id, item['id'], item['system_qty'], item['system_qty'])
        )

    mysql.connection.commit()
    cur.close()
    return audit_id


def get_audit(audit_id):
    """Get one audit header plus conductor/approver names."""
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT a.id,
               a.status,
               a.created_at,
               a.submitted_at,
               a.approved_at,
               a.conducted_by,
               a.approved_by,
               conductor.name AS conducted_by_name,
               conductor.role AS conducted_by_role,
               approver.name AS approved_by_name
        FROM audits a
        JOIN users conductor ON a.conducted_by = conductor.id
        LEFT JOIN users approver ON a.approved_by = approver.id
        WHERE a.id = %s
        """,
        (audit_id,)
    )
    row = cur.fetchone()
    cur.close()
    return row


def get_audit_items(audit_id, category=None):
    """Get all audit line items, optionally filtered by category."""
    cur = mysql.connection.cursor()

    if category and category != 'all':
        cur.execute(
            """
            SELECT ai.id,
                   ai.audit_id,
                   ai.inventory_item_id,
                   ai.system_qty,
                   ai.physical_count,
                   i.item_name,
                   i.category,
                   (ai.physical_count - ai.system_qty) AS difference_qty
            FROM audit_items ai
            JOIN inventory_items i ON ai.inventory_item_id = i.id
            WHERE ai.audit_id = %s
              AND LOWER(i.category) = LOWER(%s)
            ORDER BY i.item_name
            """,
            (audit_id, category)
        )
    else:
        cur.execute(
            """
            SELECT ai.id,
                   ai.audit_id,
                   ai.inventory_item_id,
                   ai.system_qty,
                   ai.physical_count,
                   i.item_name,
                   i.category,
                   (ai.physical_count - ai.system_qty) AS difference_qty
            FROM audit_items ai
            JOIN inventory_items i ON ai.inventory_item_id = i.id
            WHERE ai.audit_id = %s
            ORDER BY i.item_name
            """,
            (audit_id,)
        )

    rows = cur.fetchall()
    cur.close()
    return rows


def save_audit_counts(audit_id, form_data):
    """Save the entered physical counts for an audit."""
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id, inventory_item_id, system_qty FROM audit_items WHERE audit_id = %s",
        (audit_id,)
    )
    items = cur.fetchall()

    for item in items:
        raw_value = form_data.get(
            f"physical_count_{item['inventory_item_id']}",
            item['system_qty']
        )
        physical_count = int(raw_value) if raw_value not in [None, ''] else 0

        cur.execute(
            "UPDATE audit_items SET physical_count = %s WHERE id = %s",
            (physical_count, item['id'])
        )

    mysql.connection.commit()
    cur.close()


def mark_audit_status(audit_id, status):
    """Change audit status to Draft or Submitted."""
    cur = mysql.connection.cursor()

    if status == 'Submitted':
        cur.execute(
            "UPDATE audits SET status = 'Submitted', submitted_at = NOW() WHERE id = %s",
            (audit_id,)
        )
    elif status == 'Draft':
        cur.execute(
            "UPDATE audits SET status = 'Draft' WHERE id = %s",
            (audit_id,)
        )

    mysql.connection.commit()
    cur.close()


def get_audit_summary(audit_id):
    """Build summary data for audit summary pages."""
    audit = get_audit(audit_id)
    items = get_audit_items(audit_id)
    discrepancies = sum(1 for item in items if int(item['difference_qty']) != 0)

    return {
        'audit': audit,
        'items': items,
        'total_items_checked': len(items),
        'discrepancies_found': discrepancies,
    }


def approve_audit(audit_id, manager_id):
    """
    Approve an audit:
    - update live inventory
    - write activity log rows
    - mark audit approved

    IMPORTANT:
    Activity log should show the person who conducted the audit,
    not the manager who approved it.
    """
    audit = get_audit(audit_id)

    if not audit or audit['status'] != 'Submitted':
        return False

    items = get_audit_items(audit_id)
    cur = mysql.connection.cursor()

    log_user_id = audit['conducted_by']

    for item in items:
        old_qty = int(item['system_qty'])
        new_qty = int(item['physical_count'])
        diff = new_qty - old_qty

        cur.execute(
            "UPDATE inventory_items SET system_qty = %s WHERE id = %s",
            (new_qty, item['inventory_item_id'])
        )

        if diff != 0:
            action = 'Add' if diff > 0 else 'Sub'

            cur.execute(
                """
                INSERT INTO inventory_updates
                    (inventory_item_id, updated_by, action_type, qty_change, old_qty, new_qty, audit_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    item['inventory_item_id'],
                    log_user_id,
                    action,
                    diff,
                    old_qty,
                    new_qty,
                    audit_id
                )
            )

        cur.execute(
            "UPDATE audit_items SET system_qty = %s WHERE id = %s",
            (new_qty, item['id'])
        )

    cur.execute(
        """
        UPDATE audits
        SET status = 'Approved',
            approved_by = %s,
            approved_at = NOW()
        WHERE id = %s
        """,
        (manager_id, audit_id)
    )

    mysql.connection.commit()
    cur.close()
    return True


def get_activity_log(page=1, per_page=10):
    """Get paginated activity log rows."""
    offset = (page - 1) * per_page
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM inventory_updates")
    total_rows = cur.fetchone()['total']

    cur.execute(
        """
        SELECT iu.id,
               iu.created_at,
               u.name AS user_name,
               u.role,
               i.item_name,
               iu.action_type,
               iu.qty_change
        FROM inventory_updates iu
        JOIN users u ON iu.updated_by = u.id
        JOIN inventory_items i ON iu.inventory_item_id = i.id
        ORDER BY iu.created_at DESC, iu.id DESC
        LIMIT %s OFFSET %s
        """,
        (per_page, offset)
    )
    rows = cur.fetchall()
    cur.close()

    total_pages = (total_rows + per_page - 1) // per_page
    return rows, total_pages


def audit_access_allowed(audit, user):
    """Manager can view all audits. Shift lead only their own."""
    if not audit:
        return False

    if user.role == 'Manager':
        return True

    return audit['conducted_by'] == int(user.id)


# ── Helper: Python date → 'm/d/yyyy' string ─────────────────
def fmt_date(d):
    if d is None:
        return None
    return f"{d.month}/{d.day}/{d.year}"


# =========================
# BASIC ROUTES
# =========================
@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'Manager':
            return redirect(url_for('inventory'))
        elif current_user.role == 'ShiftLead':
            return redirect(url_for('inventory'))
        elif current_user.role == 'Employee':
            return redirect(url_for('inventory'))

    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, name, email, password, role FROM users WHERE email = %s",
            (email,)
        )
        user_data = cur.fetchone()
        cur.close()

        if user_data and check_password_hash(user_data['password'], password):
            user = User(**user_data)
            login_user(user)
            return redirect(url_for('home'))

        return render_template('login.html', error='Invalid email or password.')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# =========================
# MANAGER ROUTES
# =========================
@app.route('/man-audit-1')
@login_required
@role_required('Manager')
def man_audit_1():
    return render_template(
        'man-audit-1.html',
        last_audit=get_latest_approved_audit(),
        pending_audit=get_pending_submitted_audit(),
        draft_audit=get_user_draft_audit(current_user.id),
    )


@app.route('/man-audit-2', methods=['GET', 'POST'])
@login_required
@role_required('Manager')
def man_audit_2():
    audit_id = request.args.get('audit_id', type=int)
    mode = request.args.get('mode', 'resume')
    category = request.args.get('category', 'all')

    if not audit_id:
        draft = get_user_draft_audit(current_user.id)

        if mode == 'new':
            if draft:
                delete_user_draft_audit(current_user.id)
            audit_id = create_audit(current_user.id)
        elif draft:
            audit_id = draft['id']
        else:
            audit_id = create_audit(current_user.id)

    audit = get_audit(audit_id)

    if not audit_access_allowed(audit, current_user):
        abort(403)

    if request.method == 'POST':
        audit_id = request.form.get('audit_id', type=int)
        action = request.form.get('action')

        save_audit_counts(audit_id, request.form)

        if action == 'submit':
            mark_audit_status(audit_id, 'Submitted')
            return redirect(url_for('man_audit_3', audit_id=audit_id))

        return redirect(url_for('man_audit_1'))

    items = get_audit_items(audit_id, None if category == 'all' else category)

    return render_template(
        'man-audit-2.html',
        audit=audit,
        inventory_items=items,
        selected_category=category,
    )


@app.route('/man-audit-3', methods=['GET', 'POST'])
@login_required
@role_required('Manager')
def man_audit_3():
    audit_id = request.args.get('audit_id', type=int)

    if not audit_id:
        pending = get_pending_submitted_audit()
        if pending:
            audit_id = pending['id']
        else:
            draft = get_user_draft_audit(current_user.id)
            if draft:
                audit_id = draft['id']

    if not audit_id:
        return redirect(url_for('man_audit_1'))

    audit = get_audit(audit_id)

    if not audit_access_allowed(audit, current_user):
        abort(403)

    if request.method == 'POST' and request.form.get('action') == 'approve':
        approve_audit(audit_id, current_user.id)
        return redirect(url_for('man_audit_1'))

    summary = get_audit_summary(audit_id)
    return render_template('man-audit-3.html', **summary)


@app.route('/man-audit-4')
@login_required
@role_required('Manager')
def man_audit_4():
    page = request.args.get('page', 1, type=int)
    per_page = 10

    activity_rows, total_pages = get_activity_log(page, per_page)

    return render_template(
        'man-audit-4.html',
        activity_rows=activity_rows,
        current_page=page,
        total_pages=total_pages
    )


# =========================
# SHIFT LEAD ROUTES
# =========================
@app.route('/sl-audit-1')
@login_required
@role_required('ShiftLead')
def sl_audit_1():
    return render_template(
        'sl-audit-1.html',
        last_audit=get_latest_user_visible_audit(current_user.id),
        draft_audit=get_user_draft_audit(current_user.id),
    )


@app.route('/sl-audit-2', methods=['GET', 'POST'])
@login_required
@role_required('ShiftLead')
def sl_audit_2():
    audit_id = request.args.get('audit_id', type=int)
    mode = request.args.get('mode', 'resume')
    category = request.args.get('category', 'all')

    if not audit_id:
        draft = get_user_draft_audit(current_user.id)

        if mode == 'new':
            if draft:
                delete_user_draft_audit(current_user.id)
            audit_id = create_audit(current_user.id)
        elif draft:
            audit_id = draft['id']
        else:
            audit_id = create_audit(current_user.id)

    audit = get_audit(audit_id)

    if not audit_access_allowed(audit, current_user):
        abort(403)

    if request.method == 'POST':
        audit_id = request.form.get('audit_id', type=int)
        action = request.form.get('action')

        save_audit_counts(audit_id, request.form)

        if action == 'submit':
            mark_audit_status(audit_id, 'Submitted')
            return redirect(url_for('sl_audit_3', audit_id=audit_id))

        return redirect(url_for('sl_audit_1'))

    items = get_audit_items(audit_id, None if category == 'all' else category)

    return render_template(
        'sl-audit-2.html',
        audit=audit,
        inventory_items=items,
        selected_category=category,
    )


@app.route('/sl-audit-3')
@login_required
@role_required('ShiftLead')
def sl_audit_3():
    audit_id = request.args.get('audit_id', type=int)

    if not audit_id:
        draft = get_user_draft_audit(current_user.id)
        if draft:
            audit_id = draft['id']
        else:
            return redirect(url_for('sl_audit_1'))

    audit = get_audit(audit_id)

    if not audit_access_allowed(audit, current_user):
        abort(403)

    summary = get_audit_summary(audit_id)
    return render_template('sl-audit-3.html', **summary)


# =========================
# FULL INVENTORY VIEW
# =========================

@app.route('/inventory')
@login_required
def inventory():

    cur = mysql.connection.cursor()
    
    cur.execute("SELECT item_name, system_qty, created_at FROM inventory_items")
    inventory_data = cur.fetchall()
    
    cur.close()

    return render_template('man-full.html', inventory=inventory_data)


# =========================
# DASHBOARD
# =========================

@app.route('/dashboard')
@login_required
@role_required('Manager')
def dashboard():

    cur = mysql.connection.cursor()

    cur.execute("SELECT item_name, system_qty FROM inventory_items")
    all_inventory = cur.fetchall()

    cur.execute("SELECT item_name, system_qty FROM inventory_items WHERE system_qty < 10")
    restock_items = cur.fetchall()

    cur.close()

    return render_template('man-dash.html', 
                           inventory=all_inventory, 
                           alerts=restock_items)


# =========================
# MICHELLE PART
# =========================
@app.route('/manage-users')
@login_required
@role_required('Manager')
def manage_users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, role, phone FROM users ORDER BY name ASC")
    users = cur.fetchall()
    cur.close()

    return render_template('man-5.html', users=users)


@app.route('/user', methods=['POST'])
@login_required
@role_required('Manager')
def add_user():
    try:
        data = request.get_json()

        name = data.get('name')
        role = data.get('role')
        phone = data.get('phone')

        if not name or not role:
            return jsonify({"error": "Name and role are required"}), 400

        base_email = name.lower().replace(" ", "") + "@kft.com"

        cur = mysql.connection.cursor()

        email = base_email
        counter = 1
        while True:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing = cur.fetchone()
            if not existing:
                break
            email = name.lower().replace(" ", "") + str(counter) + "@kft.com"
            counter += 1

        password_hash = generate_password_hash("default123")

        cur.execute(
            """
            INSERT INTO users (name, email, password, role, phone)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, email, password_hash, role, phone)
        )
        mysql.connection.commit()
        cur.close()

        return jsonify({
            "message": "User added successfully",
            "email": email,
            "default_password": "default123"
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/user/<int:id>', methods=['DELETE'])
@login_required
@role_required('Manager')
def delete_user(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (id,))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/user/<int:id>', methods=['PUT'])
@login_required
@role_required('Manager')
def update_user(id):
    try:
        data = request.get_json()

        name = data.get('name')
        role = data.get('role')
        phone = data.get('phone')

        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE users
            SET name=%s, role=%s, phone=%s
            WHERE id=%s
        """, (name, role, phone, id))

        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/predictive")
@login_required
@role_required('Manager')
def predictive_reports():
    return render_template("man-predictive-7.html")


# =========================
# NATHAN'S PART
# =========================
@app.route('/purchase-orders', methods=['GET'])
@login_required
@role_required('Manager')
def purchaseOrders():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            po.id,
            s.supplier_name,
            po.order_date,
            po.expected_date,
            po.received_date,
            po.order_status
        FROM purchase_orders po
        JOIN suppliers s
            ON po.supplier_id = s.id
        ORDER BY po.id DESC
    """)
    orders_raw = cur.fetchall()

    cur.execute("""
        SELECT
            poi.purchase_order_id,
            ii.item_name,
            poi.quantity
        FROM purchase_order_items poi
        JOIN inventory_items ii
            ON poi.inventory_item_id = ii.id
        ORDER BY poi.id ASC
    """)
    items_raw = cur.fetchall()
    cur.close()

    items_by_order = {}
    for row in items_raw:
        order_id = row['purchase_order_id']
        product_name = row['item_name']
        quantity = row['quantity']

        items_by_order.setdefault(order_id, []).append({
            'name': product_name,
            'qty': quantity
        })

    orders = []
    for row in orders_raw:
        oid = row['id']
        supplier = row['supplier_name']
        order_date = row['order_date']
        expected_date = row['expected_date']
        received_date = row['received_date']
        status = row['order_status']

        orders.append({
            'id': oid,
            'supplier': supplier,
            'order_date': fmt_date(order_date),
            'expected_date': fmt_date(expected_date),
            'received_date': fmt_date(received_date),
            'status': status,
            'items': items_by_order.get(oid, [])
        })

    return render_template('purchase_order_info.html', orders=orders)


@app.route('/purchase-orders/<int:order_id>/status', methods=['PATCH'])
@login_required
@role_required('Manager')
def update_order_status(order_id):
    if not request.is_json:
        return jsonify(error='JSON required'), 400

    new_status = request.get_json().get('status')
    if new_status not in ('Pending', 'Received', 'Ordered', 'Cancelled'):
        return jsonify(error='Invalid status'), 400

    cur = mysql.connection.cursor()

    if new_status == 'Received':
        cur.execute("""
            UPDATE purchase_orders
            SET order_status = %s,
                received_date = CURDATE()
            WHERE id = %s
        """, (new_status, order_id))
    else:
        cur.execute("""
            UPDATE purchase_orders
            SET order_status = %s,
                received_date = NULL
            WHERE id = %s
        """, (new_status, order_id))

    mysql.connection.commit()
    cur.close()

    return jsonify(
        message='Status updated',
        received_date=fmt_date(__import__('datetime').date.today()) if new_status == 'Received' else None
    ), 200


@app.route('/purchase-orders/<int:order_id>', methods=['DELETE'])
@login_required
@role_required('Manager')
def delete_purchase_order(order_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM purchase_order_items WHERE purchase_order_id = %s", (order_id,))
    cur.execute("DELETE FROM purchase_orders WHERE id = %s", (order_id,))
    mysql.connection.commit()
    cur.close()

    return jsonify(message='Order deleted'), 200


@app.route('/purchase-orders/new', methods=['GET'])
@login_required
@role_required('Manager')
def create_purchase_order_page():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, supplier_name, supplier_address
        FROM suppliers
        ORDER BY supplier_name
    """)
    suppliers = [
        {
            'id': row['id'],
            'name': row['supplier_name'],
            'address': row['supplier_address']
        }
        for row in cur.fetchall()
    ]

    cur.execute("""
        SELECT id, item_name
        FROM inventory_items
        ORDER BY item_name
    """)
    products = [
        {
            'id': row['id'],
            'name': row['item_name']
        }
        for row in cur.fetchall()
    ]

    cur.close()

    return render_template(
        'create_purchase_order.html',
        suppliers=suppliers,
        products=products
    )


@app.route('/purchase-orders', methods=['POST'])
@login_required
@role_required('Manager')
def submit_purchase_order():
    if not request.is_json:
        return jsonify(error='JSON required'), 400

    data = request.get_json()
    supplier_id = data.get('supplier_id')
    order_date = data.get('date')
    expected_date = data.get('expectedDate') or None
    products_list = data.get('products', [])

    if not supplier_id or not order_date or not products_list:
        return jsonify(error='Supplier, date, and at least one product are required'), 400

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO purchase_orders (supplier_id, order_date, expected_date, order_status)
        VALUES (%s, %s, %s, 'Pending')
    """, (supplier_id, order_date, expected_date))

    new_order_id = cur.lastrowid

    for item in products_list:
        inventory_item_id = item.get('product_id')
        qty = item.get('qty', 0)

        if inventory_item_id and qty:
            cur.execute("""
                INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
                VALUES (%s, %s, %s)
            """, (new_order_id, inventory_item_id, qty))

    cur.execute("SELECT supplier_name FROM suppliers WHERE id = %s", (supplier_id,))
    supplier_row = cur.fetchone()
    supplier_name = supplier_row['supplier_name'] if supplier_row else ''

    mysql.connection.commit()
    cur.close()

    return jsonify(
        message='Order created',
        order_id=new_order_id,
        supplier=supplier_name,
        order_date=order_date,
        expected_date=expected_date
    ), 201


@app.route('/suppliers', methods=['POST'])
@login_required
@role_required('Manager')
def add_supplier():
    data = request.get_json()
    name = data.get('name')
    address = data.get('address')

    if not name:
        return jsonify(error='Supplier name is required'), 400

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO suppliers (supplier_name, supplier_address)
        VALUES (%s, %s)
    """, (name, address))

    mysql.connection.commit()
    new_id = cur.lastrowid
    cur.close()

    return jsonify(
        message='Supplier added',
        id=new_id,
        name=name,
        address=address
    ), 200


@app.route('/suppliers/<int:id>', methods=['PATCH'])
@login_required
@role_required('Manager')
def edit_supplier(id):
    data = request.get_json()
    name = data.get('name')
    address = data.get('address')

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE suppliers
        SET supplier_name = %s,
            supplier_address = %s
        WHERE id = %s
    """, (name, address, id))
    mysql.connection.commit()
    cur.close()

    return jsonify({"message": "updated"})

@app.route('/suppliers/<int:id>', methods=['DELETE'])
@login_required
@role_required('Manager')
def delete_supplier(id):
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) AS count FROM purchase_orders WHERE supplier_id = %s", (id,))
    result = cur.fetchone()
    count = result['count'] if result else 0

    if count > 0:
        cur.close()
        return jsonify(error='Cannot delete a supplier that is used by purchase orders.'), 400

    cur.execute("DELETE FROM suppliers WHERE id = %s", (id,))
    mysql.connection.commit()
    cur.close()

    return jsonify(message='Supplier deleted'), 200

# =========================
# RUN APP
# =========================
if __name__ == '__main__':
    app.run(debug=True)

# =========================
# RUN APP
# =========================
if __name__ == '__main__':
    app.run(debug=True)
