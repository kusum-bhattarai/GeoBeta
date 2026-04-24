
# Fetches trade-war/tariff prediction markets from Polymarket Gamma API (public read, no auth).
# 4 targeted HTTP calls only — no pagination — to stay within compute timeout.

import requests
import json
import os
from datetime import datetime, timezone, timedelta

_G = "https://gamma-api.polymarket.com"
_CUTOFF = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

# Broader keyword set for relevance filtering
_KW = [
    "tariff", "trade war", "trade deal", "import duty", "export ban",
    "wto", "usmca", "customs", "trade policy", "china", "trade restriction",
    "import", "trade", "tariffs",
]
_SM = {
    "tariff":     ["trade-war", "tariff"],
    "trade war":  ["trade-war"],
    "trade deal": ["trade-war", "trade-deal"],
    "import duty":["trade-war", "tariff"],
    "export ban": ["trade-war", "export"],
    "wto":        ["trade-war", "multilateral"],
    "usmca":      ["trade-war", "usmca"],
    "customs":    ["trade-war", "tariff"],
    "china":      ["trade-war", "china"],
}
_TM = {
    "china":        ["FXI", "MCHI"],
    "steel":        ["X", "NUE"],
    "aluminum":     ["AA", "CENX"],
    "auto":         ["F", "GM"],
    "semiconductor":["SOXX", "SMH"],
    "dollar":       ["DXY", "UUP"],
    "oil":          ["USO", "XLE"],
    "eu":           ["EWG", "VGK"],
    "mexico":       ["EWW"],
    "canada":       ["EWC"],
    "agriculture":  ["MOO", "CORN"],
}

def _stags(t):
    _l, _s = t.lower(), set()
    for _k, _v in _SM.items():
        if _k in _l: _s.update(_v)
    return sorted(_s or {"trade-war"})

def _ttags(t):
    _l, _s = t.lower(), set()
    for _k, _v in _TM.items():
        if _k in _l: _s.update(_v)
    return sorted(_s)

def _rel(t):
    return any(_k in t.lower() for _k in _KW)

_hdr = {"Accept": "application/json"}
_pk = os.environ.get("POLY_KEY", "")
if _pk:
    _hdr["Authorization"] = f"Bearer {_pk}"

def _fetch(params):
    _r = requests.get(f"{_G}/markets", params=params, headers=_hdr, timeout=15)
    return _r.json() if _r.status_code == 200 else []

# Probe first page to understand tag structure
_probe = _fetch({"limit": 5, "offset": 0, "active": "true"})
if _probe:
    _sample_tags = [_m.get("tags", []) or _m.get("category", "") for _m in _probe[:3]]
    print(f"Sample market tags: {_sample_tags[:3]}")
    _sample_q = [_m.get("question", "")[:60] for _m in _probe[:3]]
    print(f"Sample questions: {_sample_q}")

# Try different query approaches for Polymarket Gamma API
# Approach 1: tag-based
_raw = (
    _fetch({"tag": "tariffs", "active": "true",  "limit": 100}) +
    _fetch({"tag": "tariffs", "active": "false", "closed": "true", "end_date_min": _CUTOFF, "limit": 100}) +
    _fetch({"tag": "trade",   "active": "true",  "limit": 100}) +
    _fetch({"tag": "trade",   "active": "false", "closed": "true", "end_date_min": _CUTOFF, "limit": 100})
)

print(f"Tag-based raw count: {len(_raw)}")

# Approach 2: keyword search (some Gamma endpoints support ?q=)
_search = _fetch({"q": "tariff", "limit": 100, "active": "true"})
_search += _fetch({"q": "china trade", "limit": 100, "active": "true"})
print(f"Search-based raw count: {len(_search)}")

_raw += _search

# Deduplicate
_seen, _uniq = set(), []
for _m in _raw:
    _id = str(_m.get("id", _m.get("conditionId", "")))
    if _id not in _seen:
        _seen.add(_id)
        _uniq.append(_m)

print(f"Unique markets: {len(_uniq)}")
# Show a few questions to understand API response structure
for _m in _uniq[:3]:
    print(f"  Q: {_m.get('question', _m.get('title', 'N/A'))[:80]}")
    print(f"     active={_m.get('active')} closed={_m.get('closed')} tags={_m.get('tags', 'N/A')}")

def _parse(raw):
    _q = raw.get("question", "") or raw.get("title", "") or ""
    if not _rel(_q):
        return None
    _p = raw.get("outcomePrices", [])
    if isinstance(_p, str): _p = json.loads(_p)
    _yes = float(_p[0]) if isinstance(_p, list) and _p else None
    _vol = next((float(raw[k]) for k in ("volumeNum", "volume", "volume24hr") if raw.get(k) is not None), None)
    _exp = next((raw[k] for k in ("endDate", "end_date", "endDateIso") if raw.get(k)), None)
    _st  = "active" if raw.get("active") else ("resolved" if (raw.get("closed") or raw.get("resolved")) else "unknown")
    _o7  = raw.get("sevenDayPriceChange") or raw.get("oneDayPriceChange")
    return {
        "id":                "poly_" + str(raw.get("id", raw.get("conditionId", ""))),
        "source":            "polymarket",
        "question":          _q,
        "market_status":     _st,
        "current_yes_price": _yes,
        "volume_usd":        _vol,
        "expiry_date":       _exp,
        "odds_7d_change":    float(_o7) if _o7 is not None else None,
        "sector_tags":       _stags(_q),
        "ticker_tags":       _ttags(_q),
        "raw_data":          raw,
    }

polymarket_records = [_p for _m in _uniq if (_p := _parse(_m))]

print(f"\nFinal: Relevant trade-war/tariff contracts: {len(polymarket_records)}")
for _r in polymarket_records[:5]:
    _v = f"${_r['volume_usd']:,.0f}" if _r["volume_usd"] else "N/A"
    print(f"  [{_r['market_status']}] {_r['question'][:75]}")
    print(f"         yes={_r['current_yes_price']}  vol={_v}  tags={_r['sector_tags']}")
