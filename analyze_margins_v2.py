import os
import pandas as pd
from bs4 import BeautifulSoup
import json

def extract_financial_data(html_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    table = soup.find('table', class_='hasBorder')
    if not table:
        return None
    
    rows = table.find_all('tr')
    data = []
    
    for row in rows:
        cols = row.find_all(['td', 'th'])
        text_cols = [c.text.strip() for c in cols]
        if text_cols:
            data.append(text_cols)
    
    # Map of synonyms to handle potential variations in naming
    metrics_map = {
        "Revenue": ["營業收入合計", "營業收入"],
        "Gross Profit": ["營業毛利", "毛利"],
        "Operating Profit": ["營業利益", "營業利潤"],
        "Net Income": ["本期淨利", "淨利", "稅後淨利"]
    }

    results = {}
    
    # Find the column index for the most recent period
    amount_col_idx = -1
    for row in data:
        if "金額" in row:
            amount_col_idx = row.index("金額")
            break
    
    if amount_col_idx == -1:
        amount_col_idx = 1

    for metric_name, synonyms in metrics_map.items():
        for row in data:
            if len(row) > 0 and any(row[0] == s for s in synonyms):
                if amount_col_idx < len(row):
                    val = row[amount_col_idx].replace(',', '').strip()
                    try:
                        results[metric_name] = float(val)
                    except ValueError:
                        results[metric_name] = None
                break
                
    return results

def main():
    base_dir = r'output\mops_financials_latest\raw_cache'
    target_companies = ['2330', '3711', '2449', '3661', '5274']
    all_results = {}

    for company in target_companies:
        # Try Q2 then Q1
        for q in ['2026Q2', '2026Q1']:
            filename = f"{company}_{q}_income_statement.html"
            path = os.path.join(base_dir, filename)
            if os.path.exists(path):
                print(f"Processing {company} from {filename}...")
                data = extract_financial_data(path)
                if data:
                    all_results[company] = data
                    break
        else:
            print(f"No income statement found for {company}")

    final_analysis = {}
    for company, vals in all_results.items():
        rev = vals.get("Revenue")
        gp = vals.get("Gross Profit")
        op = vals.get("Operating Profit")
        ni = vals.get("Net Income")
        
        margins = {}
        if rev and rev != 0:
            margins["Gross Margin (%)"] = (gp / rev * 100) if gp is not None else None
            margins["Operating Margin (%)"] = (op / rev * 100) if op is not None else None
            margins["Net Margin (%)"] = (ni / rev * 100) if ni is not None else None
        
        final_analysis[company] = {
            "values": vals,
            "margins": margins
        }

    print(json.dumps(final_analysis, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
