
import requests
import pandas as pd
from io import StringIO
import re

# Fetch S&P 500 tickers from Wikipedia using requests and basic parsing
sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_resp = requests.get(sp500_url, headers={"User-Agent": "Mozilla/5.0"})
_resp.raise_for_status()

# Use BeautifulSoup if available, otherwise use regex to extract table data
try:
    from bs4 import BeautifulSoup
    _soup = BeautifulSoup(_resp.text, 'html.parser')
    _table = _soup.find('table', {'id': 'constituents'})
    _rows = _table.find_all('tr')
    
    _data = []
    for _row in _rows[1:]:  # skip header
        _cols = _row.find_all(['td', 'th'])
        if len(_cols) >= 4:
            _data.append({
                'ticker': _cols[0].get_text(strip=True).replace('.', '-'),
                'company_name': _cols[1].get_text(strip=True),
                'sector': _cols[2].get_text(strip=True),
                'sub_sector': _cols[3].get_text(strip=True),
            })
    
    sp500_tickers_df = pd.DataFrame(_data)
    print(f"✅ Loaded {len(sp500_tickers_df)} S&P 500 tickers via BeautifulSoup")

except ImportError:
    # Fallback: use a well-known static list from SEC EDGAR directly
    # We'll fetch company tickers from EDGAR's company_tickers.json
    _edgar_url = "https://www.sec.gov/files/company_tickers.json"
    _edgar_resp = requests.get(_edgar_url, headers={"User-Agent": "research@example.com"})
    _edgar_resp.raise_for_status()
    _edgar_data = _edgar_resp.json()
    
    # Use a curated list of S&P 500 tickers (top 100 by market cap representation)
    # We'll use the EDGAR tickers and filter to a representative set
    _all_companies = pd.DataFrame([
        {'ticker': v['ticker'], 'company_name': v['title'], 'cik': str(v['cik_str']).zfill(10)}
        for v in _edgar_data.values()
    ])
    
    # Hardcode S&P 500 sector mapping for top 50 well-known tickers (representative sample)
    _sp500_sample = [
        ('AAPL', 'Apple Inc.', 'Information Technology', 'Technology Hardware, Storage & Peripherals'),
        ('MSFT', 'Microsoft Corporation', 'Information Technology', 'Systems Software'),
        ('AMZN', 'Amazon.com Inc.', 'Consumer Discretionary', 'Broadline Retail'),
        ('NVDA', 'NVIDIA Corporation', 'Information Technology', 'Semiconductors'),
        ('GOOGL', 'Alphabet Inc.', 'Communication Services', 'Interactive Media & Services'),
        ('META', 'Meta Platforms Inc.', 'Communication Services', 'Interactive Media & Services'),
        ('TSLA', 'Tesla Inc.', 'Consumer Discretionary', 'Automobile Manufacturers'),
        ('BRK-B', 'Berkshire Hathaway', 'Financials', 'Multi-Sector Holdings'),
        ('LLY', 'Eli Lilly and Co.', 'Health Care', 'Pharmaceuticals'),
        ('JPM', 'JPMorgan Chase & Co.', 'Financials', 'Diversified Banks'),
        ('V', 'Visa Inc.', 'Financials', 'Transaction & Payment Processing Services'),
        ('UNH', 'UnitedHealth Group Inc.', 'Health Care', 'Managed Health Care'),
        ('XOM', 'Exxon Mobil Corporation', 'Energy', 'Integrated Oil & Gas'),
        ('JNJ', 'Johnson & Johnson', 'Health Care', 'Pharmaceuticals'),
        ('WMT', 'Walmart Inc.', 'Consumer Staples', 'Consumer Staples Merchandise Retail'),
        ('MA', 'Mastercard Incorporated', 'Financials', 'Transaction & Payment Processing Services'),
        ('PG', 'Procter & Gamble Co.', 'Consumer Staples', 'Household Products'),
        ('COST', 'Costco Wholesale Corporation', 'Consumer Staples', 'Consumer Staples Merchandise Retail'),
        ('HD', 'Home Depot Inc.', 'Consumer Discretionary', 'Home Improvement Retail'),
        ('ABBV', 'AbbVie Inc.', 'Health Care', 'Biotechnology'),
        ('AVGO', 'Broadcom Inc.', 'Information Technology', 'Semiconductors'),
        ('MRK', 'Merck & Co. Inc.', 'Health Care', 'Pharmaceuticals'),
        ('CVX', 'Chevron Corporation', 'Energy', 'Integrated Oil & Gas'),
        ('KO', 'Coca-Cola Company', 'Consumer Staples', 'Soft Drinks & Non-alcoholic Beverages'),
        ('BAC', 'Bank of America Corp', 'Financials', 'Diversified Banks'),
        ('PEP', 'PepsiCo Inc.', 'Consumer Staples', 'Soft Drinks & Non-alcoholic Beverages'),
        ('AMD', 'Advanced Micro Devices', 'Information Technology', 'Semiconductors'),
        ('ORCL', 'Oracle Corporation', 'Information Technology', 'Systems Software'),
        ('CSCO', 'Cisco Systems Inc.', 'Information Technology', 'Communications Equipment'),
        ('TMO', 'Thermo Fisher Scientific', 'Health Care', 'Life Sciences Tools & Services'),
        ('ADBE', 'Adobe Inc.', 'Information Technology', 'Application Software'),
        ('ACN', 'Accenture plc', 'Information Technology', 'IT Consulting & Other Services'),
        ('WFC', 'Wells Fargo & Co.', 'Financials', 'Diversified Banks'),
        ('TXN', 'Texas Instruments Inc.', 'Information Technology', 'Semiconductors'),
        ('MCD', "McDonald's Corporation", 'Consumer Discretionary', 'Restaurants'),
        ('PM', 'Philip Morris International', 'Consumer Staples', 'Tobacco'),
        ('IBM', 'International Business Machines', 'Information Technology', 'IT Consulting & Other Services'),
        ('INTC', 'Intel Corporation', 'Information Technology', 'Semiconductors'),
        ('GE', 'GE Aerospace', 'Industrials', 'Aerospace & Defense'),
        ('CAT', 'Caterpillar Inc.', 'Industrials', 'Construction Machinery & Heavy Transportation Equipment'),
        ('DE', 'Deere & Company', 'Industrials', 'Agricultural & Farm Machinery'),
        ('BA', 'Boeing Company', 'Industrials', 'Aerospace & Defense'),
        ('HON', 'Honeywell International', 'Industrials', 'Industrial Conglomerates'),
        ('UPS', 'United Parcel Service', 'Industrials', 'Air Freight & Logistics'),
        ('RTX', 'RTX Corporation', 'Industrials', 'Aerospace & Defense'),
        ('LOW', "Lowe's Companies Inc.", 'Consumer Discretionary', 'Home Improvement Retail'),
        ('SPGI', 'S&P Global Inc.', 'Financials', 'Financial Exchanges & Data'),
        ('BLK', 'BlackRock Inc.', 'Financials', 'Asset Management & Custody Banks'),
        ('AMAT', 'Applied Materials Inc.', 'Information Technology', 'Semiconductor Materials & Equipment'),
        ('PANW', 'Palo Alto Networks Inc.', 'Information Technology', 'Systems Software'),
        ('ADI', 'Analog Devices Inc.', 'Information Technology', 'Semiconductors'),
        ('LRCX', 'Lam Research Corporation', 'Information Technology', 'Semiconductor Materials & Equipment'),
        ('KLAC', 'KLA Corporation', 'Information Technology', 'Semiconductor Materials & Equipment'),
        ('MRVL', 'Marvell Technology Inc.', 'Information Technology', 'Semiconductors'),
        ('QCOM', 'Qualcomm Incorporated', 'Information Technology', 'Semiconductors'),
        ('MU', 'Micron Technology Inc.', 'Information Technology', 'Semiconductors'),
        ('NFLX', 'Netflix Inc.', 'Communication Services', 'Movies & Entertainment'),
        ('DIS', 'Walt Disney Company', 'Communication Services', 'Movies & Entertainment'),
        ('T', 'AT&T Inc.', 'Communication Services', 'Integrated Telecommunication Services'),
        ('VZ', 'Verizon Communications', 'Communication Services', 'Integrated Telecommunication Services'),
        ('NKE', 'Nike Inc.', 'Consumer Discretionary', 'Footwear'),
        ('SBUX', 'Starbucks Corporation', 'Consumer Discretionary', 'Restaurants'),
        ('GS', 'Goldman Sachs Group', 'Financials', 'Investment Banking & Brokerage'),
        ('MS', 'Morgan Stanley', 'Financials', 'Investment Banking & Brokerage'),
        ('AXP', 'American Express Company', 'Financials', 'Consumer Finance'),
        ('C', 'Citigroup Inc.', 'Financials', 'Diversified Banks'),
        ('F', 'Ford Motor Company', 'Consumer Discretionary', 'Automobile Manufacturers'),
        ('GM', 'General Motors Company', 'Consumer Discretionary', 'Automobile Manufacturers'),
        ('LMT', 'Lockheed Martin Corporation', 'Industrials', 'Aerospace & Defense'),
        ('NOC', 'Northrop Grumman Corporation', 'Industrials', 'Aerospace & Defense'),
        ('MMM', '3M Company', 'Industrials', 'Industrial Conglomerates'),
        ('UNP', 'Union Pacific Corporation', 'Industrials', 'Rail Transportation'),
        ('AMT', 'American Tower Corporation', 'Real Estate', 'Telecom Tower REITs'),
        ('PLD', 'Prologis Inc.', 'Real Estate', 'Industrial REITs'),
        ('CRM', 'Salesforce Inc.', 'Information Technology', 'Application Software'),
        ('NOW', 'ServiceNow Inc.', 'Information Technology', 'Systems Software'),
        ('SNOW', 'Snowflake Inc.', 'Information Technology', 'Systems Software'),
        ('UBER', 'Uber Technologies Inc.', 'Industrials', 'Passenger Ground Transportation'),
        ('ABNB', 'Airbnb Inc.', 'Consumer Discretionary', 'Hotels, Resorts & Cruise Lines'),
        ('ZM', 'Zoom Video Communications', 'Information Technology', 'Application Software'),
        ('SQ', 'Block Inc.', 'Financials', 'Transaction & Payment Processing Services'),
        ('PYPL', 'PayPal Holdings Inc.', 'Financials', 'Transaction & Payment Processing Services'),
        ('FCX', 'Freeport-McMoRan Inc.', 'Materials', 'Copper'),
        ('NEM', 'Newmont Corporation', 'Materials', 'Gold'),
        ('APD', 'Air Products and Chemicals', 'Materials', 'Industrial Gases'),
        ('LIN', 'Linde plc', 'Materials', 'Industrial Gases'),
        ('SHW', 'Sherwin-Williams Company', 'Materials', 'Specialty Chemicals'),
        ('ECL', 'Ecolab Inc.', 'Materials', 'Specialty Chemicals'),
        ('HAL', 'Halliburton Company', 'Energy', 'Oil & Gas Equipment & Services'),
        ('SLB', 'SLB', 'Energy', 'Oil & Gas Equipment & Services'),
        ('COP', 'ConocoPhillips', 'Energy', 'Oil & Gas Exploration & Production'),
        ('EOG', 'EOG Resources Inc.', 'Energy', 'Oil & Gas Exploration & Production'),
        ('MO', 'Altria Group Inc.', 'Consumer Staples', 'Tobacco'),
        ('CL', 'Colgate-Palmolive Company', 'Consumer Staples', 'Household Products'),
        ('KMB', 'Kimberly-Clark Corporation', 'Consumer Staples', 'Household Products'),
        ('EL', 'Estee Lauder Companies', 'Consumer Staples', 'Personal Care Products'),
        ('DHR', 'Danaher Corporation', 'Health Care', 'Life Sciences Tools & Services'),
        ('ABT', 'Abbott Laboratories', 'Health Care', 'Health Care Equipment'),
    ]
    
    sp500_tickers_df = pd.DataFrame(_sp500_sample, columns=['ticker', 'company_name', 'sector', 'sub_sector'])
    print(f"✅ Loaded {len(sp500_tickers_df)} representative S&P 500 tickers (BeautifulSoup unavailable, using curated list)")

print(f"\nSectors represented: {sp500_tickers_df['sector'].nunique()}")
print(sp500_tickers_df['sector'].value_counts().to_string())
print(f"\nSample tickers:")
print(sp500_tickers_df.head(10).to_string(index=False))
