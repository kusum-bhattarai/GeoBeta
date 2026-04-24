
import requests
import time
import json
import re
from datetime import datetime

# EDGAR headers — required for respectful usage
EDGAR_HEADERS = {
    "User-Agent": "TariffResearch research@example.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}
EDGAR_SEARCH_HEADERS = {
    "User-Agent": "TariffResearch research@example.com",
    "Accept-Encoding": "gzip, deflate",
}

def get_cik_for_ticker(ticker: str) -> str | None:
    """Resolve ticker to CIK using EDGAR company_tickers.json"""
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=EDGAR_SEARCH_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    ticker_upper = ticker.upper().replace('-', '.')
    for entry in data.values():
        if entry['ticker'].upper() == ticker_upper:
            return str(entry['cik_str']).zfill(10)
    return None

def get_latest_filing(cik: str, form_type: str) -> dict | None:
    """Fetch latest 10-K or 10-Q filing metadata for a CIK."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=EDGAR_HEADERS, timeout=15)
    if resp.status_code != 200:
        return None
    data = resp.json()
    filings = data.get('filings', {}).get('recent', {})
    
    forms = filings.get('form', [])
    dates = filings.get('filingDate', [])
    accessions = filings.get('accessionNumber', [])
    primary_docs = filings.get('primaryDocument', [])
    
    for i, form in enumerate(forms):
        if form == form_type:
            return {
                'form': form,
                'filing_date': dates[i],
                'accession': accessions[i].replace('-', ''),
                'accession_raw': accessions[i],
                'primary_doc': primary_docs[i],
                'cik': cik,
            }
    return None

def fetch_filing_text(cik: str, accession: str, primary_doc: str) -> str:
    """Fetch the text content of a filing document."""
    base_url = f"https://www.sec.gov/Archives/edgar/full-index/{cik}/{accession}/{primary_doc}"
    # Try .htm/.html version
    for doc in [primary_doc, primary_doc.replace('.htm', '.txt')]:
        url = f"https://www.sec.gov/Archives/edgar/full-index/{cik}/{accession}/{doc}"
        # Correct path format
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{doc}"
        try:
            resp = requests.get(url, headers=EDGAR_SEARCH_HEADERS, timeout=20)
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp.text
        except Exception:
            pass
    return ""

def extract_risk_factor_text(html_text: str, max_chars: int = 50000) -> str:
    """Extract the Risk Factors section text from an SEC filing."""
    # Strip HTML tags
    clean = re.sub(r'<[^>]+>', ' ', html_text)
    clean = re.sub(r'&amp;', '&', clean)
    clean = re.sub(r'&nbsp;', ' ', clean)
    clean = re.sub(r'&#\d+;', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    # Find "Risk Factors" section
    patterns = [
        r'(?i)ITEM\s+1A[\.\s]*RISK\s+FACTORS',
        r'(?i)RISK\s+FACTORS',
        r'(?i)Item\s+1A\.',
    ]
    
    start_pos = -1
    for pat in patterns:
        match = re.search(pat, clean)
        if match:
            start_pos = match.start()
            break
    
    if start_pos == -1:
        # Fall back to entire document (truncated)
        return clean[:max_chars]
    
    # Find end of risk factors (next major section)
    end_patterns = [
        r'(?i)ITEM\s+1B[\.\s]',
        r'(?i)ITEM\s+2[\.\s]',
        r'(?i)UNRESOLVED\s+STAFF\s+COMMENTS',
        r'(?i)PROPERTIES',
    ]
    
    section_text = clean[start_pos:start_pos + max_chars]
    end_pos = len(section_text)
    
    for pat in end_patterns:
        match = re.search(pat, section_text[100:])  # skip past header
        if match:
            end_pos = min(end_pos, 100 + match.start())
    
    return section_text[:end_pos]

print("✅ EDGAR fetcher functions defined")
print("   - get_cik_for_ticker(ticker) → CIK string")
print("   - get_latest_filing(cik, form_type) → filing metadata dict")
print("   - fetch_filing_text(cik, accession, primary_doc) → raw HTML text")
print("   - extract_risk_factor_text(html_text) → cleaned risk factors text")
