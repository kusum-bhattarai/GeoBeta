
import pandas as pd
import numpy as np

np.random.seed(42)

# --- S&P 500 tickers sample ---
tickers = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "JPM", "BAC", "XOM",
    "CVX", "WMT", "PG", "JNJ", "UNH", "HD", "MA", "V", "DIS", "NFLX",
    "INTC", "AMD", "QCOM", "TXN", "AVGO", "MU", "AMAT", "LRCX", "KLAC", "MRVL",
    "CAT", "DE", "HON", "MMM", "GE", "LMT", "RTX", "NOC", "GD", "BA",
    "NKE", "SBUX", "MCD", "YUM", "CMG", "DPZ", "QSR", "DENN", "WEN", "JACK",
    "KO", "PEP", "MDLZ", "GIS", "CPB", "HRL", "SJM", "CAG", "MKC", "COST",
    "F", "GM", "STLA", "TM", "HMC", "RIVN", "LCID", "FSR", "WKHS", "GOEV",
    "GS", "MS", "BLK", "SCHW", "AXP", "C", "WFC", "USB", "PNC", "TFC",
    "PFE", "MRNA", "ABBV", "BMY", "LLY", "MRK", "AMGN", "GILD", "BIIB", "REGN",
    "FDX", "UPS", "CHRW", "JBHT", "XPO", "ODFL", "SAIA", "WERN", "LSTR", "KNX",
]

n = len(tickers)

# --- companies (tariff exposure data) ---
# tariff_exposure_score: 0-100 (higher = more exposed to tariffs)
# escalation_index: multiplier reflecting geopolitical escalation severity (1.0 - 2.5)
companies = pd.DataFrame({
    "ticker": tickers,
    "sector": np.random.choice(
        ["Technology", "Energy", "Consumer", "Financials", "Healthcare", "Industrials", "Auto"],
        size=n
    ),
    "tariff_exposure_score": np.random.uniform(5, 95, n).round(2),
    "escalation_index": np.random.uniform(1.0, 2.5, n).round(3),
    "revenue_foreign_pct": np.random.uniform(10, 80, n).round(2),
})

# --- stock_prices (market reaction on Liberation Day) ---
stock_prices = pd.DataFrame({
    "ticker": tickers,
    "price_delta_liberation_day_pct": np.random.uniform(-20, 5, n).round(3),  # mostly negative
    "market_reaction_score": np.random.uniform(0, 100, n).round(2),            # 0=panic, 100=calm
    "avg_volume_ratio": np.random.uniform(0.8, 4.5, n).round(3),               # volume spike ratio
})

# --- prediction_markets ---
prediction_markets = pd.DataFrame({
    "ticker": tickers,
    "odds": np.random.uniform(0.1, 0.9, n).round(4),          # market implied prob of sustained drop
    "odds_7d_change": np.random.uniform(-0.3, 0.3, n).round(4), # change over last 7 days
})

print(f"companies shape:         {companies.shape}")
print(f"stock_prices shape:      {stock_prices.shape}")
print(f"prediction_markets shape:{prediction_markets.shape}")
print("\nSample - companies:")
print(companies.head(3).to_string(index=False))
print("\nSample - stock_prices:")
print(stock_prices.head(3).to_string(index=False))
print("\nSample - prediction_markets:")
print(prediction_markets.head(3).to_string(index=False))
