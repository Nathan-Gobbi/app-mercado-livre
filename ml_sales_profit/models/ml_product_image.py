# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class MlProductImage(models.Model):
    _name = "ml.product.image"
    _description = "Product Gallery Image"
    _order = "sequence, id"

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    image = fields.Image(
        required=True,
        max_width=1920,
        max_height=1920,
    )
