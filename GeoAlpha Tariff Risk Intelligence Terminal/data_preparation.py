
"""
Data Preparation Block
Synthesizes escalation_index history, GDELT-style events, and prediction market odds
into a format suitable for zero-shot / fine-tuned geopolitical risk trajectory inference.
Since we're on a clean canvas, we simulate realistic data here.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

# ── 1. Escalation Index History (last 30 days) ───────────────────────────────
n_days = 30
dates = [datetime.today() - timedelta(days=n_days - i) for i in range(n_days)]

# Simulate a realistic escalation index (0-100 scale)
noise = np.random.randn(n_days) * 3
trend = np.linspace(35, 62, n_days)
escalation_index = np.clip(trend + noise, 0, 100).tolist()

escalation_df = pd.DataFrame({
    "date": [d.strftime("%Y-%m-%d") for d in dates],
    "escalation_index": [round(v, 2) for v in escalation_index],
})

# ── 2. GDELT-style Event Feed (last 7 days) ───────────────────────────────────
gdelt_events = [
    {"date": (datetime.today() - timedelta(days=6)).strftime("%Y-%m-%d"),
     "headline": "Border tensions rise as troops mobilize near disputed region",
     "actor1": "Country A", "actor2": "Country B", "goldstein_scale": -6.5, "n_mentions": 312},
    {"date": (datetime.today() - timedelta(days=5)).strftime("%Y-%m-%d"),
     "headline": "UN Security Council convenes emergency session on regional conflict",
     "actor1": "UN", "actor2": "Country A", "goldstein_scale": -3.0, "n_mentions": 215},
    {"date": (datetime.today() - timedelta(days=4)).strftime("%Y-%m-%d"),
     "headline": "Ceasefire talks collapse; diplomatic envoy withdraws from negotiations",
     "actor1": "Country A", "actor2": "Country B", "goldstein_scale": -7.2, "n_mentions": 489},
    {"date": (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d"),
     "headline": "Humanitarian corridor opens for civilian evacuation",
     "actor1": "NGO", "actor2": "Country B", "goldstein_scale": 2.5, "n_mentions": 98},
    {"date": (datetime.today() - timedelta(days=2)).strftime("%Y-%m-%d"),
     "headline": "Aerial strikes reported on infrastructure in contested zone",
     "actor1": "Country A", "actor2": "Country B", "goldstein_scale": -8.0, "n_mentions": 674},
    {"date": (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d"),
     "headline": "Sanctions package announced by G7 targeting conflict actors",
     "actor1": "G7", "actor2": "Country A", "goldstein_scale": -4.5, "n_mentions": 541},
    {"date": datetime.today().strftime("%Y-%m-%d"),
     "headline": "Peace talks proposed by regional mediator; parties signal openness",
     "actor1": "Mediator", "actor2": "Country A", "goldstein_scale": 3.8, "n_mentions": 187},
]
gdelt_df = pd.DataFrame(gdelt_events)

# ── 3. Prediction Market Odds ─────────────────────────────────────────────────
prediction_market_df = pd.DataFrame({
    "date": [datetime.today().strftime("%Y-%m-%d")],
    "prob_escalation_rising":      [0.58],
    "prob_escalation_stable":      [0.27],
    "prob_escalation_deescalating":[0.15],
    "market_volume_usd":           [1_250_000],
    "source": ["Metaculus/Manifold composite"],
})

# ── 4. Composite narrative for model input ────────────────────────────────────
recent_index = escalation_df["escalation_index"].tail(7).tolist()
trend_delta  = recent_index[-1] - recent_index[0]
trend_str    = "increasing" if trend_delta > 2 else ("decreasing" if trend_delta < -2 else "flat")

headlines = " | ".join(gdelt_df["headline"].tolist())
avg_goldstein = round(gdelt_df["goldstein_scale"].mean(), 2)

mkt = prediction_market_df.iloc[0]
market_signal = (
    f"Market assigns {mkt['prob_escalation_rising']:.0%} probability to rising escalation, "
    f"{mkt['prob_escalation_stable']:.0%} to stable, and "
    f"{mkt['prob_escalation_deescalating']:.0%} to de-escalating."
)

# Final composite text fed into the NLP model
composite_text = (
    f"7-day escalation index trend is {trend_str} "
    f"(values: {', '.join(str(round(v,1)) for v in recent_index)}). "
    f"Average GDELT Goldstein Scale score over the period: {avg_goldstein} "
    f"(negative = hostile). Recent headlines: {headlines}. {market_signal}"
)

print("=== Data Preparation Summary ===")
print(f"Escalation index (last 7 days): {[round(v,2) for v in recent_index]}")
print(f"Trend: {trend_str} (Δ {trend_delta:+.2f})")
print(f"GDELT avg Goldstein scale: {avg_goldstein}")
print(f"Prediction market — rising: {mkt['prob_escalation_rising']:.0%} | "
      f"stable: {mkt['prob_escalation_stable']:.0%} | "
      f"de-escalating: {mkt['prob_escalation_deescalating']:.0%}")
print(f"\nComposite model input text:\n\"{composite_text}\"")
print("\nAll datasets prepared ✓")
