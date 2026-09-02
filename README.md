# AI_Project

## MOPS AI 供應鏈財報爬蟲

`mops_financial_crawler.py` 依上游、中游、下游及 13 個次領域整理題目所列的 36 家公司，擷取 MOPS 的完整合併資產負債表、綜合損益表與現金流量表。原始 HTML 會留在 `raw_cache`，重跑時直接使用快取；結構化資料採 JSON Lines，同時輸出原始字串與可分析的數值欄，並依 `by_category/供應鏈環節/次領域` 拆分資料。根目錄另附公司清單、請求清單及錯誤清單。

```powershell
python mops_financial_crawler.py --start-year 2024 --end-year 2024 --end-quarter 4
```

可用 `--stock-id 2330`、`--stage 上游`、`--category 晶圓代工與先進封裝` 或 `--statement balance_sheet` 限縮範圍。未指定期間時，預設由 2013 年抓到最近已完成申報的季度。MOPS 有流量限制，程式預設每次等待 2 秒、每 60 次額外冷卻 45 秒，遇拒絕頁會指數退避；完整執行不應縮短這些值。中斷後直接重跑會沿用快取。

完整歷史資料改用季度彙總爬蟲，可大幅減少請求數：

```powershell
python mops_bulk_financial_crawler.py
```

輸出位於 `output/mops_financials_full`，包含長格式財報 CSV、分類 CSV、請求紀錄、各公司資料覆蓋期間及摘要。

已完成的資料集包含：

- `financial_statements_long.csv`：2013 Q1 至 2026 Q2 的完整長格式財報資料。
- `by_category/`：依供應鏈環節及次領域拆分的 CSV。
- `coverage.csv`：各公司、各報表的可用期間。
- `request_manifest.csv`：MOPS 季度、市場及報表請求稽核紀錄。
- `mops_ai_supply_chain_financials_2013_2026Q2.xlsx`：可直接使用 Excel 開啟的整理版本。

損益表與現金流量表的季度數值依 MOPS 原表呈現，其中第二季、第三季及年度資料屬年初至當期的累計值；資產負債表則為季末時點值。`raw_value` 為 MOPS 原始文字，`value` 為可分析的數值欄；原始 `--` 會在 `value` 中保留為空值。
