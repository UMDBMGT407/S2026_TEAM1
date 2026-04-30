# =============================================================================
# ai_assistant_module.py
# Place in New/ — same folder as app.py
#
# Exports:
#   get_inventory_snapshot(cur)              → dict
#   build_system_prompt(role, snapshot)      → str
#   call_ai(provider, api_key, sys, msgs)    → str
#
# Schema verified against Dump.sql (uploaded 2026-04-29):
#   inventory_items   : id, item_name, category, system_qty
#   inventory_updates : inventory_item_id, updated_by→users.id, action_type,
#                       qty_change, old_qty, new_qty, created_at
#   delivery_audits   : purchase_order_id, inventory_item_id, quantity_ordered,
#                       quantity_received, received_by→users.id, received_at
#   purchase_orders   : id, supplier_id, order_date, expected_date,
#                       received_date, order_status, audit_status
#   purchase_order_items: purchase_order_id, inventory_item_id, quantity
#   order_predictions : inventory_item_id, prediction_quantity,
#                       prediction_order_by_date
#   suppliers         : id, supplier_name, supplier_address
#   users             : id, name, email, role
# =============================================================================

from datetime import datetime

ANTHROPIC_MODEL = 'claude-haiku-4-5-20251001'
GROQ_MODEL      = 'llama-3.3-70b-versatile'

LOW_STOCK_THRESHOLD  = 5
HIGH_STOCK_THRESHOLD = 50


# =============================================================================
# DB SNAPSHOT
# =============================================================================

def get_inventory_snapshot(cur):
    """
    Run read-only queries and return a structured dict.
    `cur` must be a MySQLdb DictCursor open inside a Flask request context.
    """
    snap = {}

    # 1. All inventory items
    cur.execute("""
        SELECT id, item_name, category, system_qty
        FROM inventory_items
        ORDER BY category, item_name
    """)
    snap['all_items'] = [dict(r) for r in cur.fetchall()]

    snap['zero_stock'] = [i for i in snap['all_items'] if i['system_qty'] == 0]
    snap['low_stock']  = [i for i in snap['all_items']
                          if 0 < i['system_qty'] <= LOW_STOCK_THRESHOLD]
    snap['high_stock'] = [i for i in snap['all_items']
                          if i['system_qty'] >= HIGH_STOCK_THRESHOLD]

    # 2. Recent / open purchase orders
    cur.execute("""
        SELECT po.id,
               s.supplier_name,
               po.order_date,
               po.expected_date,
               po.received_date,
               po.order_status,
               po.audit_status
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.order_status != 'Cancelled'
          AND (po.order_status IN ('Pending','Ordered')
               OR po.order_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY))
        ORDER BY po.order_date DESC
    """)
    snap['purchase_orders'] = [dict(r) for r in cur.fetchall()]

    # 3. Open PO line items
    cur.execute("""
        SELECT po.id AS po_id,
               ii.item_name,
               ii.category,
               poi.quantity AS qty_ordered,
               po.order_status
        FROM purchase_order_items poi
        JOIN purchase_orders po   ON poi.purchase_order_id = po.id
        JOIN inventory_items ii   ON poi.inventory_item_id = ii.id
        WHERE po.order_status IN ('Pending','Ordered')
        ORDER BY po.id, ii.item_name
    """)
    snap['open_po_line_items'] = [dict(r) for r in cur.fetchall()]

    # 4. Recent delivery discrepancies (last 14 days)
    #    Columns confirmed: quantity_ordered, quantity_received, received_by→users.name,
    #                       received_at  (all in delivery_audits schema)
    cur.execute("""
        SELECT da.purchase_order_id,
               ii.item_name,
               da.quantity_ordered,
               da.quantity_received,
               (da.quantity_received - da.quantity_ordered) AS discrepancy,
               u.name  AS received_by,
               da.received_at
        FROM delivery_audits da
        JOIN inventory_items ii ON da.inventory_item_id = ii.id
        JOIN users u            ON da.received_by       = u.id
        WHERE da.received_at >= DATE_SUB(NOW(), INTERVAL 14 DAY)
          AND da.quantity_received != da.quantity_ordered
        ORDER BY da.received_at DESC
        LIMIT 20
    """)
    snap['recent_discrepancies'] = [dict(r) for r in cur.fetchall()]

    # 5. Order predictions
    cur.execute("""
        SELECT ii.item_name,
               op.prediction_quantity,
               op.prediction_order_by_date,
               ii.system_qty AS current_qty
        FROM order_predictions op
        JOIN inventory_items ii ON op.inventory_item_id = ii.id
        WHERE op.prediction_order_by_date >= CURDATE()
        ORDER BY op.prediction_order_by_date ASC
    """)
    snap['predictions'] = [dict(r) for r in cur.fetchall()]

    # 6. Recent inventory activity (last 7 days)
    #    Columns confirmed: action_type enum('Add','Sub','Correct','Receive','Audit'),
    #                       qty_change, old_qty, new_qty, created_at, updated_by→users.name
    cur.execute("""
        SELECT ii.item_name,
               iu.action_type,
               iu.qty_change,
               iu.old_qty,
               iu.new_qty,
               u.name  AS updated_by,
               iu.created_at
        FROM inventory_updates iu
        JOIN inventory_items ii ON iu.inventory_item_id = ii.id
        JOIN users u            ON iu.updated_by        = u.id
        WHERE iu.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        ORDER BY iu.created_at DESC
        LIMIT 25
    """)
    snap['recent_activity'] = [dict(r) for r in cur.fetchall()]

    # 7. Suppliers
    cur.execute("SELECT id, supplier_name, supplier_address FROM suppliers")
    snap['suppliers'] = [dict(r) for r in cur.fetchall()]

    # 8. Pending delivery audits
    cur.execute("""
        SELECT po.id,
               s.supplier_name,
               po.order_date,
               po.received_date,
               po.audit_status
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.order_status = 'Received'
          AND po.audit_status IN ('Pending', 'Awaiting Approval')
        ORDER BY po.received_date DESC
    """)
    snap['pending_audits'] = [dict(r) for r in cur.fetchall()]

    snap['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    return snap


# =============================================================================
# SYSTEM PROMPT BUILDER
# =============================================================================

def _items(lst, show_qty=True):
    if not lst:
        return "  (none)"
    lines = []
    for it in lst:
        if show_qty:
            lines.append(f"  • {it['item_name']} ({it['category']}) — qty: {it['system_qty']}")
        else:
            lines.append(f"  • {it['item_name']} ({it['category']})")
    return "\n".join(lines)


def build_system_prompt(role, snap):
    today = datetime.now().strftime('%B %d, %Y')

    ctx = [
        f"TODAY: {today}",
        "STORE: Kung Fu Tea",
        "",
        "=== ZERO STOCK (must reorder) ===",
        _items(snap['zero_stock']),
        "",
        f"=== LOW STOCK (≤{LOW_STOCK_THRESHOLD} units) ===",
        _items(snap['low_stock']),
    ]

    if snap['pending_audits']:
        pa = "\n".join(
            f"  • PO #{r['id']} from {r['supplier_name']}"
            f" (received {r['received_date']}) — audit: {r['audit_status']}"
            for r in snap['pending_audits']
        )
        ctx += ["", "=== DELIVERY AUDITS AWAITING ACTION ===", pa]

    if role in ('Manager', 'ShiftLead'):
        if snap['recent_discrepancies']:
            disc = "\n".join(
                f"  • {r['item_name']}: ordered {r['quantity_ordered']},"
                f" received {r['quantity_received']}"
                f" ({'+'if r['discrepancy']>0 else ''}{r['discrepancy']})"
                f" on {str(r['received_at'])[:10]}"
                for r in snap['recent_discrepancies']
            )
            ctx += ["", "=== RECENT DELIVERY DISCREPANCIES (last 14 days) ===", disc]

        if snap['open_po_line_items']:
            po_lines = "\n".join(
                f"  • PO #{r['po_id']} [{r['order_status']}]:"
                f" {r['item_name']} × {r['qty_ordered']}"
                for r in snap['open_po_line_items']
            )
            ctx += ["", "=== OPEN PURCHASE ORDER LINE ITEMS ===", po_lines]

        if snap['recent_activity']:
            act = "\n".join(
                f"  • {r['updated_by']} [{r['action_type']}] {r['item_name']}:"
                f" {r['old_qty']} → {r['new_qty']}"
                f" ({'+' if r['qty_change'] >= 0 else ''}{r['qty_change']})"
                for r in snap['recent_activity']
            )
            ctx += ["", "=== INVENTORY ACTIVITY (last 7 days) ===", act]

    if role == 'Manager':
        if snap['predictions']:
            pred = "\n".join(
                f"  • {r['item_name']}: reorder {r['prediction_quantity']} units"
                f" by {r['prediction_order_by_date']} (current: {r['current_qty']})"
                for r in snap['predictions']
            )
            ctx += ["", "=== REORDER PREDICTIONS ===", pred]

        if snap['high_stock']:
            ctx += [f"", f"=== OVERSTOCK (≥{HIGH_STOCK_THRESHOLD} units) ===",
                    _items(snap['high_stock'])]

        if snap['purchase_orders']:
            po_sum = "\n".join(
                f"  • PO #{r['id']} — {r['supplier_name']}"
                f" — ordered {r['order_date']}, status: {r['order_status']},"
                f" audit: {r['audit_status']}"
                for r in snap['purchase_orders']
            )
            ctx += ["", "=== RECENT PURCHASE ORDERS ===", po_sum]

        supps = "\n".join(
            f"  • {s['supplier_name']} — {s['supplier_address']}"
            for s in snap['suppliers']
        )
        ctx += ["", "=== SUPPLIERS ===", supps]

    inventory_context = "\n".join(ctx)

    if role == 'Manager':
        persona = (
            "You are the Inventory AI Assistant for Kung Fu Tea. "
            "You are speaking with the STORE MANAGER — full authority over purchasing, "
            "supplier relationships, and all inventory operations.\n\n"
            "Your job:\n"
            "- Flag low/zero stock immediately with specific reorder recommendations\n"
            "- Highlight delivery audit discrepancies and suggest follow-up steps\n"
            "- Warn about overstock (cash tied up, spoilage risk)\n"
            "- Name the specific supplier and quantity when recommending an order\n"
            "- Summarize recent inventory activity and flag anomalies\n"
            "- Be concise, data-driven, and action-oriented\n"
        )
    elif role == 'ShiftLead':
        persona = (
            "You are the Inventory AI Assistant for Kung Fu Tea. "
            "You are speaking with the SHIFT LEAD — handles day-to-day operations, "
            "receives deliveries, and performs inventory audits.\n\n"
            "Your job:\n"
            "- Alert them to deliveries that need auditing\n"
            "- Flag items running low during their shift\n"
            "- Explain delivery discrepancies from recent audits\n"
            "- Guide them through audit procedures if asked\n"
            "- Escalate purchasing decisions to the manager — suggest but don't authorize\n"
            "- Keep language operational and shift-focused\n"
        )
    else:  # Employee
        persona = (
            "You are the Inventory AI Assistant for Kung Fu Tea. "
            "You are speaking with a TEAM MEMBER (employee).\n\n"
            "Your job:\n"
            "- Answer basic questions about what is currently in stock\n"
            "- Let them know if something is out of stock\n"
            "- Direct purchasing or audit questions to the shift lead or manager\n"
            "- Keep responses friendly, brief, and simple\n"
            "- Do NOT share financial data, supplier details, or audit records\n"
        )

    return (
        f"{persona}\n\n"
        "LIVE INVENTORY SNAPSHOT (from database at time of this request):\n"
        "─────────────────────────────────────────────────────────────────\n"
        f"{inventory_context}\n"
        "─────────────────────────────────────────────────────────────────\n\n"
        "RULES:\n"
        "- Base answers strictly on the snapshot above — never invent numbers\n"
        "- If data is missing or unclear, say so\n"
        "- Keep responses under 200 words unless a full report is requested\n"
        "- Use bullet points for lists\n"
    )


# =============================================================================
# PROVIDER DISPATCHER
# =============================================================================

def call_ai(provider, api_key, system_prompt, messages):
    """
    Call the chosen AI provider. Returns reply string. Raises on error.
    provider: 'groq' or 'anthropic'
    """
    provider = provider.lower().strip()

    if provider == 'groq':
        from groq import Groq
        client = Groq(api_key=api_key)
        groq_messages = [{'role': 'system', 'content': system_prompt}] + messages
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=groq_messages,
            max_tokens=512,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()

    elif provider == 'anthropic':
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=512,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text.strip()

    else:
        raise ValueError(f"Unknown provider '{provider}'. Use 'groq' or 'anthropic'.")
