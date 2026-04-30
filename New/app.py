# =========================
# FELICIA PART OF APP.PY
# =========================

# =========================
# IMPORTS
# =========================
from flask import Flask, request, render_template, redirect, url_for, abort, jsonify, Response
try:
    import MySQLdb
except ImportError:
    import pymysql

    pymysql.install_as_MySQLdb()
    import MySQLdb
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
import json
from datetime import datetime, timedelta
#predictive imports
from decimal import Decimal, InvalidOperation
import math
import lightgbm as lgb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import nnls
import datetime as dt
import io
import zipfile
import xml.etree.ElementTree as ET

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
          AND conductor.role = 'ShiftLead'
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


def get_projected_low_items(limit=None):
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT i.id,
               i.item_name,
               i.category,
               i.system_qty,
               latest_prediction.prediction_quantity,
               latest_prediction.prediction_order_by_date,
               latest_prediction.prediction_date_created
        FROM inventory_items i
        JOIN (
            SELECT op.inventory_item_id,
                   op.prediction_quantity,
                   op.prediction_order_by_date,
                   op.prediction_date_created
            FROM order_predictions op
            JOIN (
                SELECT inventory_item_id, MAX(prediction_date_created) AS latest_created
                FROM order_predictions
                GROUP BY inventory_item_id
            ) newest_prediction
                ON newest_prediction.inventory_item_id = op.inventory_item_id
               AND newest_prediction.latest_created = op.prediction_date_created
        ) latest_prediction
            ON latest_prediction.inventory_item_id = i.id
        WHERE latest_prediction.prediction_order_by_date IS NOT NULL
        ORDER BY latest_prediction.prediction_order_by_date ASC, i.item_name ASC
        """
    )
    rows = cur.fetchall()
    cur.close()

    today = dt.date.today()
    projected_items = []
    for row in rows:
        order_by_date = row['prediction_order_by_date']
        projected_stockout_date = order_by_date + dt.timedelta(days=PREDICTIVE_SHIP_TIME_DAYS)
        days_until_stockout = (projected_stockout_date - today).days

        if days_until_stockout <= PREDICTIVE_SHIP_TIME_DAYS:
            status_label = 'Critical'
            status_class = 'critical'
            pill_class = 'red'
        elif days_until_stockout <= PREDICTIVE_LOW_STOCK_THRESHOLD_DAYS:
            status_label = 'Low'
            status_class = 'warning'
            pill_class = 'gold'
        else:
            continue

        projected_items.append({
            'id': row['id'],
            'item_name': row['item_name'],
            'category': row['category'],
            'system_qty': round(float(row['system_qty'] or 0.0), 4),
            'prediction_quantity': round(float(row['prediction_quantity'] or 0.0), 4),
            'order_by_date': fmt_date(order_by_date),
            'stockout_date': fmt_date(projected_stockout_date),
            'days_until_stockout': days_until_stockout,
            'status_label': status_label,
            'status_class': status_class,
            'pill_class': pill_class,
        })

    return projected_items[:limit] if limit else projected_items


# =========================
# BASIC ROUTES
# =========================
@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'Manager':
            return redirect(url_for('firstdash'))
        elif current_user.role == 'ShiftLead':
            return redirect(url_for('shiftlead_dashboard'))
        elif current_user.role == 'Employee':
            return redirect(url_for('employee_dashboard'))

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

@app.route('/firstdash')
@login_required
@role_required('Manager')
def firstdash():
    projected_low_items = get_projected_low_items()
    low_count = len(projected_low_items)
    lowest_items = projected_low_items[:4]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT COUNT(*) AS pending_delivery_count
        FROM purchase_orders po
        LEFT JOIN delivery_audits da ON da.purchase_order_id = po.id
        WHERE po.order_status = 'Received'
        GROUP BY po.id
        HAVING COUNT(da.id) = 0
    """)
    pending_delivery_count = len(cur.fetchall())

    cur.execute("""
        SELECT po.id
        FROM purchase_orders po
        LEFT JOIN delivery_audits da ON da.purchase_order_id = po.id
        WHERE po.order_status = 'Received'
        GROUP BY po.id
        HAVING COUNT(da.id) = 0
        ORDER BY po.received_date DESC, po.id DESC
        LIMIT 1
    """)
    pending_delivery = cur.fetchone()

    last_audit = get_latest_approved_audit()
    pending_audit = get_pending_submitted_audit()
    manager_draft_audit = get_user_draft_audit(current_user.id)

    cur.execute("""
        SELECT i.item_name, SUM(ABS(iu.qty_change)) AS used_qty
        FROM inventory_updates iu
        JOIN inventory_items i ON iu.inventory_item_id = i.id
        WHERE iu.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        GROUP BY i.id, i.item_name
        ORDER BY used_qty DESC
        LIMIT 3
    """)
    top_used_items = cur.fetchall()

    cur.execute("""
        SELECT DAYNAME(iu.created_at) AS day_name,
               SUM(ABS(iu.qty_change)) AS total_used
        FROM inventory_updates iu
        WHERE iu.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        GROUP BY DAYNAME(iu.created_at), DAYOFWEEK(iu.created_at)
        ORDER BY DAYOFWEEK(iu.created_at)
    """)
    usage_trend = cur.fetchall()

    cur.close()

    usage_points = []
    usage_trend_points = ""

    if usage_trend:
        max_used = max(int(row['total_used']) for row in usage_trend) or 1
        x_start = 40
        x_gap = 640 / max(len(usage_trend) - 1, 1)

        for index, row in enumerate(usage_trend):
            x = x_start + index * x_gap
            y = 220 - ((int(row['total_used']) / max_used) * 170)
            usage_points.append({
                "x": round(x, 1),
                "y": round(y, 1),
                "label": row['day_name'][:3]
            })

        usage_trend_points = " ".join(
            f"{point['x']},{point['y']}" for point in usage_points
        )

    return render_template(
        'firstdash.html',
        low_count=low_count,
        lowest_items=lowest_items,
        pending_delivery_count=pending_delivery_count,
        pending_delivery=pending_delivery,
        last_audit=last_audit,
        pending_audit=pending_audit,
        manager_draft_audit=manager_draft_audit,
        top_used_items=top_used_items,
        usage_points=usage_points,
        usage_trend_points=usage_trend_points
    )

@app.route('/employee-dashboard')
@login_required
@role_required('Employee')
def employee_dashboard():
    projected_low_items = get_projected_low_items()
    low_count = len(projected_low_items)
    lowest_items = projected_low_items[:10]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT i.item_name, SUM(ABS(iu.qty_change)) AS used_qty
        FROM inventory_updates iu
        JOIN inventory_items i ON iu.inventory_item_id = i.id
        WHERE iu.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        GROUP BY i.id, i.item_name
        ORDER BY used_qty DESC
        LIMIT 10
    """)
    top_used_items = cur.fetchall()

    top_item = top_used_items[0]['item_name'] if top_used_items else 'N/A'
    lowest_item = lowest_items[0]['item_name'] if lowest_items else 'N/A'

    cur.execute("""
        SELECT DAYNAME(iu.created_at) AS day_name,
               SUM(ABS(iu.qty_change)) AS total_used
        FROM inventory_updates iu
        WHERE iu.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        GROUP BY DAYNAME(iu.created_at), DAYOFWEEK(iu.created_at)
        ORDER BY DAYOFWEEK(iu.created_at)
    """)
    usage_trend = cur.fetchall()

    cur.close()

    usage_points = []
    usage_trend_points = ""

    if usage_trend:
        max_used = max(int(row['total_used']) for row in usage_trend) or 1
        x_start = 40
        x_gap = 640 / max(len(usage_trend) - 1, 1)

        for index, row in enumerate(usage_trend):
            x = x_start + index * x_gap
            y = 220 - ((int(row['total_used']) / max_used) * 170)
            usage_points.append({
                "x": round(x, 1),
                "y": round(y, 1),
                "label": row['day_name'][:3]
            })

        usage_trend_points = " ".join(
            f"{point['x']},{point['y']}" for point in usage_points
        )

    return render_template(
        'employee-dashboard.html',
        low_count=low_count,
        lowest_items=lowest_items,
        top_used_items=top_used_items,
        top_item=top_item,
        lowest_item=lowest_item,
        usage_points=usage_points,
        usage_trend_points=usage_trend_points
    )

@app.route('/shiftlead-dashboard')
@login_required
@role_required('ShiftLead')
def shiftlead_dashboard():
    projected_low_items = get_projected_low_items()
    low_count = len(projected_low_items)
    lowest_items = projected_low_items[:3]

    cur = mysql.connection.cursor()

    # Pending delivery audits
    cur.execute("""
        SELECT COUNT(*) AS pending_delivery_count
        FROM purchase_orders po
        LEFT JOIN delivery_audits da ON da.purchase_order_id = po.id
        WHERE po.order_status = 'Received'
        GROUP BY po.id
        HAVING COUNT(da.id) = 0
    """)
    pending_rows = cur.fetchall()
    pending_delivery_count = len(pending_rows)

    # Most recent received PO needing audit
    cur.execute("""
        SELECT po.id
        FROM purchase_orders po
        LEFT JOIN delivery_audits da ON da.purchase_order_id = po.id
        WHERE po.order_status = 'Received'
        GROUP BY po.id
        HAVING COUNT(da.id) = 0
        ORDER BY po.received_date DESC, po.id DESC
        LIMIT 1
    """)
    pending_delivery = cur.fetchone()

    # Draft audit for this shift lead
    draft_audit = get_user_draft_audit(current_user.id)
    audit_status = "Active" if draft_audit else "None"

    # Top used items from activity log this week
    cur.execute("""
        SELECT i.item_name, SUM(ABS(iu.qty_change)) AS used_qty
        FROM inventory_updates iu
        JOIN inventory_items i ON iu.inventory_item_id = i.id
        WHERE iu.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        GROUP BY i.id, i.item_name
        ORDER BY used_qty DESC
        LIMIT 3
    """)
    top_used_items = cur.fetchall()

    top_item = top_used_items[0]['item_name'] if top_used_items else 'N/A'

    # Usage trend by day this week
    cur.execute("""
        SELECT DAYNAME(iu.created_at) AS day_name,
               SUM(ABS(iu.qty_change)) AS total_used
        FROM inventory_updates iu
        WHERE iu.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        GROUP BY DAYNAME(iu.created_at), DAYOFWEEK(iu.created_at)
        ORDER BY DAYOFWEEK(iu.created_at)
    """)
    usage_trend = cur.fetchall()

    cur.close()

    return render_template(
        'shiftlead-dashboard.html',
        low_count=low_count,
        lowest_items=lowest_items,
        pending_delivery_count=pending_delivery_count,
        pending_delivery=pending_delivery,
        draft_audit=draft_audit,
        audit_status=audit_status,
        top_used_items=top_used_items,
        top_item=top_item,
        usage_trend=usage_trend
    )
# =========================
# MANAGER ROUTES
# =========================
@app.route('/man-audit-1')
@login_required
@role_required('Manager')
def man_audit_1():
    return render_template(
        'man-audit-1.html',
        current_step=1,
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

    # POST: save or submit the SAME audit
    if request.method == 'POST':
        audit_id = request.form.get('audit_id', type=int)
        action = request.form.get('action')

        save_audit_counts(audit_id, request.form)

        if action == 'submit':
            mark_audit_status(audit_id, 'Submitted')
            return redirect(url_for('man_audit_3', audit_id=audit_id))

        return redirect(url_for('man_audit_2', audit_id=audit_id, category=category))

    # GET: if audit_id is provided, use that audit
    if audit_id:
        audit = get_audit(audit_id)

    else:
        draft = get_user_draft_audit(current_user.id)

        # IMPORTANT:
        # Even if mode='new', reuse existing draft first.
        # Only create a new audit if no draft exists.
        if draft:
            audit_id = draft['id']
        else:
            audit_id = create_audit(current_user.id)

        audit = get_audit(audit_id)

    if not audit_access_allowed(audit, current_user):
        abort(403)

    items = get_audit_items(audit_id, None if category == 'all' else category)

    return render_template(
        'man-audit-2.html',
        current_step=2,
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
    return render_template('man-audit-3.html',current_step=3, **summary)


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
        current_step=1,
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
        current_step=2,
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
    return render_template('sl-audit-3.html',current_step=3, **summary)


# =========================
# FULL INVENTORY VIEW
# =========================

@app.route('/inventory')
@login_required
def inventory():
    selected_category = request.args.get('category', 'all')
    cur = mysql.connection.cursor()
    
    cur.execute("SELECT DISTINCT category FROM inventory_items WHERE category IS NOT NULL ORDER BY category")
    unique_categories = [row['category'] for row in cur.fetchall()]
    
    if selected_category != 'all':
        cur.execute("SELECT id, item_name, system_qty, created_at, category FROM inventory_items WHERE LOWER(category) = %s", (selected_category.lower(),))
    else:
        cur.execute("SELECT id, item_name, system_qty, created_at, category FROM inventory_items")
        
    inventory_data = cur.fetchall()
    cur.close()

    return render_template('man-full.html', 
                           inventory=inventory_data, 
                           categories=unique_categories,
                           selected_category=selected_category)

@app.route('/inventory/add', methods=['POST'])
@login_required
@role_required('Manager', 'ShiftLead')
def add_inventory_item_direct():
    data = request.get_json()
    name = data.get('name', '').strip()
    qty = data.get('qty', 0)
    category = data.get('category', 'Uncategorized').strip()

    if not name:
        return jsonify(error="Ingredient name is required."), 400

    cur = mysql.connection.cursor()
    
    cur.execute("SELECT id FROM inventory_items WHERE LOWER(item_name) = LOWER(%s)", (name,))
    if cur.fetchone():
        cur.close()
        return jsonify(error=f"'{name}' already exists in the inventory."), 409

    try:
        cur.execute(
            "INSERT INTO inventory_items (item_name, system_qty, category, created_at) VALUES (%s, %s, %s, NOW())",
            (name, qty, category)
        )
        mysql.connection.commit()
        new_id = cur.lastrowid
        cur.close()
        return jsonify(message='Added', id=new_id)
    except Exception as e:
        return jsonify(error="A database error occurred."), 500


# =========================
# ANALYTICS
# =========================

@app.route('/dashboard')
@login_required
@role_required('Manager')
def dashboard():

    category = request.args.get('category', 'all')
    cur = mysql.connection.cursor()

    cur.execute("SELECT DISTINCT category FROM inventory_items WHERE category IS NOT NULL")
    unique_categories = [row['category'] for row in cur.fetchall()]

    inventory_query = "SELECT item_name, system_qty FROM inventory_items"

    if category != 'all':
        inventory_query += f" WHERE LOWER(category) = '{category.lower()}'"

    cur.execute(inventory_query)
    all_inventory = cur.fetchall()

    cur.close()

    restock_items = get_projected_low_items()
    if category != 'all':
        restock_items = [
            item for item in restock_items
            if str(item.get('category') or '').lower() == category.lower()
        ]

    return render_template('man-dash.html', 
                           inventory=all_inventory, 
                           alerts=restock_items,
                           categories=unique_categories,
                           selected_category=category)

@app.route('/api/analytics-data')
@login_required
def analytics_data():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    category = request.args.get('category', 'all')

    # Fallback to last 7 days
    if not start_str or not end_str:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=6)
    else:
        start_dt = datetime.strptime(start_str, '%Y-%m-%d')
        end_dt = datetime.strptime(end_str, '%Y-%m-%d')

    delta = (end_dt - start_dt).days
    labels = [(start_dt + timedelta(days=i)).strftime('%m/%d') for i in range(delta + 1)]
    days_list = [(start_dt + timedelta(days=i)).date() for i in range(delta + 1)]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    db_start = start_dt.strftime('%Y-%m-%d 00:00:00')
    db_end = end_dt.strftime('%Y-%m-%d 23:59:59')

    # --- 1. INVENTORY ACTIVITY LOGIC ---
    usage_query = """
        SELECT DATE(iu.created_at) as date, SUM(iu.qty_change) as total 
        FROM inventory_updates iu
        JOIN inventory_items ii ON iu.inventory_item_id = ii.id
        WHERE iu.created_at BETWEEN %s AND %s
    """
    u_params = [db_start, db_end]
    if category != 'all':
        usage_query += " AND ii.category = %s"
        u_params.append(category)
    usage_query += " GROUP BY DATE(iu.created_at)"
    
    cur.execute(usage_query, u_params)
    usage_map = {row['date']: float(row['total']) for row in cur.fetchall()}
    usage_values = [usage_map.get(day, 0) for day in days_list]

    # --- 2. AUDIT DISCREPANCY LOGIC ---
    audit_query = """
        SELECT DATE(a.approved_at) as audit_date, 
            SUM(ai.physical_count - ai.system_qty) as total_diff
        FROM audit_items ai
        JOIN audits a ON ai.audit_id = a.id
        JOIN inventory_items ii ON ai.inventory_item_id = ii.id
        WHERE a.status = 'Approved' 
        AND a.approved_at BETWEEN %s AND %s
    """
    a_params = [db_start, db_end]
    if category != 'all':
        audit_query += " AND ii.category = %s"
        a_params.append(category)
    audit_query += " GROUP BY DATE(a.approved_at)"

    cur.execute(audit_query, a_params)
    audit_map = {row['audit_date']: float(row['total_diff']) for row in cur.fetchall()}
    audit_values = [audit_map.get(day, 0) for day in days_list]

    cur.close()
    return jsonify({
        "labels": labels,
        "usage": usage_values,
        "audit": audit_values
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


# =========================
# PREDICTIVE PART
# =========================

XLSX_MAIN_NS = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
PREDICTIVE_SHIP_TIME_DAYS = 3
PREDICTIVE_LOW_STOCK_THRESHOLD_DAYS = 7


def get_excel_column_index(column_name):
    result = 0
    for char in column_name.upper():
        if 'A' <= char <= 'Z':
            result = (result * 26) + (ord(char) - ord('A') + 1)
    return result - 1


def get_xlsx_cell_value(cell, shared_strings):
    cell_type = cell.attrib.get('t')

    if cell_type == 'inlineStr':
        return ''.join(text.text or '' for text in cell.findall('.//a:t', XLSX_MAIN_NS))

    value_element = cell.find('a:v', XLSX_MAIN_NS)
    if value_element is None or value_element.text is None:
        return ''

    raw_value = value_element.text
    if cell_type == 's':
        return shared_strings[int(raw_value)]

    return raw_value


def read_xlsx_rows(file_bytes):
    try:
        workbook_archive = zipfile.ZipFile(io.BytesIO(file_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError('Please upload a valid .xlsx file.') from exc

    shared_strings = []
    if 'xl/sharedStrings.xml' in workbook_archive.namelist():
        shared_root = ET.fromstring(workbook_archive.read('xl/sharedStrings.xml'))
        for string_item in shared_root.findall('a:si', XLSX_MAIN_NS):
            shared_strings.append(
                ''.join(text.text or '' for text in string_item.findall('.//a:t', XLSX_MAIN_NS))
            )

    workbook_root = ET.fromstring(workbook_archive.read('xl/workbook.xml'))
    workbook_rels_root = ET.fromstring(workbook_archive.read('xl/_rels/workbook.xml.rels'))
    relationship_targets = {
        relationship.attrib['Id']: relationship.attrib['Target']
        for relationship in workbook_rels_root.findall('{*}Relationship')
    }

    first_sheet = workbook_root.find('a:sheets/a:sheet', XLSX_MAIN_NS)
    if first_sheet is None:
        raise ValueError('The workbook does not contain any sheets.')

    relationship_id = first_sheet.attrib.get(
        '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    )
    sheet_target = relationship_targets.get(relationship_id)
    if not sheet_target:
        raise ValueError('Unable to locate the worksheet data.')

    sheet_path = sheet_target if sheet_target.startswith('xl/') else f"xl/{sheet_target}"
    worksheet_root = ET.fromstring(workbook_archive.read(sheet_path))

    headers_by_index = {}
    parsed_rows = []

    for row in worksheet_root.findall('a:sheetData/a:row', XLSX_MAIN_NS):
        row_values = {}
        for cell in row.findall('a:c', XLSX_MAIN_NS):
            cell_reference = cell.attrib.get('r', '')
            column_name = ''.join(char for char in cell_reference if char.isalpha())
            if not column_name:
                continue
            row_values[get_excel_column_index(column_name)] = get_xlsx_cell_value(cell, shared_strings)

        if not row_values:
            continue

        if not headers_by_index:
            headers_by_index = {
                index: str(value).strip()
                for index, value in row_values.items()
                if str(value).strip()
            }
            continue

        parsed_rows.append({
            header: row_values.get(index, '')
            for index, header in headers_by_index.items()
        })

    if not headers_by_index:
        raise ValueError('The workbook is missing a header row.')

    return parsed_rows


def get_row_value(row, *header_names):
    normalized_row = {
        str(key).replace(' ', '').strip().lower(): value
        for key, value in row.items()
    }

    for header_name in header_names:
        normalized_header = header_name.replace(' ', '').strip().lower()
        if normalized_header in normalized_row:
            return normalized_row[normalized_header]

    return ''


def parse_pos_date(date_value):
    date_text = str(date_value or '').strip()
    if not date_text:
        raise ValueError('Missing Date value.')

    for date_format in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
        try:
            return dt.datetime.strptime(date_text, date_format).date()
        except ValueError:
            continue

    try:
        return dt.date.fromisoformat(date_text)
    except ValueError as exc:
        raise ValueError(f"Unsupported Date value: {date_text}") from exc


def parse_pos_time(time_value):
    time_text = str(time_value or '').strip()
    if not time_text:
        return dt.time(0, 0, 0)

    for time_format in ('%H:%M:%S', '%H:%M', '%I:%M:%S %p', '%I:%M %p'):
        try:
            return dt.datetime.strptime(time_text, time_format).time()
        except ValueError:
            continue

    raise ValueError(f"Unsupported Time value: {time_text}")


def parse_pos_total(total_value):
    total_text = str(total_value or '').strip().replace('$', '').replace(',', '')
    if not total_text:
        raise ValueError('Missing Total value.')

    try:
        return Decimal(total_text)
    except InvalidOperation as exc:
        raise ValueError(f"Unsupported Total value: {total_text}") from exc


def parse_pos_quantity(quantity_value):
    quantity_text = str(quantity_value or '').strip()
    if not quantity_text:
        return 1.0

    try:
        quantity = float(quantity_text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported Quantity value: {quantity_text}") from exc

    if quantity <= 0:
        raise ValueError(f"Quantity must be positive: {quantity_text}")

    return quantity


def ensure_predictive_schema_support(cur):
    required_columns = {
        'transaction_id': (
            "Database schema is missing pos_transactions.transaction_id. "
            "Apply the SQL changes in GroupSQL.sql first."
        ),
        'quantity': (
            "Database schema is missing pos_transactions.quantity. "
            "Apply the SQL changes in GroupSQL.sql first."
        ),
    }

    for column_name, error_message in required_columns.items():
        cur.execute(f"SHOW COLUMNS FROM pos_transactions LIKE '{column_name}'")
        if not cur.fetchone():
            raise ValueError(error_message)


def build_lightgbm_feature_row(activity_date, drink_id, start_date):
    iso_calendar = activity_date.isocalendar()
    return [
        int(drink_id),                             # shared product column
        int(activity_date.month),
        int(activity_date.weekday()),
        int(activity_date.day),
        int(iso_calendar.week),
        int(activity_date.timetuple().tm_yday),
        int(activity_date.weekday() >= 5),
        int((activity_date - start_date).days),
    ]


def import_pos_transactions(rows):
    if not rows:
        raise ValueError('The workbook does not contain any transaction rows.')

    required_headers = {'transactionid', 'date', 'time', 'menuitem', 'total'}
    normalized_headers = {
        str(header).replace(' ', '').strip().lower()
        for header in rows[0].keys()
    }
    missing_headers = sorted(required_headers - normalized_headers)
    if missing_headers:
        raise ValueError(
            'The workbook is missing required columns: '
            + ', '.join(missing_headers)
        )

    cleaned_rows = []
    seen_file_transaction_ids = set()
    skipped_count = 0

    for row in rows:
        transaction_id = str(get_row_value(row, 'Transaction ID', 'TransactionID') or '').strip()
        menu_item = str(get_row_value(row, 'Menu Item', 'MenuItem') or '').strip()

        if not transaction_id or not menu_item:
            skipped_count += 1
            continue

        if transaction_id in seen_file_transaction_ids:
            skipped_count += 1
            continue

        try:
            transaction_date = dt.datetime.combine(
                parse_pos_date(get_row_value(row, 'Date')),
                parse_pos_time(get_row_value(row, 'Time')),
            )
            transaction_amount = parse_pos_total(get_row_value(row, 'Total'))
            quantity = parse_pos_quantity(get_row_value(row, 'Quantity'))
        except ValueError:
            skipped_count += 1
            continue

        cleaned_rows.append({
            'transaction_id': transaction_id,
            'menu_item': menu_item,
            'transaction_date': transaction_date,
            'transaction_amount': transaction_amount,
            'quantity': quantity,
        })
        seen_file_transaction_ids.add(transaction_id)

    if not cleaned_rows:
        raise ValueError('No valid POS transaction rows were found in the workbook.')

    transaction_ids = [row['transaction_id'] for row in cleaned_rows]
    cur = mysql.connection.cursor()

    try:
        ensure_predictive_schema_support(cur)

        existing_transaction_ids = set()
        if transaction_ids:
            placeholders = ','.join(['%s'] * len(transaction_ids))
            cur.execute(
                f"SELECT transaction_id FROM pos_transactions WHERE transaction_id IN ({placeholders})",
                tuple(transaction_ids)
            )
            existing_transaction_ids = {
                row['transaction_id']
                for row in cur.fetchall()
            }

        cur.execute("SELECT id, drink_name FROM drinks")
        drinks_by_name = {
            row['drink_name'].strip().lower(): row['id']
            for row in cur.fetchall()
        }

        imported_count = 0
        created_drinks = []
        created_drink_names = set()

        for row in cleaned_rows:
            if row['transaction_id'] in existing_transaction_ids:
                skipped_count += 1
                continue

            drink_lookup_key = row['menu_item'].lower()
            drink_id = drinks_by_name.get(drink_lookup_key)

            if not drink_id:
                cur.execute(
                    "INSERT INTO drinks (drink_name) VALUES (%s)",
                    (row['menu_item'],)
                )
                drink_id = cur.lastrowid
                drinks_by_name[drink_lookup_key] = drink_id

                if row['menu_item'] not in created_drink_names:
                    created_drinks.append(row['menu_item'])
                    created_drink_names.add(row['menu_item'])

            cur.execute(
                """
                INSERT INTO pos_transactions (
                    transaction_id,
                    transaction_date,
                    transaction_amount,
                    drink_id,
                    quantity
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    row['transaction_id'],
                    row['transaction_date'],
                    row['transaction_amount'],
                    drink_id,
                    row['quantity'],
                )
            )
            imported_count += 1

        mysql.connection.commit()
        return {
            'imported_count': imported_count,
            'skipped_count': skipped_count,
            'created_drinks': created_drinks,
        }
    except Exception:
        mysql.connection.rollback()
        raise
    finally:
        cur.close()


def infer_recipe_quantities_with_regression():
    cur = mysql.connection.cursor()

    try:
        ensure_predictive_schema_support(cur)

        cur.execute("SELECT id, drink_name FROM drinks ORDER BY id")
        drinks = cur.fetchall()
        drink_names = {row['id']: row['drink_name'] for row in drinks}

        cur.execute("SELECT id, item_name FROM inventory_items ORDER BY id")
        inventory_items = cur.fetchall()
        ingredient_names = {row['id']: row['item_name'] for row in inventory_items}

        cur.execute(
            """
            SELECT drink_id, inventory_item_id
            FROM drink_product
            ORDER BY inventory_item_id, drink_id
            """
        )
        recipe_links = cur.fetchall()
        if not recipe_links:
            raise ValueError('No drink-to-ingredient mappings were found in drink_product.')

        drinks_by_ingredient = {}
        for row in recipe_links:
            drinks_by_ingredient.setdefault(row['inventory_item_id'], []).append(row['drink_id'])

        cur.execute(
            """
            SELECT DATE(transaction_date) AS activity_date,
                   drink_id,
                   SUM(COALESCE(quantity, 1)) AS sold_qty
            FROM pos_transactions
            GROUP BY DATE(transaction_date), drink_id
            ORDER BY DATE(transaction_date), drink_id
            """
        )
        pos_rows = cur.fetchall()
        if not pos_rows:
            raise ValueError('No POS transaction history is available for regression.')

        sales_by_date = {}
        for row in pos_rows:
            activity_date = row['activity_date']
            sales_by_date.setdefault(activity_date, {})[row['drink_id']] = float(row['sold_qty'] or 0.0)

        cur.execute(
            """
            SELECT DATE(created_at) AS activity_date,
                   inventory_item_id,
                   SUM(ABS(qty_change)) AS used_qty
            FROM inventory_updates
            WHERE action_type = 'Sub'
              AND qty_change < 0
            GROUP BY DATE(created_at), inventory_item_id
            ORDER BY DATE(created_at), inventory_item_id
            """
        )
        usage_rows = cur.fetchall()
        if not usage_rows:
            raise ValueError('No negative inventory update history is available for regression.')

        usage_by_ingredient = {}
        for row in usage_rows:
            usage_by_ingredient.setdefault(row['inventory_item_id'], {})[row['activity_date']] = float(
                row['used_qty'] or 0.0
            )

        updated_pairs = []
        skipped_ingredients = []

        for ingredient_id, ingredient_drink_ids in drinks_by_ingredient.items():
            usage_by_date = usage_by_ingredient.get(ingredient_id, {})
            if not usage_by_date:
                skipped_ingredients.append({
                    'ingredient_id': ingredient_id,
                    'ingredient_name': ingredient_names.get(ingredient_id, f'Ingredient {ingredient_id}'),
                    'reason': 'No inventory usage history',
                })
                continue

            observed_dates = sorted(usage_by_date.keys())
            design_matrix = []
            targets = []
            for activity_date in observed_dates:
                row_sales = [
                    sales_by_date.get(activity_date, {}).get(drink_id, 0.0)
                    for drink_id in ingredient_drink_ids
                ]
                if not any(value > 0 for value in row_sales):
                    continue

                design_matrix.append(row_sales)
                targets.append(usage_by_date.get(activity_date, 0.0))

            if not design_matrix or not targets:
                skipped_ingredients.append({
                    'ingredient_id': ingredient_id,
                    'ingredient_name': ingredient_names.get(ingredient_id, f'Ingredient {ingredient_id}'),
                    'reason': 'No overlapping POS and inventory history',
                })
                continue

            coefficients, _ = nnls(design_matrix, targets)
            ingredient_updated = False

            for drink_id, coefficient in zip(ingredient_drink_ids, coefficients):
                if coefficient <= 0:
                    continue

                estimated_quantity = round(float(coefficient), 4)
                cur.execute(
                    """
                    UPDATE drink_product
                    SET quantity = %s
                    WHERE drink_id = %s AND inventory_item_id = %s
                    """,
                    (estimated_quantity, drink_id, ingredient_id)
                )
                updated_pairs.append({
                    'drink_id': drink_id,
                    'drink_name': drink_names.get(drink_id, f'Drink {drink_id}'),
                    'ingredient_id': ingredient_id,
                    'ingredient_name': ingredient_names.get(ingredient_id, f'Ingredient {ingredient_id}'),
                    'quantity': estimated_quantity,
                })
                ingredient_updated = True

            if not ingredient_updated:
                skipped_ingredients.append({
                    'ingredient_id': ingredient_id,
                    'ingredient_name': ingredient_names.get(ingredient_id, f'Ingredient {ingredient_id}'),
                    'reason': 'Regression returned only zero coefficients',
                })

        if not updated_pairs:
            raise ValueError(
                'Regression ran, but no recipe quantities could be estimated from the current POS '
                'and inventory update history.'
            )

        print("\n=== Predictive Regression Results ===")
        print(
            f"Updated {len(updated_pairs)} drink/ingredient quantities across "
            f"{len({row['drink_id'] for row in updated_pairs})} drinks and "
            f"{len({row['ingredient_id'] for row in updated_pairs})} ingredients."
        )
        for row in updated_pairs:
            print(
                f"{row['drink_name']} -> {row['ingredient_name']}: {row['quantity']}"
            )
        if skipped_ingredients:
            print("\nSkipped ingredients:")
            for row in skipped_ingredients[:10]:
                print(f"{row['ingredient_name']}: {row['reason']}")
        print("=== End Predictive Regression Results ===\n")

        mysql.connection.commit()
        return {
            'updated_pair_count': len(updated_pairs),
            'updated_ingredient_count': len({row['ingredient_id'] for row in updated_pairs}),
            'updated_drink_count': len({row['drink_id'] for row in updated_pairs}),
            'updated_pairs_preview': updated_pairs[:10],
            'skipped_ingredients': skipped_ingredients[:10],
        }
    except Exception:
        mysql.connection.rollback()
        raise
    finally:
        cur.close()


def build_forecast_chart_response(title, forecast_dates=None, forecast_values=None, message=None):
    figure, axis = plt.subplots(figsize=(8.6, 4.8))
    figure.patch.set_facecolor('#fcefe4')
    axis.set_facecolor('#fff8f4')

    if message:
        axis.text(
            0.5,
            0.5,
            message,
            ha='center',
            va='center',
            wrap=True,
            fontsize=14,
            color='#964f4c',
            transform=axis.transAxes,
        )
        axis.set_xticks([])
        axis.set_yticks([])
    else:
        x_positions = list(range(len(forecast_dates)))
        axis.plot(
            x_positions,
            forecast_values,
            color='#964f4c',
            linewidth=2.5,
            marker='o',
            markersize=5,
        )
        axis.fill_between(x_positions, forecast_values, color='#964f4c', alpha=0.12)
        axis.set_xticks(x_positions)
        axis.set_xticklabels(
            [forecast_date.strftime('%m/%d') for forecast_date in forecast_dates],
            rotation=45,
            ha='right',
            fontsize=13,
        )
        axis.tick_params(axis='y', labelsize=12)
        axis.set_ylabel('Projected Stock On Hand', fontsize=14)
        axis.grid(axis='y', alpha=0.2)

    axis.set_title(title, color='#2f1d1b', fontsize=16, pad=12)
    for spine in axis.spines.values():
        spine.set_color('#d9c1b3')

    png_buffer = io.BytesIO()
    figure.tight_layout()
    figure.savefig(
        png_buffer,
        format='png',
        dpi=160,
        bbox_inches='tight',
        facecolor=figure.get_facecolor(),
    )
    plt.close(figure)
    png_buffer.seek(0)
    return Response(png_buffer.getvalue(), mimetype='image/png')


def build_lightgbm_forecast_payload(forecast_horizon_days=7):
    cur = mysql.connection.cursor()
    ship_time_days = PREDICTIVE_SHIP_TIME_DAYS

    try:
        ensure_predictive_schema_support(cur)

        cur.execute(
            """
            SELECT poi.inventory_item_id,
                   poi.quantity,
                   po.order_status,
                   po.order_date,
                   po.expected_date
            FROM purchase_order_items poi
            JOIN purchase_orders po ON po.id = poi.purchase_order_id
            WHERE po.order_status IN ('Pending', 'Ordered')
              AND po.received_date IS NULL
            ORDER BY poi.inventory_item_id, po.order_date, po.expected_date
            """
        )
        purchase_order_rows = cur.fetchall()

        incoming_deliveries_by_ingredient = {}
        incoming_deliveries_preview = []
        for row in purchase_order_rows:
            delivery_date = row['expected_date'] or (
                row['order_date'] + dt.timedelta(days=ship_time_days)
                if row['order_date'] else None
            )
            if not delivery_date:
                continue

            ingredient_id = row['inventory_item_id']
            quantity = float(row['quantity'] or 0.0)
            if quantity <= 0:
                continue

            incoming_deliveries_by_ingredient.setdefault(ingredient_id, {})
            incoming_deliveries_by_ingredient[ingredient_id][delivery_date] = (
                incoming_deliveries_by_ingredient[ingredient_id].get(delivery_date, 0.0) + quantity
            )
            incoming_deliveries_preview.append({
                'inventory_item_id': ingredient_id,
                'delivery_date': delivery_date,
                'quantity': round(quantity, 4),
                'status': row['order_status'],
            })

        cur.execute(
            """
            SELECT DATE(transaction_date) AS activity_date,
                   drink_id,
                   SUM(COALESCE(quantity, 1)) AS sold_qty
            FROM pos_transactions
            GROUP BY DATE(transaction_date), drink_id
            ORDER BY DATE(transaction_date), drink_id
            """
        )
        pos_rows = cur.fetchall()
        if not pos_rows:
            raise ValueError('No POS transaction history is available for LightGBM forecasting.')

        sales_lookup = {}
        drink_ids = set()
        all_dates = set()
        for row in pos_rows:
            activity_date = row['activity_date']
            drink_id = int(row['drink_id'])
            sold_qty = float(row['sold_qty'] or 0.0)
            sales_lookup[(activity_date, drink_id)] = sold_qty
            drink_ids.add(drink_id)
            all_dates.add(activity_date)

        if not drink_ids or not all_dates:
            raise ValueError('POS transaction history is missing usable drink/date observations.')

        cur.execute("SELECT id, drink_name FROM drinks ORDER BY id")
        drink_names = {row['id']: row['drink_name'] for row in cur.fetchall()}

        start_date = min(all_dates)
        last_history_date = max(all_dates)
        ordered_drink_ids = sorted(drink_ids)

        training_dates = []
        current_date = start_date
        while current_date <= last_history_date:
            training_dates.append(current_date)
            current_date += dt.timedelta(days=1)

        training_features = []
        training_targets = []
        for activity_date in training_dates:
            for drink_id in ordered_drink_ids:
                training_features.append(
                    build_lightgbm_feature_row(activity_date, drink_id, start_date)
                )
                training_targets.append(
                    sales_lookup.get((activity_date, drink_id), 0.0)
                )

        feature_matrix = np.array(training_features, dtype=float)
        target_vector = np.array(training_targets, dtype=float)
        if feature_matrix.size == 0 or target_vector.size == 0:
            raise ValueError('Unable to build LightGBM training data from POS history.')

        train_dataset = lgb.Dataset(
            feature_matrix,
            label=target_vector,
            categorical_feature=[0],
            free_raw_data=False,
        )
        model = lgb.train(
            {
                'objective': 'regression',
                'metric': 'l2',
                'learning_rate': 0.05,
                'num_leaves': 31,
                'min_data_in_leaf': 5,
                'feature_fraction': 0.9,
                'bagging_fraction': 0.9,
                'bagging_freq': 1,
                'seed': 42,
                'verbosity': -1,
            },
            train_dataset,
            num_boost_round=200,
        )

        future_dates = [
            last_history_date + dt.timedelta(days=offset)
            for offset in range(1, forecast_horizon_days + 1)
        ]
        future_features = []
        future_keys = []
        for activity_date in future_dates:
            for drink_id in ordered_drink_ids:
                future_features.append(
                    build_lightgbm_feature_row(activity_date, drink_id, start_date)
                )
                future_keys.append((activity_date, drink_id))

        future_matrix = np.array(future_features, dtype=float)
        predictions = model.predict(future_matrix)

        drink_forecasts = {}
        drink_forecast_preview = []
        for (activity_date, drink_id), prediction in zip(future_keys, predictions):
            predicted_qty = round(max(0.0, float(prediction)), 4)
            drink_forecasts[(activity_date, drink_id)] = predicted_qty
            drink_forecast_preview.append({
                'forecast_date': activity_date.isoformat(),
                'drink_id': drink_id,
                'drink_name': drink_names.get(drink_id, f'Drink {drink_id}'),
                'predicted_qty': predicted_qty,
            })

        cur.execute(
            """
            SELECT dp.drink_id,
                   dp.inventory_item_id,
                   dp.quantity,
                   i.item_name,
                   i.category,
                   i.system_qty
            FROM drink_product dp
            JOIN inventory_items i ON i.id = dp.inventory_item_id
            WHERE dp.quantity IS NOT NULL
              AND dp.quantity > 0
            ORDER BY dp.inventory_item_id, dp.drink_id
            """
        )
        recipe_rows = cur.fetchall()
        if not recipe_rows:
            raise ValueError('No recipe quantities are available for ingredient forecasting.')

        ingredient_forecasts = {}
        for row in recipe_rows:
            ingredient_id = row['inventory_item_id']
            ingredient_entry = ingredient_forecasts.setdefault(
                ingredient_id,
                {
                    'inventory_item_id': ingredient_id,
                    'item_name': row['item_name'],
                    'category': row['category'] or 'Uncategorized',
                    'current_qty': float(row['system_qty'] or 0.0),
                    'daily_usage': {},
                    'incoming_deliveries': incoming_deliveries_by_ingredient.get(ingredient_id, {}),
                }
            )

            recipe_qty = float(row['quantity'] or 0.0)
            if recipe_qty <= 0:
                continue

            for forecast_date in future_dates:
                drink_forecast_qty = drink_forecasts.get((forecast_date, row['drink_id']), 0.0)
                if drink_forecast_qty <= 0:
                    continue

                ingredient_entry['daily_usage'][forecast_date] = (
                    ingredient_entry['daily_usage'].get(forecast_date, 0.0)
                    + (drink_forecast_qty * recipe_qty)
                )

        category_usage_series = {'all': {}}
        category_current_stock = {'all': 0.0}
        category_incoming_series = {'all': {}}
        prediction_rows = []
        for ingredient_entry in ingredient_forecasts.values():
            if not ingredient_entry['daily_usage']:
                continue

            category_key = str(ingredient_entry['category'] or 'Uncategorized').strip()
            normalized_category_key = category_key.lower()
            category_usage_series.setdefault(normalized_category_key, {})
            category_current_stock.setdefault(normalized_category_key, 0.0)
            category_incoming_series.setdefault(normalized_category_key, {})

            category_current_stock['all'] += ingredient_entry['current_qty']
            category_current_stock[normalized_category_key] += ingredient_entry['current_qty']

            for forecast_date in future_dates:
                daily_usage = ingredient_entry['daily_usage'].get(forecast_date, 0.0)
                incoming_qty = ingredient_entry['incoming_deliveries'].get(forecast_date, 0.0)
                category_usage_series['all'][forecast_date] = (
                    category_usage_series['all'].get(forecast_date, 0.0) + daily_usage
                )
                category_usage_series[normalized_category_key][forecast_date] = (
                    category_usage_series[normalized_category_key].get(forecast_date, 0.0) + daily_usage
                )
                category_incoming_series['all'][forecast_date] = (
                    category_incoming_series['all'].get(forecast_date, 0.0) + incoming_qty
                )
                category_incoming_series[normalized_category_key][forecast_date] = (
                    category_incoming_series[normalized_category_key].get(forecast_date, 0.0) + incoming_qty
                )

            running_stock = ingredient_entry['current_qty']
            horizon_usage = 0.0
            stockout_date = None
            for forecast_date in future_dates:
                running_stock += ingredient_entry['incoming_deliveries'].get(forecast_date, 0.0)
                daily_usage = ingredient_entry['daily_usage'].get(forecast_date, 0.0)
                horizon_usage += daily_usage
                running_stock -= daily_usage
                if running_stock <= 0:
                    stockout_date = forecast_date
                    break

            total_projected_usage = round(horizon_usage, 4)
            if total_projected_usage <= 0:
                continue

            if stockout_date is None:
                average_daily_usage = horizon_usage / len(future_dates)
                if average_daily_usage <= 0:
                    continue

                projected_date = future_dates[-1]
                projected_stock = running_stock
                while projected_stock > 0:
                    projected_date += dt.timedelta(days=1)
                    projected_stock += ingredient_entry['incoming_deliveries'].get(projected_date, 0.0)
                    projected_stock -= average_daily_usage
                    if projected_stock <= 0:
                        stockout_date = projected_date
                        break

            order_by_date = stockout_date - dt.timedelta(days=ship_time_days)

            prediction_rows.append({
                'inventory_item_id': ingredient_entry['inventory_item_id'],
                'item_name': ingredient_entry['item_name'],
                'current_qty': round(ingredient_entry['current_qty'], 4),
                'prediction_quantity': total_projected_usage,
                'stockout_date': stockout_date,
                'order_by_date': order_by_date,
            })

        if not prediction_rows:
            raise ValueError('LightGBM completed, but no ingredient forecasts could be generated.')

        category_stock_projection_series = {}
        for category_key, usage_series in category_usage_series.items():
            running_stock = float(category_current_stock.get(category_key, 0.0))
            stock_values = []
            for forecast_date in future_dates:
                running_stock += category_incoming_series.get(category_key, {}).get(forecast_date, 0.0)
                running_stock -= usage_series.get(forecast_date, 0.0)
                stock_values.append(round(running_stock, 4))
            category_stock_projection_series[category_key] = stock_values

        feature_importance = model.feature_importance(importance_type='gain').tolist()
        feature_names = [
            'drink_id',
            'month',
            'day_of_week',
            'day_of_month',
            'week_of_year',
            'day_of_year',
            'is_weekend',
            'days_since_start',
        ]

        print("\n=== LightGBM Forecast Results ===")
        print(
            f"Training rows: {len(training_targets)} | "
            f"Drinks: {len(ordered_drink_ids)} | "
            f"History range: {start_date} to {last_history_date}"
        )
        print("Shared model feature importance:")
        for feature_name, importance_value in zip(feature_names, feature_importance):
            print(f"  {feature_name}: {round(float(importance_value), 4)}")

        print("\nDrink forecast preview:")
        for row in drink_forecast_preview[:20]:
            print(
                f"  {row['forecast_date']} | {row['drink_name']} | "
                f"predicted sold qty = {row['predicted_qty']}"
            )

        print("\nIngredient forecast rows:")
        for row in prediction_rows[:20]:
            print(
                f"  {row['item_name']} | current={row['current_qty']} | "
                f"projected={row['prediction_quantity']} | stockout {row['stockout_date']} | "
                f"order by {row['order_by_date']}"
            )
        print("\nIncoming deliveries preview:")
        for row in incoming_deliveries_preview[:20]:
            print(
                f"  ingredient_id={row['inventory_item_id']} | delivery={row['delivery_date']} | "
                f"qty={row['quantity']} | status={row['status']}"
            )
        print("\nCategory stock projection preview:")
        for category_key, stock_values in list(category_stock_projection_series.items())[:10]:
            print(f"  {category_key}: {stock_values}")
        print("=== End LightGBM Forecast Results ===\n")

        return {
            'forecast_horizon_days': forecast_horizon_days,
            'ship_time_days': ship_time_days,
            'training_row_count': len(training_targets),
            'trained_drink_count': len(ordered_drink_ids),
            'forecast_row_count': len(prediction_rows),
            'future_dates': future_dates,
            'category_current_stock': {
                key: round(value, 4) for key, value in category_current_stock.items()
            },
            'category_usage_series': {
                key: [round(series.get(forecast_date, 0.0), 4) for forecast_date in future_dates]
                for key, series in category_usage_series.items()
            },
            'category_incoming_series': {
                key: [round(series.get(forecast_date, 0.0), 4) for forecast_date in future_dates]
                for key, series in category_incoming_series.items()
            },
            'category_stock_projection_series': category_stock_projection_series,
            'feature_names': feature_names,
            'feature_importance': [round(float(value), 4) for value in feature_importance],
            'prediction_rows': prediction_rows,
            'incoming_deliveries_preview': incoming_deliveries_preview[:10],
            'drink_forecast_preview': drink_forecast_preview[:10],
            'ingredient_forecast_preview': prediction_rows[:10],
        }
    finally:
        cur.close()


def train_lightgbm_and_refresh_predictions(forecast_horizon_days=7):
    forecast_payload = build_lightgbm_forecast_payload(forecast_horizon_days=forecast_horizon_days)
    cur = mysql.connection.cursor()

    try:
        cur.execute("DELETE FROM order_predictions")
        for prediction_row in forecast_payload['prediction_rows']:
            cur.execute(
                """
                INSERT INTO order_predictions (
                    inventory_item_id,
                    prediction_quantity,
                    prediction_order_by_date,
                    prediction_date_created
                )
                VALUES (%s, %s, %s, NOW())
                """,
                (
                    prediction_row['inventory_item_id'],
                    prediction_row['prediction_quantity'],
                    prediction_row['order_by_date'],
                )
            )

        mysql.connection.commit()
    except Exception:
        mysql.connection.rollback()
        raise
    finally:
        cur.close()

    return {
        'forecast_horizon_days': forecast_payload['forecast_horizon_days'],
        'training_row_count': forecast_payload['training_row_count'],
        'trained_drink_count': forecast_payload['trained_drink_count'],
        'forecast_row_count': forecast_payload['forecast_row_count'],
        'drink_forecast_preview': forecast_payload['drink_forecast_preview'],
        'ingredient_forecast_preview': forecast_payload['ingredient_forecast_preview'],
    }


@app.route("/predictive/chart")
@login_required
@role_required('Manager', 'ShiftLead', 'Employee')
def predictive_forecast_chart():
    selected_category = (request.args.get('category', 'all') or 'all').strip()

    try:
        forecast_payload = build_lightgbm_forecast_payload()
        category_key = 'all' if selected_category.lower() == 'all' else selected_category.lower()
        forecast_values = forecast_payload['category_stock_projection_series'].get(category_key)

        if not forecast_values:
            return build_forecast_chart_response(
                title=f"{selected_category.title()} Stock On Hand Projection",
                message='No forecast data is available for the selected category.',
            )

        chart_title = (
            'All Categories Stock On Hand Projection'
            if category_key == 'all'
            else f"{selected_category} Stock On Hand Projection"
        )
        return build_forecast_chart_response(
            title=chart_title,
            forecast_dates=forecast_payload['future_dates'],
            forecast_values=forecast_values,
        )
    except Exception as exc:
        return build_forecast_chart_response(
            title='Ingredient Forecast',
            message=f"Unable to build forecast chart: {exc}",
        )


@app.route("/predictive")
@login_required
@role_required('Manager', 'ShiftLead', 'Employee')
def predictive_reports():
    selected_category = request.args.get('category', 'all')
    ship_time_days = PREDICTIVE_SHIP_TIME_DAYS
    low_stock_threshold_days = PREDICTIVE_LOW_STOCK_THRESHOLD_DAYS

    try:
        infer_recipe_quantities_with_regression()
        train_lightgbm_and_refresh_predictions()
    except Exception as exc:
        print(f"Predictive auto-refresh skipped: {exc}")

    cur = mysql.connection.cursor()

    cur.execute("SELECT id, drink_name FROM drinks ORDER BY drink_name")
    drinks = cur.fetchall()

    cur.execute(
        """
        SELECT d.drink_name
        FROM drinks d
        LEFT JOIN drink_product dp ON dp.drink_id = d.id
        WHERE dp.drink_id IS NULL
        ORDER BY d.drink_name
        """
    )
    blank_recipe_names = [row['drink_name'] for row in cur.fetchall()]

    cur.execute("SELECT id, item_name FROM inventory_items ORDER BY item_name")
    inventory_items = cur.fetchall()

    cur.execute(
        """
        SELECT DISTINCT category
        FROM inventory_items
        WHERE category IS NOT NULL
        ORDER BY category
        """
    )
    categories = [row['category'] for row in cur.fetchall()]

    predictive_query = """
        SELECT i.id,
               i.item_name,
               i.category,
               i.system_qty,
               latest_prediction.prediction_quantity,
               latest_prediction.prediction_order_by_date,
               latest_prediction.prediction_date_created
        FROM inventory_items i
        LEFT JOIN (
            SELECT op.inventory_item_id,
                   op.prediction_quantity,
                   op.prediction_order_by_date,
                   op.prediction_date_created
            FROM order_predictions op
            JOIN (
                SELECT inventory_item_id, MAX(prediction_date_created) AS latest_created
                FROM order_predictions
                GROUP BY inventory_item_id
            ) newest_prediction
                ON newest_prediction.inventory_item_id = op.inventory_item_id
               AND newest_prediction.latest_created = op.prediction_date_created
        ) latest_prediction
            ON latest_prediction.inventory_item_id = i.id
    """

    predictive_params = []
    if selected_category != 'all':
        predictive_query += " WHERE LOWER(i.category) = LOWER(%s)"
        predictive_params.append(selected_category)

    predictive_query += " ORDER BY i.item_name"
    cur.execute(predictive_query, tuple(predictive_params))
    predictive_rows = cur.fetchall()
    cur.close()

    today = dt.date.today()
    predictive_items = []
    recommended_orders = []

    for row in predictive_rows:
        prediction_date = row['prediction_order_by_date']
        current_qty = round(float(row['system_qty'] or 0.0), 4)
        prediction_quantity = float(row['prediction_quantity'] or 0.0)
        projected_stockout_date = (
            prediction_date + dt.timedelta(days=ship_time_days)
            if prediction_date else None
        )
        days_until_stockout = (
            (projected_stockout_date - today).days
            if projected_stockout_date else None
        )

        if days_until_stockout is not None and days_until_stockout <= ship_time_days:
            status_label = 'Critical'
            status_class = 'predictive-status-critical'
        elif days_until_stockout is not None and days_until_stockout <= low_stock_threshold_days:
            status_label = 'Low'
            status_class = 'predictive-status-low'
        else:
            status_label = 'In Stock'
            status_class = 'predictive-status-ok'

        predictive_item = {
            'id': row['id'],
            'item_name': row['item_name'],
            'category': row['category'],
            'system_qty': current_qty,
            'prediction_quantity': prediction_quantity,
            'order_by_date': fmt_date(prediction_date) if prediction_date else 'No prediction',
            'stockout_date': fmt_date(projected_stockout_date) if projected_stockout_date else 'No prediction',
            'prediction_created_at': (
                row['prediction_date_created'].strftime('%m/%d/%Y %I:%M %p')
                if row['prediction_date_created'] else 'N/A'
            ),
            'status_label': status_label,
            'status_class': status_class,
            'has_prediction': prediction_date is not None,
            '_sort_stockout_date': projected_stockout_date,
        }
        predictive_items.append(predictive_item)

        if (
            predictive_item['has_prediction']
            and prediction_quantity > 0
            and status_label in ('Critical', 'Low')
        ):
            recommended_orders.append({
                'item_name': row['item_name'],
                'system_qty': current_qty,
                'prediction_quantity': prediction_quantity,
                'rounded_prediction_quantity': int(math.ceil(prediction_quantity)),
                'order_by_date': predictive_item['order_by_date'],
                'stockout_date': predictive_item['stockout_date'],
                'prediction_created_at': predictive_item['prediction_created_at'],
                '_sort_date': prediction_date,
            })

    predictive_items.sort(
        key=lambda item: (
            item['_sort_stockout_date'] or dt.date.max,
            item['item_name'].lower(),
        )
    )
    for item in predictive_items:
        item.pop('_sort_stockout_date', None)

    recommended_orders.sort(
        key=lambda order: (
            order['_sort_date'] or dt.date.max,
            -order['prediction_quantity'],
            order['item_name'],
        )
    )
    for order in recommended_orders:
        order.pop('_sort_date', None)
    recommended_order = recommended_orders[0] if recommended_orders else None

    return render_template(
        "man-predictive-7.html",
        drinks=drinks,
        inventory_items=inventory_items,
        predictive_items=predictive_items,
        categories=categories,
        selected_category=selected_category,
        recommended_order=recommended_order,
        recommended_orders=recommended_orders,
        ship_time_days=ship_time_days,
        blank_recipe_names=blank_recipe_names,
    )


@app.route("/predictive/import-pos", methods=['POST'])
@login_required
@role_required('Manager')
def import_predictive_pos_data():
    upload_file = request.files.get('file')
    if not upload_file or not upload_file.filename:
        return jsonify({"error": "Please choose an Excel file to upload."}), 400

    if not upload_file.filename.lower().endswith('.xlsx'):
        return jsonify({"error": "Only .xlsx POS files are supported."}), 400

    try:
        import_summary = import_pos_transactions(read_xlsx_rows(upload_file.read()))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Unable to import POS data: {exc}"}), 500

    created_drinks = import_summary['created_drinks']
    message = (
        f"Imported {import_summary['imported_count']} POS transactions and skipped "
        f"{import_summary['skipped_count']} existing or invalid rows."
    )
    if created_drinks:
        message += f" Added {len(created_drinks)} new drink(s)."

    return jsonify({
        "message": message,
        **import_summary,
    }), 200


@app.route("/predictive/recipes/regression", methods=['POST'])
@login_required
@role_required('Manager')
def run_predictive_recipe_regression():
    try:
        regression_summary = infer_recipe_quantities_with_regression()
        forecast_summary = train_lightgbm_and_refresh_predictions()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Unable to estimate recipe quantities: {exc}"}), 500

    return jsonify({
        "message": (
            f"Updated {regression_summary['updated_pair_count']} recipe quantities across "
            f"{regression_summary['updated_drink_count']} drinks and "
            f"{regression_summary['updated_ingredient_count']} ingredients, then trained "
            f"LightGBM on {forecast_summary['training_row_count']} daily POS rows and wrote "
            f"{forecast_summary['forecast_row_count']} ingredient forecasts."
        ),
        "regression": regression_summary,
        "forecast": forecast_summary,
    }), 200


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
        for inventory_item_id in deduped_product_ids:
            cur.execute(
                """
                INSERT INTO drink_product (drink_id, inventory_item_id, quantity)
                VALUES (%s, %s, %s)
                """,
                (drink_id, inventory_item_id, deduped_products_by_id[inventory_item_id])
            )

        mysql.connection.commit()
        return jsonify({
            "message": f"Recipe saved for {drink_name}",
            "drink_id": drink_id,
            "drink_name": drink_name
        }), 200
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()


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
            po.order_status,
            po.audit_status
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
            'items': items_by_order.get(oid, []),
            'audit_status': row['audit_status']
        })

    return render_template('purchase_order_info.html', orders=orders)


@app.route('/purchase-orders/<int:order_id>/status', methods=['PATCH'])
@login_required
@role_required('Manager')
def update_order_status(order_id):
    if not request.is_json:
        return jsonify(error='JSON required'), 400

    new_status = request.get_json().get('status')
    if new_status not in ('Pending', 'Received', 'Cancelled'):
        return jsonify(error='Invalid status'), 400

    cur = mysql.connection.cursor()

    if new_status == 'Received':
        cur.execute("""
            UPDATE purchase_orders
            SET order_status = %s,
                received_date = CURDATE(),
                audit_status = 'Pending'
            WHERE id = %s
        """, (new_status, order_id))
    elif new_status == 'Pending':
        cur.execute("""
            UPDATE purchase_orders
            SET order_status = %s,
                received_date = NULL,
                audit_status = 'Pending'
            WHERE id = %s
        """, (new_status, order_id))
    else:  # Cancelled
        cur.execute("""
            UPDATE purchase_orders
            SET order_status = %s,
                audit_status = 'Pending'
            WHERE id = %s
        """, (new_status, order_id))

    mysql.connection.commit()
    cur.close()

    return jsonify(
        message='Status updated',
        received_date=fmt_date(__import__('datetime').date.today()) if new_status == 'Received' else None
    ), 200


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
        INSERT INTO purchase_orders (supplier_id, order_date, expected_date, order_status, audit_status)
        VALUES (%s, %s, %s, 'Pending', 'Pending')
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
# LEON PART (DELIVERY + INVENTORY EXTENSIONS)
# =========================

#import datetime
# ^ this is now done at the top


# ── APPLY PURCHASE ORDER TO INVENTORY ─────────────────
def apply_confirmed_audit_to_inventory(order_id, user_id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            da.inventory_item_id,
            da.quantity_received,
            ii.system_qty,
            ii.item_name
        FROM delivery_audits da
        JOIN inventory_items ii
            ON da.inventory_item_id = ii.id
        WHERE da.purchase_order_id = %s
    """, (order_id,))
    items = cur.fetchall()

    for item in items:
        old_qty = int(item['system_qty'])
        received_qty = int(item['quantity_received'])
        new_qty = old_qty + received_qty

        cur.execute("""
            UPDATE inventory_items
            SET system_qty = %s
            WHERE id = %s
        """, (new_qty, item['inventory_item_id']))

        cur.execute("""
            INSERT INTO inventory_updates
                (inventory_item_id, updated_by, action_type, qty_change, old_qty, new_qty, purchase_order_id, reason)
            VALUES
                (%s, %s, 'Restock', %s, %s, %s, %s, %s)
        """, (
            item['inventory_item_id'],
            user_id,
            received_qty,
            old_qty,
            new_qty,
            order_id,
            f'Confirmed delivery audit for PO #{order_id}'
        ))

    mysql.connection.commit()
    cur.close()

def apply_purchase_order_to_inventory(order_id, received_by_user_id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT poi.inventory_item_id,
               poi.quantity AS qty_ordered,
               ii.system_qty AS current_qty,
               ii.item_name
        FROM purchase_order_items poi
        JOIN inventory_items ii ON poi.inventory_item_id = ii.id
        WHERE poi.purchase_order_id = %s
    """, (order_id,))
    items = cur.fetchall()

    for item in items:
        old_qty = int(item['current_qty'])
        ordered_qty = int(item['qty_ordered'])
        new_qty = old_qty + ordered_qty

        # update inventory
        cur.execute(
            "UPDATE inventory_items SET system_qty = %s WHERE id = %s",
            (new_qty, item['inventory_item_id'])
        )

        # log update
        cur.execute("""
            INSERT INTO inventory_updates
            (inventory_item_id, updated_by, action_type, qty_change, old_qty, new_qty, purchase_order_id, reason)
            VALUES (%s, %s, 'Restock', %s, %s, %s, %s, %s)
        """, (
            item['inventory_item_id'],
            received_by_user_id,
            ordered_qty,
            old_qty,
            new_qty,
            order_id,
            f'PO #{order_id} received'
        ))

        # delivery audit
        cur.execute("""
            INSERT INTO delivery_audits
            (purchase_order_id, inventory_item_id, quantity_ordered, quantity_received, received_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            order_id,
            item['inventory_item_id'],
            ordered_qty,
            ordered_qty,
            received_by_user_id
        ))

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
    cur.execute("""
        SELECT
            po.id,
            s.supplier_name,
            po.order_date,
            po.expected_date,
            po.received_date,
            po.order_status,
            po.audit_status
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        ORDER BY po.id DESC
    """)
    rows = cur.fetchall()
    cur.close()

    orders = []
    awaiting_audit = []
    awaiting_approval = []
    reviewed_orders = []

    for row in rows:
        order = {
            'id': row['id'],
            'supplier': row['supplier_name'],
            'order_date': fmt_date(row['order_date']),
            'expected_date': fmt_date(row['expected_date']),
            'received_date': fmt_date(row['received_date']),
            'status': row['order_status'],
            'audit_status': row['audit_status']
        }

        orders.append(order)

        if row['order_status'] == 'Received' and row['audit_status'] == 'Pending':
            awaiting_audit.append(order)
        elif row['audit_status'] == 'Awaiting Approval':
            awaiting_approval.append(order)
        elif row['audit_status'] == 'Reviewed':
            reviewed_orders.append(order)

    return render_template(
        'delivery_audit.html',
        orders=orders,
        awaiting_audit=awaiting_audit,
        awaiting_approval=awaiting_approval,
        reviewed_orders=reviewed_orders,
        order=None
    )

@app.route('/sl-delivery-audit')
@login_required
@role_required('ShiftLead')
def sl_delivery_audit_list():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT
            po.id,
            s.supplier_name,
            po.order_date,
            po.expected_date,
            po.received_date,
            po.order_status,
            po.audit_status
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.order_status = 'Received'
        ORDER BY po.id DESC
    """)
    rows = cur.fetchall()
    cur.close()

    awaiting_audit = []
    awaiting_approval = []

    for row in rows:
        order = {
            'id': row['id'],
            'supplier': row['supplier_name'],
            'order_date': fmt_date(row['order_date']),
            'expected_date': fmt_date(row['expected_date']),
            'received_date': fmt_date(row['received_date']),
            'status': row['order_status'],
            'audit_status': row['audit_status']
        }

        if row['audit_status'] == 'Pending':
            awaiting_audit.append(order)
        elif row['audit_status'] == 'Awaiting Approval':
            awaiting_approval.append(order)

    return render_template(
        'sl-delivery_audit.html',
        awaiting_audit=awaiting_audit,
        awaiting_approval=awaiting_approval,
        order=None
    )

@app.route('/delivery-audit/<int:order_id>', methods=['GET', 'POST'])
@login_required
@role_required('Manager')
def delivery_audit_detail(order_id):
    cur = mysql.connection.cursor()

    # PO header + audit metadata
    cur.execute("""
        SELECT 
            po.id,
            po.order_date,
            po.expected_date,
            po.received_date,
            po.order_status,
            po.audit_status,
            s.supplier_name,
            MAX(da.received_at) AS audited_at,
            MAX(u.name) AS audited_by_name
        FROM purchase_orders po
        JOIN suppliers s
            ON po.supplier_id = s.id
        LEFT JOIN delivery_audits da
            ON da.purchase_order_id = po.id
        LEFT JOIN users u
            ON da.received_by = u.id
        WHERE po.id = %s
        GROUP BY
            po.id,
            po.order_date,
            po.expected_date,
            po.received_date,
            po.order_status,
            po.audit_status,
            s.supplier_name
    """, (order_id,))
    order = cur.fetchone()

    if not order:
        cur.close()
        return "Order not found", 404

    # PO line items + audited quantities
    cur.execute("""
        SELECT
            poi.inventory_item_id,
            ii.item_name,
            ii.category,
            poi.quantity AS qty_ordered,
            da.quantity_received AS qty_received,
            ii.system_qty AS last_recorded_qty
        FROM purchase_order_items poi
        JOIN inventory_items ii
            ON poi.inventory_item_id = ii.id
        LEFT JOIN delivery_audits da
            ON da.purchase_order_id = poi.purchase_order_id
           AND da.inventory_item_id = poi.inventory_item_id
        WHERE poi.purchase_order_id = %s
        ORDER BY ii.item_name
    """, (order_id,))
    line_items = cur.fetchall()

    audit_has_been_submitted = False
    has_discrepancy = False
    discrepancy_count = 0

    for item in line_items:
        qty_ordered = int(item['qty_ordered'] or 0)

        if item['qty_received'] is None:
            item['difference'] = None
            continue

        audit_has_been_submitted = True
        qty_received = int(item['qty_received'])
        difference = qty_received - qty_ordered
        
        item['difference'] = difference

        if difference != 0:
            has_discrepancy = True
            discrepancy_count += 1

    if request.method == 'POST':
        for item in line_items:
            raw = request.form.get(
                f"qty_received_{item['inventory_item_id']}",
                item['qty_ordered']
            )
            qty_received = int(raw) if raw not in (None, '') else 0

            cur.execute("""
                INSERT INTO delivery_audits (
                    purchase_order_id,
                    inventory_item_id,
                    quantity_ordered,
                    quantity_received,
                    received_by
                )
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    quantity_ordered = VALUES(quantity_ordered),
                    quantity_received = VALUES(quantity_received),
                    received_by = VALUES(received_by)
            """, (
                order_id,
                item['inventory_item_id'],
                item['qty_ordered'],
                qty_received,
                current_user.id
            ))

        cur.execute("""
            UPDATE purchase_orders
            SET audit_status = 'Confirmed'
            WHERE id = %s
        """, (order_id,))

        mysql.connection.commit()

        # Only now update inventory/activity log
        apply_confirmed_audit_to_inventory(order_id, current_user.id)

        cur.close()
        return redirect(url_for('delivery_audit_list', confirmed='true'))

    order_data = {
        'id': order['id'],
        'supplier': order['supplier_name'],
        'order_date': fmt_date(order['order_date']),
        'expected_date': fmt_date(order['expected_date']),
        'received_date': fmt_date(order['received_date']),
        'status': order['order_status'],
        'audit_status': order['audit_status'],
        'received_by_name': order['audited_by_name'],
        'received_at': fmt_date(order['audited_at']) if order['audited_at'] else None
    }

    cur.close()
    return render_template(
        'delivery_audit.html',
        order=order_data,
        line_items=line_items,
        has_discrepancy=has_discrepancy,
        discrepancy_count=discrepancy_count,
        audit_has_been_submitted=audit_has_been_submitted
    )


@app.route('/sl-delivery-audit/<int:order_id>', methods=['GET', 'POST'])
@login_required
@role_required('ShiftLead')
def sl_delivery_audit_detail(order_id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT po.id,
               po.order_date,
               po.expected_date,
               po.received_date,
               po.order_status,
               po.audit_status,
               s.supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.id = %s
    """, (order_id,))
    order = cur.fetchone()

    if not order:
        cur.close()
        return "Order not found", 404

    cur.execute("""
        SELECT poi.inventory_item_id,
               ii.item_name,
               ii.category,
               poi.quantity AS qty_ordered,
               da.quantity_received AS qty_received,
               ii.system_qty AS last_recorded_qty
        FROM purchase_order_items poi
        JOIN inventory_items ii ON poi.inventory_item_id = ii.id
        LEFT JOIN delivery_audits da
          ON da.purchase_order_id = poi.purchase_order_id
         AND da.inventory_item_id = poi.inventory_item_id
        WHERE poi.purchase_order_id = %s
        ORDER BY ii.item_name
    """, (order_id,))
    line_items = cur.fetchall()

    if request.method == 'POST':
        for item in line_items:
            raw = request.form.get(f"qty_received_{item['inventory_item_id']}", item['qty_ordered'])
            qty_received = int(raw) if raw not in (None, '') else 0

            cur.execute("""
                INSERT INTO delivery_audits (
                    purchase_order_id,
                    inventory_item_id,
                    quantity_ordered,
                    quantity_received,
                    received_by
                )
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    quantity_ordered = VALUES(quantity_ordered),
                    quantity_received = VALUES(quantity_received),
                    received_by = VALUES(received_by)
            """, (
                order_id,
                item['inventory_item_id'],
                item['qty_ordered'],
                qty_received,
                current_user.id
            ))

        cur.execute("""
            UPDATE purchase_orders
            SET audit_status = 'Awaiting Approval'
            WHERE id = %s
        """, (order_id,))

        mysql.connection.commit()
        cur.close()
        return redirect(url_for('sl_delivery_audit_list'))

    order_data = {
        'id': order['id'],
        'supplier': order['supplier_name'],
        'order_date': fmt_date(order['order_date']),
        'expected_date': fmt_date(order['expected_date']),
        'received_date': fmt_date(order['received_date']),
        'status': order['order_status'],
        'audit_status': order['audit_status']
    }

    cur.close()
    return render_template('sl-delivery_audit.html', order=order_data, line_items=line_items)


# =========================
# DELIVERY AUDIT API
# =========================
@app.route('/api/delivery-audit/<int:order_id>')
@login_required
@role_required('Manager')
def get_delivery_audit(order_id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT po.id AS order_id,
               po.order_status,
               po.order_date,
               po.expected_date,
               po.received_date,
               s.supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.id = %s
    """, (order_id,))

    order = cur.fetchone()

    if not order:
        cur.close()
        return jsonify(error='Order not found'), 404

    cur.execute("""
        SELECT poi.inventory_item_id,
               i.item_name,
               i.category,
               poi.quantity AS qty_ordered,
               da.quantity_received AS qty_received,
               da.received_at,
               (COALESCE(da.quantity_received, 0) - poi.quantity) AS discrepancy
        FROM purchase_order_items poi
        JOIN inventory_items i ON poi.inventory_item_id = i.id
        LEFT JOIN delivery_audits da
            ON da.purchase_order_id = poi.purchase_order_id
           AND da.inventory_item_id = poi.inventory_item_id
        WHERE poi.purchase_order_id = %s
        ORDER BY i.item_name
    """, (order_id,))

    rows = cur.fetchall()
    cur.close()

    return jsonify({
        'order': {
            'id': order['order_id'],
            'status': order['order_status'],
            'supplier': order['supplier_name'],
            'order_date': fmt_date(order['order_date']),
            'expected_date': fmt_date(order['expected_date']),
            'received_date': fmt_date(order['received_date']),
        },
        'items': rows
    })

# =========================
# INVENTORY UPDATE (API)
# =========================
@app.route('/inventory/<int:item_id>', methods=['PATCH'])
@login_required
@role_required('Manager', 'ShiftLead', 'Employee')
def update_inventory_item(item_id):
    data = request.get_json()

    action = data.get('action')
    qty = int(data.get('qty', 0))

    if action not in ['add', 'subtract']:
        return jsonify(error='Invalid action'), 400

    if qty <= 0:
        return jsonify(error='Quantity must be greater than 0'), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT system_qty FROM inventory_items WHERE id = %s", (item_id,))
    item = cur.fetchone()

    if not item:
        cur.close()
        return jsonify(error='Item not found'), 404

    old_qty = item['system_qty']

    if action == 'add':
        new_qty = old_qty + qty
    else:
        new_qty = old_qty - qty

    if new_qty < 0:
        cur.close()
        return jsonify(error='Inventory cannot go below zero'), 400

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
        (
            item_id,
            current_user.id,
            'Add' if action == 'add' else 'Sub',
            qty if action == 'add' else -qty,
            old_qty,
            new_qty,
            'Manual inventory update'
        )
    )

    mysql.connection.commit()
    cur.close()

    return jsonify(message='Updated', new_qty=new_qty)

@app.route('/inventory/<int:item_id>', methods=['DELETE'])
@login_required
@role_required('Manager', 'ShiftLead')
def delete_inventory_item(item_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM inventory_items WHERE id = %s", (item_id,))
    mysql.connection.commit()
    cur.close()

    return jsonify(message='Deleted')


# =========================
# PREDICTIONS API
# =========================
@app.route('/api/predictions')
@login_required
@role_required('Manager')
def api_predictions():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT i.item_name, i.system_qty,
               op.prediction_quantity, op.prediction_order_by_date
        FROM order_predictions op
        JOIN inventory_items i ON op.inventory_item_id = i.id
    """)

    rows = cur.fetchall()
    cur.close()

    today = datetime.date.today()

    result = []
    for r in rows:
        result.append({
            'item_name': r['item_name'],
            'system_qty': r['system_qty'],
            'prediction_quantity': r['prediction_quantity'],
            'order_by_date': fmt_date(r['prediction_order_by_date'])
        })

    return jsonify(result)

# =========================
# RUN APP
# =========================
if __name__ == '__main__':
    app.run(debug=True)
