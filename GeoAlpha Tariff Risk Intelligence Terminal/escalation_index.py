
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
import json
import uuid

# ─────────────────────────────────────────────
# 1.  Connect using DATABASE_URL canvas constant
# ─────────────────────────────────────────────
conn = psycopg2.connect(DATABASE_URL)
cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
print("✅ Connected to Neon database")

# ─────────────────────────────────────────────
# Helper: safe scalar → float
# ─────────────────────────────────────────────
def safe_float(val, default=0.5):
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ═══════════════════════════════════════════════════════════════
# COMPONENT 1: component_deal_inverted
#   = 1 – odds(trade-deal market)
#   prediction_markets.odds ∈ [0,1] is the YES probability
# ═══════════════════════════════════════════════════════════════
cur.execute("""
    SELECT odds
    FROM   prediction_markets
    WHERE  (LOWER(question) LIKE '%trade deal%'
        OR  LOWER(question) LIKE '%deal reached%'
        OR  LOWER(question) LIKE '%trade agreement%')
      AND  market_status NOT IN ('resolved', 'cancelled')
    ORDER  BY updated_at DESC
    LIMIT  1
""")
row = cur.fetchone()
raw_deal_prob = safe_float(row["odds"] if row else None, default=0.5)
component_deal_inverted = round(1.0 - max(0.0, min(1.0, raw_deal_prob)), 6)


# ═══════════════════════════════════════════════════════════════
# COMPONENT 2: component_tariff_odds
#   = odds(tariff-escalation market)
# ═══════════════════════════════════════════════════════════════
cur.execute("""
    SELECT odds
    FROM   prediction_markets
    WHERE  LOWER(question) LIKE '%tariff%'
      AND  market_status NOT IN ('resolved', 'cancelled')
    ORDER  BY updated_at DESC
    LIMIT  1
""")
row = cur.fetchone()
raw_tariff = safe_float(row["odds"] if row else None, default=0.5)
component_tariff_odds = round(max(0.0, min(1.0, raw_tariff)), 6)


# ═══════════════════════════════════════════════════════════════
# COMPONENT 3: component_gdelt_intensity
#   geopolitical_events columns (confirmed):
#   goldstein_scale, tone, event_timestamp
#   Goldstein: –10 (conflict) → +10 (cooperation)  → invert to [0,1]
#   Tone:      negative values → higher escalation  → invert to [0,1]
# ═══════════════════════════════════════════════════════════════
cur.execute("""
    SELECT AVG(goldstein_scale) AS avg_goldstein,
           AVG(tone)            AS avg_tone
    FROM   geopolitical_events
    WHERE  event_timestamp >= NOW() - INTERVAL '7 days'
""")
row = cur.fetchone()
avg_goldstein = safe_float(row["avg_goldstein"] if row else None, default=0.0)
avg_tone      = safe_float(row["avg_tone"]      if row else None, default=0.0)

g_norm = max(0.0, min(1.0, (-avg_goldstein + 10.0) / 20.0))   # invert scale
t_norm = max(0.0, min(1.0, (-avg_tone)      / 10.0))           # invert & normalise
component_gdelt_intensity = round(g_norm * 0.6 + t_norm * 0.4, 6)


# ═══════════════════════════════════════════════════════════════
# COMPONENT 4: component_import_price
#   macro_signals series_id='IR' (FRED Import Price Index)
#   trend_score ∈ [−1, +1] → rescale to [0, 1]
# ═══════════════════════════════════════════════════════════════
cur.execute("""
    SELECT trend_score, value
    FROM   macro_signals
    WHERE  series_id = 'IR'
    ORDER  BY observation_date DESC
    LIMIT  2
""")
rows_ir = cur.fetchall()
if rows_ir and rows_ir[0]["trend_score"] is not None:
    raw_ip = safe_float(rows_ir[0]["trend_score"], default=0.0)
    component_import_price = round(max(0.0, min(1.0, (raw_ip + 1.0) / 2.0)), 6)
elif len(rows_ir) == 2:
    v_new = safe_float(rows_ir[0]["value"])
    v_old = safe_float(rows_ir[1]["value"])
    pct   = (v_new - v_old) / max(abs(v_old), 1e-9)
    component_import_price = round(max(0.0, min(1.0, (pct * 100 + 5.0) / 20.0)), 6)
else:
    component_import_price = 0.5


# ═══════════════════════════════════════════════════════════════
# COMPONENT 5: component_ppi
#   macro_signals series_id='PPIACO'
# ═══════════════════════════════════════════════════════════════
cur.execute("""
    SELECT trend_score, value
    FROM   macro_signals
    WHERE  series_id = 'PPIACO'
    ORDER  BY observation_date DESC
    LIMIT  2
""")
rows_ppi = cur.fetchall()
if rows_ppi and rows_ppi[0]["trend_score"] is not None:
    raw_ppi = safe_float(rows_ppi[0]["trend_score"], default=0.0)
    component_ppi = round(max(0.0, min(1.0, (raw_ppi + 1.0) / 2.0)), 6)
elif len(rows_ppi) == 2:
    v_new = safe_float(rows_ppi[0]["value"])
    v_old = safe_float(rows_ppi[1]["value"])
    pct   = (v_new - v_old) / max(abs(v_old), 1e-9)
    component_ppi = round(max(0.0, min(1.0, (pct * 100 + 5.0) / 20.0)), 6)
else:
    component_ppi = 0.5


# ─────────────────────────────────────────────
# Weights & component summary
# ─────────────────────────────────────────────
WEIGHTS = {
    "component_deal_inverted":   0.30,
    "component_tariff_odds":     0.25,
    "component_gdelt_intensity": 0.20,
    "component_import_price":    0.15,
    "component_ppi":             0.10,
}

components = {
    "component_deal_inverted":   component_deal_inverted,
    "component_tariff_odds":     component_tariff_odds,
    "component_gdelt_intensity": component_gdelt_intensity,
    "component_import_price":    component_import_price,
    "component_ppi":             component_ppi,
}

print("\n── Component scores (normalised 0–1) ──────────────")
for name, val in components.items():
    bar   = "█" * int(val * 20) + "░" * (20 - int(val * 20))
    contr = val * WEIGHTS[name]
    print(f"  {name:<30}  {val:.4f}  (w={WEIGHTS[name]:.2f})  contrib={contr:.4f}  [{bar}]")


# ─────────────────────────────────────────────
# Weighted composite index
# ─────────────────────────────────────────────
index_score = sum(components[c] * w for c, w in WEIGHTS.items())
index_score = round(max(0.0, min(1.0, index_score)), 6)


# ─────────────────────────────────────────────
# Severity label
# ─────────────────────────────────────────────
def label_score(score: float) -> str:
    if score < 0.25:  return "low"
    if score < 0.50:  return "medium"
    if score < 0.75:  return "high"
    return "critical"

index_label = label_score(index_score)


# ─────────────────────────────────────────────
# 7-day change (vs oldest row from ~7 days ago)
# ─────────────────────────────────────────────
cur.execute("""
    SELECT index_score
    FROM   escalation_index
    WHERE  computed_at <= NOW() - INTERVAL '6 days 12 hours'
    ORDER  BY computed_at DESC
    LIMIT  1
""")
prev_row    = cur.fetchone()
prev_score  = safe_float(prev_row["index_score"] if prev_row else None, default=None)
index_7d_change = round(index_score - prev_score, 6) if prev_score is not None else None

computed_at = datetime.now(timezone.utc)

print("\n── Escalation Index ──────────────────────────────")
print(f"  index_score     : {index_score:.4f}")
print(f"  index_label     : {index_label}")
print(f"  index_7d_change : {index_7d_change}")
print(f"  computed_at     : {computed_at.isoformat()}")


# ─────────────────────────────────────────────
# Upsert into escalation_index
#   Schema: id(serial), source_id(UNIQUE NOT NULL),
#   computed_at, index_score, label,
#   component_*, index_7d_change, created_at, updated_at
#
#   source_id acts as a unique run key.
#   We use a UUID per run so each execution always inserts
#   a fresh row (idempotent re-runs are controlled upstream
#   by the scheduler; here we log every computation).
# ─────────────────────────────────────────────
_run_source_id = str(uuid.uuid4())

cur.execute("""
    INSERT INTO escalation_index (
        source_id,
        computed_at,
        index_score,
        label,
        index_7d_change,
        component_deal_inverted,
        component_tariff_odds,
        component_gdelt_intensity,
        component_import_price,
        component_ppi
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s
    )
    RETURNING id
""", (
    _run_source_id,
    computed_at,
    index_score,
    index_label,
    index_7d_change,
    component_deal_inverted,
    component_tariff_odds,
    component_gdelt_intensity,
    component_import_price,
    component_ppi,
))
new_id = cur.fetchone()["id"]
conn.commit()

cur.close()
conn.close()

print(f"\n✅  Escalation index inserted — escalation_index.id = {new_id}")
print(f"    source_id (run key) = {_run_source_id}")

# ─────────────────────────────────────────────
# Expose downstream-ready block variables
# ─────────────────────────────────────────────
escalation_index_score     = index_score
escalation_index_label     = index_label
escalation_index_7d_change = index_7d_change
escalation_computed_at     = computed_at.isoformat()
escalation_components      = components

print(f"\n📦 Block variables available downstream:")
print(f"   escalation_index_score     = {escalation_index_score}")
print(f"   escalation_index_label     = {escalation_index_label}")
print(f"   escalation_index_7d_change = {escalation_index_7d_change}")
print(f"   escalation_computed_at     = {escalation_computed_at}")
print(f"   escalation_components:")
for k, v in escalation_components.items():
    print(f"     {k:<30} = {v:.4f}")
