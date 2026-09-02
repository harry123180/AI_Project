import re

file_path = r'output\mops_financials_latest\raw_cache\2330_2026Q2_income_statement.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

metrics = {
    "營業收入合計": "Total Operating Revenue",
    "營業毛利": "Gross Profit",
    "營業利益": "Operating Income",
    "本期淨利": "Net Income"
}

# Find the table that starts with 民國115年第2季
# We want the first "金額" column (115年第2季)
# The structure is <td>Metric Name</td><td>Value</td><td>%</td>...

for key, eng in metrics.items():
    # Search for the key, then find the first <td> following it that contains a number
    pattern = rf"<{key}.*?</td>\s*<td[^>]*>.*?([\d,.]+)</td>"
    match = re.search(pattern, content, re.S)
    if match:
        print(f"{eng} ({key}): {match.group(1)}")
    else:
        print(f"{eng} ({key}): Not found")
