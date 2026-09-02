from __future__ import annotations

import argparse
import csv
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from analyze_salary_trend import load_records


SOURCE_URL = "https://pip.moi.gov.tw/Publicize/Info/E1060"
REGIONS = ("全國", "新北市", "臺北市", "桃園市", "臺中市", "臺南市", "高雄市")


@dataclass(frozen=True, order=True)
class Quarter:
    year: int
    quarter: int

    @property
    def label(self) -> str:
        return f"{self.year}Q{self.quarter}"


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; salary-house-price-research/1.0)",
            "Accept-Language": "zh-TW,zh;q=0.9",
        }
    )
    return session


def parse_roc_quarter(raw: str) -> Quarter:
    match = re.search(r"(\d+)\s*年\s*第\s*(\d)\s*季", raw)
    if not match:
        raise ValueError(f"無法辨識季度：{raw!r}")
    return Quarter(int(match.group(1)) + 1911, int(match.group(2)))


def scrape_house_price_index(url: str = SOURCE_URL) -> list[dict[str, str | float]]:
    session = build_session()
    response = session.get(url, timeout=30)
    response.raise_for_status()
    time.sleep(0.5)

    soup = BeautifulSoup(response.text, "html.parser")
    target_table = None
    for table in soup.find_all("table"):
        headers = [cell.get_text(" ", strip=True) for cell in table.find_all("th")]
        text = table.get_text(" ", strip=True)
        if all(region in text for region in REGIONS) and "101年第3季" in text:
            target_table = table
            break
    if target_table is None:
        raise ValueError("找不到全國及六都住宅價格季指數表格，網站結構可能已變更")

    rows: list[dict[str, str | float]] = []
    for tr in target_table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
        if len(cells) < len(REGIONS) + 1 or not re.search(r"\d+\s*年\s*第\s*\d\s*季", cells[0]):
            continue
        quarter = parse_roc_quarter(cells[0])
        record: dict[str, str | float] = {
            "period": quarter.label,
            "year": quarter.year,
            "quarter": quarter.quarter,
        }
        for region, value in zip(REGIONS, cells[1 : len(REGIONS) + 1]):
            record[region] = float(value.replace(",", ""))
        rows.append(record)

    rows.sort(key=lambda row: (int(row["year"]), int(row["quarter"])))
    if len(rows) < 20:
        raise ValueError(f"只解析到 {len(rows)} 筆季度資料，拒絕輸出不完整結果")
    return rows


def save_house_price_csv(rows: list[dict[str, str | float]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["period", "year", "quarter", *REGIONS]
    with output_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_house_price_csv(path: Path) -> list[dict[str, str | float]]:
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        row["year"] = int(row["year"])
        row["quarter"] = int(row["quarter"])
        for region in REGIONS:
            row[region] = float(row[region])
    return rows


def quarterly_salary(xml_path: Path) -> dict[Quarter, float]:
    grouped: dict[Quarter, list[int]] = defaultdict(list)
    for record in load_records(xml_path):
        if record.frequency != "monthly":
            continue
        quarter = Quarter(record.period.year, (record.period.month - 1) // 3 + 1)
        grouped[quarter].append(record.industry_and_services)
    return {
        quarter: sum(values) / len(values)
        for quarter, values in grouped.items()
        if len(values) == 3
    }


def configure_chinese_font() -> None:
    candidates = (
        "Microsoft JhengHei",
        "Noto Sans CJK TC",
        "Noto Sans TC",
        "PingFang TC",
        "Arial Unicode MS",
    )
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in candidates:
        if candidate in installed:
            plt.rcParams["font.family"] = candidate
            break
    plt.rcParams["axes.unicode_minus"] = False


def draw_comparison(
    house_rows: list[dict[str, str | float]],
    salary_by_quarter: dict[Quarter, float],
    region: str,
    output_path: Path,
) -> tuple[Quarter, Quarter, float, float]:
    house_by_quarter = {
        Quarter(int(row["year"]), int(row["quarter"])): float(row[region])
        for row in house_rows
    }
    quarters = sorted(set(house_by_quarter) & set(salary_by_quarter))
    if len(quarters) < 2:
        raise ValueError("房價與薪資沒有足夠的共同季度")

    house = [house_by_quarter[quarter] for quarter in quarters]
    salary = [salary_by_quarter[quarter] for quarter in quarters]
    house_growth = [value / house[0] * 100 for value in house]
    salary_growth = [value / salary[0] * 100 for value in salary]
    affordability = [h / s * 100 for h, s in zip(house_growth, salary_growth)]
    house_yoy = [(house[i] / house[i - 4] - 1) * 100 for i in range(4, len(house))]
    salary_yoy = [(salary[i] / salary[i - 4] - 1) * 100 for i in range(4, len(salary))]

    configure_chinese_font()
    x = list(range(len(quarters)))
    fig, axes = plt.subplots(3, 1, figsize=(15, 13), sharex=True)
    fig.suptitle(f"{region}住宅價格與工業及服務業薪資增長比較", fontsize=20, y=0.985)

    axes[0].plot(x, house_growth, label=f"{region}住宅價格", color="#ea580c", linewidth=2.4)
    axes[0].plot(x, salary_growth, label="工業及服務業薪資", color="#2563eb", linewidth=2.4)
    axes[0].axhline(100, color="#64748b", linewidth=0.8)
    axes[0].set_title(f"A. 累積增幅（{quarters[0].label}=100）")
    axes[0].set_ylabel("指數")
    axes[0].legend(frameon=False)

    axes[1].plot(x[4:], house_yoy, label="住宅價格年增率", color="#ea580c", linewidth=1.8)
    axes[1].plot(x[4:], salary_yoy, label="薪資年增率", color="#2563eb", linewidth=1.8)
    axes[1].axhline(0, color="#64748b", linewidth=0.8)
    axes[1].set_title("B. 同季年增率")
    axes[1].set_ylabel("年增率（%）")
    axes[1].legend(frameon=False)

    axes[2].fill_between(x, 100, affordability, color="#7c3aed", alpha=0.18)
    axes[2].plot(x, affordability, color="#7c3aed", linewidth=2.2)
    axes[2].axhline(100, color="#64748b", linewidth=0.8)
    axes[2].set_title("C. 房價相對所得指數（上升代表房價增長快於薪資）")
    axes[2].set_ylabel("相對指數")
    axes[2].set_xlabel("季度", labelpad=42)

    for ax in axes:
        ax.grid(axis="y", color="#dbeafe", linewidth=0.8, alpha=0.9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.1f}"))
    axes[2].set_xticks(x, [f"Q{quarter.quarter}" for quarter in quarters])
    axes[2].tick_params(axis="x", labelsize=8, pad=4, length=4)

    year_positions: dict[int, list[int]] = defaultdict(list)
    for position, quarter in enumerate(quarters):
        year_positions[quarter.year].append(position)
    year_centers = [sum(positions) / len(positions) for positions in year_positions.values()]
    year_axis = axes[2].secondary_xaxis("bottom")
    year_axis.spines["bottom"].set_position(("outward", 24))
    year_axis.set_xticks(year_centers, [str(year) for year in year_positions])
    year_axis.tick_params(axis="x", labelsize=8, pad=3, length=0)

    house_total_growth = house_growth[-1] - 100
    salary_total_growth = salary_growth[-1] - 100
    fig.text(
        0.5,
        0.012,
        (
            f"共同期間：{quarters[0].label}–{quarters[-1].label}｜"
            f"房價累積增幅 {house_total_growth:.1f}%｜薪資累積增幅 {salary_total_growth:.1f}%｜"
            f"房價相對所得指數 {affordability[-1]:.1f}｜來源：內政部不動產資訊平台、薪資XML"
        ),
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.065, 1, 0.965), h_pad=2.2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return quarters[0], quarters[-1], house_total_growth, salary_total_growth


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取住宅價格指數並與薪資增長比較")
    parser.add_argument("--salary-xml", type=Path, default=Path("dataset/mp05002.xml"))
    parser.add_argument("--house-csv", type=Path, default=Path("dataset/house_price_index.csv"))
    parser.add_argument("--output", type=Path, default=Path("house_price_income_comparison.png"))
    parser.add_argument("--region", choices=REGIONS, default="全國")
    parser.add_argument("--refresh", action="store_true", help="重新從官方網站下載住宅價格資料")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.refresh or not args.house_csv.exists():
        house_rows = scrape_house_price_index()
        save_house_price_csv(house_rows, args.house_csv)
        print(f"已下載 {len(house_rows)} 季住宅價格資料至 {args.house_csv.resolve()}")
    else:
        house_rows = load_house_price_csv(args.house_csv)
        print(f"使用快取資料 {args.house_csv.resolve()}")

    start, end, house_growth, salary_growth = draw_comparison(
        house_rows,
        quarterly_salary(args.salary_xml),
        args.region,
        args.output,
    )
    print(
        f"已輸出 {args.output.resolve()}：{start.label}–{end.label}，"
        f"房價增幅 {house_growth:.1f}%，薪資增幅 {salary_growth:.1f}%。"
    )


if __name__ == "__main__":
    main()
