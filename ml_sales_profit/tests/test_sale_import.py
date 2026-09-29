# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import date

from odoo.exceptions import UserError

from .common import MlSalesProfitCase, read_report, sale_row, sales_file, xlsx


class TestSaleImport(MlSalesProfitCase):
    def _import(self, rows, name="vendas.xlsx"):
        sale_import = self.env["ml.sale.import"].create(
            {"file": sales_file(rows), "file_name": name}
        )
        sale_import.action_process()
        return sale_import

    def _week(self):
        return [
            sale_row(
                "1001",
                "20 de setembro de 2026 21:01 hs.",
                "Entregue",
                1,
                200.0,
                "TST001",
                "Fake Shock Kit",
                "Cor : Preto",
                "Premium",
            ),
            sale_row(
                "1002",
                "18 de setembro de 2026 10:00 hs.",
                "A caminho",
                2,
                360.0,
                "tst 001",
                "Fake Shock Kit",
                " ",
                "Clássico",
            ),
            # Unknown SKU: kept, but without profit
            sale_row(
                "1003",
                "16 de setembro de 2026 09:00 hs.",
                "Entregue",
                1,
                50.0,
                "XYZ999",
                "Unknown Product",
                " ",
                "Clássico",
            ),
            # Ignored rows: cancelled, without SKU and without units
            sale_row(
                "1004",
                "16 de setembro de 2026 09:00 hs.",
                "Cancelada pelo comprador",
                1,
                200.0,
                "TST001",
                "Fake Shock Kit",
                " ",
                "Premium",
            ),
            sale_row(
                "1005",
                "16 de setembro de 2026 09:00 hs.",
                "Entregue",
                1,
                10.0,
                " ",
                "No SKU",
                " ",
                "Premium",
            ),
            sale_row(
                "1006",
                "16 de setembro de 2026 09:00 hs.",
                "Entregue",
                0,
                0.0,
                "TST001",
                "Fake Shock Kit",
                " ",
                "Premium",
            ),
        ]

    def test_process(self):
        sale_import = self._import(self._week())
        self.assertEqual(sale_import.state, "done")
        self.assertEqual(sale_import.line_count, 3)
        self.assertEqual(sale_import.not_found_count, 1)
        self.assertEqual(sale_import.date_from, date(2026, 9, 16))
        self.assertEqual(sale_import.date_to, date(2026, 9, 20))
        self.assertEqual(sale_import.name, "Sales 16/09/2026 - 20/09/2026")

        premium = sale_import.line_ids.filtered(lambda line: line.sale_number == "1001")
        self.assertRecordValues(
            premium,
            [
                {
                    "sku": "TST001",
                    "listing_id": self.premium.id,
                    "product_tmpl_id": self.product.id,
                    "revenue": 200.0,
                    "revenue_origin": "direct",
                    "unit_tax": 12.0,
                    "unit_net_profit": 37.9,
                    "unit_gross_profit": 49.9,
                    "net_profit": 37.9,
                    "profit_status": "ok",
                }
            ],
        )
        classic = sale_import.line_ids.filtered(lambda line: line.sale_number == "1002")
        self.assertEqual(classic.sku, "TST001")
        self.assertEqual(classic.listing_id, self.classic)
        self.assertAlmostEqual(classic.net_profit, 2 * 29.1)
        unknown = sale_import.line_ids.filtered(lambda line: line.sku == "XYZ999")
        self.assertEqual(unknown.profit_status, "not_found")
        self.assertEqual(unknown.net_profit, 0.0)

        self.assertAlmostEqual(sale_import.total_units, 4)
        self.assertAlmostEqual(sale_import.total_revenue, 610.0)
        self.assertAlmostEqual(sale_import.total_net_profit, 37.9 + 58.2)
        self.assertAlmostEqual(
            sale_import.net_margin, 100 * (37.9 + 58.2) / 610.0, places=2
        )

    def test_overlapping_imports_do_not_duplicate_sales(self):
        Line = self.env["ml.sale.line"]
        domain = [("sale_number", "in", ["1001", "1002", "1003", "1010"])]
        week = self._import(self._week())
        month = self._import(
            self._week()
            + [
                sale_row(
                    "1010",
                    "2 de setembro de 2026 09:00 hs.",
                    "Entregue",
                    1,
                    200.0,
                    "TST001",
                    "Fake Shock Kit",
                    " ",
                    "Premium",
                )
            ]
        )
        self.assertEqual(month.line_count, 4)
        self.assertEqual(Line.search_count(domain), 4)
        self.assertEqual(
            week.line_ids,
            month.line_ids
            - month.line_ids.filtered(lambda line: line.sale_number == "1010"),
        )
        # Resetting one import keeps the sales still used by the other one
        week.action_reset_draft()
        self.assertFalse(week.line_ids)
        self.assertEqual(Line.search_count(domain), 4)
        month.unlink()
        self.assertEqual(Line.search_count(domain), 0)

    def test_sale_cancelled_later_is_removed(self):
        week = self._import(self._week())
        self._import(
            [
                sale_row(
                    "1001",
                    "20 de setembro de 2026 21:01 hs.",
                    "Cancelada pelo vendedor",
                    1,
                    200.0,
                    "TST001",
                    "Fake Shock Kit",
                    "Cor : Preto",
                    "Premium",
                )
            ]
            + self._week()[1:2]
        )
        self.assertEqual(week.line_count, 2)
        self.assertNotIn("1001", week.line_ids.mapped("sale_number"))

    def test_revenue_rebuilt_from_listing(self):
        sale_import = self._import(
            [
                sale_row(
                    "2001",
                    "20 de setembro de 2026",
                    "Entregue",
                    2,
                    "",
                    "TST001",
                    "Fake Shock Kit",
                    " ",
                    "Premium",
                ),
            ]
        )
        line = sale_import.line_ids
        self.assertEqual(line.revenue_origin, "rebuilt")
        self.assertEqual(line.revenue, 400.0)

    def test_report(self):
        sale_import = self._import(self._week())
        sale_import.action_download_report()
        self.assertEqual(
            sale_import.report_file_name, "Sales summary 16-09 a 20-09.xlsx"
        )
        report = read_report(sale_import.report_file)
        self.assertEqual(list(report), ["Resumo_Estoque", "Resumo_Financeiro"])
        stock = report["Resumo_Estoque"]
        self.assertEqual(
            stock[1:],
            [
                ["TST001", "Fake Shock Kit", "Cor : Preto", 3, 560],
                ["XYZ999", "Unknown Product", None, 1, 50],
                ["TOTAL", None, None, 4, 610],
            ],
        )
        financial = report["Resumo_Financeiro"]
        self.assertEqual(len(financial), 5)
        # Sorted by units sold, the classic listing (2 units) comes first
        self.assertEqual(
            financial[1][:6], ["TST001", "Fake Shock Kit", None, "Classic", 2, 360]
        )
        self.assertEqual(financial[1][8], 29.1)
        self.assertEqual(financial[-1][0], "TOTAL")
        self.assertEqual(financial[-1][11], 96.1)

    def test_wrong_file(self):
        sale_import = self.env["ml.sale.import"].create(
            {"file": xlsx([["foo"]]), "file_name": "x.xlsx"}
        )
        with self.assertRaises(UserError):
            sale_import.action_process()
        sale_import.file = False
        with self.assertRaises(UserError):
            sale_import.action_process()
