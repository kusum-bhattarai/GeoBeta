
import requests
import time
import json
import re
import math
import pandas as pd
from datetime import datetime

# ── Configuration ────────────────────────────────────────────────────────────
RATE_LIMIT_DELAY = 0.12   # SEC EDGAR allows ~10 req/sec; stay safe at ~8 req/sec
MAX_TICKERS = len(sp500_tickers_df)   # Process all S&P 500 tickers
BATCH_REPORT_SIZE = 25    # Print progress every N tickers

# ── CIK Lookup Cache ─────────────────────────────────────────────────────────
# Fetch the full EDGAR ticker→CIK map once to avoid repeated requests
print("📥 Fetching EDGAR company tickers index...")
_cik_resp = requests.get(
    "https://www.sec.gov/files/company_tickers.json",
    headers=EDGAR_SEARCH_HEADERS,
    timeout=30
)
_cik_resp.raise_for_status()
_cik_raw = _cik_resp.json()

# Build lookup dict: TICKER_UPPER → zero-padded CIK
_cik_lookup = {}
for _entry in _cik_raw.values():
    _t = _entry['ticker'].upper().replace('-', '.')
    _cik_lookup[_t] = str(_entry['cik_str']).zfill(10)

print(f"✅ CIK index loaded: {len(_cik_lookup):,} companies\n")

# ── Filing ingestion loop ────────────────────────────────────────────────────
edgar_results = []
_errors = []

for _idx, _row in sp500_tickers_df.head(MAX_TICKERS).iterrows():
    _ticker   = _row['ticker']
    _company  = _row['company_name']
    _sector   = _row['sector']
    _sub      = _row['sub_sector']
    
    # Resolve CIK
    _cik_key = _ticker.upper().replace('-', '.')
    _cik = _cik_lookup.get(_cik_key)
    if not _cik:
        _errors.append((_ticker, 'CIK not found'))
        continue
    
    # ── Fetch latest 10-K then fall back to 10-Q ───────────────────────
    _filing = None
    _filing_type = None
    
    _sub_url = f"https://data.sec.gov/submissions/CIK{_cik}.json"
    time.sleep(RATE_LIMIT_DELAY)
    _sub_resp = requests.get(_sub_url, headers=EDGAR_HEADERS, timeout=15)
    if _sub_resp.status_code != 200:
        _errors.append((_ticker, f'submissions HTTP {_sub_resp.status_code}'))
        continue
    
    _sub_data = _sub_resp.json()
    _recent = _sub_data.get('filings', {}).get('recent', {})
    _forms   = _recent.get('form', [])
    _dates   = _recent.get('filingDate', [])
    _accs    = _recent.get('accessionNumber', [])
    _pdocs   = _recent.get('primaryDocument', [])
    
    # Prefer 10-K, then 10-Q
    for _want in ('10-K', '10-Q'):
        for _fi, _form in enumerate(_forms):
            if _form == _want:
                _filing = {
                    'form': _form,
                    'filing_date': _dates[_fi],
                    'accession': _accs[_fi].replace('-', ''),
                    'primary_doc': _pdocs[_fi],
                }
                _filing_type = _form
                break
        if _filing:
            break
    
    if not _filing:
        _errors.append((_ticker, 'No 10-K or 10-Q found'))
        continue
    
    # ── Download filing document ───────────────────────────────────────
    _acc_no   = _filing['accession']
    _pdoc     = _filing['primary_doc']
    _cik_int  = int(_cik)
    _doc_url  = f"https://www.sec.gov/Archives/edgar/data/{_cik_int}/{_acc_no}/{_pdoc}"
    
    time.sleep(RATE_LIMIT_DELAY)
    _doc_resp = requests.get(_doc_url, headers=EDGAR_SEARCH_HEADERS, timeout=25)
    
    if _doc_resp.status_code != 200 or len(_doc_resp.text) < 200:
        _errors.append((_ticker, f'doc fetch HTTP {_doc_resp.status_code}'))
        continue
    
    # ── Extract risk factor text ───────────────────────────────────────
    _risk_text = extract_risk_factor_text(_doc_resp.text, max_chars=60000)
    
    # ── Score tariff exposure ──────────────────────────────────────────
    _score_result = compute_tariff_score(_risk_text)
    
    edgar_results.append({
        'ticker':                _ticker,
        'company_name':          _company,
        'sector':                _sector,
        'sub_sector':            _sub,
        'tariff_exposure_score': _score_result['tariff_exposure_score'],
        'exposure_level':        _score_result['exposure_level'],
        'key_filing_quote':      _score_result['key_filing_quote'],
        'filing_date':           _filing['filing_date'],
        'filing_type':           _filing_type,
        'regions':               _score_result['regions'],  # list → JSONB in DB
    })
    
    # Progress report
    if (len(edgar_results) + len(_errors)) % BATCH_REPORT_SIZE == 0:
        _done = len(edgar_results) + len(_errors)
        _pct  = 100 * _done / MAX_TICKERS
        print(f"  [{_pct:5.1f}%] Processed {_done}/{MAX_TICKERS} | "
              f"OK: {len(edgar_results)} | Errors: {len(_errors)}")

# ── Build final DataFrame ────────────────────────────────────────────────────
edgar_results_df = pd.DataFrame(edgar_results)

print(f"\n{'='*60}")
print(f"✅ EDGAR Ingestion Complete")
print(f"   Tickers processed:  {MAX_TICKERS}")
print(f"   Successful:         {len(edgar_results)}")
print(f"   Errors/skipped:     {len(_errors)}")
if edgar_results_df.shape[0] > 0:
    print(f"\n📊 Exposure Level Distribution:")
    print(edgar_results_df['exposure_level'].value_counts().to_string())
    print(f"\n📊 Score Statistics:")
    print(edgar_results_df['tariff_exposure_score'].describe().round(1).to_string())
    print(f"\n🔍 Top 10 Highest Tariff Exposure:")
    _top10 = edgar_results_df.nlargest(10, 'tariff_exposure_score')[
        ['ticker', 'company_name', 'sector', 'tariff_exposure_score', 'exposure_level']
    ]
    print(_top10.to_string(index=False))
    if _errors:
        print(f"\n⚠️  Errors (first 10):")
        for _t, _e in _errors[:10]:
            print(f"   {_t}: {_e}")
