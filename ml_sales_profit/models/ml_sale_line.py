# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models

from .ml_listing import LISTING_TYPES


class MlSaleLine(models.Model):
    """A sale of the Mercado Livre report, crossed with its listing.

    Unit values are copied from the listing when the spreadsheet is processed,
    so later price or cost changes do not rewrite the past.
    """

    _name = "ml.sale.line"
    _inherit = ["ml.import.line.mixin"]
    _description = "Mercado Livre Sale"
    _order = "sale_date desc, id desc"
    _rec_name = "sale_number"

    import_ids = fields.Many2many(
        comodel_name="ml.sale.import",
        relation="ml_sale_import_line_rel",
        column1="line_id",
        column2="import_id",
        string="Imports",
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    sale_number = fields.Char(readonly=True, index=True)
    sale_date = fields.Date(readonly=True, index=True)
    ml_status = fields.Char(string="Mercado Livre Status", readonly=True)
    sku = fields.Char(string="SKU", readonly=True, index=True)
    title = fields.Char(string="Listing Title", readonly=True)
    variation = fields.Char(readonly=True)
    listing_type = fields.Selection(selection=LISTING_TYPES, readonly=True)
    listing_id = fields.Many2one(
        comodel_name="ml.listing", string="Listing", readonly=True, ondelete="set null"
    )
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product",
        readonly=True,
        ondelete="set null",
    )
    units = fields.Float(readonly=True, digits=(16, 0))
    revenue_ml = fields.Monetary(
        string="Mercado Livre Revenue",
        readonly=True,
        help="'Receita por produtos' column of the Mercado Livre report.",
    )
    revenue = fields.Monetary(readonly=True)
    revenue_origin = fields.Selection(
        selection=[
            ("direct", "Direct"),
            ("rebuilt", "Rebuilt"),
            ("not_found", "Price Not Found"),
        ],
        readonly=True,
        help="Direct: revenue read from the report. Rebuilt: units multiplied by "
        "the listing price, because the report had no revenue.",
    )
    unit_tax = fields.Monetary(readonly=True)
    unit_net_profit = fields.Monetary(readonly=True)
    unit_gross_profit = fields.Monetary(
        readonly=True, help="Unit net profit plus unit tax."
    )
    gross_profit = fields.Monetary(compute="_compute_profit", store=True)
    net_profit = fields.Monetary(compute="_compute_profit", store=True)
    gross_margin = fields.Float(
        string="Gross Margin (%)",
        compute="_compute_profit",
        store=True,
        digits=(16, 2),
        aggregator=None,
    )
    net_margin = fields.Float(
        string="Net Margin (%)",
        compute="_compute_profit",
        store=True,
        digits=(16, 2),
        aggregator=None,
    )
    profit_status = fields.Selection(
        selection=[("ok", "OK"), ("not_found", "Listing Not Found")],
        readonly=True,
    )

    @api.depends("units", "revenue", "unit_net_profit", "unit_gross_profit")
    def _compute_profit(self):
        for line in self:
            line.net_profit = line.units * line.unit_net_profit
            line.gross_profit = line.units * line.unit_gross_profit
            line.net_margin = (
                100 * line.net_profit / line.revenue if line.revenue else 0.0
            )
            line.gross_margin = (
                100 * line.gross_profit / line.revenue if line.revenue else 0.0
            )
