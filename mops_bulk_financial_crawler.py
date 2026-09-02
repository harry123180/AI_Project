"""從 MOPS 季度彙總報表下載 AI 供應鏈公司全部可用財報資料。"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import time
from collections import defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from mops_financial_crawler import companies, expand_html_table, parse_number, periods


BASE_URL = "https://mopsov.twse.com.tw/mops/web"
ENDPOINTS = {
    "income_statement": "ajax_t163sb04",
    "balance_sheet": "ajax_t163sb05",
    "cash_flow": "ajax_t163sb20",
}
MARKETS = ("sii", "otc")


def unique_headers(headers: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    output = []
    for index, header in enumerate(headers, 1):
        header = header.strip() or f"欄位_{index}"
        counts[header] = counts.get(header, 0) + 1
        output.append(header if counts[header] == 1 else f"{header}_{counts[header]}")
    return output


def parse_bulk_statement(html: str, target_ids: set[str]) -> dict[str, dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, dict[str, str]] = {}
    for table in soup.find_all("table"):
        rows = expand_html_table(table)
        if not rows:
            continue
        header = rows[0]
        if len(header) < 3 or "公司" not in header[0] or "代號" not in header[0]:
            continue
        headers = unique_headers(header)
        for row in rows[1:]:
            if not row:
                continue
            stock_id = row[0].strip()
            if stock_id not in target_ids:
                continue
            padded = row + [""] * (len(headers) - len(row))
            result[stock_id] = {headers[i]: padded[i] for i in range(len(headers))}
    return result


class BulkCrawler:
    def __init__(self, output: Path, delay: float, timeout: float = 120.0,
                 content_retries: int = 5) -> None:
        self.output = output
        self.cache = output / "raw_cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.timeout = timeout
        self.content_retries = content_retries
        self.session = requests.Session()
        retry = Retry(total=5, connect=5, read=5, backoff_factor=2,
                      status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET", "POST"))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; MOPSFinancialResearch/1.0)",
            "Referer": "https://mopsov.twse.com.tw/mops/web/index",
        })

    def fetch(self, year: int, quarter: int, statement: str, market: str) -> str:
        path = self.cache / f"{year}Q{quarter}_{statement}_{market}.html"
        if path.exists():
            return path.read_text(encoding="utf-8")
        payload = {
            "encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1",
            "TYPEK": market, "year": str(year - 1911), "season": str(quarter),
        }
        endpoint = ENDPOINTS[statement]
        reason = ""
        for attempt in range(1, self.content_retries + 1):
            response = self.session.post(f"{BASE_URL}/{endpoint}", data=payload,
                                         timeout=self.timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            html = response.text
            rejected = ("FOR SECURITY REASONS" in html or "錯誤代碼" in html
                        or len(html) < 500)
            if not rejected:
                path.write_text(html, encoding="utf-8")
                time.sleep(self.delay + random.uniform(0.2, 0.8))
                return html
            reason = f"HTTP {response.status_code}, {len(html)} bytes"
            cooldown = min(180.0, 20.0 * 2 ** (attempt - 1))
            logging.warning("MOPS 拒絕回應，冷卻 %.0f 秒（%s/%s）", cooldown,
                            attempt, self.content_retries)
            time.sleep(cooldown)
        raise RuntimeError(f"MOPS 多次拒絕請求（{reason}）")

    def run(self, start_year: int, end_year: int, end_quarter: int,
            batch_size: int, batch_pause: float) -> dict:
        company_map = {item.stock_id: item for item in companies()}
        target_ids = set(company_map)
        period_list = list(periods(start_year, end_year, end_quarter))
        total = len(period_list) * len(ENDPOINTS) * len(MARKETS)
        request_no = 0
        rows: list[dict] = []
        manifest: list[dict] = []
        found_keys: set[tuple[str, int, int, str]] = set()

        for year, quarter in period_list:
            for statement, endpoint in ENDPOINTS.items():
                for market in MARKETS:
                    request_no += 1
                    entry = {"year": year, "quarter": quarter, "statement": statement,
                             "market": market, "endpoint": endpoint}
                    try:
                        html = self.fetch(year, quarter, statement, market)
                        found = parse_bulk_statement(html, target_ids)
                        entry.update(status="ok", matched_companies=len(found))
                        for stock_id, record in found.items():
                            company = company_map[stock_id]
                            found_keys.add((stock_id, year, quarter, statement))
                            for account, raw_value in record.items():
                                if account in {"公司 代號", "公司代號", "公司名稱"}:
                                    continue
                                rows.append({
                                    "stage": company.stage, "category": company.category,
                                    "stock_id": stock_id, "company_name": company.name,
                                    "year": year, "quarter": quarter,
                                    "statement": statement, "account": account,
                                    "value": parse_number(raw_value), "raw_value": raw_value,
                                    "market": market,
                                    "source_url": f"{BASE_URL}/{endpoint}",
                                })
                        logging.info("[%s/%s] %sQ%s %s %s：%s 家", request_no, total,
                                     year, quarter, statement, market, len(found))
                    except Exception as exc:
                        entry.update(status="error", error=str(exc), matched_companies=0)
                        logging.error("[%s/%s] %s", request_no, total, entry)
                    manifest.append(entry)
                    if request_no % 20 == 0 or request_no == total:
                        self.write_outputs(rows, manifest, found_keys, period_list, company_map)
                    if request_no < total and batch_size and request_no % batch_size == 0:
                        logging.info("批次冷卻 %.0f 秒", batch_pause)
                        time.sleep(batch_pause)
        return self.write_outputs(rows, manifest, found_keys, period_list, company_map)

    def write_outputs(self, rows: list[dict], manifest: list[dict], found_keys: set,
                      period_list: list[tuple[int, int]], company_map: dict) -> dict:
        self.output.mkdir(parents=True, exist_ok=True)
        self.write_csv(self.output / "financial_statements_long.csv", rows)
        self.write_csv(self.output / "request_manifest.csv", manifest)

        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows:
            grouped[(row["stage"], row["category"])].append(row)
        for (stage, category), group_rows in grouped.items():
            folder = self.output / "by_category" / stage / category
            folder.mkdir(parents=True, exist_ok=True)
            self.write_csv(folder / "financial_statements_long.csv", group_rows)

        coverage = []
        for stock_id, company in company_map.items():
            for statement in ENDPOINTS:
                available = sorted((year, quarter) for sid, year, quarter, stmt in found_keys
                                   if sid == stock_id and stmt == statement)
                coverage.append({
                    "stage": company.stage, "category": company.category,
                    "stock_id": stock_id, "company_name": company.name,
                    "statement": statement, "period_count": len(available),
                    "first_period": f"{available[0][0]}Q{available[0][1]}" if available else "",
                    "last_period": f"{available[-1][0]}Q{available[-1][1]}" if available else "",
                })
        self.write_csv(self.output / "coverage.csv", coverage)
        errors = [item for item in manifest if item["status"] == "error"]
        summary = {
            "companies": len(company_map), "periods": len(period_list),
            "company_statement_periods": len(found_keys), "metric_rows": len(rows),
            "requests": len(manifest), "request_errors": len(errors),
        }
        (self.output / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    @staticmethod
    def write_csv(path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8-sig")
            return
        fields = list(dict.fromkeys(key for row in rows for key in row))
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/mops_financials_full"))
    parser.add_argument("--start-year", type=int, default=2013)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--end-quarter", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--batch-pause", type=float, default=45.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = BulkCrawler(args.output, args.delay).run(
        args.start_year, args.end_year, args.end_quarter, args.batch_size, args.batch_pause)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
