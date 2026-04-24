
import re
import json

# ── Tariff/trade keyword taxonomy ───────────────────────────────────────────
# Weighted keyword groups for scoring
TARIFF_KEYWORDS = {
    # High-weight tariff-specific terms
    'tariff_direct': {
        'weight': 5,
        'terms': [
            'tariff', 'tariffs', 'anti-dumping', 'antidumping', 'countervailing duty',
            'section 301', 'section 232', 'section 201', 'trade remedy',
            'safeguard tariff', 'retaliatory tariff', 'punitive tariff',
        ]
    },
    # High-weight trade war / sanctions
    'trade_conflict': {
        'weight': 4,
        'terms': [
            'trade war', 'trade dispute', 'trade tensions', 'trade conflict',
            'trade restriction', 'trade barrier', 'trade sanction',
            'import ban', 'export ban', 'economic sanction', 'sanctions',
            'export control', 'entity list', 'blacklist', 'denied party',
            'bureau of industry', 'BIS', 'OFAC',
        ]
    },
    # Medium-weight supply chain & sourcing
    'supply_chain': {
        'weight': 3,
        'terms': [
            'supply chain disruption', 'supply chain risk', 'sourcing risk',
            'import duty', 'import cost', 'customs duty', 'customs tariff',
            'import restriction', 'quota', 'non-tariff barrier',
            'country of origin', 'rules of origin', 'reshoring', 'nearshoring',
            'friendshoring', 'procurement risk', 'vendor risk', 'supplier risk',
        ]
    },
    # Medium-weight geopolitical / country risk
    'geopolitical': {
        'weight': 3,
        'terms': [
            'geopolitical', 'geopolitical risk', 'geopolitical uncertainty',
            'china tariff', 'chinese tariff', 'us-china', 'sino-american',
            'trade policy', 'trade regulation', 'protectionism', 'protectionist',
            'nationalism', 'deglobalization', 'decoupling',
            'most favored nation', 'MFN', 'WTO', 'world trade organization',
        ]
    },
    # Lower-weight general trade terms
    'trade_general': {
        'weight': 2,
        'terms': [
            'international trade', 'global trade', 'cross-border trade',
            'import', 'export', 'customs', 'border adjustment',
            'free trade agreement', 'FTA', 'USMCA', 'NAFTA', 'CPTPP',
            'trade agreement', 'bilateral trade', 'multilateral trade',
        ]
    },
    # Region-specific tariff references
    'region_specific': {
        'weight': 4,
        'terms': [
            'china', 'chinese', 'prc', 'hong kong', 'taiwan', 'russia', 'russian',
            'iran', 'north korea', 'venezuela', 'myanmar', 'belarus',
            'EU tariff', 'european union tariff', 'india tariff', 'vietnam',
            'mexico tariff', 'canada tariff',
        ]
    },
}

# Region mapping for JSONB regions field
REGION_PATTERNS = {
    'China': r'\b(china|chinese|prc|hong.?kong|sino)\b',
    'Russia': r'\b(russia|russian|kremlin)\b',
    'Europe': r'\b(europe|european union|eu|brexit)\b',
    'Asia_Pacific': r'\b(asia|asian|vietnam|taiwan|south korea|japan|india|southeast asia)\b',
    'Americas': r'\b(mexico|canada|latin america|south america|usmca|nafta)\b',
    'Middle_East': r'\b(middle east|iran|saudi arabia|gulf)\b',
    'Global': r'\b(global|worldwide|international)\b',
}

def compute_tariff_score(risk_text: str) -> dict:
    """
    Compute a tariff exposure score (0-100) from risk factor text.
    
    Returns dict with:
      - tariff_exposure_score (int, 0-100)
      - exposure_level (str: low/medium/high/critical)
      - key_filing_quote (str: most relevant sentence)
      - regions (list of affected regions)
      - keyword_hits (dict: category → count, for transparency)
    """
    if not risk_text or len(risk_text.strip()) < 50:
        return {
            'tariff_exposure_score': 0,
            'exposure_level': 'low',
            'key_filing_quote': '',
            'regions': [],
            'keyword_hits': {},
        }
    
    text_lower = risk_text.lower()
    
    # ── Step 1: Count weighted keyword hits ──────────────────────────────
    raw_score = 0
    keyword_hits = {}
    
    for category, config in TARIFF_KEYWORDS.items():
        hits = 0
        for term in config['terms']:
            # Count occurrences (case-insensitive, word boundary aware)
            pattern = r'(?i)\b' + re.escape(term) + r'\b'
            matches = re.findall(pattern, risk_text)
            hits += len(matches)
        
        if hits > 0:
            weighted = hits * config['weight']
            raw_score += weighted
            keyword_hits[category] = hits
    
    # ── Step 2: Context amplifiers ───────────────────────────────────────
    # Significant/material language boosts score
    amplifier_patterns = [
        (r'(?i)material(ly)?\s+(adverse|impact|effect)', 2.0),
        (r'(?i)significant(ly)?\s+(increase|impact|affect)', 1.8),
        (r'(?i)substantial(ly)?\s+(impact|affect|increase)', 1.8),
        (r'(?i)adversely\s+affect', 1.5),
        (r'(?i)cannot\s+predict|unpredictab', 1.3),
        (r'(?i)escalat(e|ing|ion)', 1.4),
        (r'(?i)may\s+result\s+in\s+(higher|increased|additional)', 1.3),
    ]
    
    amplifier_factor = 1.0
    for pat, amp in amplifier_patterns:
        if re.search(pat, risk_text):
            amplifier_factor = max(amplifier_factor, amp)
    
    adjusted_score = raw_score * amplifier_factor
    
    # ── Step 3: Normalize to 0–100 ───────────────────────────────────────
    # Calibrated so:
    #   ~5 raw pts → ~15 (low)
    #   ~15 raw pts → ~40 (medium)
    #   ~35 raw pts → ~70 (high)
    #   ~60+ raw pts → 90+ (critical)
    import math
    normalized = min(100, int(100 * (1 - math.exp(-adjusted_score / 40))))
    
    # ── Step 4: Exposure level thresholds ────────────────────────────────
    if normalized < 20:
        exposure_level = 'low'
    elif normalized < 45:
        exposure_level = 'medium'
    elif normalized < 70:
        exposure_level = 'high'
    else:
        exposure_level = 'critical'
    
    # ── Step 5: Extract best key quote ───────────────────────────────────
    sentences = re.split(r'(?<=[.!?])\s+', risk_text)
    best_sentence = ''
    best_sent_score = 0
    
    for sent in sentences:
        if len(sent) < 30 or len(sent) > 600:
            continue
        sent_score = 0
        for category, config in TARIFF_KEYWORDS.items():
            for term in config['terms']:
                if term.lower() in sent.lower():
                    sent_score += config['weight']
        if sent_score > best_sent_score:
            best_sent_score = sent_score
            best_sentence = sent.strip()
    
    # Trim quote to 500 chars
    key_quote = best_sentence[:500] if best_sentence else risk_text[:300]
    
    # ── Step 6: Identify regions ─────────────────────────────────────────
    affected_regions = []
    for region, pattern in REGION_PATTERNS.items():
        if re.search(pattern, risk_text, re.IGNORECASE):
            affected_regions.append(region)
    
    return {
        'tariff_exposure_score': normalized,
        'exposure_level': exposure_level,
        'key_filing_quote': key_quote,
        'regions': affected_regions,
        'keyword_hits': keyword_hits,
    }

# ── Sanity-test on a synthetic sample ────────────────────────────────────────
_test_text = """
Our operations are subject to significant tariff risks. The U.S. government has imposed Section 301 
tariffs on approximately $300 billion of goods imported from China, which materially adversely affects 
our supply chain and cost structure. Retaliatory tariffs imposed by the Chinese government on U.S. goods 
have escalated trade tensions between the two nations. We cannot predict whether these tariffs will be 
maintained, increased, or extended to additional products. Trade war escalation could significantly 
increase our cost of goods sold and adversely affect our margins.
"""

_test_result = compute_tariff_score(_test_text)
print("✅ Tariff scoring engine ready")
print(f"\n📊 Sanity test on sample text:")
print(f"   Score:          {_test_result['tariff_exposure_score']}/100")
print(f"   Exposure Level: {_test_result['exposure_level']}")
print(f"   Regions:        {_test_result['regions']}")
print(f"   Keyword Hits:   {_test_result['keyword_hits']}")
print(f"   Key Quote:      {_test_result['key_filing_quote'][:120]}...")
