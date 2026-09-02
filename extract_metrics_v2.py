import re

file_path = r'output\mops_financials_latest\raw_cache\2330_2026Q2_income_statement.html'
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    metrics = {
        "營業收入合計": "Total Operating Revenue",
        "營業毛利": "Gross Profit",
        "營業利益": "Operating Income",
        "本期淨利": "Net Income"
    }

    # The 2026Q2 (115年第2季) column is the first data column.
    # We look for the metric name and then the very next <td> that contains the number.
    for key, eng in metrics.items():
        # Use a regex that finds the metric name, then captures the first number in the following <td>
        # We allow for variations in <td> tags (e.g., class='even').
        pattern = rf">{key}</td>\s*<td[^>]*>\s*([0-9,.]+)\s*</td>"
        match = re.search(pattern, content)
        if match:
            print(f"{eng}: {match.group(1)}")
        else:
            # Try a more flexible pattern if the first one fails
            pattern_flex = rf">{key}.*?</td>\s*<td[^>]*>\s*([0-9,.]+)\s*</td>"
            match_flex = re.search(pattern_flex, content, re.S)
            if match_flex:
                print(f"{eng}: {match_flex.group(1)}")
            else:
                print(f"{eng}: Not found")
except Exception as e:
    print(f"Error: {e}")
