
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Zerve design system ───────────────────────────────────────────────────────
BG      = "#1D1D20"
TEXT    = "#fbfbff"
SUBTEXT = "#909094"
BLUE    = "#A1C9F4"
ORANGE  = "#FFB482"
GREEN   = "#8DE5A1"
CORAL   = "#FF9F9B"
LAVNDR  = "#D0BBFF"
YELLOW  = "#ffd400"

COLOR_MAP = {
    "overpriced":    GREEN,
    "fairly-priced": BLUE,
    "underpriced":   CORAL,
}

# Top 25 by absolute misprice gap
_top25 = mispricing_ranked.head(25).copy()
_colors = _top25["classification"].map(COLOR_MAP).tolist()

# ── CHART 1 — Misprice Gap Waterfall (top 25) ────────────────────────────────
fig1, ax1 = plt.subplots(figsize=(14, 6))
fig1.patch.set_facecolor(BG)
ax1.set_facecolor(BG)

_bars = ax1.bar(
    _top25["ticker"],
    _top25["misprice_gap"],
    color=_colors,
    edgecolor="none",
    width=0.7,
    zorder=3,
)
ax1.axhline(0, color=SUBTEXT, linewidth=0.8, linestyle="--", zorder=2)
ax1.axhline( 3.0, color=GREEN, linewidth=0.6, linestyle=":", alpha=0.5, zorder=2)
ax1.axhline(-3.0, color=CORAL, linewidth=0.6, linestyle=":", alpha=0.5, zorder=2)

ax1.set_title("Mispricing Gap — Top 25 Most Mispriced S&P 500 Stocks", color=TEXT, fontsize=13, pad=12, fontweight="bold")
ax1.set_xlabel("Ticker", color=SUBTEXT, fontsize=10)
ax1.set_ylabel("Misprice Gap (%)", color=SUBTEXT, fontsize=10)
ax1.tick_params(colors=SUBTEXT, labelsize=8)
plt.xticks(rotation=45, ha="right")
for spine in ax1.spines.values():
    spine.set_edgecolor("#333337")

_legend = [
    mpatches.Patch(color=GREEN, label="Overpriced (stock too resilient)"),
    mpatches.Patch(color=BLUE,  label="Fairly-Priced"),
    mpatches.Patch(color=CORAL, label="Underpriced (market over-reacted)"),
]
ax1.legend(handles=_legend, facecolor=BG, edgecolor="#333337", labelcolor=TEXT, fontsize=8, loc="lower left")
ax1.grid(axis="y", color="#333337", linewidth=0.5, zorder=1)
plt.tight_layout()
plt.savefig("misprice_gap_bar.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.show()

# ── CHART 2 — Expected vs Actual Drawdown Scatter (all 100 stocks) ───────────
fig2, ax2 = plt.subplots(figsize=(10, 8))
fig2.patch.set_facecolor(BG)
ax2.set_facecolor(BG)

for cls, clr in COLOR_MAP.items():
    _mask = mispricing_ranked["classification"] == cls
    _sub  = mispricing_ranked[_mask]
    ax2.scatter(
        _sub["actual_drawdown"],
        _sub["expected_drawdown"],
        color=clr, label=cls.capitalize(), s=55, alpha=0.85, edgecolors="none", zorder=3,
    )

# 45° fair-pricing line
_lim = (-55, 10)
ax2.plot(_lim, _lim, color=YELLOW, linewidth=1.0, linestyle="--", label="Fair pricing line", zorder=2)

# Annotate top 5 outliers
_top5 = mispricing_ranked.head(5)
for _, row in _top5.iterrows():
    ax2.annotate(
        row["ticker"],
        xy=(row["actual_drawdown"], row["expected_drawdown"]),
        xytext=(5, 5), textcoords="offset points",
        fontsize=7, color=TEXT, alpha=0.85,
    )

ax2.set_title("Expected vs. Actual Drawdown — Liberation Day", color=TEXT, fontsize=13, pad=12, fontweight="bold")
ax2.set_xlabel("Actual Drawdown on Liberation Day (%)", color=SUBTEXT, fontsize=10)
ax2.set_ylabel("Expected Drawdown (tariff-adjusted model, %)", color=SUBTEXT, fontsize=10)
ax2.tick_params(colors=SUBTEXT, labelsize=9)
for spine in ax2.spines.values():
    spine.set_edgecolor("#333337")
ax2.legend(facecolor=BG, edgecolor="#333337", labelcolor=TEXT, fontsize=9)
ax2.grid(color="#333337", linewidth=0.5, zorder=1)
plt.tight_layout()
plt.savefig("expected_vs_actual_scatter.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.show()

# ── CHART 3 — Classification breakdown by sector ─────────────────────────────
_sector_cls = (
    mispricing_ranked
    .groupby(["sector", "classification"])
    .size()
    .unstack(fill_value=0)
    .reindex(columns=["overpriced", "fairly-priced", "underpriced"], fill_value=0)
)
_sectors = _sector_cls.index.tolist()
_x = np.arange(len(_sectors))
_w = 0.25

fig3, ax3 = plt.subplots(figsize=(12, 6))
fig3.patch.set_facecolor(BG)
ax3.set_facecolor(BG)

ax3.bar(_x - _w, _sector_cls["overpriced"],    width=_w, color=GREEN, label="Overpriced",    edgecolor="none")
ax3.bar(_x,      _sector_cls["fairly-priced"], width=_w, color=BLUE,  label="Fairly-Priced", edgecolor="none")
ax3.bar(_x + _w, _sector_cls["underpriced"],   width=_w, color=CORAL, label="Underpriced",   edgecolor="none")

ax3.set_xticks(_x)
ax3.set_xticklabels(_sectors, rotation=30, ha="right", color=SUBTEXT, fontsize=9)
ax3.set_ylabel("Number of Stocks", color=SUBTEXT, fontsize=10)
ax3.set_title("Mispricing Classification by Sector", color=TEXT, fontsize=13, pad=12, fontweight="bold")
ax3.tick_params(colors=SUBTEXT)
for spine in ax3.spines.values():
    spine.set_edgecolor("#333337")
ax3.legend(facecolor=BG, edgecolor="#333337", labelcolor=TEXT, fontsize=9)
ax3.grid(axis="y", color="#333337", linewidth=0.5, zorder=0)
plt.tight_layout()
plt.savefig("classification_by_sector.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.show()

print("All 3 charts rendered successfully.")
