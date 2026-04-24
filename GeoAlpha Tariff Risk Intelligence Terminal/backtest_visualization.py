import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Zerve dark theme ──────────────────────────────────────────────────────────
BG      = "#1D1D20"
TEXT    = "#fbfbff"
SUBTEXT = "#909094"
BLUE    = "#A1C9F4"
ORANGE  = "#FFB482"
GREEN   = "#8DE5A1"
CORAL   = "#FF9F9B"
GOLD    = "#ffd400"
SUCCESS = "#17b26a"
DANGER  = "#f04438"

matplotlib.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor":   BG,
    "axes.edgecolor":   SUBTEXT,
    "axes.labelcolor":  TEXT,
    "xtick.color":      TEXT,
    "ytick.color":      TEXT,
    "text.color":       TEXT,
    "grid.color":       "#2e2e35",
    "font.family":      "sans-serif",
})

# ── Data prep ─────────────────────────────────────────────────────────────────
events = backtest_summary["event_name"].tolist()
short_labels = [
    "Trade War\n(Jul 2018)",
    "COVID\n(Mar 2020)",
]

# ── Chart 1: Pre-event escalation trajectory ──────────────────────────────────
fig1, ax1 = plt.subplots(figsize=(10, 5), facecolor=BG)
ax1.set_facecolor(BG)

colors = [BLUE, ORANGE]
day_keys = [f"day_minus_{i}" for i in range(7, 0, -1)]

for idx, row in backtest_raw.iterrows():
    traj = row["pre_event_trajectory"]
    vals = [traj.get(k, np.nan) for k in day_keys]
    days = list(range(-7, 0))
    color = colors[idx % len(colors)]
    ax1.plot(days, vals, marker="o", color=color, linewidth=2.5, markersize=6,
             label=short_labels[idx])
    ax1.annotate(f"{vals[-1]:.2f}", xy=(-1, vals[-1]),
                 xytext=(4, 0), textcoords="offset points",
                 color=color, fontsize=9)

ax1.axvline(0, color=CORAL, linestyle="--", linewidth=1.5, alpha=0.7, label="Event Day")
ax1.set_xlabel("Days Before Event", fontsize=11)
ax1.set_ylabel("Escalation Index", fontsize=11)
ax1.set_title("Pre-Event Escalation Index Trajectory", fontsize=14, fontweight="bold", pad=12)
ax1.set_xticks(range(-7, 1))
ax1.set_xticklabels([f"D-{abs(d)}" if d < 0 else "Event" for d in range(-7, 1)])
ax1.legend(facecolor=BG, edgecolor=SUBTEXT, labelcolor=TEXT)
ax1.grid(axis="y", alpha=0.3)
fig1.tight_layout()

# ── Chart 2: Actual vs Predicted Returns by Sector ────────────────────────────
fig2, axes = plt.subplots(1, 2, figsize=(13, 6), facecolor=BG)

event_ids = sector_df["event_id"].unique()
for ax, eid, color, label in zip(axes, event_ids, [BLUE, ORANGE], short_labels):
    sub = sector_df[sector_df["event_id"] == eid].copy()
    x = np.arange(len(sub))
    w = 0.35
    ax.bar(x - w/2, sub["post_return"] * 100,      width=w, color=CORAL,  label="Actual Return",    alpha=0.9)
    ax.bar(x + w/2, sub["predicted_return"] * 100, width=w, color=color,  label="Predicted Return", alpha=0.7)
    ax.axhline(0, color=SUBTEXT, linewidth=0.8, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(sub["sector"].tolist(), rotation=30, ha="right")
    ax.set_ylabel("Return (%)", fontsize=10)
    ax.set_title(f"{label}\nActual vs Predicted Sector Returns", fontsize=12, fontweight="bold")
    ax.legend(facecolor=BG, edgecolor=SUBTEXT, labelcolor=TEXT, fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.set_facecolor(BG)
    ax.tick_params(colors=TEXT)

fig2.suptitle("Sector Return Accuracy: Escalation Signal vs Reality", fontsize=14,
              fontweight="bold", color=TEXT, y=1.01)
fig2.tight_layout()

# ── Chart 3: Hit Rate & MAE scorecard ─────────────────────────────────────────
fig3, axes3 = plt.subplots(1, 2, figsize=(10, 5), facecolor=BG)

# Hit rate bar
hit_rates = backtest_summary["event_hit_rate_pct"].tolist()
bar_colors = [SUCCESS if h == 100 else GOLD for h in hit_rates]
ax_l = axes3[0]
ax_l.set_facecolor(BG)
bars = ax_l.bar(short_labels, hit_rates, color=bar_colors, edgecolor="none", width=0.5)
ax_l.axhline(100, color=SUCCESS, linestyle="--", linewidth=1.2, alpha=0.5)
for bar, h in zip(bars, hit_rates):
    ax_l.text(bar.get_x() + bar.get_width()/2, h + 1, f"{h:.0f}%",
              ha="center", va="bottom", color=TEXT, fontsize=12, fontweight="bold")
ax_l.set_ylim(0, 115)
ax_l.set_ylabel("Hit Rate (%)", fontsize=11)
ax_l.set_title("Direction Prediction Hit Rate\n(Correct / Total Sector Calls)", fontsize=12, fontweight="bold")
ax_l.grid(axis="y", alpha=0.2)

# MAE bar
maes = (backtest_summary["mean_abs_return_error"] * 100).tolist()
ax_r = axes3[1]
ax_r.set_facecolor(BG)
mae_colors = [GOLD if m < 10 else DANGER for m in maes]
bars2 = ax_r.bar(short_labels, maes, color=mae_colors, edgecolor="none", width=0.5)
for bar, m in zip(bars2, maes):
    ax_r.text(bar.get_x() + bar.get_width()/2, m + 0.3, f"{m:.1f}%",
              ha="center", va="bottom", color=TEXT, fontsize=12, fontweight="bold")
ax_r.set_ylabel("Mean Absolute Return Error (%)", fontsize=11)
ax_r.set_title("Return Magnitude Prediction Error\n(Predicted vs Actual, MAE)", fontsize=12, fontweight="bold")
ax_r.grid(axis="y", alpha=0.2)

fig3.suptitle(
    f"Overall Hit Rate: {backtest_metrics['overall_hit_rate']*100:.0f}%  |  "
    f"Overall MAE: {backtest_metrics['overall_mae']*100:.2f}%  |  "
    f"{backtest_metrics['n_sector_calls']} Sector Calls across {backtest_metrics['n_events']} Events",
    fontsize=11, color=GOLD, y=1.03
)
fig3.tight_layout()

print("Backtest visualizations rendered.")
print(f"  Hit rate  : {backtest_metrics['overall_hit_rate']*100:.0f}%")
print(f"  MAE       : {backtest_metrics['overall_mae']*100:.2f}%")
