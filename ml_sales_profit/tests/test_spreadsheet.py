# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import date, datetime

from odoo.tests.common import BaseCase

from ..tools import spreadsheet


class TestSpreadsheet(BaseCase):
    def test_parse_ml_date(self):
        parse = spreadsheet.parse_ml_date
        self.assertEqual(parse("20 de setembro de 2026 21:01 hs."), date(2026, 9, 20))
        self.assertEqual(parse("1 de março de 2026"), date(2026, 3, 1))
        self.assertEqual(parse(datetime(2026, 1, 2, 10, 0)), date(2026, 1, 2))
        self.assertIsNone(parse("sem data"))
        self.assertIsNone(parse(None))

    def test_parse_brl_amount(self):
        parse = spreadsheet.parse_brl_amount
        self.assertEqual(parse("-1.234,56"), -1234.56)
        self.assertEqual(parse("21,90"), 21.9)
        self.assertEqual(parse(15.5), 15.5)
        self.assertIsNone(parse(""))
        self.assertIsNone(parse("abc"))

    def test_parse_float(self):
        self.assertEqual(spreadsheet.parse_float("2"), 2.0)
        self.assertEqual(spreadsheet.parse_float(3), 3.0)
        self.assertIsNone(spreadsheet.parse_float("#DIV/0!"))
        self.assertIsNone(spreadsheet.parse_float(" "))

    def test_clean_values(self):
        self.assertEqual(spreadsheet.clean_sku(" ng 0001\xa0"), "NG0001")
        self.assertEqual(spreadsheet.clean_sku("nan"), "")
        self.assertEqual(spreadsheet.clean_code(611056143650.0), "611056143650")
        self.assertEqual(spreadsheet.clean_code("87149100\n"), "87149100")

    def test_columns(self):
        header = ["Estado", "Descrição do status", "Tipo de anúncio", "Tipo"]
        self.assertEqual(spreadsheet.column_index(header, ["Tipo"]), 3)
        self.assertEqual(spreadsheet.column_index(header, ["Status"]), 1)
        self.assertIsNone(spreadsheet.column_index(header, ["SKU"]))
        rows = [("a",), ("SKU", "Unidades", "Data da venda")]
        self.assertEqual(spreadsheet.find_header(rows, ["data da venda", "sku"]), 1)
