# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models

from ..tools.spreadsheet import fold

LISTING_TYPES = [
    ("premium", "Premium"),
    ("classic", "Classic"),
]

# How Mercado Livre writes each listing type in its spreadsheets
LISTING_TYPE_BY_TEXT = {
    "premium": "premium",
    "classico": "classic",
}


def listing_type_from_text(text):
    """Return the listing type key for a text such as ``"Clássico"``."""
    return LISTING_TYPE_BY_TEXT.get(fold(text), False)


class MlListing(models.Model):
    _name = "ml.listing"
    _description = "Mercado Livre Listing"
    _order = "default_code, product_tmpl_id, listing_type desc"
    _rec_names_search = ["default_code", "product_tmpl_id"]

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product",
        required=True,
        ondelete="cascade",
        index=True,
    )
    default_code = fields.Char(
        string="SKU", related="product_tmpl_id.default_code", store=True
    )
    manufacturer_code = fields.Char(related="product_tmpl_id.ml_manufacturer_code")
    barcode = fields.Char(string="EAN", related="product_tmpl_id.barcode")
    ncm = fields.Char(string="NCM", related="product_tmpl_id.ml_ncm")
    standard_price = fields.Float(
        string="Cost",
        related="product_tmpl_id.standard_price",
        digits="Product Price",
        help="Cost of the product.",
    )
    listing_type = fields.Selection(
        selection=LISTING_TYPES, string="Type", required=True, default="premium"
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    price = fields.Monetary(string="Sale Price")
    net_amount = fields.Monetary(
        help="Amount you receive from Mercado Livre after fees and shipping.",
    )
    tax_amount = fields.Monetary(
        string="Tax",
        compute="_compute_profit",
        store=True,
        help="Sale price multiplied by the tax rate set in the settings.",
    )
    packaging_cost = fields.Monetary(string="Packaging")
    net_profit = fields.Monetary(
        compute="_compute_profit",
        store=True,
        help="Net amount minus cost, tax and packaging.",
    )
    profit_percent = fields.Float(
        string="Profit %",
        compute="_compute_profit",
        store=True,
        digits=(16, 2),
        aggregator="avg",
        help="Net profit over the sale price.",
    )

    _sql_constraints = [
        (
            "product_type_uniq",
            "unique(product_tmpl_id, listing_type, company_id)",
            "A product can only have one listing of each type.",
        )
    ]

    @api.depends(
        "price",
        "net_amount",
        "packaging_cost",
        "company_id.ml_tax_rate",
        "product_tmpl_id.product_variant_ids.standard_price",
    )
    def _compute_profit(self):
        for listing in self:
            cost = listing.product_tmpl_id.with_company(
                listing.company_id
            ).standard_price
            listing.tax_amount = listing.price * listing.company_id.ml_tax_rate / 100
            listing.net_profit = listing.net_amount - (
                cost + listing.tax_amount + listing.packaging_cost
            )
            listing.profit_percent = (
                100 * listing.net_profit / listing.price if listing.price else 0.0
            )

    @api.depends("product_tmpl_id", "listing_type")
    def _compute_display_name(self):
        type_names = dict(self._fields["listing_type"]._description_selection(self.env))
        for listing in self:
            listing.display_name = " - ".join(
                filter(
                    None,
                    [
                        listing.product_tmpl_id.display_name,
                        type_names.get(listing.listing_type),
                    ],
                )
            )
