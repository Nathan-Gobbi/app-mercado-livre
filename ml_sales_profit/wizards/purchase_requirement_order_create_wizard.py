# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, fields, models


class PurchaseRequirementOrderCreateWizard(models.TransientModel):
    _name = "purchase.requirement.order.create.wizard"
    _description = "Create Purchase Order"

    supplier_id = fields.Many2one(
        comodel_name="res.partner",
        domain="[('is_product_supplier', '=', True)]",
        help="Leave empty to start an order without a supplier.",
    )

    def action_create_order(self):
        self.ensure_one()
        order = self.env["purchase.requirement.order"].create(
            {"supplier_id": self.supplier_id.id}
        )
        if self.supplier_id:
            products = self.env["product.template"].search(
                [
                    ("active", "=", True),
                    ("preferred_supplier_id", "=", self.supplier_id.id),
                    ("purchase_requirement_qty", ">", 0),
                ],
                order="default_code, name",
            )
            order.line_ids = [
                fields.Command.create(
                    {
                        "product_id": product.id,
                        "current_stock_qty": product.ml_stock_qty,
                        "minimum_stock_qty": product.ml_min_stock_qty,
                        "quantity": product.purchase_requirement_qty,
                        "unit_cost": product.standard_price,
                    }
                )
                for product in products
            ]
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Order"),
            "res_model": "purchase.requirement.order",
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
        }
