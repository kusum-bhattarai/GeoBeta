import json
import re
import urllib.request
import urllib.error
import psycopg2
import os

# ── Helper: call Anthropic API via urllib (no SDK needed) ─────────────────────
def call_claude(api_key, system_prompt, user_prompt, model="claude-opus-4-5", max_tokens=1024):
    """Call Anthropic Messages API directly via urllib."""
    url = "https://api.anthropic.com/v1/messages"
    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["content"][0]["text"].strip()


# ── Prompts ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a senior supply chain risk analyst specializing in SEC filing analysis,
trade policy, and tariff exposure. You extract structured intelligence from corporate disclosures
with precision and consistency. Always respond with valid JSON only — no markdown fences, no preamble."""

ANALYSIS_PROMPT = """Analyze the following SEC filing excerpt for {ticker} and extract supply chain risk intelligence.

FILING EXCERPT:
{filing_text}

Return a JSON object with EXACTLY this structure:
{{
  "dependencies": ["<specific supplier/country/input dependency>", ...],
  "exposed_products": ["<specific product line or category exposed to tariffs>", ...],
  "risk_regions": ["<geographic region with concentration risk>", ...],
  "mitigations": ["<specific mitigation strategy mentioned in filing>", ...],
  "analyst_summary": "<2-3 sentence professional summary of key supply chain risks and tariff exposure>"
}}

Rules:
- Be specific and precise — extract only what is explicitly or strongly implied in the text
- Each array should have 1-5 items maximum
- analyst_summary must be concise, actionable, and suitable for an equity research report
- If a category has no evidence in the text, return an empty array []
- Return valid JSON only"""

# ── Resolve ANTHROPIC_API_KEY ──────────────────────────────────────────────────
# Zerve canvas constants are injected as Python variables at block runtime.
# ANTHROPIC_API_KEY must be added as a canvas constant with that exact name.
# Check environment as fallback (some Zerve environments also inject via env vars).
_anthro_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not _anthro_key:
    raise EnvironmentError(
        "ANTHROPIC_API_KEY is not set in the environment. "
        "Please add it as a canvas constant under Settings > Constants "
        "with the name 'ANTHROPIC_API_KEY'."
    )

# ── DB connection ──────────────────────────────────────────────────────────────
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# ── Analysis ───────────────────────────────────────────────────────────────────
analysis_results = []

print(f"Analyzing {len(companies_df)} high/critical exposure companies with Claude claude-opus-4-5...\n")
print("=" * 70)

for _, row in companies_df.iterrows():
    ticker = row["ticker"]
    filing_text = row["key_filing_quote"]
    company_id = row["id"]
    current_exposure_map = row["exposure_pct_map"] or {}

    print(f"\n📊 Analyzing {ticker}...")

    prompt = ANALYSIS_PROMPT.format(ticker=ticker, filing_text=filing_text)

    raw_response = call_claude(
        api_key=_anthro_key,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=prompt,
    )

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_response, flags=re.MULTILINE).strip()
    structured = json.loads(cleaned)

    required_keys = {"dependencies", "exposed_products", "risk_regions", "mitigations", "analyst_summary"}
    missing = required_keys - set(structured.keys())
    if missing:
        raise ValueError(f"Claude response for {ticker} missing keys: {missing}")

    analyst_summary = structured["analyst_summary"]

    updated_exposure_map = dict(current_exposure_map) if isinstance(current_exposure_map, dict) else {}
    updated_exposure_map["supply_chain_analysis"] = {
        "dependencies": structured["dependencies"],
        "exposed_products": structured["exposed_products"],
        "risk_regions": structured["risk_regions"],
        "mitigations": structured["mitigations"],
    }

    cursor.execute(
        """
        UPDATE companies
        SET key_filing_quote = %s,
            exposure_pct_map = %s::jsonb,
            updated_at       = NOW()
        WHERE id = %s
        """,
        (analyst_summary, json.dumps(updated_exposure_map), company_id),
    )
    conn.commit()

    analysis_results.append({"ticker": ticker, "structured_output": structured, "db_updated": True})

    print(f"  ✅ Dependencies    : {structured['dependencies']}")
    print(f"  ✅ Exposed Products: {structured['exposed_products']}")
    print(f"  ✅ Risk Regions    : {structured['risk_regions']}")
    print(f"  ✅ Mitigations     : {structured['mitigations']}")
    print(f"  📝 Summary: {analyst_summary}")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print(f"\n✅ Complete! Updated {len(analysis_results)} companies in the database.")
print("\n📋 ANALYSIS SUMMARY")
print("=" * 70)
for r in analysis_results:
    t = r["ticker"]
    s = r["structured_output"]
    print(f"\n{t}:")
    print(f"  Analyst Summary : {s['analyst_summary']}")
    print(f"  Key Risk Regions: {', '.join(s['risk_regions']) if s['risk_regions'] else 'None identified'}")
    print(f"  Exposed Products: {', '.join(s['exposed_products']) if s['exposed_products'] else 'None identified'}")
    print(f"  Mitigations     : {', '.join(s['mitigations']) if s['mitigations'] else 'None disclosed'}")
