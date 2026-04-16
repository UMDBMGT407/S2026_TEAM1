# =========================
# FELICIA PART OF APP.PY
# =========================

# =========================
# APP7.PY  — built on app5_fixed
# Benchmark 2a changes applied
# =========================
#
# ── REQUIRED DB SCHEMA ADDITIONS ────────────────────────────────────────────
#
#   -- 1. Extra columns on inventory_updates (run once):
#   ALTER TABLE inventory_updates
#       ADD COLUMN purchase_order_id INT NULL,
#       ADD COLUMN reason            VARCHAR(255) NULL,
#       ADD FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id);
#
#   -- 2. delivery_audits table (run once):
#   CREATE TABLE IF NOT EXISTS delivery_audits (
#       id                  INT AUTO_INCREMENT PRIMARY KEY,
#       purchase_order_id   INT NOT NULL,
#       inventory_item_id   INT NOT NULL,
#       quantity_ordered     INT NOT NULL,
#       quantity_received    INT NOT NULL,
#       received_by         INT NOT NULL,
#       received_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#       notes               TEXT,
#       FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id),
#       FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id),
#       FOREIGN KEY (received_by)       REFERENCES users(id)
#   );
#
#   -- 3. order_predictions table (from Fix 2, previous session):
#   CREATE TABLE IF NOT EXISTS order_predictions (
#       id                        INT AUTO_INCREMENT PRIMARY KEY,
#       inventory_item_id         INT NOT NULL,
#       prediction_quantity       INT NOT NULL,
#       prediction_order_by_date  DATE NOT NULL,
#       created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#       FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id) ON DELETE CASCADE
#   );
# ────────────────────────────────────────────────────────────────────────────


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
import datetime


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
    """Get the most recent approved audit in the system."""
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
    """Delete all draft audits for this user (audit_items cascade)."""
    cur = mysql.connection.cursor()
    cur.execute(
        "DELETE FROM audits WHERE conducted_by = %s AND status = 'Draft'",
        (user_id,)
    )
    mysql.connection.commit()
    cur.close()


def get_latest_user_visible_audit(user_id):
    """Get the current user's most recent Submitted or Approved audit."""
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
    """
    Create a new draft audit and snapshot all inventory items into it.
    system_qty at snapshot time reflects the current live inventory,
    which already includes any quantities received from purchase orders.
    """
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
    """
    Get all audit line items, optionally filtered by category.
    system_qty is the snapshot captured when the audit was created —
    it equals whatever inventory showed at that moment (post-PO-receiving).
    """
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
    - update live inventory to physical counts
    - write inventory_updates log rows (action_type = 'Audit')
    - mark audit approved
    Activity log shows the conductor, not the approving manager.
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
                    (inventory_item_id, updated_by, action_type, qty_change,
                     old_qty, new_qty, audit_id, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    item['inventory_item_id'],
                    log_user_id,
                    action,
                    diff,
                    old_qty,
                    new_qty,
                    audit_id,
                    'Audit adjustment'
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
    """
    Get paginated activity log rows.
    Shows all sources: manual adjustments, audit corrections, PO receiving.
    """
    offset = (page - 1) * per_page
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM inventory_updates")
    total_rows = cur.fetchone()['total']

    cur.execute(
        """
        SELECT iu.id,
               iu.created_at,
               u.name  AS user_name,
               u.role,
               i.item_name,
               i.category,
               iu.action_type,
               iu.qty_change,
               iu.old_qty,
               iu.new_qty,
               iu.reason,
               iu.audit_id,
               iu.purchase_order_id
        FROM inventory_updates iu
        JOIN users u          ON iu.updated_by       = u.id
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


# ── Helper: Python date → 'm/d/yyyy' string ─────────────────────────────────
def fmt_date(d):
    if d is None:
        return None
    return f"{d.month}/{d.day}/{d.year}"


# ── Helper: distinct category list from inventory_items ─────────────────────
def get_inventory_categories():
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT DISTINCT category FROM inventory_items WHERE category IS NOT NULL ORDER BY category"
    )
    rows = cur.fetchall()
    cur.close()
    return [r['category'] for r in rows]


# =========================
# BASIC ROUTES
# =========================
@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role in ('Manager', 'ShiftLead'):
            return redirect(url_for('inventory'))
        elif current_user.role == 'Employee':
            return redirect(url_for('employee_home'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email    = request.form['email']
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
# MANAGER AUDIT ROUTES
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
    mode     = request.args.get('mode', 'resume')
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
        action   = request.form.get('action')
        save_audit_counts(audit_id, request.form)

        if action == 'submit':
            mark_audit_status(audit_id, 'Submitted')
            return redirect(url_for('man_audit_3', audit_id=audit_id))

        return redirect(url_for('man_audit_1'))

    items      = get_audit_items(audit_id, None if category == 'all' else category)
    categories = get_inventory_categories()

    return render_template(
        'man-audit-2.html',
        audit=audit,
        inventory_items=items,
        selected_category=category,
        categories=categories,
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
    page     = request.args.get('page', 1, type=int)
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
    mode     = request.args.get('mode', 'resume')
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
        action   = request.form.get('action')
        save_audit_counts(audit_id, request.form)

        if action == 'submit':
            mark_audit_status(audit_id, 'Submitted')
            return redirect(url_for('sl_audit_3', audit_id=audit_id))

        return redirect(url_for('sl_audit_1'))

    items      = get_audit_items(audit_id, None if category == 'all' else category)
    categories = get_inventory_categories()

    return render_template(
        'sl-audit-2.html',
        audit=audit,
        inventory_items=items,
        selected_category=category,
        categories=categories,
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
# EMPLOYEE PLACEHOLDER
# =========================
@app.route('/employee-home')
@login_required
@role_required('Employee')
def employee_home():
    return '<h1>Employee home placeholder</h1>'


# =========================
# FULL INVENTORY VIEW
# FIX: category filter + category column in GET
# FIX: POST merged here (no duplicate route)
# =========================
@app.route('/inventory', methods=['GET', 'POST'])
@login_required
@role_required('Manager', 'ShiftLead')
def inventory():
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify(error='JSON required'), 400

        name     = data.get('name', '').strip()
        category = data.get('category', 'Other').strip()

        try:
            qty = max(0, int(data.get('qty', 0)))
        except (ValueError, TypeError):
            return jsonify(error='qty must be an integer'), 400

        if not name:
            return jsonify(error='name is required'), 400

        cur = mysql.connection.cursor()
        try:
            cur.execute(
                "INSERT INTO inventory_items (item_name, category, system_qty) VALUES (%s, %s, %s)",
                (name, category, qty)
            )
            new_id = cur.lastrowid
            mysql.connection.commit()
            return jsonify(message='Item added', id=new_id, name=name, category=category, qty=qty), 201
        except Exception as e:
            return jsonify(error=str(e)), 500
        finally:
            cur.close()

    # ── GET ──────────────────────────────────────────────────────────────────
    # FIX (Felicia + benchmark): category filter + category column
    category_filter = request.args.get('category', 'all')

    cur = mysql.connection.cursor()

    if category_filter and category_filter != 'all':
        cur.execute(
            """
            SELECT id, item_name, category, system_qty, created_at
            FROM inventory_items
            WHERE LOWER(category) = LOWER(%s)
            ORDER BY item_name
            """,
            (category_filter,)
        )
    else:
        cur.execute(
            "SELECT id, item_name, category, system_qty, created_at FROM inventory_items ORDER BY item_name"
        )

    inventory_data = cur.fetchall()
    cur.close()

    categories = get_inventory_categories()

    return render_template(
        'man-full.html',
        inventory=inventory_data,
        categories=categories,
        selected_category=category_filter,
    )


# =========================
# DASHBOARD — enhanced analytics
# FIX: cross-check outgoing vs on-hand; discrepancy summary; PO stats
# =========================
@app.route('/dashboard')
@login_required
@role_required('Manager')
def dashboard():
    cur = mysql.connection.cursor()

    # All inventory with category
    cur.execute("SELECT item_name, category, system_qty FROM inventory_items ORDER BY item_name")
    all_inventory = cur.fetchall()

    # Low-stock alerts (below 10)
    cur.execute(
        "SELECT item_name, category, system_qty FROM inventory_items WHERE system_qty < 10 ORDER BY system_qty"
    )
    restock_items = cur.fetchall()

    # ── Analytics: 30-day window ─────────────────────────────────────────────
    cur.execute(
        """
        SELECT
            SUM(CASE WHEN action_type = 'Receive' THEN  qty_change ELSE 0 END) AS total_received,
            SUM(CASE WHEN action_type = 'Sub'     THEN -qty_change ELSE 0 END) AS total_consumed,
            SUM(CASE WHEN action_type = 'Add'
                      AND purchase_order_id IS NULL
                      AND audit_id          IS NULL THEN qty_change ELSE 0 END) AS total_manual_add,
            COUNT(DISTINCT CASE WHEN action_type = 'Receive'
                                THEN purchase_order_id END)                     AS orders_received
        FROM inventory_updates
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
    )
    movement = cur.fetchone()

    # ── Discrepancy cross-check ───────────────────────────────────────────────
    # How much was physically missing vs what system thought in last approved audit
    cur.execute(
        """
        SELECT
            COUNT(*)                                           AS items_checked,
            SUM(CASE WHEN ai.physical_count < ai.system_qty
                     THEN ai.system_qty - ai.physical_count
                     ELSE 0 END)                              AS total_shrinkage,
            SUM(CASE WHEN ai.physical_count > ai.system_qty
                     THEN ai.physical_count - ai.system_qty
                     ELSE 0 END)                              AS total_surplus,
            SUM(ABS(ai.physical_count - ai.system_qty))       AS total_discrepancy
        FROM audit_items ai
        JOIN audits a ON ai.audit_id = a.id
        WHERE a.status = 'Approved'
          AND a.approved_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
        """
    )
    audit_discrepancy = cur.fetchone()

    # ── PO status counts ─────────────────────────────────────────────────────
    cur.execute(
        """
        SELECT order_status, COUNT(*) AS cnt
        FROM purchase_orders
        GROUP BY order_status
        """
    )
    po_status_rows = cur.fetchall()
    po_stats = {r['order_status']: r['cnt'] for r in po_status_rows}

    # ── Delivery audit discrepancies (ordered vs received) ───────────────────
    cur.execute(
        """
        SELECT COUNT(*) AS delivery_discrepancies
        FROM delivery_audits
        WHERE quantity_received != quantity_ordered
          AND received_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
    )
    delivery_disc_row = cur.fetchone()

    cur.close()

    return render_template(
        'man-dash.html',
        inventory=all_inventory,
        alerts=restock_items,
        movement=movement,
        audit_discrepancy=audit_discrepancy,
        po_stats=po_stats,
        delivery_discrepancies=delivery_disc_row['delivery_discrepancies'],
    )


# =========================
# ANALYTICS API
# Cross-check: units taken out vs units on hand vs audit discrepancies
# =========================
@app.route('/api/analytics')
@login_required
@role_required('Manager')
def api_analytics():
    """
    Returns JSON with:
    - movement_by_category: per-category receive/consume totals (last 30 days)
    - audit_discrepancies:  items that had mismatches in approved audits (last 90 days)
    - delivery_discrepancies: PO ordered vs received mismatches
    - po_fulfillment: rate of POs received vs ordered
    """
    cur = mysql.connection.cursor()

    # Movement broken down by category and action type
    cur.execute(
        """
        SELECT i.category,
               iu.action_type,
               SUM(ABS(iu.qty_change)) AS total_units
        FROM inventory_updates iu
        JOIN inventory_items i ON iu.inventory_item_id = i.id
        WHERE iu.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY i.category, iu.action_type
        ORDER BY i.category, iu.action_type
        """
    )
    movement_rows = cur.fetchall()

    # Build a nested dict: {category: {action_type: units}}
    movement_by_category = {}
    for r in movement_rows:
        cat = r['category'] or 'Uncategorized'
        movement_by_category.setdefault(cat, {})
        movement_by_category[cat][r['action_type']] = int(r['total_units'])

    # Items with audit discrepancies in last 90 days
    cur.execute(
        """
        SELECT i.item_name,
               i.category,
               ai.system_qty,
               ai.physical_count,
               (ai.physical_count - ai.system_qty) AS discrepancy,
               a.approved_at
        FROM audit_items ai
        JOIN inventory_items i ON ai.inventory_item_id = i.id
        JOIN audits a          ON ai.audit_id          = a.id
        WHERE a.status = 'Approved'
          AND a.approved_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
          AND ai.physical_count != ai.system_qty
        ORDER BY ABS(ai.physical_count - ai.system_qty) DESC
        LIMIT 50
        """
    )
    audit_disc_rows = cur.fetchall()
    audit_discrepancies = [
        {
            'item_name':      r['item_name'],
            'category':       r['category'],
            'system_qty':     r['system_qty'],
            'physical_count': r['physical_count'],
            'discrepancy':    int(r['discrepancy']),
            'approved_at':    str(r['approved_at']) if r['approved_at'] else None,
        }
        for r in audit_disc_rows
    ]

    # Delivery discrepancies: what was ordered vs what showed up
    cur.execute(
        """
        SELECT da.purchase_order_id,
               i.item_name,
               i.category,
               da.quantity_ordered,
               da.quantity_received,
               (da.quantity_received - da.quantity_ordered) AS discrepancy,
               da.received_at
        FROM delivery_audits da
        JOIN inventory_items i ON da.inventory_item_id = i.id
        WHERE da.quantity_received != da.quantity_ordered
        ORDER BY da.received_at DESC
        LIMIT 50
        """
    )
    delivery_disc_rows = cur.fetchall()
    delivery_discrepancies = [
        {
            'purchase_order_id': r['purchase_order_id'],
            'item_name':         r['item_name'],
            'category':          r['category'],
            'quantity_ordered':  r['quantity_ordered'],
            'quantity_received': r['quantity_received'],
            'discrepancy':       int(r['discrepancy']),
            'received_at':       str(r['received_at']) if r['received_at'] else None,
        }
        for r in delivery_disc_rows
    ]

    # PO fulfillment rate
    cur.execute(
        "SELECT COUNT(*) AS total FROM purchase_orders"
    )
    total_po = cur.fetchone()['total']

    cur.execute(
        "SELECT COUNT(*) AS received FROM purchase_orders WHERE order_status = 'Received'"
    )
    received_po = cur.fetchone()['received']

    fulfillment_rate = round(received_po / total_po * 100, 1) if total_po > 0 else 0

    cur.close()

    return jsonify({
        'movement_by_category':  movement_by_category,
        'audit_discrepancies':   audit_discrepancies,
        'delivery_discrepancies': delivery_discrepancies,
        'po_fulfillment': {
            'total':    total_po,
            'received': received_po,
            'rate_pct': fulfillment_rate,
        },
    })


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
        data  = request.get_json()
        name  = data.get('name')
        role  = data.get('role')
        phone = data.get('phone')

        if not name or not role:
            return jsonify({"error": "Name and role are required"}), 400

        base_email = name.lower().replace(" ", "") + "@kft.com"

        cur     = mysql.connection.cursor()
        email   = base_email
        counter = 1
        while True:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if not cur.fetchone():
                break
            email = name.lower().replace(" ", "") + str(counter) + "@kft.com"
            counter += 1

        password_hash = generate_password_hash("default123")

        cur.execute(
            "INSERT INTO users (name, email, password, role, phone) VALUES (%s, %s, %s, %s, %s)",
            (name, email, password_hash, role, phone)
        )
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "User added successfully", "email": email, "default_password": "default123"})

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
        data  = request.get_json()
        name  = data.get('name')
        role  = data.get('role')
        phone = data.get('phone')

        cur = mysql.connection.cursor()
        cur.execute(
            "UPDATE users SET name=%s, role=%s, phone=%s WHERE id=%s",
            (name, role, phone, id)
        )
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================
# PREDICTIVE
# =========================

@app.route("/predictive")
@login_required
@role_required('Manager')
def predictive_reports():
    cur = mysql.connection.cursor()
    try:
        cur.execute("SELECT id, drink_name FROM drinks ORDER BY drink_name")
        drinks = cur.fetchall()
        cur.execute("SELECT id, item_name FROM inventory_items ORDER BY item_name")
        inventory_items = cur.fetchall()
    finally:
        cur.close()

    return render_template(
        "man-predictive-7.html",
        drinks=drinks,
        inventory_items=inventory_items
    )


@app.route("/predictive/recipe", methods=['POST'])
@login_required
@role_required('Manager')
def upsert_predictive_recipe():
    if not request.is_json:
        return jsonify({"error": "JSON required"}), 400

    data = request.get_json(silent=True) or {}
    drink_name = (data.get('drink_name') or '').strip()
    products = data.get('products') or []

    if not drink_name:
        return jsonify({"error": "Drink name is required"}), 400
    if not isinstance(products, list) or not products:
        return jsonify({"error": "At least one product is required"}), 400

    cleaned_products = []
    for product in products:
        try:
            inventory_item_id = int(product.get('inventory_item_id'))
        except (TypeError, ValueError, AttributeError):
            return jsonify({"error": "Invalid product selection"}), 400
        try:
            quantity = int(product.get('quantity', 0))
        except (TypeError, ValueError, AttributeError):
            quantity = 0
        cleaned_products.append({
            "inventory_item_id": inventory_item_id,
            "quantity": max(0, quantity)
        })

    # Merge duplicate products by summing quantities.
    deduped_products_by_id = {}
    for product in cleaned_products:
        inventory_item_id = product["inventory_item_id"]
        deduped_products_by_id[inventory_item_id] = (
            deduped_products_by_id.get(inventory_item_id, 0) + product["quantity"]
        )
    deduped_product_ids = list(deduped_products_by_id.keys())

    cur = mysql.connection.cursor()
    try:
        placeholders = ",".join(["%s"] * len(deduped_product_ids))
        cur.execute(
            f"SELECT id FROM inventory_items WHERE id IN ({placeholders})",
            tuple(deduped_product_ids)
        )
        valid_inventory_ids = {row['id'] for row in cur.fetchall()}
        if len(valid_inventory_ids) != len(deduped_product_ids):
            return jsonify({"error": "One or more selected products do not exist"}), 400

        cur.execute(
            "SELECT id FROM drinks WHERE LOWER(drink_name) = LOWER(%s) LIMIT 1",
            (drink_name,)
        )
        existing_drink = cur.fetchone()

        if existing_drink:
            drink_id = existing_drink['id']
            cur.execute(
                "UPDATE drinks SET drink_name = %s WHERE id = %s",
                (drink_name, drink_id)
            )
        else:
            cur.execute(
                "INSERT INTO drinks (drink_name) VALUES (%s)",
                (drink_name,)
            )
            drink_id = cur.lastrowid

        # Overwrite recipe mappings by replacing all ingredient links for this drink.
        cur.execute("DELETE FROM drink_product WHERE drink_id = %s", (drink_id,))

        # Support both schema variants:
        # 1) drink_product(drink_id, inventory_item_id)
        # 2) drink_product(drink_id, inventory_item_id, quantity)
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'drink_product'
              AND COLUMN_NAME = 'quantity'
            """
        )
        has_quantity_column = cur.fetchone()['cnt'] > 0

        for inventory_item_id in deduped_product_ids:
            quantity = deduped_products_by_id[inventory_item_id]
            if has_quantity_column:
                cur.execute(
                    """
                    INSERT INTO drink_product (drink_id, inventory_item_id, quantity)
                    VALUES (%s, %s, %s)
                    """,
                    (drink_id, inventory_item_id, quantity)
                )
            else:
                cur.execute(
                    """
                    INSERT INTO drink_product (drink_id, inventory_item_id)
                    VALUES (%s, %s)
                    """,
                    (drink_id, inventory_item_id)
                )

        mysql.connection.commit()
        return jsonify({
            "message": f"Recipe saved for {drink_name}",
            "drink_id": drink_id,
            "drink_name": drink_name,
            "supports_quantity": has_quantity_column
        }), 200
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()


# =========================
# NATHAN'S PART — PURCHASE ORDERS
# =========================
@app.route('/purchase-orders', methods=['GET'])
@login_required
@role_required('Manager')
def purchaseOrders():
    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT po.id,
               s.supplier_name,
               po.order_date,
               po.expected_date,
               po.received_date,
               po.order_status
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        ORDER BY po.id DESC
        """
    )
    orders_raw = cur.fetchall()

    cur.execute(
        """
        SELECT poi.purchase_order_id,
               ii.item_name,
               poi.quantity
        FROM purchase_order_items poi
        JOIN inventory_items ii ON poi.inventory_item_id = ii.id
        ORDER BY poi.id ASC
        """
    )
    items_raw = cur.fetchall()
    cur.close()

    items_by_order = {}
    for row in items_raw:
        items_by_order.setdefault(row['purchase_order_id'], []).append({
            'name': row['item_name'],
            'qty':  row['quantity']
        })

    orders = []
    for row in orders_raw:
        oid = row['id']
        orders.append({
            'id':            oid,
            'supplier':      row['supplier_name'],
            'order_date':    fmt_date(row['order_date']),
            'expected_date': fmt_date(row['expected_date']),
            'received_date': fmt_date(row['received_date']),
            'status':        row['order_status'],
            'items':         items_by_order.get(oid, [])
        })

    return render_template('purchase_order_info.html', orders=orders)


@app.route('/purchase-orders/<int:order_id>/status', methods=['PATCH'])
@login_required
@role_required('Manager')
def update_order_status(order_id):
    """
    FIX (benchmark): when status → 'Received':
      - auto-apply PO quantities to live inventory
      - log each line in inventory_updates (action_type='Receive')
      - create delivery_audits rows for the delivery audit trail
    This is the missing link between purchase order and inventory.
    """
    if not request.is_json:
        return jsonify(error='JSON required'), 400

    new_status = request.get_json().get('status')
    if new_status not in ('Pending', 'Received', 'Ordered', 'Cancelled'):
        return jsonify(error='Invalid status'), 400

    cur = mysql.connection.cursor()

    # Prevent double-applying if already Received
    cur.execute("SELECT order_status FROM purchase_orders WHERE id = %s", (order_id,))
    current_row = cur.fetchone()
    cur.close()

    if not current_row:
        return jsonify(error='Order not found'), 404

    was_already_received = (current_row['order_status'] == 'Received')

    cur = mysql.connection.cursor()
    if new_status == 'Received':
        cur.execute(
            "UPDATE purchase_orders SET order_status = %s, received_date = CURDATE() WHERE id = %s",
            (new_status, order_id)
        )
    else:
        cur.execute(
            "UPDATE purchase_orders SET order_status = %s, received_date = NULL WHERE id = %s",
            (new_status, order_id)
        )
    mysql.connection.commit()
    cur.close()

    # Apply inventory only once
    if new_status == 'Received' and not was_already_received:
        apply_purchase_order_to_inventory(order_id, current_user.id)

    return jsonify(
        message='Status updated',
        received_date=fmt_date(datetime.date.today()) if new_status == 'Received' else None
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

    cur.execute("SELECT id, supplier_name, supplier_address FROM suppliers ORDER BY supplier_name")
    suppliers = [{'id': r['id'], 'name': r['supplier_name'], 'address': r['supplier_address']}
                 for r in cur.fetchall()]

    cur.execute("SELECT id, item_name FROM inventory_items ORDER BY item_name")
    products = [{'id': r['id'], 'name': r['item_name']} for r in cur.fetchall()]

    cur.close()
    return render_template('create_purchase_order.html', suppliers=suppliers, products=products)


@app.route('/purchase-orders', methods=['POST'])
@login_required
@role_required('Manager')
def submit_purchase_order():
    if not request.is_json:
        return jsonify(error='JSON required'), 400

    data          = request.get_json()
    supplier_id   = data.get('supplier_id')
    order_date    = data.get('date')
    expected_date = data.get('expectedDate') or None
    products_list = data.get('products', [])

    if not supplier_id or not order_date or not products_list:
        return jsonify(error='Supplier, date, and at least one product are required'), 400

    cur = mysql.connection.cursor()

    cur.execute(
        "INSERT INTO purchase_orders (supplier_id, order_date, expected_date, order_status) VALUES (%s, %s, %s, 'Pending')",
        (supplier_id, order_date, expected_date)
    )
    new_order_id = cur.lastrowid

    for item in products_list:
        inventory_item_id = item.get('product_id')
        qty               = item.get('qty', 0)
        if inventory_item_id and qty:
            cur.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity) VALUES (%s, %s, %s)",
                (new_order_id, inventory_item_id, qty)
            )

    cur.execute("SELECT supplier_name FROM suppliers WHERE id = %s", (supplier_id,))
    supplier_row  = cur.fetchone()
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


# =========================
# LEON
# =========================

# ── NEW: apply a received purchase order to live inventory ───────────────────
def apply_purchase_order_to_inventory(order_id, received_by_user_id):
    """
    When a PO is marked Received:
      1. For each line item, add the ordered quantity to system_qty.
      2. Write an inventory_updates row (action_type='Receive').
      3. Write a delivery_audits row recording ordered vs received qty.

    This closes the loop: PO → inventory → activity log → delivery audit.
    quantity_received is set equal to quantity_ordered by default (no
    partial-delivery UI yet); the delivery_audits table stores both so
    future partial-delivery support only needs a UI change, not a schema
    change.
    """
    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT poi.inventory_item_id,
               poi.quantity          AS qty_ordered,
               ii.system_qty        AS current_qty,
               ii.item_name
        FROM purchase_order_items poi
        JOIN inventory_items ii ON poi.inventory_item_id = ii.id
        WHERE poi.purchase_order_id = %s
        """,
        (order_id,)
    )
    items = cur.fetchall()

    for item in items:
        old_qty     = int(item['current_qty'])
        ordered_qty = int(item['qty_ordered'])
        new_qty     = old_qty + ordered_qty

        # 1. Update live inventory
        cur.execute(
            "UPDATE inventory_items SET system_qty = %s WHERE id = %s",
            (new_qty, item['inventory_item_id'])
        )

        # 2. Log the receive event
        cur.execute(
            """
            INSERT INTO inventory_updates
                (inventory_item_id, updated_by, action_type, qty_change,
                 old_qty, new_qty, purchase_order_id, reason)
            VALUES (%s, %s, 'Receive', %s, %s, %s, %s, %s)
            """,
            (
                item['inventory_item_id'],
                received_by_user_id,
                ordered_qty,
                old_qty,
                new_qty,
                order_id,
                f'PO #{order_id} received'
            )
        )

        # 3. Delivery audit row (ordered == received until partial-delivery UI added)
        cur.execute(
            """
            INSERT INTO delivery_audits
                (purchase_order_id, inventory_item_id,
                 quantity_ordered, quantity_received, received_by)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (order_id, item['inventory_item_id'], ordered_qty, ordered_qty, received_by_user_id)
        )

    mysql.connection.commit()
    cur.close()


# =========================
# DELIVERY AUDIT PAGES
# =========================
@app.route('/delivery-audit')
@login_required
@role_required('Manager')
def delivery_audit_list():
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT po.id,
               s.supplier_name,
               po.order_date,
               po.expected_date,
               po.received_date,
               po.order_status,
               COUNT(da.id) AS audit_line_count
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        LEFT JOIN delivery_audits da ON da.purchase_order_id = po.id
        GROUP BY po.id, s.supplier_name, po.order_date,
                 po.expected_date, po.received_date, po.order_status
        ORDER BY po.id DESC
        """
    )
    orders_raw = cur.fetchall()
    cur.close()

    orders = []
    for row in orders_raw:
        orders.append({
            'id':               row['id'],
            'supplier':         row['supplier_name'],
            'order_date':       fmt_date(row['order_date']),
            'expected_date':    fmt_date(row['expected_date']),
            'received_date':    fmt_date(row['received_date']),
            'status':           row['order_status'],
            'audit_line_count': row['audit_line_count'],
            'has_audit':        row['audit_line_count'] > 0,
        })

    return render_template('delivery_audit.html', orders=orders, order=None)


@app.route('/delivery-audit/<int:order_id>', methods=['GET', 'POST'])
@login_required
@role_required('Manager')
def delivery_audit_detail(order_id):
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT po.id,
               po.order_status,
               po.order_date,
               po.expected_date,
               po.received_date,
               s.supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.id = %s
        """,
        (order_id,)
    )
    order = cur.fetchone()

    if not order:
        cur.close()
        return 'Order not found', 404

    if request.method == 'POST':
        cur.execute(
            """
            SELECT poi.inventory_item_id,
                   poi.quantity AS qty_ordered,
                   da.id AS delivery_audit_id,
                   da.quantity_received AS qty_received_existing
            FROM purchase_order_items poi
            LEFT JOIN delivery_audits da
                   ON da.purchase_order_id = poi.purchase_order_id
                  AND da.inventory_item_id = poi.inventory_item_id
            WHERE poi.purchase_order_id = %s
            """,
            (order_id,)
        )
        line_items = cur.fetchall()

        try:
            for item in line_items:
                iid = item['inventory_item_id']
                qty_ordered = int(item['qty_ordered'])
                old_received = int(item['qty_received_existing'] or 0)
                raw = request.form.get(f'qty_received_{iid}', str(qty_ordered))

                try:
                    new_received = max(0, int(raw))
                except (ValueError, TypeError):
                    new_received = old_received

                delta = new_received - old_received

                if item['delivery_audit_id']:
                    cur.execute(
                        """
                        UPDATE delivery_audits
                        SET quantity_ordered = %s,
                            quantity_received = %s,
                            received_by = %s,
                            received_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (qty_ordered, new_received, current_user.id, item['delivery_audit_id'])
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO delivery_audits
                            (purchase_order_id, inventory_item_id, quantity_ordered, quantity_received, received_by)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (order_id, iid, qty_ordered, new_received, current_user.id)
                    )

                if delta != 0:
                    cur.execute("SELECT system_qty FROM inventory_items WHERE id = %s", (iid,))
                    inv_row = cur.fetchone()
                    if not inv_row:
                        raise ValueError(f'Inventory item {iid} not found')

                    old_qty = int(inv_row['system_qty'])
                    new_qty = old_qty + delta
                    if new_qty < 0:
                        raise ValueError('Delivery audit adjustment would make inventory negative')

                    cur.execute(
                        "UPDATE inventory_items SET system_qty = %s WHERE id = %s",
                        (new_qty, iid)
                    )

                    action_type = 'Receive' if delta > 0 else 'Audit'
                    reason = (
                        f'Delivery audit submitted for PO #{order_id}'
                        if old_received == 0 and delta > 0
                        else f'Delivery audit adjustment for PO #{order_id}'
                    )

                    cur.execute(
                        """
                        INSERT INTO inventory_updates
                            (inventory_item_id, updated_by, action_type, qty_change,
                             old_qty, new_qty, purchase_order_id, reason)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (iid, current_user.id, action_type, delta, old_qty, new_qty, order_id, reason)
                    )

            if order['order_status'] != 'Received':
                cur.execute(
                    "UPDATE purchase_orders SET order_status = 'Received', received_date = CURDATE() WHERE id = %s",
                    (order_id,)
                )

            mysql.connection.commit()
        except Exception:
            mysql.connection.rollback()
            cur.close()
            raise

        cur.close()
        return redirect(url_for('delivery_audit_list'))

    cur.execute(
        """
        SELECT poi.inventory_item_id,
               i.item_name,
               i.category,
               poi.quantity AS qty_ordered,
               da.quantity_received AS qty_received,
               da.received_at
        FROM purchase_order_items poi
        JOIN inventory_items i ON poi.inventory_item_id = i.id
        LEFT JOIN delivery_audits da
               ON da.purchase_order_id = poi.purchase_order_id
              AND da.inventory_item_id = poi.inventory_item_id
        WHERE poi.purchase_order_id = %s
        ORDER BY i.item_name
        """,
        (order_id,)
    )
    line_items = cur.fetchall()
    cur.close()

    order_data = {
        'id':            order['id'],
        'status':        order['order_status'],
        'supplier':      order['supplier_name'],
        'order_date':    fmt_date(order['order_date']),
        'expected_date': fmt_date(order['expected_date']),
        'received_date': fmt_date(order['received_date']),
    }

    return render_template('delivery_audit.html', order=order_data, line_items=line_items)


# =========================
# DELIVERY AUDIT API
# FIX (Felicia): delivery audit — see what was ordered vs received per PO
# =========================
@app.route('/api/delivery-audit/<int:order_id>')
@login_required
@role_required('Manager')
def get_delivery_audit(order_id):
    """
    Returns the delivery audit for a specific purchase order:
    - what was ordered (from purchase_order_items)
    - what was recorded as received (from delivery_audits)
    - any discrepancies between them
    This gives visibility into the receiving process end-to-end.
    """
    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT po.id             AS order_id,
               po.order_status,
               po.order_date,
               po.expected_date,
               po.received_date,
               s.supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.id = %s
        """,
        (order_id,)
    )
    order = cur.fetchone()

    if not order:
        cur.close()
        return jsonify(error='Order not found'), 404

    cur.execute(
        """
        SELECT poi.inventory_item_id,
               i.item_name,
               i.category,
               poi.quantity                                    AS qty_ordered,
               COALESCE(da.quantity_received, NULL)            AS qty_received,
               COALESCE(da.quantity_received - poi.quantity, NULL) AS discrepancy
        FROM purchase_order_items poi
        JOIN inventory_items i  ON poi.inventory_item_id = i.id
        LEFT JOIN delivery_audits da
               ON da.purchase_order_id = poi.purchase_order_id
              AND da.inventory_item_id = poi.inventory_item_id
        WHERE poi.purchase_order_id = %s
        ORDER BY i.item_name
        """,
        (order_id,)
    )
    line_items = cur.fetchall()
    cur.close()

    return jsonify({
        'order': {
            'id':            order['order_id'],
            'status':        order['order_status'],
            'supplier':      order['supplier_name'],
            'order_date':    fmt_date(order['order_date']),
            'expected_date': fmt_date(order['expected_date']),
            'received_date': fmt_date(order['received_date']),
        },
        'line_items': [
            {
                'item_name':    r['item_name'],
                'category':     r['category'],
                'qty_ordered':  r['qty_ordered'],
                'qty_received': r['qty_received'],     # NULL if not yet received
                'discrepancy':  int(r['discrepancy']) if r['discrepancy'] is not None else None,
            }
            for r in line_items
        ],
        'fully_received': order['order_status'] == 'Received',
    })


# =========================
# SUPPLIERS
# =========================
@app.route('/suppliers', methods=['POST'])
@login_required
@role_required('Manager')
def add_supplier():
    data    = request.get_json()
    name    = data.get('name')
    address = data.get('address')

    if not name:
        return jsonify(error='Supplier name is required'), 400

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO suppliers (supplier_name, supplier_address) VALUES (%s, %s)",
        (name, address)
    )
    mysql.connection.commit()
    new_id = cur.lastrowid
    cur.close()

    return jsonify(message='Supplier added', id=new_id, name=name, address=address), 200


@app.route('/suppliers/<int:id>', methods=['PATCH'])
@login_required
@role_required('Manager')
def edit_supplier(id):
    data    = request.get_json()
    name    = data.get('name')
    address = data.get('address')

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE suppliers SET supplier_name = %s, supplier_address = %s WHERE id = %s",
        (name, address, id)
    )
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

    if result and result['count'] > 0:
        cur.close()
        return jsonify(error='Cannot delete a supplier that is used by purchase orders.'), 400

    cur.execute("DELETE FROM suppliers WHERE id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    return jsonify(message='Supplier deleted'), 200


# =========================
# INVENTORY CRUD API
# =========================
@app.route('/inventory/<int:item_id>', methods=['PATCH'])
@login_required
@role_required('Manager', 'ShiftLead')
def update_inventory_item(item_id):
    """
    Manual quantity adjustment.
    FIX (benchmark): now accepts optional 'reason' field so outgoing usage
    (consumed items) can be labelled — connects manual deductions to the system.
    """
    data = request.get_json()
    if not data:
        return jsonify(error='JSON required'), 400

    action = data.get('action')
    reason = data.get('reason', '').strip() or None   # e.g. 'Used in shift', 'Spoilage'

    try:
        qty = int(data.get('qty', 0))
    except (ValueError, TypeError):
        return jsonify(error='qty must be an integer'), 400

    if qty <= 0:
        return jsonify(error='qty must be positive'), 400
    if action not in ('add', 'subtract'):
        return jsonify(error='action must be add or subtract'), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, system_qty FROM inventory_items WHERE id = %s", (item_id,))
    item = cur.fetchone()

    if not item:
        cur.close()
        return jsonify(error='Item not found'), 404

    old_qty = item['system_qty']

    if action == 'add':
        new_qty     = old_qty + qty
        action_type = 'Add'
        qty_change  = qty
    else:
        new_qty = old_qty - qty
        if new_qty < 0:
            cur.close()
            return jsonify(error='Not enough inventory'), 400
        action_type = 'Sub'
        qty_change  = -qty

    cur.execute(
        "UPDATE inventory_items SET system_qty = %s WHERE id = %s",
        (new_qty, item_id)
    )
    cur.execute(
        """
        INSERT INTO inventory_updates
            (inventory_item_id, updated_by, action_type, qty_change, old_qty, new_qty, reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (item_id, current_user.id, action_type, qty_change, old_qty, new_qty, reason)
    )

    mysql.connection.commit()
    cur.close()

    return jsonify(message='Updated', new_qty=new_qty), 200


@app.route('/inventory/<int:item_id>', methods=['DELETE'])
@login_required
@role_required('Manager', 'ShiftLead')
def delete_inventory_item(item_id):
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt FROM audit_items ai
            JOIN audits a ON ai.audit_id = a.id
            WHERE ai.inventory_item_id = %s AND a.status IN ('Submitted', 'Approved')
            """,
            (item_id,)
        )
        if cur.fetchone()['cnt'] > 0:
            return jsonify(error='Cannot delete: item is in a submitted or approved audit.'), 400

        cur.execute(
            "SELECT COUNT(*) AS cnt FROM purchase_order_items WHERE inventory_item_id = %s",
            (item_id,)
        )
        if cur.fetchone()['cnt'] > 0:
            return jsonify(error='Cannot delete: item is referenced in a purchase order.'), 400

        cur.execute("DELETE FROM inventory_items WHERE id = %s", (item_id,))
        mysql.connection.commit()
        return jsonify(message='Item deleted'), 200
    finally:
        cur.close()


# =========================
# PREDICTIVE REPORTS API
# =========================
@app.route('/api/predictions')
@login_required
@role_required('Manager')
def api_predictions():
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            """
            SELECT i.item_name, i.system_qty,
                   op.prediction_quantity, op.prediction_order_by_date
            FROM order_predictions op
            JOIN inventory_items i ON op.inventory_item_id = i.id
            ORDER BY op.prediction_order_by_date ASC, i.item_name
            """
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    today  = datetime.date.today()
    result = []
    for r in rows:
        days   = (r['prediction_order_by_date'] - today).days
        status = 'Critical' if days <= 1 else ('Low' if days <= 5 else 'In Stock')
        result.append({
            'item_name':           r['item_name'],
            'system_qty':          r['system_qty'],
            'prediction_quantity': r['prediction_quantity'],
            'order_by_date':       fmt_date(r['prediction_order_by_date']),
            'status':              status,
        })
    return jsonify(result)


# =========================
# RUN APP
# =========================
if __name__ == '__main__':
    app.run(debug=True)
