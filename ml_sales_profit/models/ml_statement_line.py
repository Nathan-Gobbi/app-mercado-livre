# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class MlStatementLine(models.Model):
    _name = "ml.statement.line"
    _inherit = ["ml.import.line.mixin"]
    _description = "Mercado Livre Statement Outflow"
    _order = "date, transaction_type, amount, id"
    _rec_name = "transaction_type"

    import_ids = fields.Many2many(
        comodel_name="ml.statement.import",
        relation="ml_statement_import_line_rel",
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
    date = fields.Date(readonly=True, index=True)
    transaction_type = fields.Char(readonly=True)
    reference_id = fields.Char(string="Reference", readonly=True, index=True)
    amount = fields.Monetary(readonly=True)
    outflow_amount = fields.Monetary(
        string="Outflow",
        compute="_compute_outflow_amount",
        store=True,
        help="Amount as a positive value, handy for charts.",
    )
    note = fields.Char()

    @api.depends("amount")
    def _compute_outflow_amount(self):
        for line in self:
            line.outflow_amount = -line.amount
