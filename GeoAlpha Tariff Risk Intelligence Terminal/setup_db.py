
import psycopg2

db_url = DATABASE_URL  # Canvas constant

conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Create the prediction_markets table with JSONB sector/ticker tags
cur.execute("""
    CREATE TABLE IF NOT EXISTS prediction_markets (
        id                  TEXT PRIMARY KEY,
        source              TEXT NOT NULL,
        question            TEXT NOT NULL,
        market_status       TEXT,
        current_yes_price   NUMERIC(8,4),
        volume_usd          NUMERIC(20,2),
        expiry_date         TIMESTAMPTZ,
        odds_7d_change      NUMERIC(8,4),
        sector_tags         JSONB DEFAULT '[]'::JSONB,
        ticker_tags         JSONB DEFAULT '[]'::JSONB,
        raw_data            JSONB,
        fetched_at          TIMESTAMPTZ DEFAULT NOW(),
        updated_at          TIMESTAMPTZ DEFAULT NOW()
    );
""")

cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_pm_sector_tags
    ON prediction_markets USING GIN (sector_tags);
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_pm_ticker_tags
    ON prediction_markets USING GIN (ticker_tags);
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_pm_source_status
    ON prediction_markets (source, market_status);
""")

conn.commit()
cur.close()
conn.close()

print("✅ prediction_markets table created/verified with GIN indexes on JSONB tag columns.")
print("   Columns: id, source, question, market_status, current_yes_price, volume_usd,")
print("            expiry_date, odds_7d_change, sector_tags, ticker_tags, raw_data,")
print("            fetched_at, updated_at")
