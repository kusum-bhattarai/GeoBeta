
import json
import psycopg2
import psycopg2.extras
import uuid

# ── Database connection ───────────────────────────────────────────────────────
_conn = psycopg2.connect(DATABASE_URL)
_conn.autocommit = False
_cur = _conn.cursor()
print("✅ Connected to Neon database")

# ── Inspect full schema of existing companies table ───────────────────────────
_cur.execute("""
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'companies' 
ORDER BY ordinal_position;
""")
_existing_cols = _cur.fetchall()
_existing_col_names = {row[0] for row in _existing_cols}

# Identify NOT NULL columns without defaults (excluding PK)
_notnull_no_default = {
    row[0] for row in _existing_cols 
    if row[2] == 'NO' and row[3] is None and row[0] not in ('id', 'ticker')
}
print(f"ℹ️  Columns with NOT NULL + no default: {_notnull_no_default}")

# ── Add any missing columns ───────────────────────────────────────────────────
_cols_to_add = {
    'tariff_exposure_score': 'NUMERIC',
    'exposure_level': 'TEXT',
    'key_filing_quote': 'TEXT',
    'filing_date': 'DATE',
    'filing_type': 'TEXT',
    'regions': 'JSONB',
    'updated_at': 'TIMESTAMPTZ',
    'sub_sector': 'TEXT',
    'sector': 'TEXT',
    'company_name': 'TEXT',
    'ticker': 'TEXT',
}
for _col, _dtype in _cols_to_add.items():
    if _col not in _existing_col_names:
        _cur.execute(f"ALTER TABLE companies ADD COLUMN IF NOT EXISTS {_col} {_dtype};")
        print(f"   ➕ Added column: {_col} {_dtype}")
_conn.commit()

# ── Ensure UNIQUE constraint on ticker ────────────────────────────────────────
_cur.execute("""
SELECT COUNT(*) FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
WHERE tc.table_name = 'companies' 
    AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
    AND kcu.column_name = 'ticker';
""")
_has_unique_ticker = _cur.fetchone()[0] > 0

if not _has_unique_ticker:
    _cur.execute("""
    DELETE FROM companies a USING companies b 
    WHERE a.id > b.id AND a.ticker IS NOT DISTINCT FROM b.ticker AND b.ticker IS NOT NULL;
    """)
    _cur.execute("ALTER TABLE companies ADD CONSTRAINT companies_ticker_unique UNIQUE (ticker);")
    _conn.commit()
    print("✅ UNIQUE constraint on ticker added")
else:
    print("✅ UNIQUE/PK constraint on ticker already exists")

# ── Indexes ───────────────────────────────────────────────────────────────────
_cur.execute("CREATE INDEX IF NOT EXISTS idx_companies_exposure_level ON companies (exposure_level);")
_cur.execute("CREATE INDEX IF NOT EXISTS idx_companies_score ON companies (tariff_exposure_score DESC NULLS LAST);")
_cur.execute("CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies (sector);")
_conn.commit()
print("✅ Indexes ensured")

# ── Build upsert records — include source_id (NOT NULL requirement) ───────────
# source_id is required NOT NULL — use 'edgar_pipeline' as the source identifier
_records = []
for _, _row in edgar_results_df.iterrows():
    _regions_json = json.dumps(_row['regions']) if isinstance(_row['regions'], list) else json.dumps([])
    _filing_date  = _row['filing_date'] if _row['filing_date'] else None
    _records.append((
        f"edgar_{_row['ticker']}",   # source_id: required NOT NULL
        _row['ticker'],
        _row['company_name'],
        _row['sector'],
        _row['sub_sector'],
        int(_row['tariff_exposure_score']),
        _row['exposure_level'],
        _row['key_filing_quote'][:1000] if _row['key_filing_quote'] else None,
        _filing_date,
        _row['filing_type'],
        _regions_json,
    ))

# ── Batch UPSERT on ticker ────────────────────────────────────────────────────
_upsert_sql = """
INSERT INTO companies 
    (source_id, ticker, company_name, sector, sub_sector, tariff_exposure_score, 
     exposure_level, key_filing_quote, filing_date, filing_type, regions, updated_at)
VALUES 
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
ON CONFLICT (ticker) DO UPDATE SET
    source_id              = EXCLUDED.source_id,
    company_name           = EXCLUDED.company_name,
    sector                 = EXCLUDED.sector,
    sub_sector             = EXCLUDED.sub_sector,
    tariff_exposure_score  = EXCLUDED.tariff_exposure_score,
    exposure_level         = EXCLUDED.exposure_level,
    key_filing_quote       = EXCLUDED.key_filing_quote,
    filing_date            = EXCLUDED.filing_date,
    filing_type            = EXCLUDED.filing_type,
    regions                = EXCLUDED.regions,
    updated_at             = NOW();
"""

psycopg2.extras.execute_batch(_cur, _upsert_sql, _records, page_size=100)
_conn.commit()
print(f"✅ Upserted {len(_records)} records into companies table")

# ── Verify results ────────────────────────────────────────────────────────────
_cur.execute("""
SELECT 
    exposure_level,
    COUNT(*) AS count,
    ROUND(AVG(tariff_exposure_score::numeric), 1) AS avg_score,
    MIN(tariff_exposure_score) AS min_score,
    MAX(tariff_exposure_score) AS max_score
FROM companies
WHERE tariff_exposure_score IS NOT NULL
GROUP BY exposure_level
ORDER BY avg_score DESC;
""")
_stat_rows = _cur.fetchall()
print("\n📊 Database verification — Exposure Level Summary:")
print(f"{'Level':<12} {'Count':>6} {'Avg Score':>10} {'Min':>6} {'Max':>6}")
print("-" * 42)
for _r in _stat_rows:
    print(f"{_r[0]:<12} {_r[1]:>6} {float(_r[2]):>10.1f} {_r[3]:>6} {_r[4]:>6}")

_cur.execute("SELECT COUNT(*) FROM companies WHERE tariff_exposure_score IS NOT NULL;")
_total = _cur.fetchone()[0]
print(f"\n📦 Total scored rows in companies table: {_total}")

_cur.execute("""
SELECT ticker, company_name, sector, tariff_exposure_score, exposure_level, filing_type
FROM companies 
WHERE tariff_exposure_score IS NOT NULL
ORDER BY tariff_exposure_score DESC LIMIT 5;
""")
_top5 = _cur.fetchall()
print("\n🔍 Top 5 Highest Tariff Exposure in DB:")
for _r in _top5:
    print(f"  {_r[0]:<8} {_r[1]:<35} {_r[4]:>8}  {_r[3]:>3}/100  [{_r[5]}]")

_cur.close()
_conn.close()
print("\n✅ Database connection closed. Ingestion pipeline complete!")
