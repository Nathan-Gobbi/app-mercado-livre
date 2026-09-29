# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    ml_tax_rate = fields.Float(
        string="Mercado Livre Tax Rate (%)",
        default=6.0,
        help="Percentage of the listing sale price paid as tax.",
    )
