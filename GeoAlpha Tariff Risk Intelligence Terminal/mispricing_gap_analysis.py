
import pandas as pd
import numpy as np

# ── 1. JOIN all three datasets on ticker ──────────────────────────────────────
merged = (
    companies
    .merge(stock_prices, on="ticker", how="inner")
    .merge(prediction_markets, on="ticker", how="inner")
)

# ── 2. COMPUTE expected_drawdown ──────────────────────────────────────────────
# Logic:
#   • Base drawdown driven by tariff exposure (0-100 → scaled to 0-25 % drawdown range)
#   • Amplified by escalation_index (1.0–2.5×) reflecting geopolitical severity
#   • Market's implied probability (odds) adjusts for forward-looking signal
#   • odds_7d_change captures momentum — rising odds = more expected pain
#   • Result expressed as a negative percentage (drawdown)
#
#   Formula:
#     raw_drawdown = -(tariff_exposure_score / 100) * 25        # max 25% drop at full exposure
#     escalation_amplified = raw_drawdown * escalation_index    # up to -62.5% at max escalation
#     odds_adjustment = escalation_amplified * (0.5 + odds)    # odds shifts severity [0.6–1.4×]
#     momentum_adj = odds_adjustment * (1 + odds_7d_change)    # rising odds worsen expectation
#     expected_drawdown = clipped at -50% floor (extreme scenarios capped)

merged["_raw_drawdown"] = -(merged["tariff_exposure_score"] / 100.0) * 25.0
merged["_escalation_amplified"] = merged["_raw_drawdown"] * merged["escalation_index"]
merged["_odds_adjustment"] = merged["_escalation_amplified"] * (0.5 + merged["odds"])
merged["expected_drawdown"] = (
    merged["_odds_adjustment"] * (1 + merged["odds_7d_change"])
).clip(lower=-50.0).round(4)

# ── 3. ACTUAL drawdown (direct from Liberation Day price delta) ───────────────
merged["actual_drawdown"] = merged["price_delta_liberation_day_pct"].round(4)

# ── 4. MISPRICE GAP ──────────────────────────────────────────────────────────
# misprice_gap = expected_drawdown − actual_drawdown
#   • Positive gap → stock fell LESS than expected → market OVERPRICED it (premium)
#   • Negative gap → stock fell MORE than expected → market UNDERPRICED the risk
#   • Near zero    → fairly priced

merged["misprice_gap"] = (merged["expected_drawdown"] - merged["actual_drawdown"]).round(4)

# ── 5. CLASSIFY ───────────────────────────────────────────────────────────────
OVERPRICED_THRESHOLD  =  3.0   # actual < expected by >3%  → market is too optimistic
UNDERPRICED_THRESHOLD = -3.0   # actual > expected by >3%  → market over-reacted

def classify(gap):
    if gap > OVERPRICED_THRESHOLD:
        return "overpriced"      # stock held up too well vs. tariff fundamentals
    elif gap < UNDERPRICED_THRESHOLD:
        return "underpriced"     # stock dropped more than fundamentals imply
    else:
        return "fairly-priced"

merged["classification"] = merged["misprice_gap"].apply(classify)

# ── 6. BUILD RANKED OUTPUT DataFrame ─────────────────────────────────────────
mispricing_ranked = (
    merged[[
        "ticker", "sector",
        "tariff_exposure_score", "escalation_index",
        "odds", "odds_7d_change",
        "expected_drawdown", "actual_drawdown",
        "misprice_gap", "classification",
        "market_reaction_score", "avg_volume_ratio",
    ]]
    .assign(abs_misprice_gap=lambda df: df["misprice_gap"].abs())
    .sort_values("abs_misprice_gap", ascending=False)
    .drop(columns="abs_misprice_gap")
    .reset_index(drop=True)
)

mispricing_ranked.index += 1   # 1-based rank
mispricing_ranked.index.name = "rank"

# ── 7. SUMMARY STATS ─────────────────────────────────────────────────────────
_counts = mispricing_ranked["classification"].value_counts()
print("=" * 65)
print("  MISPRICING GAP ANALYSIS — S&P 500 Liberation Day Impact")
print("=" * 65)
print(f"\nClassification breakdown (n={len(mispricing_ranked)}):")
for cls in ["overpriced", "fairly-priced", "underpriced"]:
    print(f"  {cls:<15} : {_counts.get(cls, 0):>4} stocks")

print(f"\nMisprice gap stats:")
print(f"  Mean   : {mispricing_ranked['misprice_gap'].mean():+.2f}%")
print(f"  Std    : {mispricing_ranked['misprice_gap'].std():.2f}%")
print(f"  Min    : {mispricing_ranked['misprice_gap'].min():+.2f}%")
print(f"  Max    : {mispricing_ranked['misprice_gap'].max():+.2f}%")

print(f"\nTop 15 most mispriced stocks:\n")
_display_cols = [
    "ticker", "sector", "tariff_exposure_score",
    "expected_drawdown", "actual_drawdown", "misprice_gap", "classification"
]
print(mispricing_ranked[_display_cols].head(15).to_string())
