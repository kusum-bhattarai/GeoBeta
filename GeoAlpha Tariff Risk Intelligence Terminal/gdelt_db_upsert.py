import json
import psycopg2
import psycopg2.extras
import numpy as np
from datetime import datetime

# ─────────────────────────────────────────────────────────────────
# Upsert GDELT events → geopolitical_events (Neon Postgres)
# DATABASE_URL canvas secret constant is injected at runtime
#
# Existing table schema key columns:
#   id (bigint PK auto), source_id (text NOT NULL),
#   source_event_id (text, unique), headline, lat, lon,
#   country, severity (numeric), goldstein_scale, tone,
#   affected_tickers (jsonb), affected_sectors (jsonb),
#   source_url, domain, language, event_timestamp (timestamptz),
#   created_at, updated_at, source_country, actor1, actor2,
#   positive_score, negative_score, published_date, ingested_at
# ─────────────────────────────────────────────────────────────────

ADD_UNIQUE_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'geopolitical_events_source_event_id_key'
    ) THEN
        ALTER TABLE geopolitical_events
            ADD CONSTRAINT geopolitical_events_source_event_id_key
            UNIQUE (source_event_id);
    END IF;
END $$;
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_geo_country  ON geopolitical_events (source_country);",
    "CREATE INDEX IF NOT EXISTS idx_geo_severity ON geopolitical_events (severity);",
    "CREATE INDEX IF NOT EXISTS idx_geo_ingested ON geopolitical_events (ingested_at DESC);",
]

# source_id = 'gdelt' (NOT NULL column)
UPSERT_SQL = """
INSERT INTO geopolitical_events (
    source_id,
    source_event_id,
    headline,
    source_url,
    domain,
    source_country,
    country,
    actor1,
    actor2,
    goldstein_scale,
    tone,
    positive_score,
    negative_score,
    severity,
    affected_tickers,
    affected_sectors,
    published_date,
    language,
    ingested_at,
    updated_at,
    lat,
    lon,
    event_timestamp
) VALUES (
    'gdelt',
    %(source_event_id)s,
    %(headline)s,
    %(source_url)s,
    %(domain)s,
    %(source_country)s,
    %(country)s,
    %(actor1)s,
    %(actor2)s,
    %(goldstein_scale)s,
    %(tone)s,
    %(positive_score)s,
    %(negative_score)s,
    %(severity)s,
    %(affected_tickers)s,
    %(affected_sectors)s,
    %(published_date)s,
    %(language)s,
    %(ingested_at)s,
    %(updated_at)s,
    %(lat)s,
    %(lon)s,
    %(event_timestamp)s
)
ON CONFLICT (source_event_id) DO UPDATE SET
    headline         = EXCLUDED.headline,
    source_url       = EXCLUDED.source_url,
    source_country   = EXCLUDED.source_country,
    country          = EXCLUDED.country,
    actor1           = EXCLUDED.actor1,
    goldstein_scale  = EXCLUDED.goldstein_scale,
    tone             = EXCLUDED.tone,
    positive_score   = EXCLUDED.positive_score,
    negative_score   = EXCLUDED.negative_score,
    severity         = EXCLUDED.severity,
    affected_tickers = EXCLUDED.affected_tickers,
    updated_at       = NOW();
"""

def safe_float(v):
    if v is None: return None
    try:
        f = float(v)
        return None if (f != f) else f
    except (ValueError, TypeError):
        return None

def safe_list(v) -> list:
    if isinstance(v, np.ndarray):    return v.tolist()
    if isinstance(v, (list, tuple)): return list(v)
    return []

def severity_to_numeric(s: str) -> float:
    return {"low": 2.0, "medium": 5.0, "high": 8.0, "critical": 10.0}.get(str(s).lower(), 2.0)

# ─── Prepare rows ────────────────────────────────────────────────
now_iso = datetime.utcnow().isoformat()
db_rows = []

for _, row in gdelt_events_df.iterrows():
    src_url = str(row.get("source_url", "") or "")
    parts   = src_url.split("/")
    domain  = parts[2][:200] if len(parts) > 2 else ""
    country = str(row.get("source_country", "UNKNOWN") or "UNKNOWN")

    db_rows.append({
        "source_event_id":  str(row["event_id"]),
        "headline":         str(row["headline"])[:2000],
        "source_url":       src_url[:1000],
        "domain":           domain,
        "source_country":   country,
        "country":          country,
        "actor1":           str(row.get("actor1", "") or ""),
        "actor2":           str(row.get("actor2", "") or ""),
        "goldstein_scale":  safe_float(row["goldstein_scale"]),
        "tone":             safe_float(row["tone"]),
        "positive_score":   safe_float(row["positive_score"]),
        "negative_score":   safe_float(row["negative_score"]),
        "severity":         severity_to_numeric(row["severity"]),
        "affected_tickers": json.dumps(safe_list(row["affected_tickers"])),
        "affected_sectors": json.dumps([]),
        "published_date":   str(row.get("published_date", "") or ""),
        "language":         str(row.get("language", "") or ""),
        "ingested_at":      now_iso,
        "updated_at":       now_iso,
        "lat":              None,
        "lon":              None,
        "event_timestamp":  now_iso,
    })

print(f"📦 Prepared {len(db_rows)} rows (source_id literal 'gdelt' in SQL)")

# ─── DB ops ──────────────────────────────────────────────────────
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur  = conn.cursor()

cur.execute(ADD_UNIQUE_SQL)
conn.commit()
print("✅ Unique constraint on source_event_id ensured")

for sql in INDEX_SQL:
    cur.execute(sql)
conn.commit()
print("✅ Indexes ensured")

psycopg2.extras.execute_batch(cur, UPSERT_SQL, db_rows, page_size=50)
conn.commit()

# ─── Verify ──────────────────────────────────────────────────────
cur.execute("SELECT COUNT(*), MAX(ingested_at) FROM geopolitical_events;")
total, latest = cur.fetchone()
print(f"\n✅ Upsert complete — {total} total rows in geopolitical_events")
print(f"   Latest ingested_at: {latest}")

cur.execute("""
    SELECT CASE
        WHEN severity < 4 THEN 'low'
        WHEN severity < 7 THEN 'medium'
        WHEN severity < 9 THEN 'high'
        ELSE 'critical'
    END AS sev_label, COUNT(*)
    FROM geopolitical_events
    GROUP BY 1 ORDER BY COUNT(*) DESC;
""")
print("\nSeverity breakdown in DB:")
for sev, cnt in cur.fetchall():
    print(f"  {sev}: {cnt}")

cur.execute("""
    SELECT source_country, COUNT(*)
    FROM geopolitical_events
    WHERE source_id = 'gdelt'
    GROUP BY source_country ORDER BY COUNT(*) DESC LIMIT 10;
""")
print("\nTop GDELT source countries:")
for cty, cnt in cur.fetchall():
    print(f"  {cty}: {cnt}")

cur.execute("""
    SELECT
        COUNT(*) FILTER (WHERE jsonb_array_length(affected_tickers) > 0) AS with_tickers,
        ROUND(AVG(tone)::NUMERIC, 3)            AS avg_tone,
        ROUND(MIN(goldstein_scale)::NUMERIC, 2) AS min_goldstein,
        ROUND(MAX(goldstein_scale)::NUMERIC, 2) AS max_goldstein
    FROM geopolitical_events WHERE source_id = 'gdelt';
""")
wt, at, gmin, gmax = cur.fetchone()
print(f"\nGDELT stats — events with tickers: {wt} | avg_tone: {at} | Goldstein [{gmin}, {gmax}]")

cur.close()
conn.close()

upsert_row_count = len(db_rows)
print(f"\n🎯 GDELT pipeline complete — {upsert_row_count} events upserted into geopolitical_events.")
