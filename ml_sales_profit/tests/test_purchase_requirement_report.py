# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.exceptions import UserError, ValidationError

from .common import MlSalesProfitCase


class TestPurchaseRequirementOrder(MlSalesProfitCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Supplier A", "is_product_supplier": True}
        )
        cls.product.write(
            {
                "ml_stock_qty": 3,
                "ml_min_stock_qty": 8,
                "preferred_supplier_id": cls.supplier.id,
                "standard_price": 12,
            }
        )

    def _create_order(self, supplier=None):
        wizard = self.env["purchase.requirement.order.create.wizard"].create(
            {"supplier_id": supplier.id if supplier else False}
        )
        action = wizard.action_create_order()
        return self.env["purchase.requirement.order"].browse(action["res_id"])

    def test_quantity_to_purchase(self):
        self.assertEqual(self.product.purchase_requirement_qty, 5)
        self.product.ml_stock_qty = 10
        self.assertEqual(self.product.purchase_requirement_qty, 0)

    def test_supplier_order_loads_only_required_products(self):
        ignored = self.env["product.template"].create(
            {
                "name": "Enough Stock",
                "ml_stock_qty": 5,
                "ml_min_stock_qty": 5,
                "preferred_supplier_id": self.supplier.id,
            }
        )
        order = self._create_order(self.supplier)
        self.assertEqual(order.supplier_id, self.supplier)
        self.assertEqual(order.line_ids.product_id, self.product)
        self.assertNotIn(ignored, order.line_ids.product_id)
        self.assertEqual(order.line_ids.quantity, 5)
        self.assertEqual(order.amount_total, 60)

    def test_order_without_supplier_starts_empty_and_is_editable(self):
        order = self._create_order()
        self.assertFalse(order.supplier_id)
        self.assertFalse(order.line_ids)
        unassigned_product = self.env["product.template"].create(
            {"name": "Unassigned Product", "standard_price": 12}
        )
        line = self.env["purchase.requirement.order.line"].create(
            {
                "order_id": order.id,
                "product_id": unassigned_product.id,
                "quantity": 2,
            }
        )
        self.assertEqual(line.current_stock_qty, 0)
        self.assertEqual(line.unit_cost, 12)
        line.quantity = 3
        self.assertEqual(order.amount_total, 36)
        line.unlink()
        self.assertFalse(order.line_ids)

    def test_product_must_match_order_supplier_or_be_unassigned(self):
        other_supplier = self.env["res.partner"].create(
            {"name": "Supplier B", "is_product_supplier": True}
        )
        other_product = self.env["product.template"].create(
            {
                "name": "Other Supplier Product",
                "preferred_supplier_id": other_supplier.id,
            }
        )
        unassigned_product = self.env["product.template"].create(
            {"name": "Unassigned Product"}
        )
        order = self._create_order(self.supplier)
        self.env["purchase.requirement.order.line"].create(
            {"order_id": order.id, "product_id": unassigned_product.id}
        )
        with self.assertRaises(ValidationError):
            self.env["purchase.requirement.order.line"].create(
                {"order_id": order.id, "product_id": other_product.id}
            )

    def test_progress_pdf_and_completion_update_stock_once(self):
        order = self._create_order(self.supplier)
        order.line_ids.quantity = 2
        order.action_start()
        self.assertEqual(order.state, "progress")
        action = order.action_print()
        self.assertTrue(action)
        report = self.env.ref("ml_sales_profit.action_purchase_requirement_report")
        html, _report_type = report._render_qweb_html(report.report_name, order.ids)
        self.assertIn(b"Supplier A", html)
        self.assertIn(b"Fake Shock Kit", html)
        with self.assertRaises(UserError):
            order.line_ids.quantity = 3
        with self.assertRaises(UserError):
            order.line_ids.unlink()
        order.action_done()
        self.assertEqual(order.state, "done")
        self.assertEqual(self.product.ml_stock_qty, 5)
        with self.assertRaises(UserError):
            order.action_done()
        self.assertEqual(self.product.ml_stock_qty, 5)

    def test_empty_order_cannot_start(self):
        order = self._create_order()
        with self.assertRaises(UserError):
            order.action_start()
