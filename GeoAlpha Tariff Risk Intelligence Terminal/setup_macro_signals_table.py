
import psycopg2
import os

# Connect via DATABASE_URL constant (available as variable in canvas)
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS macro_signals (
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

print("✅ macro_signals table created (or already exists).")
cur.close()
conn.close()
