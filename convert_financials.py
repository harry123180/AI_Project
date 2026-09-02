import os
import re
from bs4 import BeautifulSoup

def html_to_markdown_table(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the main table (usually the one with 'hasBorder' class)
    table = soup.find('table', class_='hasBorder')
    if not table:
        return "No financial table found."

    # Extract title and company
    title = ""
    company = ""
    h2 = soup.find('h2')
    if h2:
        title = h2.get_text(strip=True)
    h4 = soup.find('h4')
    if h4:
        company = h4.get_text(strip=True)

    # Extract unit and period from table headers
    rows = table.find_all('tr')
    period = ""
    unit = ""
    
    # The first few rows usually contain period and unit
    for row in rows[:3]:
        cells = row.find_all(['th', 'td'])
        if cells:
            text = cells[0].get_text(strip=True)
            if "民國" in text:
                period = text
            elif "單位" in text:
                unit = text

    # Process table headers and data
    # We look for the row that starts the actual column headers (會計項目)
    start_idx = 0
    for i, row in enumerate(rows):
        cells = row.find_all(['th', 'td'])
        if cells and "會計項目" in cells[0].get_text(strip=True):
            start_idx = i
            break
    
    header_row = rows[start_idx]
    sub_header_row = rows[start_idx + 1] if start_idx + 1 < len(rows) else None
    
    # Build primary headers
    headers = []
    for cell in header_row.find_all(['th', 'td']):
        headers.append(cell.get_text(strip=True))
    
    # Build sub-headers (Amount, %, etc.)
    sub_headers = []
    if sub_header_row:
        for cell in sub_header_row.find_all(['th', 'td']):
            sub_headers.append(cell.get_text(strip=True))
    
    # For MOPS, the headers are complex. We'll use the sub_header_row 
    # (the one with 金額, %) as the main Markdown header for simplicity.
    
    actual_headers = []
    if sub_header_row:
        actual_headers = [cell.get_text(strip=True) for cell in sub_header_row.find_all(['th', 'td'])]
    else:
        actual_headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]

    # If the first cell is empty, name it "會計項目"
    if actual_headers and not actual_headers[0]:
        actual_headers[0] = "會計項目"

    # Create Markdown table
    md = f"# {title}\n\n"
    md += f"**公司：** {company}\n"
    md += f"**期間：** {period}\n"
    md += f"**單位：** {unit}\n\n"
    
    # Table Header
    md += "| " + " | ".join(actual_headers) + " |\n"
    md += "| " + " | ".join(["---"] * len(actual_headers)) + " |\n"
    
    # Table Data
    for row in rows[start_idx + 2:]:
        cells = row.find_all(['th', 'td'])
        if not cells: continue
        
        row_data = [cell.get_text(strip=True) for cell in cells]
        # Clean up numbers (remove excessive spaces)
        row_data = [re.sub(r'\s+', ' ', d).strip() for d in row_data]
        md += "| " + " | ".join(row_data) + " |\n"
        
    return md

def main():
    files_to_process = [
        "output\\mops_financials_latest\\raw_cache\\3661_2026Q1_income_statement.html",
        "output\\mops_financials_latest\\raw_cache\\3661_2026Q1_cash_flow.html",
        "output\\mops_financials_latest\\raw_cache\\3661_2026Q2_balance_sheet.html",
        "output\\mops_financials_latest\\raw_cache\\3661_2026Q2_income_statement.html",
        "output\\mops_financials_latest\\raw_cache\\3661_2026Q2_cash_flow.html",
        "output\\mops_financials_latest\\raw_cache\\3443_2026Q1_balance_sheet.html",
        "output\\mops_financials_latest\\raw_cache\\3443_2026Q1_income_statement.html",
        "output\\mops_financials_latest\\raw_cache\\3443_2026Q1_cash_flow.html",
        "output\\mops_financials_latest\\raw_cache\\3443_2026Q2_balance_sheet.html",
        "output\\mops_financials_latest\\raw_cache\\3443_2026Q2_income_statement.html",
        "output\\mops_financials_latest\\raw_cache\\3443_2026Q2_cash_flow.html",
        "output\\mops_financials_latest\\raw_cache\\3035_2026Q1_balance_sheet.html",
        "output\\mops_financials_latest\\raw_cache\\3035_2026Q1_income_statement.html",
        "output\\mops_financials_latest\\raw_cache\\3035_2026Q1_cash_flow.html",
        "output\\mops_financials_latest\\raw_cache\\3035_2026Q2_balance_sheet.html",
        "output\\mops_financials_latest\\raw_cache\\3035_2026Q2_income_statement.html",
        "output\\mops_financials_latest\\raw_cache\\3035_2026Q2_cash_flow.html"
    ]
    
    output_dir = "output\\mops_financials_md"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    for file_path in files_to_process:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
            
        print(f"Processing {file_path}...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            md_content = html_to_markdown_table(content)
            
            # Construct output path
            rel_path = file_path.replace("output\\mops_financials_latest\\raw_cache", "output\\mops_financials_md")
            rel_path = rel_path.replace(".html", ".md")
            
            # Ensure subdirectories in the output path exist
            out_folder = os.path.dirname(rel_path)
            if not os.path.exists(out_folder):
                os.makedirs(out_folder)
                
            with open(rel_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            
    print("Conversion complete.")

if __name__ == "__main__":
    main()
