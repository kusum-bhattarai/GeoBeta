import pandas as pd
import numpy as np
import ast

# ── 1. Parse JSON-encoded columns from the DB ─────────────────────────────────
def parse_json_col(val):
    """Safely parse a dict-like string or object."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        return ast.literal_eval(val)
    return {}

backtest_raw["pre_event_trajectory"] = backtest_raw["pre_event_trajectory"].apply(parse_json_col)
backtest_raw["post_event_sector_returns"] = backtest_raw["post_event_sector_returns"].apply(parse_json_col)

# ── 2. Compute pre-event escalation index stats ───────────────────────────────
def traj_stats(traj: dict) -> dict:
    """Derive slope, mean and start/end values from day_minus_N dict."""
    if not traj:
        return {"esc_start": np.nan, "esc_end": np.nan, "esc_mean": np.nan, "esc_slope": np.nan}
    sorted_days = sorted(traj.items(), key=lambda kv: -int(kv[0].replace("day_minus_", "")))
    # sorted_days[0] is the earliest (largest N), sorted_days[-1] is day_minus_1
    values = [float(v) for _, v in sorted_days if v is not None]
    if len(values) < 2:
        return {"esc_start": np.nan, "esc_end": np.nan, "esc_mean": np.nan, "esc_slope": np.nan}
    x = np.arange(len(values), dtype=float)
    slope = float(np.polyfit(x, values, 1)[0])
    return {
        "esc_start": values[0],
        "esc_end":   values[-1],
        "esc_mean":  float(np.mean(values)),
        "esc_slope": slope,
    }

traj_df = pd.DataFrame(backtest_raw["pre_event_trajectory"].apply(traj_stats).tolist())
backtest_raw = pd.concat([backtest_raw.reset_index(drop=True), traj_df], axis=1)

# ── 3. Explode post-event returns into per-sector rows ────────────────────────
sector_rows = []
for _, row in backtest_raw.iterrows():
    for sector, ret in row["post_event_sector_returns"].items():
        if ret is None:
            continue  # skip null return entries
        sector_rows.append({
            "event_id":         row["id"],
            "event_name":       row["event_name"],
            "event_date":       row["event_date"],
            "event_type":       row["event_type"],
            "sector":           sector,
            "post_return":      float(ret),
            "index_was_rising": bool(row["index_was_rising_pre_event"]),
            "esc_slope":        row["esc_slope"],
            "esc_mean":         row["esc_mean"],
            "esc_end":          row["esc_end"],
        })

sector_df = pd.DataFrame(sector_rows)

# ── 4. Signal logic: rising index → predict negative returns ──────────────────
sector_df["signal_predicts_negative"] = sector_df["index_was_rising"]
sector_df["actual_negative"]          = sector_df["post_return"] < 0

# ── 5. Per-sector accuracy ────────────────────────────────────────────────────
sector_df["prediction_correct"] = (
    sector_df["signal_predicts_negative"] == sector_df["actual_negative"]
)

# ── 6. Return magnitude prediction ───────────────────────────────────────────
# Predicted return ≈ –esc_end * sensitivity_factor
SENSITIVITY = 0.10
sector_df["predicted_return"] = np.where(
    sector_df["signal_predicts_negative"],
    -sector_df["esc_end"] * SENSITIVITY,
    sector_df["esc_end"] * SENSITIVITY,
)
sector_df["return_prediction_error"] = sector_df["predicted_return"] - sector_df["post_return"]
sector_df["abs_return_error"]        = sector_df["return_prediction_error"].abs()

# ── 7. Per-event backtest summary ─────────────────────────────────────────────
event_summary = (
    sector_df
    .groupby(["event_id", "event_name", "event_date", "event_type"], as_index=False)
    .agg(
        sectors_evaluated    = ("sector",                  "count"),
        correct_calls        = ("prediction_correct",      "sum"),
        event_hit_rate       = ("prediction_correct",      "mean"),
        avg_post_return      = ("post_return",             "mean"),
        avg_predicted_return = ("predicted_return",        "mean"),
        avg_return_error     = ("return_prediction_error", "mean"),
        mae                  = ("abs_return_error",        "mean"),
        index_was_rising     = ("index_was_rising",        "first"),
        esc_slope            = ("esc_slope",               "first"),
        esc_end              = ("esc_end",                 "first"),
    )
)

event_summary["event_hit_rate_pct"] = (event_summary["event_hit_rate"] * 100).round(1)
event_summary["correct_calls"]      = event_summary["correct_calls"].astype(int)

# ── 8. Overall backtest metrics ───────────────────────────────────────────────
overall_hit_rate   = sector_df["prediction_correct"].mean()
overall_mae        = sector_df["abs_return_error"].mean()
n_events           = len(event_summary)
n_sector_calls     = len(sector_df)
n_correct          = int(sector_df["prediction_correct"].sum())

# ── 9. Final backtest_summary DataFrame (for Streamlit dashboard) ─────────────
backtest_summary = event_summary[[
    "event_id", "event_name", "event_date", "event_type",
    "index_was_rising", "esc_slope", "esc_end",
    "sectors_evaluated", "correct_calls", "event_hit_rate_pct",
    "avg_post_return", "avg_predicted_return", "avg_return_error", "mae",
]].copy()

backtest_summary.rename(columns={
    "esc_slope": "pre_event_esc_slope",
    "esc_end":   "pre_event_esc_value",
    "mae":       "mean_abs_return_error",
}, inplace=True)

float_cols = ["pre_event_esc_slope", "pre_event_esc_value",
              "avg_post_return", "avg_predicted_return",
              "avg_return_error", "mean_abs_return_error"]
backtest_summary[float_cols] = backtest_summary[float_cols].round(4)

# ── 10. Aggregate backtest metrics dict (for dashboard KPI cards) ──────────────
backtest_metrics = {
    "n_events":         n_events,
    "n_sector_calls":   n_sector_calls,
    "n_correct":        n_correct,
    "overall_hit_rate": round(float(overall_hit_rate), 4),
    "overall_mae":      round(float(overall_mae), 4),
}

# ── Print summary ─────────────────────────────────────────────────────────────
print("=" * 65)
print("  BACKTEST SUMMARY — Escalation Index vs. Sector Returns")
print("=" * 65)
print(f"\n  Events replayed    : {n_events}")
print(f"  Sector calls total : {n_sector_calls}")
print(f"  Correct calls      : {n_correct}")
print(f"  Overall hit rate   : {overall_hit_rate:.1%}")
print(f"  Overall MAE        : {overall_mae:.4f}  ({overall_mae*100:.2f}%)")
print()
print("Per-Event Summary:")
print(backtest_summary.to_string(index=False))
print()
print("Per-Sector Detail:")
print(sector_df[[
    "event_name", "sector", "index_was_rising", "post_return",
    "predicted_return", "return_prediction_error", "prediction_correct"
]].to_string(index=False))
