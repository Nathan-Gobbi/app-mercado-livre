# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class MlStatementExcludedType(models.Model):
    _name = "ml.statement.excluded.type"
    _description = "Mercado Livre Statement Ignored Transaction Type"
    _order = "name"

    name = fields.Char(
        string="Transaction Type",
        required=True,
        help="Outflows with exactly this transaction type are left out of the "
        "statement import.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "This transaction type is already ignored.")
    ]
