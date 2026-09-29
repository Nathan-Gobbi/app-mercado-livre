# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.exceptions import UserError

from .common import MlSalesProfitCase, stock_file, xlsx


class TestStockImport(MlSalesProfitCase):
    def _import(self, rows):
        wizard = self.env["ml.stock.import.wizard"].create(
            {"file": stock_file(rows), "file_name": "Estoque.xlsx"}
        )
        return wizard.action_import()

    def test_import_products_and_listings(self):
        result = self._import(
            [
                # Product row, holding the Premium listing
                [
                    "TST100",
                    "Fake Pedal",
                    "803-00-1",
                    7890000000017,
                    87149100,
                    160,
                    "Premium",
                    253.9,
                    196.13,
                    15.23,
                    0.1,
                    20.8,
                    8.19,
                    6,
                    -1,
                ],
                # Next row of the same product: its Classic listing
                [
                    "TST100",
                    None,
                    None,
                    None,
                    None,
                    None,
                    "Clássico",
                    239.9,
                    191.36,
                    14.39,
                    0.1,
                    16.87,
                    7.03,
                    None,
                    None,
                ],
                # Product without listing type: product only
                [
                    "TST101",
                    "Fake Chain",
                    None,
                    None,
                    "87149100\n",
                    20,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    3,
                    0,
                ],
            ]
        )
        self.assertEqual(result["params"]["type"], "success")
        pedal = self.env["product.template"].search([("default_code", "=", "TST100")])
        self.assertRecordValues(
            pedal,
            [
                {
                    "name": "Fake Pedal",
                    "ml_manufacturer_code": "803-00-1",
                    "barcode": "7890000000017",
                    "ml_ncm": "87149100",
                    "standard_price": 160,
                    "ml_stock_qty": 6,
                    "ml_min_stock_qty": 7,
                    "ml_stock_difference": -1,
                    "ml_stock_value": 960,
                }
            ],
        )
        self.assertEqual(
            sorted(pedal.ml_listing_ids.mapped("listing_type")),
            ["classic", "premium"],
        )
        premium = pedal.ml_listing_ids.filtered(
            lambda line: line.listing_type == "premium"
        )
        # Tax and profit are recomputed by Odoo with the same formula,
        # rounded to cents
        self.assertAlmostEqual(premium.tax_amount, 15.23)
        self.assertAlmostEqual(premium.net_profit, 20.80)
        chain = self.env["product.template"].search([("default_code", "=", "TST101")])
        self.assertEqual(chain.ml_ncm, "87149100")
        self.assertFalse(chain.ml_listing_ids)

    def test_reimport_updates(self):
        row = [
            "TST001",
            "Fake Shock Kit",
            None,
            None,
            None,
            90,
            "Premium",
            210.0,
            160.0,
            None,
            0.1,
            None,
            None,
            2,
            0,
        ]
        self._import([row])
        self.assertEqual(self.product.standard_price, 90)
        self.assertEqual(self.premium.price, 210.0)
        self.assertEqual(
            self.env["product.template"].search_count(
                [("default_code", "=", "TST001")]
            ),
            1,
        )

    def test_cost_taken_from_formula(self):
        # Color variants leave the cost empty and use the cost of the first
        # color in their formulas, like the real stock spreadsheet
        self._import(
            [
                [
                    "TST300",
                    "Fake Grip Black",
                    None,
                    None,
                    None,
                    6.5,
                    "Clássico",
                    21.9,
                    12.72,
                    None,
                    0.1,
                    "=I2-(F2+J2+K2)",
                    None,
                    4,
                    0,
                ],
                [
                    "TST301",
                    "Fake Grip Blue",
                    None,
                    None,
                    None,
                    None,
                    "Clássico",
                    21.9,
                    12.72,
                    None,
                    0.1,
                    "=I3-($F$2+J3+K3)",
                    None,
                    2,
                    0,
                ],
                [
                    "TST302",
                    "Fake Grip Red",
                    None,
                    None,
                    None,
                    None,
                    "Clássico",
                    21.9,
                    12.72,
                    None,
                    0.1,
                    "=I4-(F4+J4+K4)",
                    None,
                    1,
                    0,
                ],
            ]
        )
        products = self.env["product.template"].search(
            [("default_code", "in", ["TST300", "TST301", "TST302"])]
        )
        costs = {p.default_code: p.standard_price for p in products}
        self.assertEqual(costs, {"TST300": 6.5, "TST301": 6.5, "TST302": 0.0})

    def test_named_row_with_same_sku_is_a_listing(self):
        self._import(
            [
                [
                    "TST400",
                    "Fake Tape",
                    None,
                    None,
                    None,
                    30,
                    "Premium",
                    99.9,
                    70.0,
                    None,
                    0.1,
                    None,
                    None,
                    5,
                    0,
                ],
                [
                    "TST400",
                    "Clássico - Fake Tape",
                    None,
                    None,
                    None,
                    None,
                    "Clássico",
                    89.9,
                    65.0,
                    None,
                    0.1,
                    None,
                    None,
                    None,
                    None,
                ],
            ]
        )
        tape = self.env["product.template"].search([("default_code", "=", "TST400")])
        self.assertEqual(tape.name, "Fake Tape")
        self.assertEqual(tape.standard_price, 30)
        self.assertEqual(len(tape.ml_listing_ids), 2)

    def test_duplicate_barcode_is_reported(self):
        self.product.barcode = "7890000000024"
        result = self._import(
            [
                [
                    "TST200",
                    "Fake Tire",
                    None,
                    7890000000024,
                    None,
                    10,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    1,
                    0,
                ]
            ]
        )
        self.assertEqual(result["params"]["type"], "warning")
        tire = self.env["product.template"].search([("default_code", "=", "TST200")])
        self.assertFalse(tire.barcode)

    def test_wrong_file(self):
        wizard = self.env["ml.stock.import.wizard"].create(
            {"file": xlsx([["foo", "bar"]]), "file_name": "x.xlsx"}
        )
        with self.assertRaises(UserError):
            wizard.action_import()
