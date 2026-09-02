from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter


TIME_FIELD = "年月別_Year_and_month"
SERIES_FIELDS = {
    "工業及服務業": "工業及服務業__Industry_and_services_金額_新臺幣元",
    "男性": "男性_Male_金額_新臺幣元",
    "女性": "女性_Female_金額_新臺幣元",
    "批發及零售業": "批發及零售業_Wholesale_and_retail_trade_金額_新臺幣元",
}


@dataclass(frozen=True)
class SalaryRecord:
    period: datetime
    frequency: str
    status: str
    industry_and_services: int
    male: int
    female: int
    wholesale_and_retail: int


def parse_period(raw_period: str) -> tuple[datetime, str, str]:
    """將 YYYY、YYYYMM 及尾端含 Ⓟ/Ⓡ 的期間文字轉成日期。"""
    status = "final"
    if raw_period.endswith("Ⓟ"):
        status = "provisional"
    elif raw_period.endswith("Ⓡ"):
        status = "revised"

    digits = re.sub(r"\D", "", raw_period)
    if len(digits) == 4:
        return datetime(int(digits), 1, 1), "annual", status
    if len(digits) == 6:
        return datetime(int(digits[:4]), int(digits[4:]), 1), "monthly", status
    raise ValueError(f"無法辨識年月格式：{raw_period!r}")


def load_records(xml_path: Path) -> list[SalaryRecord]:
    root = ET.parse(xml_path).getroot()
    records: list[SalaryRecord] = []

    for row_number, row in enumerate(root.findall("每人每月經常性薪資"), start=1):
        values = {child.tag: (child.text or "").strip() for child in row}
        try:
            period, frequency, status = parse_period(values[TIME_FIELD])
            records.append(
                SalaryRecord(
                    period=period,
                    frequency=frequency,
                    status=status,
                    industry_and_services=int(values[SERIES_FIELDS["工業及服務業"]]),
                    male=int(values[SERIES_FIELDS["男性"]]),
                    female=int(values[SERIES_FIELDS["女性"]]),
                    wholesale_and_retail=int(values[SERIES_FIELDS["批發及零售業"]]),
                )
            )
        except (KeyError, ValueError) as error:
            raise ValueError(f"第 {row_number} 筆資料格式錯誤：{error}") from error

    if not records:
        raise ValueError("XML 中沒有找到薪資資料")
    return sorted(records, key=lambda record: record.period)


def configure_chinese_font() -> None:
    candidates = [
        "Microsoft JhengHei",
        "Noto Sans CJK TC",
        "Noto Sans TC",
        "PingFang TC",
        "Arial Unicode MS",
    ]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in candidates:
        if candidate in installed:
            plt.rcParams["font.family"] = candidate
            break
    plt.rcParams["axes.unicode_minus"] = False


def draw_chart(records: list[SalaryRecord], frequency: str, output_path: Path) -> int:
    selected = [record for record in records if record.frequency == frequency]
    if not selected:
        raise ValueError(f"沒有 {frequency} 資料可供繪圖")

    configure_chinese_font()
    dates = [record.period for record in selected]
    series = {
        "工業及服務業": [record.industry_and_services for record in selected],
        "男性": [record.male for record in selected],
        "女性": [record.female for record in selected],
        "批發及零售業": [record.wholesale_and_retail for record in selected],
    }
    colors = {
        "工業及服務業": "#2563eb",
        "男性": "#0f766e",
        "女性": "#db2777",
        "批發及零售業": "#ea580c",
    }

    fig, ax = plt.subplots(figsize=(15, 8))
    for label, salaries in series.items():
        ax.plot(
            dates,
            salaries,
            label=label,
            color=colors[label],
            linewidth=2.1 if label == "批發及零售業" else 1.6,
            linestyle="--" if label == "批發及零售業" else "-",
        )

    frequency_label = "月資料" if frequency == "monthly" else "年度資料"
    ax.set_title(f"工業及服務業與批發及零售業經常性薪資比較（{frequency_label}）", fontsize=17)
    ax.set_xlabel("時間")
    ax.set_ylabel("薪資（新臺幣元）")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    ax.grid(axis="y", color="#dbeafe", linewidth=0.8, alpha=0.9)
    ax.legend(frameon=False, ncol=3, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.margins(x=0.01)

    start = selected[0].period.strftime("%Y-%m" if frequency == "monthly" else "%Y")
    end = selected[-1].period.strftime("%Y-%m" if frequency == "monthly" else "%Y")
    fig.text(0.5, 0.015, f"資料期間：{start} 至 {end}；來源：dataset/mp05002.xml", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.035, 1, 1))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return len(selected)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="繪製工業及服務業男性、女性經常性薪資折線圖")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("dataset/mp05002.xml"),
        help="來源 XML 路徑",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("salary_trend.png"),
        help="輸出 PNG 路徑",
    )
    parser.add_argument(
        "--frequency",
        choices=("monthly", "annual"),
        default="monthly",
        help="繪製月資料或年度資料，預設為 monthly",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_records(args.input)
    count = draw_chart(records, args.frequency, args.output)
    print(f"已輸出 {args.output.resolve()}，共使用 {count} 筆 {args.frequency} 資料。")


if __name__ == "__main__":
    main()
