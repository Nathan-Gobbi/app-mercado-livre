# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from werkzeug.utils import redirect

from odoo import fields, http
from odoo.http import request


class MercadoLivreOAuthController(http.Controller):
    @http.route("/ml/oauth/callback", type="http", auth="user", csrf=False)
    def oauth_callback(self, code=None, state=None, error=None, **_kwargs):
        if error or not code or not state:
            return request.not_found()
        company = request.env.company
        if (
            not request.env.user.has_group("ml_sales_profit.group_ml_manager")
            or state != company.ml_api_oauth_state
            or not company.ml_api_oauth_state_expires_at
            or company.ml_api_oauth_state_expires_at < fields.Datetime.now()
        ):
            return request.not_found()
        company._ml_exchange_authorization_code(code)
        return redirect("/odoo/settings?app=ml_sales_profit")
