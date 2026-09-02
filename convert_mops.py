import os
from bs4 import BeautifulSoup
import pandas as pd

def convert_html_to_markdown(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the main table (usually the one with class 'hasBorder')
    table = soup.find('table', class_='hasBorder')
    if not table:
        return "No table found."

    # Extract all rows
    rows = table.find_all('tr')
    
    data = []
    for row in rows:
        # Extract text from cells, removing extra whitespace
        cols = [ele.text.strip() for ele in row.find_all(['td', 'th'])]
        if cols:
            data.append(cols)

    if not data:
        return "No data in table."

    # The MOPS tables often have complex headers.
    # Row 0: Title (e.g., 民國115年第1季)
    # Row 1: Unit (e.g., 單位：新台幣仟元)
    # Row 2: Main categories (Accounting items, dates)
    # Row 3: Sub-headers (Amount, %)
    
    # For professional Markdown, we'll simplify the header.
    # Let's reconstruct the header based on the content.
    
    # The structure is typically:
    # Item | 115Y 01-03 Amt | 115Y 01-03 % | 115Y Q1 Amt | 115Y Q1 % | 114Y 01-03 Amt | ...
    
    # We filter out the first two rows as they are just title/unit
    table_data = data[2:] 
    
    # Header from row 2 and 3
    header_row = table_data[0]
    sub_header_row = table_data[1]
    
    # Since Markdown doesn't support colspan, we flatten the headers
    final_header = []
    # First cell is "會計項目"
    final_header.append(header_row[0])
    
    # The rest are grouped in 2s (Amount, %)
    # Header row has 4 date ranges (colspan=2 each) -> total 1 + 2*4 = 9 columns
    # The header_row itself might only have 5 elements because of colspans
    
    # Let's manually map the dates based on the text
    dates = [
        "115年01月01日至115年03月31日",
        "115年第1季",
        "114年01月01日至114年03月31日",
        "114年第1季"
    ]
    
    flattened_header = ["會計項目"]
    for date in dates:
        flattened_header.append(f"{date} 金額")
        flattened_header.append(f"{date} %")
        
    # The actual data starts from index 2
    rows_data = table_data[2:]
    
    # Build Markdown table
    md = "| " + " | ".join(flattened_header) + " |\n"
    md += "| " + " | ".join(["---"] * len(flattened_header)) + " |\n"
    
    for row in rows_data:
        # Ensure row has enough cells
        if len(row) < len(flattened_header):
            row += [""] * (len(flattened_header) - len(row))
        
        # Clean up values (remove empty strings or excessive spaces)
        cleaned_row = [val.strip() for val in row[:len(flattened_header)]]
        md += "| " + " | ".join(cleaned_row) + " |\n"
        
    return md

file_path = r'output\mops_financials_latest\raw_cache\3661_2026Q1_income_statement.html'
print(convert_html_to_markdown(file_path))
