
import pandas as pd
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
N_PERIODS      = 6      # rolling window for OLS slope
FLAT_THRESHOLD = 0.10   # |score| below this → 'flat'

# ── Build per-series trend scores manually (avoids groupby column-drop issue) ─
results = []
for sid, grp in fred_raw_df.sort_values(["series_id", "observation_date"]).groupby("series_id"):
    vals   = grp["value"].values.astype(float)
    n      = len(vals)
    slopes = np.full(n, np.nan)

    for i in range(N_PERIODS - 1, n):
        window   = vals[i - N_PERIODS + 1 : i + 1]
        x        = np.arange(N_PERIODS, dtype=float)
        slope    = np.polyfit(x, window, 1)[0]
        mean_abs = np.mean(np.abs(window))
        slopes[i] = slope / mean_abs if mean_abs != 0 else 0.0

    tmp = grp.copy().reset_index(drop=True)
    tmp["trend_score"] = np.round(slopes, 6)
    tmp["direction"]   = [
        "flat" if np.isnan(s) else ("up" if s > FLAT_THRESHOLD else ("down" if s < -FLAT_THRESHOLD else "flat"))
        for s in slopes
    ]
    results.append(tmp)

macro_signals_df = pd.concat(results, ignore_index=True)

print(f"✅ Trend signals computed — {len(macro_signals_df)} rows, columns: {list(macro_signals_df.columns)}")
print("\nLatest signal per series:")
latest_rows = (
    macro_signals_df
    .sort_values("observation_date")
    .drop_duplicates("series_id", keep="last")
    [["series_id", "series_name", "observation_date", "value", "trend_score", "direction"]]
    .reset_index(drop=True)
)
print(latest_rows.to_string(index=False))
