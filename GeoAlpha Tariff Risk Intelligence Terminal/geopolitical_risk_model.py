
"""
Geopolitical Risk Trajectory Prediction Model
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Architecture: Weighted Ensemble of three complementary signals
  1. Keyword-weighted NLP scorer  — geopolitical risk lexicon applied to headlines
  2. Quantitative trend signal    — escalation index gradient + Goldstein scale
  3. Prediction market odds       — probability-calibrated external signal

Outputs:
  • prediction_label       → "rising" | "stable" | "de-escalating"
  • prediction_confidence  → float [0,1]
  • prediction_scores_all  → dict with all class probabilities
  • run_record             → full provenance dict for auditing

Filesystem versioning:
  geo_risk_model/model_config.json   — model identity + ensemble config
  geo_risk_model/latest_run.json     — most recent inference result
  geo_risk_model/run_log.jsonl       — append-only run history
"""

import os
import re
import json
import math
import numpy as np
from datetime import datetime
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────
LABELS        = ["rising", "stable", "de-escalating"]
MODEL_VERSION = "1.0.0"
MODEL_DIR     = "geo_risk_model"
RUN_TS        = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
NLP_WEIGHT    = 0.45
TREND_WEIGHT  = 0.30
MARKET_WEIGHT = 0.25

os.makedirs(MODEL_DIR, exist_ok=True)
print(f"[{RUN_TS}]  Geopolitical Risk Trajectory Model  v{MODEL_VERSION}")
print(f"  Ensemble weights → NLP: {NLP_WEIGHT} | Trend: {TREND_WEIGHT} | Market: {MARKET_WEIGHT}\n")

# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL 1 — Keyword-weighted NLP geopolitical risk scorer
# Lexicon built from GDELT/CAMEO conflict coding + conflict-studies literature
# ══════════════════════════════════════════════════════════════════════════════

# Polarity lexicons: positive weight → "rising", negative → "de-escalating"
RISING_KEYWORDS = {
    "strikes": 1.8, "aerial": 1.6, "attack": 1.7, "mobilize": 1.5,
    "troops": 1.4, "ceasefire collapse": 2.0, "collapse": 1.5, "withdraw": 1.3,
    "sanctions": 1.2, "tensions rise": 1.9, "tensions": 1.1, "conflict": 1.2,
    "military": 1.3, "missile": 1.8, "bombardment": 1.9, "siege": 1.7,
    "blockade": 1.5, "emergency session": 1.3, "failed": 1.1, "hostilities": 1.6,
}
STABLE_KEYWORDS = {
    "monitor": 0.8, "watchful": 0.7, "cautious": 0.6, "standoff": 0.9,
    "stalemate": 1.0, "no change": 1.0, "status quo": 0.9,
}
DEESC_KEYWORDS = {
    "peace talks": 1.8, "ceasefire": 1.6, "de-escalation": 2.0, "withdrawal": 1.5,
    "mediator": 1.4, "negotiations": 1.2, "humanitarian corridor": 1.5, "openness": 1.2,
    "agreement": 1.4, "truce": 1.8, "dialogue": 1.1, "reconciliation": 1.3,
    "evacuation": 0.9, "aid": 0.8, "diplomatic": 1.0,
}

def keyword_score(text: str) -> dict:
    """Return raw un-normalised scores for each trajectory class."""
    text_lower = text.lower()
    scores = {"rising": 0.0, "stable": 0.0, "de-escalating": 0.0}
    for kw, w in RISING_KEYWORDS.items():
        if kw in text_lower:
            scores["rising"] += w
    for kw, w in STABLE_KEYWORDS.items():
        if kw in text_lower:
            scores["stable"] += w
    for kw, w in DEESC_KEYWORDS.items():
        if kw in text_lower:
            scores["de-escalating"] += w
    return scores

def softmax(scores: dict) -> dict:
    """Convert raw scores to probability distribution via softmax."""
    vals  = np.array([scores[l] for l in LABELS], dtype=float)
    vals  = vals - vals.max()            # numerical stability
    exps  = np.exp(vals)
    probs = exps / exps.sum()
    return dict(zip(LABELS, probs.tolist()))

# Score all headlines + composite text
raw_headline_scores = defaultdict(float)
for _, row in gdelt_df.iterrows():
    hs = keyword_score(row["headline"])
    # Weight by log mention count (more-mentioned events carry more signal)
    weight = math.log1p(row["n_mentions"])
    for lbl in LABELS:
        raw_headline_scores[lbl] += hs[lbl] * weight

# Also score the full composite text (captures market signal text)
composite_raw = keyword_score(composite_text)
for lbl in LABELS:
    raw_headline_scores[lbl] += composite_raw[lbl] * 0.5   # lower weight than headlines

# Guard: if all zeros, assign uniform
if all(v == 0 for v in raw_headline_scores.values()):
    raw_headline_scores = {"rising": 1.0, "stable": 1.0, "de-escalating": 1.0}

nlp_scores = softmax(raw_headline_scores)
print("[SIGNAL 1 — NLP keyword scorer]")
print(f"  Raw headline scores : {dict(raw_headline_scores)}")
print(f"  Softmax probs       : { {k: round(v,4) for k,v in nlp_scores.items()} }")

# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL 2 — Quantitative trend encoder
# Features: escalation index gradient + Goldstein scale
# ══════════════════════════════════════════════════════════════════════════════

# Escalation gradient (normalised to [-1, +1])
max_delta  = 20.0   # theoretical max for 7-day window
grad_norm  = float(np.clip(trend_delta / max_delta, -1, 1))

# Goldstein scale (normalised to [-1, +1], range is approx [-10, +10])
gold_norm  = float(np.clip(avg_goldstein / 10.0, -1, 1))

# Combined trend score: positive → rising, negative → de-escalating
trend_signal = (0.7 * grad_norm + 0.3 * (-gold_norm))   # gold<0 → hostile → +rising

def trend_to_probs(signal: float) -> dict:
    """Map scalar trend signal [-1,1] to 3-class soft probability."""
    # rising plateau at +1, de-escalating at -1, stable peaks at 0
    p_rising  = float(np.clip(0.5 + 0.5 * signal, 0.05, 0.90))
    p_deesc   = float(np.clip(0.5 - 0.5 * signal, 0.05, 0.90))
    p_stable  = max(0.05, 1.0 - p_rising - p_deesc)
    # normalise
    _s = p_rising + p_stable + p_deesc
    return {
        "rising":        round(p_rising / _s, 4),
        "stable":        round(p_stable / _s, 4),
        "de-escalating": round(p_deesc  / _s, 4),
    }

trend_probs = trend_to_probs(trend_signal)
print(f"\n[SIGNAL 2 — Quantitative trend]")
print(f"  7-day Δ escalation index : {trend_delta:+.2f}  (normalised: {grad_norm:+.3f})")
print(f"  Avg Goldstein scale      : {avg_goldstein:+.2f}  (normalised: {gold_norm:+.3f})")
print(f"  Combined trend signal    : {trend_signal:+.3f}")
print(f"  Trend probs              : {trend_probs}")

# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL 3 — Prediction market odds
# ══════════════════════════════════════════════════════════════════════════════
mkt_probs = {
    "rising":        float(prediction_market_df["prob_escalation_rising"].iloc[0]),
    "stable":        float(prediction_market_df["prob_escalation_stable"].iloc[0]),
    "de-escalating": float(prediction_market_df["prob_escalation_deescalating"].iloc[0]),
}
print(f"\n[SIGNAL 3 — Prediction market]")
print(f"  {mkt_probs}")

# ══════════════════════════════════════════════════════════════════════════════
# ENSEMBLE FUSION — Weighted average of all three signals
# ══════════════════════════════════════════════════════════════════════════════
ensemble_scores = {}
for lbl in LABELS:
    ensemble_scores[lbl] = (
        NLP_WEIGHT    * nlp_scores[lbl]    +
        TREND_WEIGHT  * trend_probs[lbl]   +
        MARKET_WEIGHT * mkt_probs[lbl]
    )
_total = sum(ensemble_scores.values())
ensemble_scores = {k: v / _total for k, v in ensemble_scores.items()}

prediction_label      = max(ensemble_scores, key=ensemble_scores.get)
prediction_confidence = round(ensemble_scores[prediction_label], 4)
prediction_scores_all = {k: round(v, 4) for k, v in ensemble_scores.items()}

print(f"\n[ENSEMBLE RESULT]")
print(f"  Scores : {prediction_scores_all}")

# ══════════════════════════════════════════════════════════════════════════════
# FILESYSTEM VERSIONING
# ══════════════════════════════════════════════════════════════════════════════
run_record = {
    "run_timestamp":          RUN_TS,
    "model_version":          MODEL_VERSION,
    "model_type":             "keyword_nlp_quant_market_ensemble",
    "labels":                 LABELS,
    "input_text_preview":     composite_text[:200] + "…",
    "nlp_keyword_scores":     {k: round(v, 4) for k, v in nlp_scores.items()},
    "trend_signal":           round(trend_signal, 4),
    "trend_probs":            trend_probs,
    "market_probs":           {k: round(v, 4) for k, v in mkt_probs.items()},
    "ensemble_weights":       {"nlp": NLP_WEIGHT, "trend": TREND_WEIGHT, "market": MARKET_WEIGHT},
    "ensemble_scores":        prediction_scores_all,
    "prediction_label":       prediction_label,
    "prediction_confidence":  prediction_confidence,
    "escalation_index_trend": trend_str,
    "trend_delta":            round(trend_delta, 4),
    "avg_goldstein_scale":    float(avg_goldstein),
}

# Latest run (overwrite)
latest_path = os.path.join(MODEL_DIR, "latest_run.json")
with open(latest_path, "w") as f:
    json.dump(run_record, f, indent=2)

# Append-only run log
log_path = os.path.join(MODEL_DIR, "run_log.jsonl")
with open(log_path, "a") as f:
    f.write(json.dumps(run_record) + "\n")

# Model config (written once, not overwritten on re-runs)
config_path = os.path.join(MODEL_DIR, "model_config.json")
if not os.path.exists(config_path):
    config = {
        "model_type":       "keyword_nlp_quant_market_ensemble",
        "model_version":    MODEL_VERSION,
        "labels":           LABELS,
        "ensemble_weights": {"nlp": NLP_WEIGHT, "trend": TREND_WEIGHT, "market": MARKET_WEIGHT},
        "nlp_component":    "Geopolitical-domain keyword lexicon with softmax normalisation",
        "trend_component":  "Escalation index gradient + Goldstein scale encoding",
        "market_component": "Prediction market probability calibration",
        "created_at":       RUN_TS,
        "description": (
            "Fully self-contained geopolitical risk trajectory classifier. "
            "Fuses domain-expert keyword NLP scoring, quantitative escalation index trend "
            "analysis, and prediction market odds via calibrated weighted ensemble. "
            "Predicts 7-day-ahead trajectory: rising / stable / de-escalating."
        ),
    }
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

with open(log_path) as f:
    n_runs = sum(1 for _ in f)

print(f"\n[PERSISTENCE]")
print(f"  {config_path}   (model config)")
print(f"  {latest_path}   (latest run)")
print(f"  {log_path}      ({n_runs} total run(s) logged)")

# ══════════════════════════════════════════════════════════════════════════════
# FINAL OUTPUT
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'━'*55}")
print(f"  7-DAY GEOPOLITICAL RISK TRAJECTORY FORECAST")
print(f"{'━'*55}")
print(f"  Prediction : {prediction_label.upper()}")
print(f"  Confidence : {prediction_confidence:.1%}")
print(f"\n  Class Distribution:")
for lbl in LABELS:
    pct = prediction_scores_all[lbl]
    bar = "█" * int(pct * 40)
    marker = " ◄" if lbl == prediction_label else ""
    print(f"    {lbl:<18} {pct:.1%}  {bar}{marker}")
print(f"{'━'*55}")
