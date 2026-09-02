import re

file_path = r'output\mops_financials_latest\raw_cache\2330_2026Q2_income_statement.html'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    metrics_to_find = {
        "營業收入合計": "Total Operating Revenue",
        "營業毛利": "Gross Profit",
        "營業利益": "Operating Income",
        "本期淨利": "Net Income"
    }

    # The table layout is:
    # <td ...>Metric Name</td><td ...>Amount (Q2 115)</td><td ...>%</td><td ...>Amount (Q2 114)</td>...
    # We want the first numeric amount after the metric name.

    results = {}
    for key, eng_name in metrics_to_find.items():
        # Pattern: match the key, then skip everything until we find the first <td ...> with digits/commas
        # Using re.S to match across lines if necessary, though it's one big line here.
        pattern = rf">{key}</td>\s*<td[^>]*>\s*([0-9,.]+)\s*</td>"
        match = re.search(pattern, content, re.S)
        if match:
            results[eng_name] = match.group(1)
        else:
            results[eng_name] = "Not Found"

    for eng, val in results.items():
        print(f"{eng}: {val}")

except Exception as e:
    print(f"Error: {e}")
