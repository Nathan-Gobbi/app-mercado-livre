# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseRequirementReportWizard(models.TransientModel):
    _name = "purchase.requirement.report.wizard"
    _description = "Purchase Requirement Report"

    report_date = fields.Date(required=True, default=fields.Date.context_today)
    line_ids = fields.One2many(
        comodel_name="purchase.requirement.report.line",
        inverse_name="wizard_id",
        string="Products to Purchase",
    )
    missing_supplier_product_ids = fields.Many2many(
        comodel_name="product.template",
        relation="purchase_requirement_missing_supplier_rel",
        string="Products Without Supplier",
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        products = self.env["product.template"].search(
            [("active", "=", True), ("purchase_requirement_qty", ">", 0)],
            order="preferred_supplier_id, default_code, name",
        )
        supplied_products = products.filtered("preferred_supplier_id")
        values["line_ids"] = [
            fields.Command.create(
                {
                    "product_id": product.id,
                    "supplier_id": product.preferred_supplier_id.id,
                    "current_stock_qty": product.ml_stock_qty,
                    "minimum_stock_qty": product.ml_min_stock_qty,
                    "quantity": product.purchase_requirement_qty,
                    "unit_cost": product.standard_price,
                }
            )
            for product in supplied_products
        ]
        values["missing_supplier_product_ids"] = [
            fields.Command.set((products - supplied_products).ids)
        ]
        return values

    def action_print_report(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(
                _(
                    "There are no products below minimum stock with a preferred "
                    "supplier to include in the report."
                )
            )
        return self.env.ref(
            "ml_sales_profit.action_purchase_requirement_report"
        ).report_action(self)

    def _supplier_groups(self):
        self.ensure_one()
        grouped = defaultdict(lambda: self.env["purchase.requirement.report.line"])
        for line in self.line_ids.sorted(
            key=lambda item: (
                item.supplier_id.display_name,
                item.product_id.default_code or "",
                item.product_id.name,
            )
        ):
            grouped[line.supplier_id] |= line
        return grouped.items()


class PurchaseRequirementReportLine(models.TransientModel):
    _name = "purchase.requirement.report.line"
    _description = "Purchase Requirement Report Line"

    wizard_id = fields.Many2one(
        comodel_name="purchase.requirement.report.wizard",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        comodel_name="product.template", string="Product", required=True, readonly=True
    )
    supplier_id = fields.Many2one(
        comodel_name="res.partner", string="Supplier", required=True, readonly=True
    )
    current_stock_qty = fields.Float(
        string="Current Stock", digits=(16, 0), readonly=True
    )
    minimum_stock_qty = fields.Float(
        string="Minimum Stock", digits=(16, 0), readonly=True
    )
    quantity = fields.Float(
        string="Quantity to Purchase", digits=(16, 0), required=True, readonly=True
    )
    unit_cost = fields.Monetary(required=True, readonly=True)
    currency_id = fields.Many2one(related="product_id.cost_currency_id", readonly=True)
    subtotal = fields.Monetary(
        string="Estimated Total",
        compute="_compute_subtotal",
        currency_field="currency_id",
    )

    @api.depends("quantity", "unit_cost")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_cost
