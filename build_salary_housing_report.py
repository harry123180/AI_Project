from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from analyze_salary_trend import load_records
from scrape_house_price_income import Quarter, load_house_price_csv, quarterly_salary


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output" / "pdf" / "taiwan_salary_housing_growth_report.pdf"

BLUE = colors.HexColor("#2563EB")
DARK_BLUE = colors.HexColor("#153E75")
LIGHT_BLUE = colors.HexColor("#EAF3FF")
ORANGE = colors.HexColor("#EA580C")
PURPLE = colors.HexColor("#7C3AED")
TEXT = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#CBD5E1")


def register_fonts() -> tuple[str, str]:
    candidates = [
        (Path("C:/Windows/Fonts/msjh.ttc"), "MicrosoftJhengHei"),
        (Path("C:/Windows/Fonts/msjhbd.ttc"), "MicrosoftJhengHeiBold"),
    ]
    if not all(path.exists() for path, _ in candidates):
        raise FileNotFoundError("找不到 Microsoft JhengHei 字型，無法可靠輸出繁體中文PDF")
    pdfmetrics.registerFont(TTFont(candidates[0][1], str(candidates[0][0]), subfontIndex=0))
    pdfmetrics.registerFont(TTFont(candidates[1][1], str(candidates[1][0]), subfontIndex=0))
    return candidates[0][1], candidates[1][1]


def make_styles(font: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName=bold,
            fontSize=26,
            leading=36,
            textColor=DARK_BLUE,
            alignment=TA_LEFT,
            spaceAfter=12,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["Normal"],
            fontName=font,
            fontSize=12,
            leading=20,
            textColor=MUTED,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName=bold,
            fontSize=20,
            leading=27,
            textColor=DARK_BLUE,
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=14,
            leading=20,
            textColor=BLUE,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=font,
            fontSize=10.5,
            leading=17,
            textColor=TEXT,
            spaceAfter=7,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName=font,
            fontSize=10.2,
            leading=16,
            textColor=TEXT,
            leftIndent=14,
            firstLineIndent=-8,
            bulletIndent=4,
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=font,
            fontSize=8.2,
            leading=12,
            textColor=MUTED,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=12,
            leading=19,
            textColor=DARK_BLUE,
            leftIndent=8,
            rightIndent=8,
        ),
    }


def calculate_metrics() -> dict[str, float | str]:
    salary_records = load_records(ROOT / "dataset" / "mp05002.xml")
    annual = {
        record.period.year: record
        for record in salary_records
        if record.frequency == "annual" and record.status == "final"
    }
    first, last = annual[1980], annual[2025]
    years = 2025 - 1980
    cagr = lambda start, end: ((end / start) ** (1 / years) - 1) * 100

    house_rows = load_house_price_csv(ROOT / "dataset" / "house_price_index.csv")
    salary_q = quarterly_salary(ROOT / "dataset" / "mp05002.xml")
    house_q = {
        Quarter(int(row["year"]), int(row["quarter"])): float(row["全國"])
        for row in house_rows
    }
    common = sorted(set(house_q) & set(salary_q))
    start_q, end_q = common[0], common[-1]
    house_growth = (house_q[end_q] / house_q[start_q] - 1) * 100
    salary_growth = (salary_q[end_q] / salary_q[start_q] - 1) * 100
    relative_index = (1 + house_growth / 100) / (1 + salary_growth / 100) * 100

    return {
        "salary_cagr": cagr(first.industry_and_services, last.industry_and_services),
        "wholesale_cagr": cagr(first.wholesale_and_retail, last.wholesale_and_retail),
        "house_growth": house_growth,
        "salary_growth": salary_growth,
        "relative_index": relative_index,
        "start_q": start_q.label,
        "end_q": end_q.label,
    }


def scaled_image(path: Path, max_width: float, max_height: float) -> Image:
    from PIL import Image as PILImage

    with PILImage.open(path) as source:
        width, height = source.size
    scale = min(max_width / width, max_height / height)
    return Image(str(path), width=width * scale, height=height * scale)


def header_footer(canvas, doc, font: str) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
    canvas.setFont(font, 7.8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, height - 10.5 * mm, "臺灣薪資與住宅價格增長分析")
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"第 {doc.page} 頁")
    canvas.restoreState()


def build_pdf() -> Path:
    font, bold = register_fonts()
    styles = make_styles(font, bold)
    metrics = calculate_metrics()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
        title="臺灣薪資與住宅價格增長分析報告",
        author="Codex",
        subject="1980至2026年薪資、產業與住宅價格趨勢比較",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="content")
    doc.addPageTemplates(
        PageTemplate(id="report", frames=[frame], onPage=lambda c, d: header_footer(c, d, font))
    )

    story = []

    story.extend(
        [
            Spacer(1, 23 * mm),
            Paragraph("臺灣薪資與住宅價格<br/>增長分析報告", styles["cover_title"]),
            Spacer(1, 4 * mm),
            Table([["1980-2026", "全國薪資", "住宅價格", "房價相對所得"]], colWidths=[37 * mm] * 4,
                  style=TableStyle([
                      ("FONTNAME", (0, 0), (-1, -1), bold),
                      ("FONTSIZE", (0, 0), (-1, -1), 10),
                      ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                      ("BACKGROUND", (0, 0), (-1, -1), BLUE),
                      ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                      ("TOPPADDING", (0, 0), (-1, -1), 9),
                      ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                  ])),
            Spacer(1, 12 * mm),
            Paragraph(
                "本報告整合行政院主計總處每人每月經常性薪資資料，以及內政部全國與六都住宅價格季指數，分析薪資、產業及住宅價格的長期增長速度。",
                styles["cover_subtitle"],
            ),
            Spacer(1, 52 * mm),
            Paragraph("資料更新範圍", styles["h2"]),
            Paragraph("薪資資料：1980年至2026年6月；房價共同分析期間：2012Q3至2026Q1。", styles["body"]),
            Paragraph("製表日期：2026年8月29日", styles["small"]),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("執行摘要", styles["h1"]),
            Table(
                [
                    ["指標", "結果", "解讀"],
                    ["全國房價累積增幅", f"{metrics['house_growth']:.1f}%", f"{metrics['start_q']}至{metrics['end_q']}"],
                    ["同期經常性薪資增幅", f"{metrics['salary_growth']:.1f}%", "以季度平均薪資計算"],
                    ["房價相對所得指數", f"{metrics['relative_index']:.1f}", "2012Q3設為100"],
                    ["長期薪資CAGR", f"{metrics['salary_cagr']:.2f}%", "1980至2025完整年度"],
                    ["批發零售業CAGR", f"{metrics['wholesale_cagr']:.2f}%", "1980至2025完整年度"],
                ],
                colWidths=[50 * mm, 38 * mm, 75 * mm],
                repeatRows=1,
                style=TableStyle([
                    ("FONTNAME", (0, 0), (-1, 0), bold),
                    ("FONTNAME", (0, 1), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                    ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BLUE]),
                    ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]),
            ),
            Spacer(1, 8 * mm),
            Table(
                [[Paragraph(
                    "核心結論：薪資並非沒有增長，而是2012年後全國住宅價格增長明顯更快。房價相對所得指數由100升至約139，表示房價相對薪資的累積壓力增加約39%。",
                    styles["callout"],
                )]],
                colWidths=[doc.width],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                    ("BOX", (0, 0), (-1, -1), 1, BLUE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]),
            ),
            Spacer(1, 8 * mm),
            Paragraph("主要觀察", styles["h2"]),
            Paragraph("1. 1980至2025年，工業及服務業整體薪資長期上升，女性薪資的長期增速高於男性，但薪資水準差距仍存在。", styles["bullet"]),
            Paragraph("2. 批發及零售業全期增速略低於整體產業，但2010年後的階段性增速略高，早期薪資優勢仍已逐漸消失。", styles["bullet"]),
            Paragraph("3. 全國房價在2012至2015年及2020至2024年出現兩波明顯擴張，均快於同期薪資增長。", styles["bullet"]),
            Paragraph("4. 2025年後房價轉為負成長、薪資維持正成長，使相對壓力由高點回落，但尚未回到2012年的狀態。", styles["bullet"]),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("一、資料與分析方法", styles["h1"]),
            Paragraph("薪資資料", styles["h2"]),
            Paragraph(
                "來源檔案為 dataset/mp05002.xml，共605筆、23欄，包含年度及月資料。報告使用工業及服務業整體、男性、女性及批發零售業經常性薪資。年度比較排除2026暫定值；季度比較則將三個月薪資取算術平均。",
                styles["body"],
            ),
            Paragraph("住宅價格資料", styles["h2"]),
            Paragraph(
                "由Python程式抓取內政部不動產資訊平台「全國及六都住宅價格季指數」。資料涵蓋全國、新北市、臺北市、桃園市、臺中市、臺南市及高雄市，自2012Q3開始，原始基期為2016年全年=100。",
                styles["body"],
            ),
            Paragraph("比較方式", styles["h2"]),
            Table(
                [
                    ["分析", "公式與目的"],
                    ["基期指數", "當期數值 ÷ 起始期數值 × 100；排除起始水準不同的影響"],
                    ["年增率", "當期 ÷ 去年同期 - 1；觀察短期增長速度與轉折"],
                    ["CAGR", "(期末 ÷ 期初)^(1/年數) - 1；比較長期平均增速"],
                    ["房價相對所得指數", "房價基期指數 ÷ 薪資基期指數 × 100；上升代表房價增長快於薪資"],
                ],
                colWidths=[45 * mm, 118 * mm],
                style=TableStyle([
                    ("FONTNAME", (0, 0), (-1, 0), bold),
                    ("FONTNAME", (0, 1), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                    ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BLUE]),
                    ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]),
            ),
            Spacer(1, 8 * mm),
            Paragraph("地理範圍注意事項", styles["h2"]),
            Paragraph(
                "全國房價與全國薪資的地理範圍一致。六都個別房價圖目前仍搭配全國薪資，因此只能解讀為「該城市房價相對全國薪資」，不能視為該城市居民的房價所得負擔。",
                styles["body"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("二、薪資長期趨勢", styles["h1"]),
            scaled_image(ROOT / "salary_trend_comparison.png", doc.width, 105 * mm),
            Spacer(1, 4 * mm),
            Paragraph("圖1　工業及服務業、男性、女性及批發零售業月薪資趨勢", styles["small"]),
            Paragraph("趨勢解讀", styles["h2"]),
            Paragraph("• 四條曲線長期向上，但男性薪資始終高於整體與女性；女性薪資增長較快，差距縮小速度仍有限。", styles["bullet"]),
            Paragraph("• 批發及零售業在早期略高於整體，約2000年後多數時間略低於整體，顯示其相對薪資優勢減弱。", styles["bullet"]),
            Paragraph("• 2000年代薪資曲線趨平，2010年後恢復增長，2020年後增速再度提高。", styles["bullet"]),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("三、兩產業增長速度比較", styles["h1"]),
            scaled_image(ROOT / "salary_growth_dashboard.png", doc.width, 170 * mm),
            Spacer(1, 3 * mm),
            Paragraph("圖2　工業及服務業與批發零售業增長速度分析", styles["small"]),
            Paragraph("主要發現", styles["h2"]),
            Paragraph("• 全期CAGR為整體4.13%、批發零售業3.99%，長期差距不大，但整體略快。", styles["bullet"]),
            Paragraph("• 2000至2009年是共同停滯期；2010至2019及2020至2025年則由批發零售業略快。", styles["bullet"]),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("四、房價與薪資增長比較", styles["h1"]),
            scaled_image(ROOT / "house_price_income_comparison.png", doc.width, 170 * mm),
            Spacer(1, 5 * mm),
            Paragraph("圖3　全國住宅價格與工業及服務業薪資增長比較", styles["small"]),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("五、結果代表什麼", styles["h1"]),
            Paragraph("1. 購屋能力相對下降", styles["h2"]),
            Paragraph(
                "2012Q3至2026Q1，全國房價增長82.2%，同期經常性薪資增長31.1%。這表示受僱者雖然加薪，但單靠薪資累積追上房價的難度提高。",
                styles["body"],
            ),
            Paragraph("2. 問題是增速失衡，不是薪資完全停滯", styles["h2"]),
            Paragraph(
                "薪資曲線持續向上且波動較小；房價則在短期內快速上升、盤整或下跌。更精確的論述是「薪資增長持續落後房價」，而非「薪資沒有增加」。",
                styles["body"],
            ),
            Paragraph("3. 兩波房價擴張造成主要差距", styles["h2"]),
            Paragraph(
                "2012至2015年是第一波差距擴大；2015至2019年房價盤整，薪資持續增加，使相對壓力稍有改善。2020至2024年出現第二波且更強的房價增長，房價相對所得指數一度超過150。",
                styles["body"],
            ),
            Paragraph("4. 近期改善屬於邊際改善", styles["h2"]),
            Paragraph(
                "2025年後房價年增率轉負、薪資仍正成長，使房價相對所得指數由高點降至約139。壓力正在下降，但仍高於2012年的100，尚不足以抵銷過去累積的增幅。",
                styles["body"],
            ),
            Table(
                [[Paragraph(
                    "可支持的觀點：2012年後臺灣住宅價格與經常性薪資的增長速度失衡，造成購屋負擔的相對惡化；近期房價修正帶來改善，但尚未回復至早期水準。",
                    styles["callout"],
                )]],
                colWidths=[doc.width],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3E8FF")),
                    ("BOX", (0, 0), (-1, -1), 1, PURPLE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]),
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("六、限制與後續分析", styles["h1"]),
            Paragraph("目前結果不能直接等同房價所得比", styles["h2"]),
            Paragraph("房價資料是品質調整後的價格指數，不是平均總價；薪資資料是平均經常性薪資，不是薪資中位數或家庭可支配所得。因此相對指數適合比較增長速度，不能直接解讀成需要多少年所得才能購屋。", styles["body"]),
            Paragraph("尚未納入的因素", styles["h2"]),
            Paragraph("• 獎金、加班費、兼職收入及其他家庭所得。", styles["bullet"]),
            Paragraph("• 房貸利率、貸款成數、貸款年限與每月還款額。", styles["bullet"]),
            Paragraph("• 住宅坪數、屋齡、區位及交易物件組成。", styles["bullet"]),
            Paragraph("• 六都各自的薪資或家庭所得，因此目前六都圖不能代表當地居民負擔。", styles["bullet"]),
            Paragraph("建議下一階段", styles["h2"]),
            Table(
                [
                    ["優先項目", "用途"],
                    ["六都薪資或家庭可支配所得", "建立地理範圍一致的城市比較"],
                    ["房價所得比與貸款負擔率", "衡量實際購屋負擔，而非僅比較增速"],
                    ["房貸利率與貸款條件", "估算每月現金流壓力"],
                    ["CPI與實質薪資", "區分名目加薪與實際購買力"],
                    ["實價登錄中位單價", "檢查價格指數與市場成交資料是否一致"],
                ],
                colWidths=[65 * mm, 98 * mm],
                style=TableStyle([
                    ("FONTNAME", (0, 0), (-1, 0), bold),
                    ("FONTNAME", (0, 1), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                    ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BLUE]),
                    ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]),
            ),
            Spacer(1, 8 * mm),
            Paragraph("資料來源", styles["h2"]),
            Paragraph("1. 行政院主計總處，每人每月經常性薪資XML，dataset/mp05002.xml。", styles["small"]),
            Paragraph("2. 內政部不動產資訊平台，住宅價格指數：https://pip.moi.gov.tw/Publicize/Info/E1060", styles["small"]),
            Paragraph("3. 政府資料開放平臺，實價登錄批次資料：https://data.gov.tw/dataset/25119", styles["small"]),
        ]
    )

    doc.build(story)
    return OUTPUT


if __name__ == "__main__":
    print(build_pdf())
