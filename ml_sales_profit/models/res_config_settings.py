# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ml_tax_rate = fields.Float(related="company_id.ml_tax_rate", readonly=False)
    ml_api_enabled = fields.Boolean(related="company_id.ml_api_enabled", readonly=False)
    ml_api_client_id = fields.Char(
        related="company_id.ml_api_client_id", readonly=False
    )
    ml_api_client_secret = fields.Char(
        related="company_id.ml_api_client_secret", readonly=False
    )
    ml_api_redirect_uri = fields.Char(
        related="company_id.ml_api_redirect_uri", readonly=False
    )
    ml_api_seller_id = fields.Char(related="company_id.ml_api_seller_id")
    ml_api_nickname = fields.Char(related="company_id.ml_api_nickname")
    ml_api_last_sync_at = fields.Datetime(related="company_id.ml_api_last_sync_at")
    ml_api_initial_sync_days = fields.Integer(
        related="company_id.ml_api_initial_sync_days", readonly=False
    )

    def action_ml_authorize(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.company_id._ml_authorization_url(),
            "target": "self",
        }

    def action_ml_sync_orders(self):
        self.ensure_one()
        self.company_id.action_ml_sync_orders()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Mercado Livre"),
                "message": self.env._("Orders synchronized successfully."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }
