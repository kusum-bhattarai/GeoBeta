
import requests
import pandas as pd
from datetime import datetime, timedelta

# ── FRED series to track ──────────────────────────────────────────────────────
SERIES = {
    "IR":     "Import Price Index (All Commodities)",
    "PPIACO": "Producer Price Index (All Commodities)",
    "CPIAUCSL": "Consumer Price Index (Urban, All Items)",
    "PCEPI":  "PCE Price Index",
    "UNRATE": "Unemployment Rate",
    "BOPGSTB": "Trade Balance (Goods & Services, BOP)",
}

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
# Fetch last 24 months of data to have enough history for trend calculation
start_date = (datetime.today() - timedelta(days=730)).strftime("%Y-%m-%d")

all_records = []

for series_id, series_name in SERIES.items():
    params = {
        "series_id":         series_id,
        "api_key":           FRED_API_KEY,
        "file_type":         "json",
        "observation_start": start_date,
        "sort_order":        "asc",
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    obs = resp.json().get("observations", [])

    for o in obs:
        if o["value"] == ".":          # FRED missing value marker
            continue
        all_records.append({
            "series_id":        series_id,
            "series_name":      series_name,
            "observation_date": o["date"],
            "value":            float(o["value"]),
        })

fred_raw_df = pd.DataFrame(all_records)
fred_raw_df["observation_date"] = pd.to_datetime(fred_raw_df["observation_date"])

print(f"✅ Fetched {len(fred_raw_df)} observations across {fred_raw_df['series_id'].nunique()} series.")
print(fred_raw_df.groupby("series_id")[["observation_date","value"]].agg(
    observations=("value","count"),
    latest_date=("observation_date","max"),
    latest_value=("value","last")
).to_string())
