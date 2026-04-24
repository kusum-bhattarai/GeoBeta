
import psycopg2
import psycopg2.extras
import pandas as pd

# ── Connect to Neon PostgreSQL ────────────────────────────────────────────────
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor()

# ── Inspect actual table schema ───────────────────────────────────────────────
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'macro_signals'
    ORDER BY ordinal_position;
""")
schema_rows = cur.fetchall()
print("Current macro_signals schema:")
for col_name, dtype, nullable in schema_rows:
    print(f"  {col_name:<25} {dtype:<20} nullable={nullable}")

# ── Drop and recreate with correct schema ─────────────────────────────────────
# (safe to do since this is initial ingestion)
cur.execute("DROP TABLE IF EXISTS macro_signals;")
cur.execute("""
    CREATE TABLE macro_signals (
        id               SERIAL PRIMARY KEY,
        series_id        VARCHAR(50)   NOT NULL,
        series_name      TEXT          NOT NULL,
        observation_date DATE          NOT NULL,
        value            NUMERIC(18,6),
        trend_score      NUMERIC(10,6),
        direction        VARCHAR(10)   CHECK (direction IN ('up','flat','down')),
        ingested_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        UNIQUE (series_id, observation_date)
    );
""")
conn.commit()
print("\n✅ Table dropped and recreated with correct schema.")

# ── Prepare rows ─────────────────────────────────────────────────────────────
upsert_df = macro_signals_df[
    ["series_id", "series_name", "observation_date", "value", "trend_score", "direction"]
].copy()

upsert_df["trend_score"] = upsert_df["trend_score"].where(
    upsert_df["trend_score"].notna(), other=None
)

upsert_rows = [
    (
        row["series_id"],
        row["series_name"],
        row["observation_date"].date() if hasattr(row["observation_date"], "date") else row["observation_date"],
        float(row["value"]) if pd.notna(row["value"]) else None,
        float(row["trend_score"]) if row["trend_score"] is not None else None,
        row["direction"],
    )
    for _, row in upsert_df.iterrows()
]

# ── Bulk upsert ───────────────────────────────────────────────────────────────
upsert_sql = """
    INSERT INTO macro_signals
        (series_id, series_name, observation_date, value, trend_score, direction, ingested_at)
    VALUES
        (%s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (series_id, observation_date) DO UPDATE SET
        series_name      = EXCLUDED.series_name,
        value            = EXCLUDED.value,
        trend_score      = EXCLUDED.trend_score,
        direction        = EXCLUDED.direction,
        ingested_at      = NOW();
"""

psycopg2.extras.execute_batch(cur, upsert_sql, upsert_rows, page_size=500)
conn.commit()

print(f"✅ Upserted {len(upsert_rows)} rows into macro_signals.")

# ── Verify ────────────────────────────────────────────────────────────────────
cur.execute("""
    SELECT series_id, series_name,
           COUNT(*)              AS total_rows,
           MIN(observation_date) AS earliest,
           MAX(observation_date) AS latest
    FROM macro_signals
    GROUP BY series_id, series_name
    ORDER BY series_id;
""")
rows_check = cur.fetchall()
print(f"\n{'series_id':<12} {'rows':>6}  {'earliest':<12} {'latest':<12}  series_name")
print("-" * 80)
for r in rows_check:
    print(f"{r[0]:<12} {r[2]:>6}  {str(r[3]):<12} {str(r[4]):<12}  {r[1]}")

cur.close()
conn.close()
