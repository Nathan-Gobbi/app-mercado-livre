# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    ml_manufacturer_code = fields.Char(string="Manufacturer Code")
    ml_ncm = fields.Char(string="NCM", help="Mercosur Common Nomenclature code.")
    ml_stock_qty = fields.Float(string="Stock", digits=(16, 0))
    ml_min_stock_qty = fields.Float(
        string="Minimum Stock",
        digits=(16, 0),
        help="Quantity you want to keep in stock. It is used to compute the "
        "stock difference.",
    )
    ml_stock_difference = fields.Float(
        string="Stock Difference",
        digits=(16, 0),
        compute="_compute_ml_stock_difference",
        store=True,
        help="Stock minus minimum stock. Negative values mean you should buy more.",
    )
    ml_stock_value = fields.Monetary(
        string="Stock Value",
        compute="_compute_ml_stock_value",
        store=True,
        currency_field="currency_id",
    )
    ml_listing_ids = fields.One2many(
        comodel_name="ml.listing",
        inverse_name="product_tmpl_id",
        string="Listings",
    )

    @api.depends("ml_stock_qty", "ml_min_stock_qty")
    def _compute_ml_stock_difference(self):
        for product in self:
            product.ml_stock_difference = (
                product.ml_stock_qty - product.ml_min_stock_qty
            )

    @api.depends("ml_stock_qty", "product_variant_ids.standard_price")
    def _compute_ml_stock_value(self):
        for product in self:
            product.ml_stock_value = product.ml_stock_qty * product.standard_price
