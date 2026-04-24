
"""
Visualises the geopolitical risk trajectory prediction:
  1. Ensemble confidence score chart (horizontal bar per class)
  2. Signal contribution breakdown (stacked bars)
  3. Escalation index 30-day trend with 7-day window highlight
"""

import json
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

# ── Zerve design tokens ────────────────────────────────────────────────────────
BG      = "#1D1D20"
TEXT    = "#fbfbff"
SUB     = "#909094"
ACCENT  = "#ffd400"
COLORS  = {"rising": "#f04438", "stable": "#A1C9F4", "de-escalating": "#17b26a"}
LABELS  = ["rising", "stable", "de-escalating"]

matplotlib.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG,
    "text.color": TEXT, "axes.labelcolor": TEXT,
    "xtick.color": TEXT, "ytick.color": TEXT,
    "axes.edgecolor": "#3a3a3e", "grid.color": "#3a3a3e",
    "font.family": "sans-serif",
})

# ── FIGURE 1 – Ensemble probability bars ─────────────────────────────────────
fig1, ax1 = plt.subplots(figsize=(9, 4), facecolor=BG)
ax1.set_facecolor(BG)

probs = [prediction_scores_all[l] for l in LABELS]
colors = [COLORS[l] for l in LABELS]
bars = ax1.barh(LABELS, probs, color=colors, height=0.55, zorder=3)

for bar, prob, lbl in zip(bars, probs, LABELS):
    ax1.text(prob + 0.01, bar.get_y() + bar.get_height() / 2,
             f"{prob:.1%}", va="center", ha="left", color=TEXT, fontsize=12, fontweight="bold")
    if lbl == prediction_label:
        ax1.text(-0.01, bar.get_y() + bar.get_height() / 2,
                 "▶ PREDICTED", va="center", ha="right", color=ACCENT, fontsize=9, fontweight="bold")

ax1.set_xlim(0, 1.15)
ax1.set_xlabel("Probability", color=SUB, fontsize=10)
ax1.set_title(
    f"7-Day Geopolitical Risk Trajectory  |  {prediction_label.upper()}  {prediction_confidence:.1%} confidence",
    color=TEXT, fontsize=13, fontweight="bold", pad=14,
)
ax1.axvline(0.5, color=SUB, linewidth=0.6, linestyle="--", alpha=0.5)
ax1.grid(axis="x", alpha=0.2, zorder=0)
ax1.spines[["top", "right"]].set_visible(False)
ax1.tick_params(labelsize=11)
plt.tight_layout()

prediction_confidence_chart = fig1

# ── FIGURE 2 – Signal contribution breakdown ─────────────────────────────────
# Read from run_record
with open("geo_risk_model/latest_run.json") as f:
    run = json.load(f)

signal_data = {
    "NLP\n(Headlines)":  [run["nlp_keyword_scores"][l]  for l in LABELS],
    "Quant\n(Trend)":    [run["trend_probs"][l]          for l in LABELS],
    "Market\n(Odds)":    [run["market_probs"][l]         for l in LABELS],
}
x = np.arange(len(signal_data))
signal_names = list(signal_data.keys())

fig2, ax2 = plt.subplots(figsize=(9, 5), facecolor=BG)
ax2.set_facecolor(BG)

width = 0.22
offsets = [-0.22, 0, 0.22]
legend_patches = []
for i, lbl in enumerate(LABELS):
    vals = [signal_data[sig][i] for sig in signal_names]
    b = ax2.bar(x + offsets[i], vals, width=width, color=COLORS[lbl], alpha=0.88, zorder=3, label=lbl)
    legend_patches.append(mpatches.Patch(color=COLORS[lbl], label=lbl.capitalize()))

ax2.set_xticks(x)
ax2.set_xticklabels(signal_names, fontsize=11, color=TEXT)
ax2.set_ylabel("Probability", color=SUB, fontsize=10)
ax2.set_ylim(0, 1.05)
ax2.set_title("Signal Contribution by Source", color=TEXT, fontsize=13, fontweight="bold", pad=14)
ax2.legend(handles=legend_patches, loc="upper right", framealpha=0.2,
           facecolor=BG, edgecolor="#3a3a3e", labelcolor=TEXT, fontsize=10)
ax2.grid(axis="y", alpha=0.2, zorder=0)
ax2.spines[["top", "right"]].set_visible(False)
plt.tight_layout()

signal_breakdown_chart = fig2

# ── FIGURE 3 – 30-day escalation index trend ─────────────────────────────────
import pandas as pd
idx_vals  = escalation_df["escalation_index"].tolist()
idx_dates = list(range(len(idx_vals)))
window_start = len(idx_vals) - 7

fig3, ax3 = plt.subplots(figsize=(11, 4.5), facecolor=BG)
ax3.set_facecolor(BG)

# Full series
ax3.plot(idx_dates, idx_vals, color="#A1C9F4", linewidth=2.0, zorder=3, label="Escalation Index")
ax3.fill_between(idx_dates, idx_vals, alpha=0.12, color="#A1C9F4")

# 7-day highlight window
ax3.axvspan(window_start - 0.5, len(idx_vals) - 0.5,
            color=COLORS[prediction_label], alpha=0.12, zorder=2)
ax3.plot(idx_dates[window_start:], idx_vals[window_start:],
         color=COLORS[prediction_label], linewidth=2.5, zorder=4, label="7-day analysis window")

# Annotation
mid_x = window_start + 3
mid_y = max(idx_vals[window_start:]) + 4
ax3.annotate(
    f"Forecast: {prediction_label.upper()}\n{prediction_confidence:.1%} confidence",
    xy=(len(idx_vals) - 1, idx_vals[-1]),
    xytext=(mid_x, mid_y),
    fontsize=9, color=ACCENT, fontweight="bold",
    arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.2),
)

ax3.set_xlabel("Day (t-30 → today)", color=SUB, fontsize=10)
ax3.set_ylabel("Escalation Index (0–100)", color=SUB, fontsize=10)
ax3.set_title("30-Day Escalation Index Trend with Forecast Window", color=TEXT,
              fontsize=13, fontweight="bold", pad=14)
ax3.set_ylim(0, 100)
ax3.grid(alpha=0.18, zorder=0)
ax3.spines[["top", "right"]].set_visible(False)
ax3.legend(loc="upper left", framealpha=0.2, facecolor=BG, edgecolor="#3a3a3e",
           labelcolor=TEXT, fontsize=10)
plt.tight_layout()

escalation_trend_chart = fig3

print(f"Visualisations generated ✓")
print(f"  1. prediction_confidence_chart  — class probability bars")
print(f"  2. signal_breakdown_chart       — NLP vs Trend vs Market contributions")
print(f"  3. escalation_trend_chart       — 30-day index with 7-day forecast window")
