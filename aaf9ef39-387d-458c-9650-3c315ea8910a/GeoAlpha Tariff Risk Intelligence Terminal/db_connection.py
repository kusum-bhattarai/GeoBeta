
import psycopg2
from sqlalchemy import create_engine, text
import pandas as pd

# ---------------------------------------------------------------------------
# Database connection utility using DATABASE_URL constant
# DATABASE_URL is a secret constant available in this canvas
# ---------------------------------------------------------------------------
db_engine = create_engine(DATABASE_URL)

# ---------------------------------------------------------------------------
# Verify connectivity with a lightweight test query
# ---------------------------------------------------------------------------
with db_engine.connect() as conn:
    result = conn.execute(text("SELECT version();"))
    pg_version = result.fetchone()[0]

print(f"✅ Connected to Neon Database")
print(f"   PostgreSQL version: {pg_version}\n")

# ---------------------------------------------------------------------------
# Confirm all 7 required tables are reachable
# ---------------------------------------------------------------------------
required_tables = [
    "companies",
    "stock_prices",
    "escalation_index",
    "geopolitical_events",
    "macro_signals",
    "prediction_markets",
    "backtest_events",
]

table_status = {}
with db_engine.connect() as conn:
    for table in required_tables:
        row = conn.execute(
            text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name=:t"),
            {"t": table},
        ).fetchone()
        exists = row[0] == 1
        if exists:
            count_row = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).fetchone()
            table_status[table] = {"exists": True, "row_count": count_row[0]}
        else:
            table_status[table] = {"exists": False, "row_count": None}

# ---------------------------------------------------------------------------
# Print summary table
# ---------------------------------------------------------------------------
print(f"{'Table':<25} {'Exists':<10} {'Row Count'}")
print("-" * 50)
all_ok = True
for tbl, info in table_status.items():
    status_icon = "✅" if info["exists"] else "❌"
    row_count = info["row_count"] if info["row_count"] is not None else "N/A"
    print(f"{status_icon} {tbl:<23} {str(info['exists']):<10} {row_count}")
    if not info["exists"]:
        all_ok = False

print()
if all_ok:
    print("✅ All 7 tables verified and reachable.")
else:
    print("⚠️  Some tables are missing — check schema above.")

# ---------------------------------------------------------------------------
# Expose reusable engine for downstream blocks
# db_engine  → SQLAlchemy Engine (use with pd.read_sql or engine.connect())
# ---------------------------------------------------------------------------
print(f"\n📦 'db_engine' (SQLAlchemy Engine) is now available for downstream blocks.")
