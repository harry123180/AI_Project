import os
import re
import csv
from bs4 import BeautifulSoup

def extract_value(text):
    if not text:
        return None
    # Remove commas and whitespace
    clean_val = text.replace(',', '').strip()
    try:
        return float(clean_val)
    except ValueError:
        return None

def parse_income_statement(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', class_='hasBorder')
    if not table:
        return None

    rows = table.find_all('tr')
    # Find the index of the column for the current period (usually the first data column after the header)
    # The header structure varies, but typically the first '金額' column is the current period.
    
    data = {}
    company_id = os.path.basename(file_path).split('_')[0]
    period = os.path.basename(file_path).split('_')[1]
    
    # Mapping target items
    targets = {
        'revenue': ['營業收入合計', '銷貨收入淨額'],
        'gross_profit': ['營業毛利'],
        'operating_profit': ['營業利益'],
        'net_profit': ['本期淨利', '稅後淨利']
    }
    
    found_values = {k: None for k in targets}
    
    for row in rows:
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue
        
        cell_text = cells[0].get_text(strip=True)
        
        for key, keywords in targets.items():
            if any(kw in cell_text for kw in keywords):
                # Try to get the value from the second column (index 1)
                if len(cells) > 1:
                    val = extract_value(cells[1].get_text(strip=True))
                    found_values[key] = val
                break
                
    return {
        'company': company_id,
        'period': period,
        'revenue': found_values['revenue'],
        'gross_profit': found_values['gross_profit'],
        'operating_profit': found_values['operating_profit'],
        'net_profit': found_values['net_profit']
    }

def main():
    cache_dir = 'output/mops_financials_latest/raw_cache'
    output_file = 'output/profit_margin_analysis.csv'
    
    all_results = []
    
    if not os.path.exists(cache_dir):
        print(f"Directory {cache_dir} not found")
        return

    for filename in os.listdir(cache_dir):
        if filename.endswith('_income_statement.html'):
            path = os.path.join(cache_dir, filename)
            res = parse_income_statement(path)
            if res:
                # Calculate margins
                rev = res['revenue']
                if rev and rev != 0:
                    res['gross_margin'] = (res['gross_profit'] / rev) * 100 if res['gross_profit'] else None
                    res['operating_margin'] = (res['operating_profit'] / rev) * 100 if res['operating_profit'] else None
                    res['net_margin'] = (res['net_profit'] / rev) * 100 if res['net_profit'] else None
                else:
                    res['gross_margin'] = res['operating_margin'] = res['net_margin'] = None
                
                all_results.append(res)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['company', 'period', 'revenue', 'gross_profit', 'operating_profit', 'net_profit', 'gross_margin', 'operating_margin', 'net_margin'])
        writer.writeheader()
        writer.writerows(all_results)
    
    print(f"Analysis complete. Results saved to {output_file}")

if __name__ == '__main__':
    main()
