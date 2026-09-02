from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter

from analyze_salary_trend import load_records


SERIES = {
    "工業及服務業": "industry_and_services",
    "批發及零售業": "wholesale_and_retail",
}
COLORS = {
    "工業及服務業": "#2563eb",
    "批發及零售業": "#ea580c",
}


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


def calculate_cagr(start_value: float, end_value: float, years: int) -> float:
    return ((end_value / start_value) ** (1 / years) - 1) * 100


def load_annual_series(xml_path: Path) -> tuple[list[int], dict[str, list[int]]]:
    records = [
        record
        for record in load_records(xml_path)
        if record.frequency == "annual" and record.status == "final"
    ]
    years = [record.period.year for record in records]
    values = {
        label: [getattr(record, attribute) for record in records]
        for label, attribute in SERIES.items()
    }
    if len(years) < 2:
        raise ValueError("至少需要兩年的完整年度資料")
    return years, values


def draw_dashboard(xml_path: Path, output_path: Path) -> None:
    years, values = load_annual_series(xml_path)
    configure_chinese_font()

    indices = {
        label: [value / salaries[0] * 100 for value in salaries]
        for label, salaries in values.items()
    }
    yoy = {
        label: [(current / previous - 1) * 100 for previous, current in zip(salaries, salaries[1:])]
        for label, salaries in values.items()
    }
    yoy_gap = [
        wholesale - overall
        for wholesale, overall in zip(yoy["批發及零售業"], yoy["工業及服務業"])
    ]

    periods = [(1980, 1989), (1990, 1999), (2000, 2009), (2010, 2019), (2020, years[-1])]
    period_labels = [f"{start}–{end}" for start, end in periods]
    year_index = {year: index for index, year in enumerate(years)}
    period_cagr = {
        label: [
            calculate_cagr(
                salaries[year_index[start]],
                salaries[year_index[end]],
                end - start,
            )
            for start, end in periods
        ]
        for label, salaries in values.items()
    }

    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    fig.suptitle("工業及服務業與批發及零售業薪資增長速度比較", fontsize=20, y=0.98)

    ax = axes[0, 0]
    for label in SERIES:
        ax.plot(years, indices[label], label=label, color=COLORS[label], linewidth=2.2)
    ax.axhline(100, color="#94a3b8", linewidth=0.8)
    ax.set_title("A. 累積增長：1980年設為100")
    ax.set_ylabel("薪資指數")
    ax.legend(frameon=False)

    ax = axes[0, 1]
    for label in SERIES:
        ax.plot(years[1:], yoy[label], label=label, color=COLORS[label], linewidth=1.7)
    ax.axhline(0, color="#64748b", linewidth=0.8)
    ax.set_title("B. 各年度薪資年增率")
    ax.set_ylabel("年增率（%）")
    ax.legend(frameon=False)

    ax = axes[1, 0]
    gap_colors = ["#ea580c" if gap >= 0 else "#2563eb" for gap in yoy_gap]
    ax.bar(years[1:], yoy_gap, color=gap_colors, width=0.8)
    ax.axhline(0, color="#334155", linewidth=0.9)
    ax.set_title("C. 增長速度差：批發零售業減整體")
    ax.set_ylabel("年增率差（百分點）")
    ax.text(
        0.01,
        0.97,
        "橘色：批發零售業較快；藍色：整體較快",
        transform=ax.transAxes,
        va="top",
        fontsize=9,
    )

    ax = axes[1, 1]
    positions = list(range(len(periods)))
    width = 0.36
    for offset, label in zip((-width / 2, width / 2), SERIES):
        bars = ax.bar(
            [position + offset for position in positions],
            period_cagr[label],
            width=width,
            label=label,
            color=COLORS[label],
        )
        ax.bar_label(bars, fmt="%.2f%%", padding=3, fontsize=9)
    ax.axhline(0, color="#64748b", linewidth=0.8)
    ax.set_xticks(positions, period_labels)
    ax.set_title("D. 不同時期年複合成長率（CAGR）")
    ax.set_ylabel("CAGR（%）")
    ax.legend(frameon=False)

    for ax in axes.flat:
        ax.grid(axis="y", color="#dbeafe", linewidth=0.8, alpha=0.9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.1f}"))
        ax.margins(x=0.02)

    long_term = {
        label: calculate_cagr(salaries[0], salaries[-1], years[-1] - years[0])
        for label, salaries in values.items()
    }
    fig.text(
        0.5,
        0.012,
        (
            f"完整年度資料：{years[0]}–{years[-1]}｜"
            f"全期 CAGR：工業及服務業 {long_term['工業及服務業']:.2f}%，"
            f"批發及零售業 {long_term['批發及零售業']:.2f}%｜"
            "來源：dataset/mp05002.xml"
        ),
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.035, 1, 0.955), h_pad=3.0, w_pad=2.5)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="比較兩個產業的薪資增長速度")
    parser.add_argument("--input", type=Path, default=Path("dataset/mp05002.xml"))
    parser.add_argument("--output", type=Path, default=Path("salary_growth_dashboard.png"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    draw_dashboard(args.input, args.output)
    print(f"已輸出 {args.output.resolve()}")


if __name__ == "__main__":
    main()
