import unittest
from datetime import date

from mops_financial_crawler import companies, latest_available_period, parse_number, parse_statement


class CrawlerTests(unittest.TestCase):
    def test_company_universe(self):
        items = companies()
        self.assertEqual(36, len(items))
        self.assertEqual(36, len({item.stock_id for item in items}))

    def test_latest_period(self):
        self.assertEqual((2025, 4), latest_available_period(date(2026, 3, 1)))
        self.assertEqual((2026, 2), latest_available_period(date(2026, 8, 29)))

    def test_number_formats(self):
        self.assertEqual(-1234, parse_number("(1,234)"))
        self.assertEqual(12.5, parse_number("12.5"))
        self.assertIsNone(parse_number("-"))

    def test_statement_parser(self):
        html = """
        <h2>合併資產負債表</h2><p>民國113年第4季 單位：新台幣仟元</p>
        <table><tr><th rowspan="2">會計項目</th><th colspan="2">113年12月31日</th></tr>
        <tr><th>金額</th><th>%</th></tr>
        <tr><td>現金及約當現金</td><td>1,234</td><td>2.5</td></tr></table>
        """
        metadata, rows = parse_statement(html)
        self.assertEqual("ok", metadata["status"])
        self.assertEqual(1, metadata["row_count"])
        self.assertEqual("現金及約當現金", rows[0]["會計項目"])
        self.assertEqual("1,234", rows[0]["113年12月31日_金額"])


if __name__ == "__main__":
    unittest.main()
