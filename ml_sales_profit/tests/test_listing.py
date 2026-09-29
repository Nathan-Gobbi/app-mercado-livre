# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from psycopg2 import IntegrityError

from odoo.tools import mute_logger

from .common import MlSalesProfitCase


class TestListing(MlSalesProfitCase):
    def test_profit(self):
        # Same formulas as the spreadsheet: tax = price * 6%,
        # profit = net amount - (cost + tax + packaging)
        self.assertAlmostEqual(self.premium.tax_amount, 12.0)
        self.assertAlmostEqual(self.premium.net_profit, 37.9)
        self.assertAlmostEqual(self.premium.profit_percent, 18.95)

    def test_profit_follows_cost_and_tax_rate(self):
        self.product.standard_price = 120
        self.assertAlmostEqual(self.premium.net_profit, 17.9)
        self.company.ml_tax_rate = 10.0
        self.assertAlmostEqual(self.premium.tax_amount, 20.0)
        self.assertAlmostEqual(self.premium.net_profit, 9.9)

    def test_zero_price(self):
        self.premium.write({"price": 0.0, "net_amount": 0.0})
        self.assertEqual(self.premium.profit_percent, 0.0)
        self.assertAlmostEqual(self.premium.net_profit, -100.1)

    def test_one_listing_per_type(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.env["ml.listing"].create(
                {"product_tmpl_id": self.product.id, "listing_type": "premium"}
            )

    def test_display_name(self):
        self.assertEqual(self.classic.display_name, "[TST001] Fake Shock Kit - Classic")

    def test_product_stock(self):
        self.product.write({"ml_stock_qty": 6, "ml_min_stock_qty": 7})
        self.assertEqual(self.product.ml_stock_difference, -1)
        self.assertEqual(self.product.ml_stock_value, 600)
        self.product.standard_price = 50
        self.assertEqual(self.product.ml_stock_value, 300)
