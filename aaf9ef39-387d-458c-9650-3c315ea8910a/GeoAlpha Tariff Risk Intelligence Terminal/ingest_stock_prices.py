import requests
import pandas as pd
import time
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, date

# ── Config ──────────────────────────────────────────────────────────────────
API_KEY = ALPHA_VANTAGE_API_KEY          # Secret constant from canvas assets
LIBERATION_DAY = date(2026, 4, 2)       # April 2, 2026 — Liberation Day tariff announcement
RATE_LIMIT_CALLS = 5                    # Alpha Vantage free tier: 5 calls/min
RATE_LIMIT_WINDOW = 62                  # 62s sliding window
MIN_CALL_GAP = 13                       # Minimum seconds between consecutive calls
#   → 13s gap ensures ≤ ~4.6 calls/min, safely under the 5/min limit
#   → Also avoids triggering the per-second burst warning
OUTPUTSIZE = "compact"                  # last ~100 trading days (free tier)

# ── DB Connection (uses DATABASE_URL secret) ─────────────────────────────────
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor()

# ── Helper: fetch TIME_SERIES_DAILY from Alpha Vantage (free tier) ───────────
def fetch_daily(ticker: str, api_key: str) -> pd.DataFrame:
    """
    Fetches daily OHLCV using TIME_SERIES_DAILY (free tier, outputsize=compact).
    Returns the last ~100 trading days. adjusted_close = close (no adjustment on free tier).
    """
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "outputsize": OUTPUTSIZE,
        "datatype": "json",
        "apikey": api_key,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    if "Error Message" in payload:
        raise ValueError(f"Alpha Vantage error for {ticker}: {payload['Error Message']}")
    if "Note" in payload:
        raise RuntimeError(f"Alpha Vantage rate-limit (Note) for {ticker}: {payload['Note']}")
    if "Information" in payload:
        raise RuntimeError(f"Alpha Vantage rate-limit (Info) for {ticker}: {payload['Information']}")

    ts = payload.get("Time Series (Daily)", {})
    if not ts:
        raise ValueError(f"No time-series data returned for {ticker}")

    records = []
    for date_str, values in ts.items():
        _close = float(values["4. close"])
        records.append({
            "source_id":         f"{ticker}_{date_str}",
            "price_date":        date_str,
            "open_price":        float(values["1. open"]),
            "high_price":        float(values["2. high"]),
            "low_price":         float(values["3. low"]),
            "close_price":       _close,
            "adjusted_close":    _close,   # free tier: no split/dividend adjustment
            "volume":            int(values["5. volume"]),
            "dividend_amount":   0.0,
            "split_coefficient": 1.0,
        })

    _df = pd.DataFrame(records)
    _df["price_date"] = pd.to_datetime(_df["price_date"]).dt.date
    _df = _df.sort_values("price_date").reset_index(drop=True)
    return _df


def compute_liberation_day_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds price_delta_liberation_day_pct, market_reaction_score, and reaction_score_adj.

    price_delta_liberation_day_pct:
        % change of close vs. Liberation Day reference close (April 2, 2026 or
        last trading day on/before that date).

    market_reaction_score:
        sign(delta) * sqrt(|delta| * volume_ratio)
        volume_ratio = volume / 30-day trailing avg volume (no look-ahead).

    reaction_score_adj:
        Winsorized market_reaction_score capped at ±10.
    """
    import numpy as np
    df = df.copy()

    _ld_candidates = df[df["price_date"] <= LIBERATION_DAY]
    if _ld_candidates.empty:
        df["price_delta_liberation_day_pct"] = None
        df["market_reaction_score"] = None
        df["reaction_score_adj"] = None
        return df

    _ld_close = _ld_candidates.iloc[-1]["adjusted_close"]

    df["price_delta_liberation_day_pct"] = (
        (df["adjusted_close"] / _ld_close - 1) * 100
    ).round(4)

    df["_vol_30d_avg"] = (
        df["volume"].rolling(window=30, min_periods=1).mean().shift(1)
    )
    df["_volume_ratio"] = df["volume"] / df["_vol_30d_avg"].replace(0, 1)

    _delta = df["price_delta_liberation_day_pct"].fillna(0)
    _vr    = df["_volume_ratio"].fillna(1)
    df["market_reaction_score"] = (
        np.sign(_delta) * np.sqrt(np.abs(_delta) * _vr)
    ).round(4)

    df["reaction_score_adj"] = df["market_reaction_score"].clip(-10, 10).round(4)
    df.drop(columns=["_vol_30d_avg", "_volume_ratio"], inplace=True)
    return df


# ── Upsert SQL — conflict on source_id ───────────────────────────────────────
UPSERT_SQL = """
INSERT INTO stock_prices (
    source_id, ticker, price_date,
    open_price, high_price, low_price, close_price,
    adjusted_close, volume, dividend_amount, split_coefficient,
    price_delta_liberation_day_pct, market_reaction_score, reaction_score_adj,
    created_at, updated_at
) VALUES %s
ON CONFLICT (source_id) DO UPDATE SET
    open_price                     = EXCLUDED.open_price,
    high_price                     = EXCLUDED.high_price,
    low_price                      = EXCLUDED.low_price,
    close_price                    = EXCLUDED.close_price,
    adjusted_close                 = EXCLUDED.adjusted_close,
    volume                         = EXCLUDED.volume,
    dividend_amount                = EXCLUDED.dividend_amount,
    split_coefficient              = EXCLUDED.split_coefficient,
    price_delta_liberation_day_pct = EXCLUDED.price_delta_liberation_day_pct,
    market_reaction_score          = EXCLUDED.market_reaction_score,
    reaction_score_adj             = EXCLUDED.reaction_score_adj,
    updated_at                     = NOW();
"""

def upsert_ticker_data(cur, ticker: str, df: pd.DataFrame):
    """Bulk-upsert a DataFrame of OHLCV rows for one ticker."""
    _now = datetime.utcnow()
    rows = [
        (
            row.source_id,
            ticker,
            row.price_date,
            row.open_price,
            row.high_price,
            row.low_price,
            row.close_price,
            row.adjusted_close,
            int(row.volume),
            row.dividend_amount,
            row.split_coefficient,
            row.price_delta_liberation_day_pct,
            row.market_reaction_score,
            row.reaction_score_adj,
            _now,
            _now,
        )
        for row in df.itertuples(index=False)
    ]
    execute_values(cur, UPSERT_SQL, rows)


# ── Main ingestion loop ──────────────────────────────────────────────────────
tickers = companies_df["ticker"].tolist()

ingestion_results = []
_call_timestamps = []
_last_call_time = None   # for minimum gap enforcement

print(f"🚀 Starting Alpha Vantage ingestion for {len(tickers)} tickers")
print(f"   Liberation Day reference : {LIBERATION_DAY}")
print(f"   Rate limit               : {RATE_LIMIT_CALLS} calls / {RATE_LIMIT_WINDOW}s  |  min gap = {MIN_CALL_GAP}s")
print(f"   Endpoint                 : TIME_SERIES_DAILY | outputsize={OUTPUTSIZE}\n")

for _idx, ticker in enumerate(tickers):
    # ── Throttle 1: minimum gap between consecutive calls ────────────────────
    if _last_call_time is not None:
        _elapsed = time.monotonic() - _last_call_time
        if _elapsed < MIN_CALL_GAP:
            _pause = MIN_CALL_GAP - _elapsed
            print(f"   ⏸  Throttling {_pause:.1f}s (min gap)...")
            time.sleep(_pause)

    # ── Throttle 2: sliding-window guard (5 calls / 62s) ────────────────────
    _now = time.monotonic()
    _call_timestamps = [t for t in _call_timestamps if _now - t < RATE_LIMIT_WINDOW]

    if len(_call_timestamps) >= RATE_LIMIT_CALLS:
        _wait = RATE_LIMIT_WINDOW - (_now - _call_timestamps[0]) + 1.0
        print(f"   ⏳ Window limit reached — waiting {_wait:.1f}s...")
        time.sleep(max(_wait, 0))

    _call_timestamps.append(time.monotonic())
    _last_call_time = time.monotonic()

    print(f"[{_idx+1}/{len(tickers)}] Fetching {ticker}...", end=" ", flush=True)

    _ticker_df = fetch_daily(ticker, API_KEY)
    _ticker_df = compute_liberation_day_metrics(_ticker_df)

    upsert_ticker_data(cur, ticker, _ticker_df)
    conn.commit()

    _latest = _ticker_df.iloc[-1]
    _ld_delta = round(float(_latest.price_delta_liberation_day_pct), 2) if _latest.price_delta_liberation_day_pct is not None else None
    _mrs = round(float(_latest.market_reaction_score), 4) if _latest.market_reaction_score is not None else None

    ingestion_results.append({
        "ticker":           ticker,
        "rows_upserted":    len(_ticker_df),
        "date_range":       f"{_ticker_df.iloc[0].price_date} → {_latest.price_date}",
        "latest_close":     round(float(_latest.close_price), 2),
        "ld_pct_delta":     _ld_delta,
        "market_rxn_score": _mrs,
        "status":           "✅ OK",
    })
    print(f"✅  {len(_ticker_df)} rows | Δ_LD={_ld_delta}% | MRS={_mrs}")

# ── Cleanup & Summary ────────────────────────────────────────────────────────
cur.close()
conn.close()

ingestion_summary_df = pd.DataFrame(ingestion_results)

print("\n" + "="*80)
print("📊 INGESTION SUMMARY")
print("="*80)
print(ingestion_summary_df.to_string(index=False))
print(f"\n✅ Total tickers processed : {len(ingestion_results)}")
print(f"   Total rows upserted     : {ingestion_summary_df['rows_upserted'].sum():,}")
