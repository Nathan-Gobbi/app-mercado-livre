# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.exceptions import UserError

from .common import MlSalesProfitCase


class TestPurchaseRequirementReport(MlSalesProfitCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier_a = cls.env["res.partner"].create(
            {"name": "Supplier A", "is_product_supplier": True}
        )
        cls.supplier_b = cls.env["res.partner"].create(
            {"name": "Supplier B", "is_product_supplier": True}
        )

    def _wizard(self):
        return self.env["purchase.requirement.report.wizard"].create({})

    def test_quantity_to_purchase(self):
        self.product.write({"ml_stock_qty": 3, "ml_min_stock_qty": 8})
        self.assertEqual(self.product.purchase_requirement_qty, 5)
        self.product.ml_stock_qty = 10
        self.assertEqual(self.product.purchase_requirement_qty, 0)

    def test_products_are_grouped_by_supplier(self):
        self.product.write(
            {
                "ml_stock_qty": 3,
                "ml_min_stock_qty": 8,
                "preferred_supplier_id": self.supplier_a.id,
            }
        )
        second = self.env["product.template"].create(
            {
                "name": "Second Product",
                "default_code": "TST002",
                "standard_price": 20,
                "ml_stock_qty": 1,
                "ml_min_stock_qty": 4,
                "preferred_supplier_id": self.supplier_b.id,
            }
        )
        wizard = self._wizard()
        self.assertEqual(wizard.line_ids.mapped("product_id"), self.product | second)
        groups = dict(wizard._supplier_groups())
        self.assertEqual(groups[self.supplier_a].product_id, self.product)
        self.assertEqual(groups[self.supplier_b].product_id, second)
        action = wizard.action_print_report()
        self.assertTrue(action)
        report = self.env.ref("ml_sales_profit.action_purchase_requirement_report")
        self.assertEqual(report.model, wizard._name)
        html, _report_type = report._render_qweb_html(report.report_name, wizard.ids)
        self.assertIn(b"Supplier A", html)
        self.assertIn(b"Fake Shock Kit", html)
        self.assertIn(b"Supplier B", html)
        self.assertIn(b"Second Product", html)

    def test_product_without_supplier_is_reported(self):
        self.product.write({"ml_stock_qty": 1, "ml_min_stock_qty": 2})
        wizard = self._wizard()
        self.assertIn(self.product, wizard.missing_supplier_product_ids)
        self.assertNotIn(self.product, wizard.line_ids.product_id)
        with self.assertRaises(UserError):
            wizard.action_print_report()

    def test_product_at_minimum_is_ignored(self):
        self.product.write(
            {
                "ml_stock_qty": 2,
                "ml_min_stock_qty": 2,
                "preferred_supplier_id": self.supplier_a.id,
            }
        )
        wizard = self._wizard()
        self.assertNotIn(self.product, wizard.line_ids.product_id)
