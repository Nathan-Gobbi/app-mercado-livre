# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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
        string="Listing SKU",
        index=True,
        help="SKU sent by Mercado Livre for this listing.",
    )
    units_per_sale = fields.Integer(
        string="Units per Sale",
        required=True,
        default=1,
        help="Physical product units consumed when one listing unit is sold.",
    )
    manufacturer_code = fields.Char(related="product_tmpl_id.ml_manufacturer_code")
    barcode = fields.Char(string="EAN", related="product_tmpl_id.barcode")
    ncm = fields.Char(string="NCM", related="product_tmpl_id.ml_ncm")
    standard_price = fields.Float(
        string="Unit Cost",
        related="product_tmpl_id.standard_price",
        digits="Product Price",
        help="Cost of one physical product unit.",
    )
    listing_cost = fields.Float(
        compute="_compute_listing_cost",
        digits="Product Price",
        help="Unit cost multiplied by the physical units in the listing.",
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
            "unique(default_code, listing_type, company_id)",
            "A listing SKU can only have one listing of each type.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if not values.get("default_code") and values.get("product_tmpl_id"):
                product = self.env["product.template"].browse(values["product_tmpl_id"])
                values["default_code"] = product.default_code
        return super().create(vals_list)

    @api.onchange("product_tmpl_id")
    def _onchange_product_tmpl_id(self):
        for listing in self.filtered(
            lambda record: record.product_tmpl_id and not record.default_code
        ):
            listing.default_code = listing.product_tmpl_id.default_code

    @api.constrains("units_per_sale")
    def _check_units_per_sale(self):
        if any(listing.units_per_sale <= 0 for listing in self):
            raise ValidationError(_("Units per sale must be greater than zero."))

    @api.constrains("default_code")
    def _check_default_code(self):
        if any(not listing.default_code for listing in self):
            raise ValidationError(_("The listing SKU is required."))

    @api.depends(
        "company_id",
        "units_per_sale",
        "product_tmpl_id.ml_is_kit",
        "product_tmpl_id.ml_component_ids.quantity",
        "product_tmpl_id.ml_component_ids.component_product_tmpl_id.product_variant_ids.standard_price",
        "product_tmpl_id.product_variant_ids.standard_price",
    )
    def _compute_listing_cost(self):
        for listing in self:
            product = listing.product_tmpl_id.with_company(listing.company_id)
            unit_cost = (
                sum(
                    component.quantity
                    * component.component_product_tmpl_id.with_company(
                        listing.company_id
                    ).standard_price
                    for component in product.ml_component_ids
                )
                if product.ml_is_kit
                else product.standard_price
            )
            listing.listing_cost = unit_cost * listing.units_per_sale

    @api.depends(
        "price",
        "net_amount",
        "packaging_cost",
        "units_per_sale",
        "company_id.ml_tax_rate",
        "product_tmpl_id.ml_is_kit",
        "product_tmpl_id.ml_component_ids.quantity",
        "product_tmpl_id.ml_component_ids.component_product_tmpl_id.product_variant_ids.standard_price",
        "product_tmpl_id.product_variant_ids.standard_price",
    )
    def _compute_profit(self):
        for listing in self:
            cost = listing.listing_cost
            listing.tax_amount = listing.price * listing.company_id.ml_tax_rate / 100
            listing.net_profit = listing.net_amount - (
                cost + listing.tax_amount + listing.packaging_cost
            )
            listing.profit_percent = (
                100 * listing.net_profit / listing.price if listing.price else 0.0
            )

    @api.depends("default_code", "product_tmpl_id", "listing_type")
    def _compute_display_name(self):
        type_names = dict(self._fields["listing_type"]._description_selection(self.env))
        for listing in self:
            listing_sku = (
                listing.default_code
                if listing.default_code != listing.product_tmpl_id.default_code
                else False
            )
            listing.display_name = " - ".join(
                filter(
                    None,
                    [
                        listing.product_tmpl_id.display_name,
                        listing_sku,
                        type_names.get(listing.listing_type),
                    ],
                )
            )
