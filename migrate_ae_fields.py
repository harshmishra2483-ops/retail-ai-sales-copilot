
import sqlite3

DB = "retail_ai_sales_copilot_v3.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

def add_column(table, column, definition):
    cols = [row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"ADDED: {table}.{column}")
    else:
        print(f"EXISTS: {table}.{column}")

add_column("retailer_orders", "area", "TEXT DEFAULT ''")
add_column("retailer_orders", "priority", "TEXT DEFAULT 'Normal'")
add_column("retailer_orders", "ai_reason", "TEXT DEFAULT ''")
add_column("retailer_orders", "requested_by", "TEXT DEFAULT 'Retailer'")
add_column("retailer_orders", "ae_decision", "TEXT DEFAULT ''")
add_column("retailer_orders", "ae_decided_at", "TEXT DEFAULT ''")
add_column("retailer_orders", "ae_notes", "TEXT DEFAULT ''")

conn.commit()

print("MIGRATION STRUCTURE READY")
print("EXISTING ORDERS PRESERVED:", cur.execute("SELECT COUNT(*) FROM retailer_orders").fetchone()[0])

conn.close()
