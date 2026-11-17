# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_product_supplier = fields.Boolean(
        string="Product Supplier",
        help="Enable this option to make the contact available as a product supplier.",
    )
