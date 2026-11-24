# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PurchaseRequirementOrder(models.Model):
    _name = "purchase.requirement.order"
    _description = "Purchase Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
    )
    supplier_id = fields.Many2one(
        comodel_name="res.partner",
        domain="[('is_product_supplier', '=', True)]",
        tracking=True,
    )
    order_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    completion_date = fields.Date(readonly=True, copy=False)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("progress", "In Progress"),
            ("done", "Done"),
        ],
        required=True,
        default="draft",
        tracking=True,
        copy=False,
    )
    line_ids = fields.One2many(
        comodel_name="purchase.requirement.order.line",
        inverse_name="order_id",
        string="Products",
        copy=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    amount_total = fields.Monetary(
        string="Total",
        compute="_compute_amount_total",
        store=True,
        currency_field="currency_id",
    )

    @api.depends("line_ids.subtotal")
    def _compute_amount_total(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped("subtotal"))

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", _("New")) == _("New"):
                values["name"] = self.env["ir.sequence"].next_by_code(
                    "purchase.requirement.order"
                ) or _("New")
        return super().create(vals_list)

    def action_start(self):
        for order in self:
            if order.state != "draft":
                continue
            if not order.line_ids:
                raise UserError(
                    _("Add at least one product before starting the order.")
                )
            if any(line.quantity <= 0 for line in order.line_ids):
                raise UserError(_("Purchase quantities must be greater than zero."))
            order.state = "progress"
        return True

    def action_print(self):
        self.ensure_one()
        if self.state != "progress":
            raise UserError(_("Only orders in progress can be printed."))
        return self.env.ref(
            "ml_sales_profit.action_purchase_requirement_report"
        ).report_action(self)

    def action_done(self):
        for order in self:
            if order.state != "progress":
                raise UserError(_("Only orders in progress can be completed."))
            for line in order.line_ids:
                line.product_id.ml_stock_qty += line.quantity
            order.write(
                {
                    "state": "done",
                    "completion_date": fields.Date.context_today(order),
                }
            )
        return True

    def unlink(self):
        if any(order.state != "draft" for order in self):
            raise UserError(_("Only draft purchase orders can be deleted."))
        return super().unlink()


class PurchaseRequirementOrderLine(models.Model):
    _name = "purchase.requirement.order.line"
    _description = "Purchase Order Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    order_id = fields.Many2one(
        comodel_name="purchase.requirement.order",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(comodel_name="product.template", required=True)
    sku = fields.Char(related="product_id.default_code", string="SKU", readonly=True)
    current_stock_qty = fields.Float(
        string="Current Stock", digits=(16, 0), readonly=True
    )
    minimum_stock_qty = fields.Float(
        string="Minimum Stock", digits=(16, 0), readonly=True
    )
    quantity = fields.Float(digits=(16, 0), required=True, default=1.0)
    unit_cost = fields.Monetary(required=True, readonly=True)
    currency_id = fields.Many2one(related="order_id.currency_id", readonly=True)
    subtotal = fields.Monetary(
        compute="_compute_subtotal",
        store=True,
        currency_field="currency_id",
    )
    order_state = fields.Selection(related="order_id.state")

    @api.depends("quantity", "unit_cost")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_cost

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            order = self.env["purchase.requirement.order"].browse(
                values.get("order_id")
            )
            if order and order.state != "draft":
                raise UserError(_("Lines can only be added while the order is draft."))
            product = self.env["product.template"].browse(values.get("product_id"))
            if product:
                values.setdefault("current_stock_qty", product.ml_stock_qty)
                values.setdefault("minimum_stock_qty", product.ml_min_stock_qty)
                values.setdefault("quantity", product.purchase_requirement_qty or 1.0)
                values.setdefault("unit_cost", product.standard_price)
        return super().create(vals_list)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.current_stock_qty = line.product_id.ml_stock_qty
                line.minimum_stock_qty = line.product_id.ml_min_stock_qty
                line.quantity = line.product_id.purchase_requirement_qty or 1.0
                line.unit_cost = line.product_id.standard_price

    @api.constrains("quantity")
    def _check_quantity(self):
        if any(line.quantity <= 0 for line in self):
            raise ValidationError(_("Purchase quantity must be greater than zero."))

    @api.constrains("product_id", "order_id")
    def _check_unique_product(self):
        for line in self:
            duplicate = self.search_count(
                [
                    ("order_id", "=", line.order_id.id),
                    ("product_id", "=", line.product_id.id),
                    ("id", "!=", line.id),
                ]
            )
            if duplicate:
                raise ValidationError(_("A product can only appear once in an order."))

    def write(self, values):
        if any(line.order_id.state != "draft" for line in self):
            allowed = {"sequence"}
            if set(values) - allowed:
                raise UserError(
                    _("Lines can only be changed while the order is draft.")
                )
        return super().write(values)

    def unlink(self):
        if any(line.order_id.state != "draft" for line in self):
            raise UserError(_("Lines can only be removed while the order is draft."))
        return super().unlink()
