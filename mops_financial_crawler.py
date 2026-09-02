"""依 AI 供應鏈分類下載公開資訊觀測站完整合併財務報表。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import random
import re
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = "https://mopsov.twse.com.tw/mops/web"
STATEMENTS = {
    "balance_sheet": "ajax_t164sb03",
    "income_statement": "ajax_t164sb04",
    "cash_flow": "ajax_t164sb05",
}

SUPPLY_CHAIN = [
    ("上游", "晶圓代工與先進封裝", [("2330", "台積電")]),
    ("上游", "晶片封測服務", [("3711", "日月光投控"), ("2449", "京元電子")]),
    ("上游", "ASIC設計服務_IP", [("3661", "世芯-KY"), ("3443", "創意"), ("3035", "智原")]),
    ("上游", "伺服器遠端管理_傳輸", [("5274", "信驊"), ("5269", "祥碩"), ("4966", "譜瑞-KY")]),
    ("中游", "散熱管理", [("3017", "奇鋐"), ("3324", "雙鴻"), ("3653", "健策")]),
    ("中游", "電源供應系統", [("2308", "台達電"), ("2301", "光寶科")]),
    ("中游", "ABF載板_高階PCB", [("3037", "欣興"), ("8046", "南電"), ("2368", "金像電"), ("2383", "台光電")]),
    ("中游", "伺服器滑軌與機殼", [("2059", "川湖"), ("8210", "勤誠"), ("6584", "南俊國際")]),
    ("中游", "高速連接器與線束", [("3665", "貿聯-KY"), ("3533", "嘉澤"), ("6290", "良維")]),
    ("下游", "伺服器ODM_整機櫃組裝", [("2317", "鴻海"), ("2382", "廣達"), ("6669", "緯穎"), ("3231", "緯創"), ("2356", "英業達")]),
    ("下游", "品牌伺服器與板卡", [("2376", "技嘉"), ("2357", "華碩"), ("2377", "微星"), ("3706", "神達")]),
    ("下游", "邊緣運算_工業AI", [("2395", "研華"), ("6166", "凌華")]),
    ("下游", "高速網路交換器", [("2345", "智邦")]),
]


@dataclass(frozen=True)
class Company:
    stage: str
    category: str
    stock_id: str
    name: str


def companies() -> list[Company]:
    return [Company(stage, category, stock_id, name)
            for stage, category, members in SUPPLY_CHAIN
            for stock_id, name in members]


def latest_available_period(today: date | None = None) -> tuple[int, int]:
    """依一般申報期限估算已完整公告的最近季度。"""
    today = today or date.today()
    if today.month >= 11:
        return today.year, 3
    if today.month >= 8:
        return today.year, 2
    if today.month >= 5:
        return today.year, 1
    return today.year - 1, 4


def periods(start_year: int, end_year: int, end_quarter: int) -> Iterable[tuple[int, int]]:
    for year in range(start_year, end_year + 1):
        last = end_quarter if year == end_year else 4
        for quarter in range(1, last + 1):
            yield year, quarter


def parse_number(value: str) -> int | float | None:
    value = value.strip().replace(",", "").replace("−", "-")
    if value in {"", "-", "--", "－"}:
        return None
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    try:
        number: int | float = float(value) if "." in value else int(value)
        return -number if negative else number
    except ValueError:
        return None


def unique_headers(rows: list[list[str]], width: int) -> list[str]:
    raw: list[str] = []
    for col in range(width):
        parts = []
        for row in rows:
            if col < len(row) and row[col] and row[col] not in parts:
                parts.append(row[col])
        raw.append("_".join(parts) or f"欄位_{col + 1}")
    counts: dict[str, int] = {}
    result = []
    for header in raw:
        counts[header] = counts.get(header, 0) + 1
        result.append(header if counts[header] == 1 else f"{header}_{counts[header]}")
    return result


def expand_html_table(table) -> list[list[str]]:
    """將 HTML table 的 rowspan/colspan 展開為矩形資料格。"""
    expanded: list[list[str]] = []
    spans: dict[int, tuple[int, str]] = {}
    for tr in table.find_all("tr"):
        row: list[str] = []
        column = 0

        def consume_span() -> None:
            nonlocal column
            remaining, value = spans[column]
            row.append(value)
            if remaining == 1:
                del spans[column]
            else:
                spans[column] = (remaining - 1, value)
            column += 1

        for cell in tr.find_all(["th", "td"], recursive=False):
            while column in spans:
                consume_span()
            value = cell.get_text(" ", strip=True)
            colspan = int(cell.get("colspan", 1) or 1)
            rowspan = int(cell.get("rowspan", 1) or 1)
            for _ in range(colspan):
                row.append(value)
                if rowspan > 1:
                    spans[column] = (rowspan - 1, value)
                column += 1
        while spans and column <= max(spans):
            if column in spans:
                consume_span()
            else:
                row.append("")
                column += 1
        expanded.append(row)
    return expanded


def parse_statement(html: str) -> tuple[dict, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    if "查無資料" in text or "資料庫中查無需求的資料" in text:
        return {"status": "no_data"}, []
    tables = soup.find_all("table")
    candidates = []
    for table in tables:
        rows = expand_html_table(table)
        if any(row and row[0] == "會計項目" for row in rows):
            candidates.append(rows)
    if not candidates:
        title = soup.find("h2")
        raise ValueError(f"找不到財報資料表：{title.get_text(strip=True) if title else text[:120]}")

    rows = max(candidates, key=len)
    header_at = next(i for i, row in enumerate(rows) if row and row[0] == "會計項目")
    header_rows = rows[header_at:header_at + 2]
    data_rows = rows[header_at + 2:]
    width = max(map(len, data_rows), default=0)
    headers = unique_headers(header_rows, width)
    records = []
    for row in data_rows:
        if not row or not row[0] or len(row) < 2:
            continue
        padded = row + [""] * (width - len(row))
        record = {headers[i]: padded[i] for i in range(width)}
        record["會計項目"] = row[0]
        records.append(record)

    heading = soup.find("h2")
    period_match = re.search(r"民國\s*(\d+)\s*年\s*第\s*(\d+)\s*季", text)
    metadata = {
        "status": "ok",
        "title": heading.get_text(" ", strip=True) if heading else "",
        "unit": "新台幣仟元" if "新台幣仟元" in text else "",
        "roc_year": int(period_match.group(1)) if period_match else None,
        "quarter": int(period_match.group(2)) if period_match else None,
        "row_count": len(records),
    }
    return metadata, records


class MOPSCrawler:
    def __init__(self, output: Path, delay: float = 2.0, timeout: float = 30.0,
                 content_retries: int = 5) -> None:
        self.output = output
        self.delay = delay
        self.timeout = timeout
        self.content_retries = content_retries
        self.cache = output / "raw_cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        retry = Retry(total=4, connect=4, read=4, backoff_factor=1.2,
                      status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET", "POST"))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; MOPSFinancialResearch/1.0)",
            "Referer": "https://mopsov.twse.com.tw/mops/web/index",
        })

    def fetch(self, company: Company, year: int, quarter: int, statement: str,
              refresh: bool = False) -> str:
        endpoint = STATEMENTS[statement]
        key = f"{company.stock_id}_{year}Q{quarter}_{statement}.html"
        cached = self.cache / key
        if cached.exists() and not refresh:
            return cached.read_text(encoding="utf-8")
        payload = {
            "encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1",
            "TYPEK": "all", "co_id": company.stock_id,
            "year": str(year - 1911), "season": str(quarter),
        }
        last_reason = ""
        for attempt in range(1, self.content_retries + 1):
            response = self.session.post(f"{BASE_URL}/{endpoint}", data=payload, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            html = response.text
            rejected = "FOR SECURITY REASONS" in html or "錯誤代碼" in html or len(html) < 500
            if not rejected:
                cached.write_text(html, encoding="utf-8")
                time.sleep(self.delay + random.uniform(0.2, 0.8))
                return html
            last_reason = f"HTTP {response.status_code}, {len(html)} bytes"
            cooldown = min(120.0, 15.0 * (2 ** (attempt - 1)))
            logging.warning("MOPS 流量防護，等待 %.0f 秒後重試（%s/%s）", cooldown,
                            attempt, self.content_retries)
            time.sleep(cooldown)
        raise RuntimeError(f"MOPS 多次拒絕請求（{last_reason}）")

    def run(self, selected: list[Company], period_list: list[tuple[int, int]],
            statements: list[str], refresh: bool = False, batch_size: int = 60,
            batch_pause: float = 45.0) -> dict:
        self.output.mkdir(parents=True, exist_ok=True)
        rows: list[dict] = []
        manifest: list[dict] = []
        errors: list[dict] = []
        total = len(selected) * len(period_list) * len(statements)
        current = 0
        for company in selected:
            for year, quarter in period_list:
                for statement in statements:
                    current += 1
                    context = {**asdict(company), "year": year, "quarter": quarter,
                               "statement": statement}
                    try:
                        html = self.fetch(company, year, quarter, statement, refresh)
                        metadata, records = parse_statement(html)
                        manifest.append({**context, **metadata})
                        for index, record in enumerate(records, 1):
                            rows.append({**context, "row_order": index,
                                         "source_url": f"{BASE_URL}/{STATEMENTS[statement]}",
                                         "values": record,
                                         "numeric_values": {
                                             key: parse_number(value)
                                             for key, value in record.items() if key != "會計項目"
                                         }})
                        logging.info("[%s/%s] %s %s %sQ%s: %s", current, total,
                                     company.stock_id, statement, year, quarter, metadata["status"])
                    except Exception as exc:
                        error = {**context, "error": str(exc)}
                        errors.append(error)
                        logging.error("[%s/%s] %s", current, total, error)
                    if current % 25 == 0 or current == total:
                        self._checkpoint(rows, manifest, errors)
                    if current < total and batch_size > 0 and current % batch_size == 0:
                        logging.info("完成 %s 次請求，冷卻 %.0f 秒", current, batch_pause)
                        time.sleep(batch_pause)
        return self._checkpoint(rows, manifest, errors)

    def _checkpoint(self, rows: list[dict], manifest: list[dict], errors: list[dict]) -> dict:
        paths = {
            "data": self.output / "financial_statements.jsonl",
            "manifest": self.output / "manifest.csv",
            "errors": self.output / "errors.json",
            "companies": self.output / "companies.csv",
        }
        with paths["data"].open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        grouped: dict[tuple[str, str], list[dict]] = {}
        for row in rows:
            grouped.setdefault((row["stage"], row["category"]), []).append(row)
        for (stage, category), category_rows in grouped.items():
            category_dir = self.output / "by_category" / stage / category
            category_dir.mkdir(parents=True, exist_ok=True)
            with (category_dir / "financial_statements.jsonl").open("w", encoding="utf-8") as handle:
                for row in category_rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._write_csv(paths["manifest"], manifest)
        paths["errors"].write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(paths["companies"], [asdict(item) for item in companies()])
        return {"records": len(rows), "requests": len(manifest), "errors": len(errors),
                "output": str(self.output)}

    @staticmethod
    def _write_csv(path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8-sig")
            return
        fields = list(dict.fromkeys(key for row in rows for key in row))
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


def main() -> None:
    latest_year, latest_quarter = latest_available_period()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/mops_financials"))
    parser.add_argument("--start-year", type=int, default=2013)
    parser.add_argument("--end-year", type=int, default=latest_year)
    parser.add_argument("--end-quarter", type=int, choices=range(1, 5), default=latest_quarter)
    parser.add_argument("--stock-id", action="append", help="只抓指定股票代號，可重複使用")
    parser.add_argument("--stage", choices=["上游", "中游", "下游"])
    parser.add_argument("--category")
    parser.add_argument("--statement", action="append", choices=STATEMENTS, help="可重複使用")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=60)
    parser.add_argument("--batch-pause", type=float, default=45.0)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")

    selected = companies()
    if args.stock_id:
        selected = [item for item in selected if item.stock_id in set(args.stock_id)]
    if args.stage:
        selected = [item for item in selected if item.stage == args.stage]
    if args.category:
        selected = [item for item in selected if item.category == args.category]
    if not selected:
        parser.error("公司篩選條件沒有符合項目")
    if args.start_year > args.end_year:
        parser.error("start-year 不可晚於 end-year")

    crawler = MOPSCrawler(args.output, delay=args.delay)
    result = crawler.run(selected, list(periods(args.start_year, args.end_year, args.end_quarter)),
                         args.statement or list(STATEMENTS), args.refresh,
                         args.batch_size, args.batch_pause)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
