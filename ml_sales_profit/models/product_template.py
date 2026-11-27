# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    _sql_constraints = [
        (
            "default_code_uniq",
            "unique(default_code)",
            "The SKU must be unique. Another product already uses this SKU.",
        )
    ]

    ml_manufacturer_code = fields.Char(string="Manufacturer Code")
    ml_ncm = fields.Char(string="NCM", help="Mercosur Common Nomenclature code.")
    ml_is_kit = fields.Boolean(
        string="Is a Kit",
        help="Kit sales consume the selected component products instead of "
        "the kit's own stock.",
    )
    ml_tax_rate = fields.Float(
        string="Tax Rate (%)",
        compute="_compute_ml_tax_rate",
        inverse="_inverse_ml_tax_rate",
        help="Percentage of the sale price deducted as tax from all listings "
        "of this company.",
    )
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
    preferred_supplier_id = fields.Many2one(
        comodel_name="res.partner",
        string="Preferred Supplier",
        domain="[('is_product_supplier', '=', True)]",
        help="Supplier that should receive the purchase requirement for this product.",
    )
    purchase_requirement_qty = fields.Float(
        string="Quantity to Purchase",
        digits=(16, 0),
        compute="_compute_purchase_requirement_qty",
        store=True,
        help="Quantity required to restore the minimum stock level.",
    )
    ml_listing_ids = fields.One2many(
        comodel_name="ml.listing",
        inverse_name="product_tmpl_id",
        string="Listings",
    )
    ml_component_ids = fields.One2many(
        comodel_name="ml.product.component",
        inverse_name="product_tmpl_id",
        string="Kit Components",
    )
    ml_parent_component_ids = fields.One2many(
        comodel_name="ml.product.component",
        inverse_name="component_product_tmpl_id",
        string="Used in Kits",
    )
    ml_kit_component_product_ids = fields.Many2many(
        comodel_name="product.template",
        string="Kit Products",
        compute="_compute_ml_kit_component_product_ids",
        inverse="_inverse_ml_kit_component_product_ids",
        help="Each selected product contributes one unit to the kit.",
    )
    ml_image_ids = fields.One2many(
        comodel_name="ml.product.image",
        inverse_name="product_tmpl_id",
        string="Gallery Images",
    )

    @api.depends_context("company")
    def _compute_ml_tax_rate(self):
        for product in self:
            product.ml_tax_rate = product.env.company.ml_tax_rate

    def _inverse_ml_tax_rate(self):
        for product in self:
            product.env.company.ml_tax_rate = product.ml_tax_rate

    @api.depends("ml_component_ids.component_product_tmpl_id")
    def _compute_ml_kit_component_product_ids(self):
        for product in self:
            product.ml_kit_component_product_ids = (
                product.ml_component_ids.component_product_tmpl_id
            )

    def _inverse_ml_kit_component_product_ids(self):
        Component = self.env["ml.product.component"]
        for product in self:
            selected = product.ml_kit_component_product_ids
            existing = product.ml_component_ids
            removed = existing.filtered(
                lambda line, selected=selected: (
                    line.component_product_tmpl_id not in selected
                )
            )
            removed.unlink()
            existing_products = (existing - removed).component_product_tmpl_id
            values = [
                {
                    "product_tmpl_id": product.id,
                    "component_product_tmpl_id": component.id,
                    "quantity": 1,
                }
                for component in selected - existing_products
            ]
            if values:
                Component.create(values)

    @api.onchange("ml_is_kit")
    def _onchange_ml_is_kit(self):
        for product in self.filtered(lambda record: not record.ml_is_kit):
            product.ml_kit_component_product_ids = False

    @api.constrains("ml_is_kit", "ml_component_ids")
    def _check_ml_kit_configuration(self):
        for product in self:
            if not product.ml_is_kit and product.ml_component_ids:
                raise ValidationError(
                    _("Remove the kit products before disabling 'Is a Kit'.")
                )
            if product.ml_is_kit and product.ml_parent_component_ids:
                raise ValidationError(_("A product used in a kit cannot become a kit."))

    @api.depends("ml_stock_qty", "ml_min_stock_qty")
    def _compute_ml_stock_difference(self):
        for product in self:
            product.ml_stock_difference = (
                product.ml_stock_qty - product.ml_min_stock_qty
            )

    @api.depends("ml_is_kit", "ml_stock_qty", "ml_min_stock_qty")
    def _compute_purchase_requirement_qty(self):
        for product in self:
            product.purchase_requirement_qty = (
                0.0
                if product.ml_is_kit
                else max(product.ml_min_stock_qty - product.ml_stock_qty, 0.0)
            )

    @api.depends("ml_stock_qty", "product_variant_ids.standard_price")
    def _compute_ml_stock_value(self):
        for product in self:
            product.ml_stock_value = product.ml_stock_qty * product.standard_price
