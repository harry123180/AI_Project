import unittest

from mops_bulk_financial_crawler import parse_bulk_statement


class BulkParserTests(unittest.TestCase):
    def test_filters_and_parses_target_company(self):
        html = """
        <table><tr><th>公司 代號</th><th>公司名稱</th><th>營業收入</th></tr>
        <tr><td>2330</td><td>台積電</td><td>1,234</td></tr>
        <tr><td>9999</td><td>其他</td><td>99</td></tr></table>
        """
        result = parse_bulk_statement(html, {"2330"})
        self.assertEqual({"2330"}, set(result))
        self.assertEqual("1,234", result["2330"]["營業收入"])


if __name__ == "__main__":
    unittest.main()
