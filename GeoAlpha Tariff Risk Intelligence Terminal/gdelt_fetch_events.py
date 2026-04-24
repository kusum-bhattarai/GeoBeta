
import requests
import pandas as pd
from datetime import datetime
import time

# ─────────────────────────────────────────────────────────────────
# GDELT 2.0 Doc API – trade-war / tariff events ingestion
# Public API – no key required
# ─────────────────────────────────────────────────────────────────

BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

SEARCH_QUERIES = [
    "tariff trade war",
    "import tax trade restriction",
    "trade dispute sanctions",
    "trade war tariff retaliation",
    "trade embargo trade deal",
]

# ─── Entity → ticker mapping ──────────────────────────────────────
ENTITY_TICKER_MAP = {
    "united states": ["SPY", "DIA", "QQQ"],
    "us ":           ["SPY", "DIA", "QQQ"],
    "america":       ["SPY"],
    "china":         ["FXI", "MCHI", "KWEB"],
    "chinese":       ["FXI", "MCHI"],
    "european union":["EZU", "VGK"],
    "europe":        ["EZU", "VGK"],
    "united kingdom":["EWU", "EWUS"],
    "britain":       ["EWU"],
    "japan":         ["EWJ", "DXJ"],
    "canada":        ["EWC"],
    "canadian":      ["EWC"],
    "mexico":        ["EWW"],
    "mexican":       ["EWW"],
    "australia":     ["EWA"],
    "india":         ["INDA", "EPI"],
    "south korea":   ["EWY"],
    "korea":         ["EWY"],
    "steel":         ["X", "NUE", "STLD"],
    "aluminum":      ["AA", "CENX"],
    "semiconductor": ["SOXX", "SMH", "TSM", "INTC", "NVDA"],
    "automotive":    ["GM", "F", "TM", "HMC"],
    "agriculture":   ["MOO", "WEAT", "CORN", "SOYB"],
    "oil":           ["XLE", "USO", "XOM", "CVX"],
    "technology":    ["QQQ", "XLK", "AAPL", "MSFT"],
    "pharma":        ["XPH", "IHE"],
    "retail":        ["XRT", "AMZN", "WMT"],
}

def fetch_gdelt(query: str, timespan: str = "72h", max_records: int = 250) -> list[dict]:
    """Fetch articles from GDELT Doc 2.0 API."""
    resp = requests.get(
        BASE_URL,
        params={"query": query, "mode": "artlist", "maxrecords": max_records,
                "timespan": timespan, "format": "json", "sort": "hybridrel"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("articles", [])

def parse_tone(tone_str) -> dict:
    keys = ["tone", "positive_score", "negative_score", "polarity",
            "activity_ref_density", "self_group_ref_density", "word_count"]
    parts = str(tone_str or "").split(",")
    result = {}
    for k, v in zip(keys, parts):
        try:
            result[k] = float(v)
        except (ValueError, TypeError):
            pass
    return result

def extract_tickers(article: dict) -> list[str]:
    text = f"{article.get('title', '')} {article.get('sourcecountry', '')}".lower()
    tickers: set[str] = set()
    for entity, tkrs in ENTITY_TICKER_MAP.items():
        if entity in text:
            tickers.update(tkrs)
    return sorted(tickers)

def severity_label(tone: float, goldstein: float) -> str:
    score = abs(goldstein) + abs(tone) * 0.5
    if score >= 15:  return "critical"
    elif score >= 8: return "high"
    elif score >= 4: return "medium"
    else:            return "low"

# ─── Fetch with per-query error tolerance ─────────────────────────
all_articles: list[dict] = []
seen_urls:    set[str]   = set()

print("🌐 Querying GDELT 2.0 Events API …")
for query in SEARCH_QUERIES:
    fetched = 0
    try:
        arts = fetch_gdelt(query, timespan="72h", max_records=250)
        for art in arts:
            url = art.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_articles.append(art)
                fetched += 1
        print(f"  ✓ '{query}' → {len(arts)} articles (+{fetched} unique, total {len(all_articles)})")
    except Exception as exc:
        print(f"  ⚠ '{query}' timed out / failed: {exc}")
    time.sleep(0.3)

print(f"\n📰 Total unique articles: {len(all_articles)}")

# ─── Parse into structured records ────────────────────────────────
records = []
for art in all_articles:
    tone_d   = parse_tone(art.get("tone", ""))
    tone_val = tone_d.get("tone", 0.0)
    goldstein= art.get("goldstein", round(-tone_val * 0.6, 2))
    country  = art.get("sourcecountry", "UNKNOWN").upper().strip() or "UNKNOWN"
    tickers  = extract_tickers(art)
    sev      = severity_label(tone_val, goldstein)
    url      = art.get("url", "")

    records.append({
        "event_id":         url[-64:] if url else "",
        "headline":         art.get("title", ""),
        "source_url":       url,
        "source_country":   country,
        "actor1":           art.get("sourcecountry", ""),
        "actor2":           "",
        "goldstein_scale":  goldstein,
        "tone":             tone_val,
        "positive_score":   tone_d.get("positive_score", 0.0),
        "negative_score":   tone_d.get("negative_score", 0.0),
        "severity":         sev,
        "affected_tickers": tickers,
        "published_date":   art.get("seendate", ""),
        "language":         art.get("language", ""),
        "ingested_at":      datetime.utcnow().isoformat(),
    })

gdelt_events_df = pd.DataFrame(records)

# Remove rows with empty event_id or headline
gdelt_events_df = gdelt_events_df[
    gdelt_events_df["event_id"].str.len() > 0
].reset_index(drop=True)

print(f"\n✅ Parsed {len(gdelt_events_df)} structured events")
print(f"\nSeverity breakdown:\n{gdelt_events_df['severity'].value_counts().to_string()}")
print(f"\nTop source countries:\n{gdelt_events_df['source_country'].value_counts().head(10).to_string()}")
print(f"\nEvents with affected tickers: {(gdelt_events_df['affected_tickers'].map(len) > 0).sum()}")
print(f"\nSample event:")
print(gdelt_events_df[["headline","source_country","severity","goldstein_scale","tone","affected_tickers"]].head(3).to_string())
