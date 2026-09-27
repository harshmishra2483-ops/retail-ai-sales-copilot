
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

DB_PATH = "retail_ai_sales_copilot_v3.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS outlets(
        outlet_id TEXT PRIMARY KEY,
        outlet_name TEXT,
        city TEXT,
        area TEXT,
        outlet_type TEXT,
        ds_name TEXT,
        area_executive TEXT,
        monthly_potential REAL DEFAULT 0,
        active INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS products(
        product_id TEXT PRIMARY KEY,
        product_name TEXT UNIQUE,
        category TEXT DEFAULT 'Cigarette',
        active INTEGER DEFAULT 1,
        demo_stock INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS visits(
        visit_id TEXT PRIMARY KEY,
        outlet_id TEXT,
        visit_date TEXT,
        ds_name TEXT,
        ds_status TEXT,
        feedback TEXT,
        latitude TEXT,
        longitude TEXT,
        photo_path TEXT,
        ai_summary TEXT,
        ai_category TEXT,
        ai_priority TEXT,
        ai_opportunity_score REAL DEFAULT 0,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS stock_snapshots(
        snapshot_id TEXT PRIMARY KEY,
        outlet_id TEXT,
        visit_id TEXT,
        product_id TEXT,
        quantity INTEGER DEFAULT 0,
        recorded_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS retailer_orders(
        order_id TEXT PRIMARY KEY,
        outlet_id TEXT,
        ds_name TEXT,
        source TEXT,
        status TEXT DEFAULT 'Requested',
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS order_items(
        item_id TEXT PRIMARY KEY,
        order_id TEXT,
        product_id TEXT,
        quantity INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS issues(
        issue_id TEXT PRIMARY KEY,
        outlet_id TEXT,
        visit_date TEXT,
        raw_feedback TEXT,
        category TEXT,
        sub_category TEXT,
        product_service TEXT,
        severity TEXT,
        priority TEXT,
        sentiment TEXT,
        summary TEXT,
        recommended_action TEXT,
        responsible_function TEXT,
        similar_past_issue_ids TEXT,
        ai_confidence TEXT,
        human_decision TEXT,
        final_action TEXT,
        status TEXT,
        assigned_owner TEXT,
        follow_up_date TEXT,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS knowledge_memory(
        memory_id TEXT PRIMARY KEY,
        outlet_id TEXT,
        feedback TEXT,
        category TEXT,
        priority TEXT,
        opportunity_score REAL,
        human_decision TEXT,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS market_snapshots(
        snapshot_id TEXT PRIMARY KEY,
        snapshot_date TEXT,
        source_status TEXT,
        summary TEXT,
        competitiveness_score REAL,
        recommendation TEXT,
        raw_json TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS area_map(
        area TEXT PRIMARY KEY,
        city TEXT,
        area_executive TEXT,
        notes TEXT
    )""")

    conn.commit()
    conn.close()

def list_outlets():
    conn=get_conn()
    rows=conn.execute("SELECT * FROM outlets ORDER BY area,outlet_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_outlet(outlet_id):
    conn=get_conn()
    row=conn.execute("SELECT * FROM outlets WHERE outlet_id=?", (outlet_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def upsert_outlet(data):
    conn=get_conn()
    oid=data.get("outlet_id") or new_id("OUT")
    conn.execute("""INSERT INTO outlets
        (outlet_id,outlet_name,city,area,outlet_type,ds_name,area_executive,monthly_potential,active)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(outlet_id) DO UPDATE SET
        outlet_name=excluded.outlet_name, city=excluded.city, area=excluded.area,
        outlet_type=excluded.outlet_type, ds_name=excluded.ds_name,
        area_executive=excluded.area_executive, monthly_potential=excluded.monthly_potential,
        active=excluded.active""",
        (oid,data.get("outlet_name","Outlet"),data.get("city",""),
         data.get("area",""),data.get("outlet_type",""),data.get("ds_name",""),
         data.get("area_executive",""),float(data.get("monthly_potential") or 0),1))
    conn.commit(); conn.close()
    return oid

def list_products():
    conn=get_conn()
    rows=conn.execute("SELECT * FROM products WHERE active=1 ORDER BY product_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def upsert_product(name, category="Cigarette", demo_stock=0):
    conn=get_conn()
    pid=new_id("PROD")
    conn.execute("""INSERT INTO products(product_id,product_name,category,active,demo_stock)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(product_name) DO UPDATE SET category=excluded.category,
                    active=1,demo_stock=excluded.demo_stock""",
                 (pid,str(name).strip(),category,1,int(demo_stock or 0)))
    conn.commit()
    row=conn.execute("SELECT product_id FROM products WHERE product_name=?", (str(name).strip(),)).fetchone()
    conn.close()
    return row["product_id"]

def insert_visit(record):
    conn=get_conn()
    vid=new_id("VIS")
    conn.execute("""INSERT INTO visits
        (visit_id,outlet_id,visit_date,ds_name,ds_status,feedback,latitude,longitude,
         photo_path,ai_summary,ai_category,ai_priority,ai_opportunity_score,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (vid,record["outlet_id"],record["visit_date"],record.get("ds_name",""),
         record.get("ds_status",""),record.get("feedback",""),record.get("latitude",""),
         record.get("longitude",""),record.get("photo_path",""),record.get("ai_summary",""),
         record.get("ai_category",""),record.get("ai_priority",""),
         float(record.get("ai_opportunity_score") or 0),datetime.now().isoformat()))
    conn.commit(); conn.close()
    return vid

def get_visits():
    conn=get_conn(); rows=conn.execute("SELECT * FROM visits ORDER BY visit_date DESC,created_at DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]

def save_stock_snapshot(outlet_id,visit_id,product_id,quantity):
    conn=get_conn()
    conn.execute("""INSERT INTO stock_snapshots VALUES(?,?,?,?,?,?)""",
                 (new_id("STK"),outlet_id,visit_id,product_id,int(quantity),datetime.now().isoformat()))
    conn.commit(); conn.close()


def get_latest_stock(outlet_id):
    """Return the latest recorded stock quantity for each product at an outlet."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.product_id, p.product_name, s.quantity, s.recorded_at
        FROM stock_snapshots s
        LEFT JOIN products p ON p.product_id = s.product_id
        INNER JOIN (
            SELECT product_id, MAX(recorded_at) AS latest_recorded_at
            FROM stock_snapshots
            WHERE outlet_id = ?
            GROUP BY product_id
        ) latest
        ON s.product_id = latest.product_id
        AND s.recorded_at = latest.latest_recorded_at
        WHERE s.outlet_id = ?
        ORDER BY p.product_name
    """, (outlet_id, outlet_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def has_recent_duplicate_order(outlet_id, ds_name, order_rows, window_minutes=10):
    """
    Prevent accidental double-click/repeated submission of the exact same
    retailer order within a short time window.

    order_rows format:
        [(product_id, product_name, quantity), ...]
    """
    conn = get_conn()

    rows = conn.execute("""
        SELECT o.order_id, o.created_at
        FROM retailer_orders o
        WHERE o.outlet_id = ?
          AND COALESCE(o.ds_name, '') = COALESCE(?, '')
          AND o.status IN ('Requested', 'Submitted')
        ORDER BY o.created_at DESC
    """, (outlet_id, ds_name)).fetchall()

    target = sorted(
        [(str(product_id), int(quantity)) for product_id, _, quantity in order_rows]
    )

    now = datetime.now()

    for row in rows:
        try:
            created = datetime.fromisoformat(row["created_at"])
        except Exception:
            continue

        if now - created > timedelta(minutes=window_minutes):
            continue

        items = conn.execute("""
            SELECT product_id, quantity
            FROM order_items
            WHERE order_id = ?
        """, (row["order_id"],)).fetchall()

        existing = sorted(
            [(str(x["product_id"]), int(x["quantity"])) for x in items]
        )

        if existing == target:
            conn.close()
            return row["order_id"]

    conn.close()
    return None

def create_order(outlet_id, ds_name, source="Retailer request",
                area="", priority="Normal", ai_reason="", requested_by="Retailer"):
    conn = get_conn()
    oid = new_id("ORD")

    conn.execute("""
        INSERT INTO retailer_orders
        (order_id, outlet_id, ds_name, source, status, created_at,
         area, priority, ai_reason, requested_by, ae_decision,
         ae_decided_at, ae_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        oid,
        outlet_id,
        ds_name,
        source,
        "Submitted",
        datetime.now().isoformat(),
        area,
        priority,
        ai_reason,
        requested_by,
        "",
        "",
        "",
    ))

    conn.commit()
    conn.close()
    return oid

def add_order_item(order_id, product_id, quantity):
    conn = get_conn()
    conn.execute(
        "INSERT INTO order_items VALUES(?,?,?,?)",
        (new_id("ITEM"), order_id, product_id, int(quantity))
    )
    conn.commit()
    conn.close()

def get_orders():
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            o.order_id,
            o.outlet_id,
            o.ds_name,
            o.source,
            o.status,
            o.created_at,
            o.area,
            o.priority,
            o.ai_reason,
            o.requested_by,
            o.ae_decision,
            o.ae_decided_at,
            o.ae_notes,
            GROUP_CONCAT(
                p.product_name || ' x ' || i.quantity,
                ', '
            ) items
        FROM retailer_orders o
        LEFT JOIN order_items i ON o.order_id=i.order_id
        LEFT JOIN products p ON p.product_id=i.product_id
        GROUP BY o.order_id
        ORDER BY o.created_at DESC
    """).fetchall()

    conn.close()
    return [dict(r) for r in rows]

def update_order_status(order_id, status):
    conn = get_conn()
    conn.execute(
        "UPDATE retailer_orders SET status=? WHERE order_id=?",
        (status, order_id)
    )
    conn.commit()
    conn.close()

def update_ae_decision(order_id, decision, notes=""):
    conn = get_conn()

    conn.execute("""
        UPDATE retailer_orders
        SET ae_decision=?,
            ae_decided_at=?,
            ae_notes=?
        WHERE order_id=?
    """, (
        decision,
        datetime.now().isoformat(),
        notes,
        order_id,
    ))

    conn.commit()
    conn.close()

def insert_issue(record):
    conn=get_conn(); iid=new_id("ISS")
    fields=["issue_id","outlet_id","visit_date","raw_feedback","category","sub_category",
            "product_service","severity","priority","sentiment","summary","recommended_action",
            "responsible_function","similar_past_issue_ids","ai_confidence","human_decision",
            "final_action","status","assigned_owner","follow_up_date","created_at"]
    vals=[iid]+[record.get(k,"") for k in fields[1:]]
    conn.execute(f"INSERT INTO issues({','.join(fields)}) VALUES({','.join(['?']*len(vals))})",vals)
    conn.commit(); conn.close(); return iid

def get_all_issues():
    conn=get_conn(); rows=conn.execute("SELECT * FROM issues ORDER BY created_at DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_issues_by_outlet(outlet_id):
    conn=get_conn(); rows=conn.execute("SELECT * FROM issues WHERE outlet_id=? ORDER BY visit_date DESC",(outlet_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def save_knowledge_feedback(outlet_id,feedback,category,priority,opportunity_score,human_decision):
    conn=get_conn()
    conn.execute("INSERT INTO knowledge_memory VALUES(?,?,?,?,?,?,?,?)",
                 (new_id("MEM"),outlet_id,feedback,category,priority,float(opportunity_score or 0),
                  human_decision,datetime.now().isoformat()))
    conn.commit(); conn.close()

def knowledge_stats():
    conn=get_conn()
    rows=conn.execute("""SELECT category, COUNT(*) n,
                                SUM(CASE WHEN human_decision='Reject' THEN 1 ELSE 0 END) rejected,
                                AVG(opportunity_score) avg_opportunity
                         FROM knowledge_memory GROUP BY category""").fetchall()
    conn.close(); return [dict(r) for r in rows]

def save_market_snapshot(s):
    conn=get_conn()
    conn.execute("INSERT INTO market_snapshots VALUES(?,?,?,?,?,?,?)",
                 (new_id("MKT"),date.today().isoformat(),s.get("source_status",""),
                  s.get("summary",""),float(s.get("competitiveness_score") or 0),
                  s.get("recommendation",""),s.get("raw_json","")))
    conn.commit(); conn.close()

def latest_market_snapshot():
    conn=get_conn()
    row=conn.execute("SELECT * FROM market_snapshots ORDER BY snapshot_date DESC,rowid DESC LIMIT 1").fetchone()
    conn.close(); return dict(row) if row else None

def import_outlet_dataframe(df):
    df=df.copy()
    df.columns=[str(c).strip().lower().replace(" ","_") for c in df.columns]

    def pick(row, names, default=""):
        for n in names:
            if n in row.index and pd.notna(row[n]):
                return row[n]
        return default

    outlets=products=areas=0
    for _,row in df.iterrows():
        outlet_name=str(pick(row,["outlet_name","outlet","shop_name","retailer_name"],"")).strip()
        if not outlet_name:
            continue
        upsert_outlet({
            "outlet_id": str(pick(row,["outlet_id","outlet_code"],"")).strip() or None,
            "outlet_name": outlet_name,
            "city": str(pick(row,["city"],"")).strip(),
            "area": str(pick(row,["area","zone","location","territory"],"")).strip(),
            "outlet_type": str(pick(row,["outlet_type","shop_type"],"")).strip(),
            "ds_name": str(pick(row,["ds","ds_name","salesperson","field_executive"],"")).strip(),
            "area_executive": str(pick(row,["area_executive","ae","supervisor"],"")).strip(),
            "monthly_potential": pick(row,["monthly_potential","potential","monthly_sales"],0),
        })
        outlets += 1

        product_cell=pick(row,["products","product","sku","brand"],"")
        if product_cell:
            for p in str(product_cell).replace(",",";").split(";"):
                if p.strip():
                    upsert_product(p.strip())
                    products += 1

        area=str(pick(row,["area","zone","location","territory"],"")).strip()
        if area:
            conn=get_conn()
            conn.execute("""INSERT INTO area_map(area,city,area_executive,notes)
                            VALUES(?,?,?,?)
                            ON CONFLICT(area) DO UPDATE SET city=excluded.city,
                            area_executive=excluded.area_executive""",
                         (area,str(pick(row,["city"],"")).strip(),
                          str(pick(row,["area_executive","ae","supervisor"],"")).strip(),"Imported from Excel"))
            conn.commit(); conn.close()
            areas += 1
    return {"outlets":outlets,"products":products,"areas":areas}
