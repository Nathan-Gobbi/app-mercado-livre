# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from dateutil.parser import isoparse

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools.spreadsheet import clean_sku

_logger = logging.getLogger(__name__)

API_URL = "https://api.mercadolibre.com"
AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
PAID_ORDER_STATUSES = {"paid", "partially_refunded"}
PREMIUM_LISTING_TYPES = {"gold_pro", "gold_premium"}


class ResCompany(models.Model):
    _inherit = "res.company"

    ml_tax_rate = fields.Float(
        string="Mercado Livre Tax Rate (%)",
        default=6.0,
        help="Percentage of the listing sale price paid as tax.",
    )
    ml_api_enabled = fields.Boolean(string="Enable Mercado Livre API")
    ml_api_client_id = fields.Char(string="Application ID", groups="base.group_system")
    ml_api_client_secret = fields.Char(string="Secret Key", groups="base.group_system")
    ml_api_redirect_uri = fields.Char(string="Redirect URI", groups="base.group_system")
    ml_api_access_token = fields.Char(groups="base.group_system", copy=False)
    ml_api_refresh_token = fields.Char(groups="base.group_system", copy=False)
    ml_api_token_expires_at = fields.Datetime(groups="base.group_system", copy=False)
    ml_api_seller_id = fields.Char(string="Seller ID", readonly=True, copy=False)
    ml_api_nickname = fields.Char(string="Seller", readonly=True, copy=False)
    ml_api_last_sync_at = fields.Datetime(readonly=True, copy=False)
    ml_api_initial_sync_days = fields.Integer(string="Initial Sync (Days)", default=30)
    ml_api_oauth_state = fields.Char(groups="base.group_system", copy=False)
    ml_api_oauth_state_expires_at = fields.Datetime(
        groups="base.group_system", copy=False
    )

    def _ml_require_credentials(self):
        self.ensure_one()
        if not all(
            (self.ml_api_client_id, self.ml_api_client_secret, self.ml_api_redirect_uri)
        ):
            raise UserError(
                _("Set the Mercado Livre Application ID, Secret Key and Redirect URI.")
            )

    def _ml_authorization_url(self):
        self.ensure_one()
        self._ml_require_credentials()
        state = secrets.token_urlsafe(32)
        self.write(
            {
                "ml_api_oauth_state": state,
                "ml_api_oauth_state_expires_at": fields.Datetime.now()
                + timedelta(minutes=15),
            }
        )
        parameters = {
            "response_type": "code",
            "client_id": self.ml_api_client_id,
            "redirect_uri": self.ml_api_redirect_uri,
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(parameters)}"

    def _ml_token_request(self, values):
        self.ensure_one()
        self._ml_require_credentials()
        payload = {
            "client_id": self.ml_api_client_id,
            "client_secret": self.ml_api_client_secret,
            **values,
        }
        try:
            response = requests.post(
                f"{API_URL}/oauth/token",
                data=payload,
                headers={"Accept": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as error:
            _logger.warning(
                "Mercado Livre OAuth request failed for company %s", self.id
            )
            raise UserError(
                _("Mercado Livre authorization failed. Try again.")
            ) from error
        if not data.get("access_token") or not data.get("refresh_token"):
            raise UserError(_("Mercado Livre did not return the required tokens."))
        self.write(
            {
                "ml_api_access_token": data["access_token"],
                "ml_api_refresh_token": data["refresh_token"],
                "ml_api_token_expires_at": fields.Datetime.now()
                + timedelta(seconds=int(data.get("expires_in", 21600))),
                "ml_api_oauth_state": False,
                "ml_api_oauth_state_expires_at": False,
            }
        )
        return data

    def _ml_exchange_authorization_code(self, code):
        self.ensure_one()
        self._ml_token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.ml_api_redirect_uri,
            }
        )
        user = self._ml_api_request("GET", "/users/me", refresh=False)
        self.write(
            {
                "ml_api_seller_id": str(user["id"]),
                "ml_api_nickname": user.get("nickname"),
                "ml_api_enabled": True,
            }
        )

    def _ml_refresh_access_token(self):
        self.ensure_one()
        if not self.ml_api_refresh_token:
            raise UserError(_("Connect the Mercado Livre account first."))
        self._ml_token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.ml_api_refresh_token,
            }
        )

    def _ml_api_request(self, method, path, params=None, refresh=True):
        self.ensure_one()
        expires_at = self.ml_api_token_expires_at
        if refresh and (
            not self.ml_api_access_token
            or not expires_at
            or expires_at <= fields.Datetime.now() + timedelta(minutes=5)
        ):
            self._ml_refresh_access_token()
        try:
            response = requests.request(
                method,
                f"{API_URL}{path}",
                params=params,
                headers={
                    "Authorization": f"Bearer {self.ml_api_access_token}",
                    "Accept": "application/json",
                },
                timeout=30,
            )
            if response.status_code == 401 and refresh:
                self._ml_refresh_access_token()
                return self._ml_api_request(method, path, params=params, refresh=False)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            _logger.warning(
                "Mercado Livre API request failed for company %s on %s", self.id, path
            )
            raise UserError(
                _("Mercado Livre API request failed for %(path)s.", path=path)
            ) from error

    @staticmethod
    def _ml_item_sku(item):
        sku = item.get("seller_sku") or item.get("seller_custom_field")
        if sku:
            return clean_sku(sku)
        attributes = (item.get("variation_attributes") or []) + (
            item.get("attributes") or []
        )
        attribute = next(
            (value for value in attributes if value.get("id") == "SELLER_SKU"), None
        )
        value = attribute and (attribute.get("value_name") or attribute.get("value_id"))
        return clean_sku(value) if value else False

    def _ml_complete_item(self, item, item_cache):
        """Fill fields sometimes omitted from an order item."""
        item_id = item.get("id")
        if not item_id or (self._ml_item_sku(item) and item.get("listing_type_id")):
            return item
        if item_id not in item_cache:
            item_cache[item_id] = self._ml_api_request("GET", f"/items/{item_id}")
        return {**item_cache[item_id], **item}

    def _ml_listing_for_item(self, item, listings_by_sku):
        sku = self._ml_item_sku(item)
        listings = listings_by_sku.get(sku, self.env["ml.listing"])
        listing_type_id = item.get("listing_type_id")
        if listing_type_id:
            listing_type = (
                "premium" if listing_type_id in PREMIUM_LISTING_TYPES else "classic"
            )
            return sku, listings.filtered(
                lambda listing: listing.listing_type == listing_type
            )[:1]
        return sku, listings if len(listings) == 1 else self.env["ml.listing"]

    def _ml_api_import(self):
        self.ensure_one()
        sale_import = self.env["ml.sale.import"].search(
            [("company_id", "=", self.id), ("source", "=", "api")], limit=1
        )
        if not sale_import:
            sale_import = self.env["ml.sale.import"].create(
                {"company_id": self.id, "source": "api", "state": "done"}
            )
        return sale_import

    def _ml_sync_order(self, order, sale_import, listings_by_sku, item_cache):
        Line = self.env["ml.sale.line"]
        order_id = str(order["id"])
        cancelled = order.get("status") == "cancelled" or order.get("cancel_detail")
        if cancelled:
            Line.search(
                [
                    ("company_id", "=", self.id),
                    ("sale_number", "=", order_id),
                    ("source", "=", "api"),
                ]
            ).unlink()
            return
        if order.get("status") not in PAID_ORDER_STATUSES:
            return
        sale_date = fields.Date.to_date(isoparse(order["date_created"]))
        for order_item in order.get("order_items", []):
            item = self._ml_complete_item(order_item.get("item") or {}, item_cache)
            sku, listing = self._ml_listing_for_item(item, listings_by_sku)
            if not sku:
                continue
            item_id = str(item.get("id") or sku)
            variation_id = str(item.get("variation_id") or "")
            api_key = ":".join((order_id, item_id, variation_id))
            units = float(order_item.get("quantity") or 0)
            if units <= 0:
                continue
            revenue = units * float(order_item.get("unit_price") or 0)
            unit_net_profit = listing.net_profit if listing else 0.0
            unit_tax = listing.tax_amount if listing else 0.0
            values = {
                "source": "api",
                "api_order_item_key": api_key,
                "sale_number": order_id,
                "sale_date": sale_date,
                "ml_status": order.get("status"),
                "sku": sku,
                "title": item.get("title"),
                "variation": item.get("variation_name"),
                "listing_type": listing.listing_type if listing else False,
                "listing_id": listing.id if listing else False,
                "product_tmpl_id": listing.product_tmpl_id.id if listing else False,
                "units": units,
                "revenue_ml": revenue,
                "revenue": revenue,
                "revenue_origin": "direct",
                "unit_tax": unit_tax,
                "unit_net_profit": unit_net_profit,
                "unit_gross_profit": unit_net_profit + unit_tax,
                "profit_status": "ok" if listing else "not_found",
                "company_id": self.id,
            }
            line = Line.search(
                [
                    ("company_id", "=", self.id),
                    ("api_order_item_key", "=", api_key),
                ],
                limit=1,
            )
            if line:
                line.write(values)
            else:
                line = Line.create(values)
            sale_import.line_ids = [fields.Command.link(line.id)]

    def action_ml_sync_orders(self):
        for company in self:
            if not company.ml_api_seller_id:
                raise UserError(_("Connect the Mercado Livre account first."))
            started_at = fields.Datetime.now()
            date_from = company.ml_api_last_sync_at
            if date_from:
                date_from -= timedelta(minutes=5)
            else:
                date_from = started_at - timedelta(
                    days=max(company.ml_api_initial_sync_days, 1)
                )
            listings = self.env["ml.listing"].search([("company_id", "=", company.id)])
            listings_by_sku = {}
            for listing in listings:
                sku = clean_sku(listing.default_code)
                listings_by_sku.setdefault(sku, self.env["ml.listing"])
                listings_by_sku[sku] |= listing
            sale_import = company._ml_api_import()
            item_cache = {}
            offset, limit, total = 0, 50, 1
            while offset < total:
                data = company._ml_api_request(
                    "GET",
                    "/orders/search",
                    params={
                        "seller": company.ml_api_seller_id,
                        "order.date_last_updated.from": (
                            date_from.isoformat(timespec="milliseconds") + "Z"
                        ),
                        "sort": "date_asc",
                        "offset": offset,
                        "limit": limit,
                    },
                )
                paging = data.get("paging") or {}
                total = int(paging.get("total", 0))
                page_limit = int(paging.get("limit", limit)) or limit
                for order in data.get("results", []):
                    company._ml_sync_order(
                        order, sale_import, listings_by_sku, item_cache
                    )
                offset += page_limit
            dates = sale_import.line_ids.mapped("sale_date")
            sale_import.write(
                {
                    "date_from": min(dates) if dates else False,
                    "date_to": max(dates) if dates else False,
                }
            )
            company.ml_api_last_sync_at = started_at
        return True

    @api.model
    def _cron_ml_sync_orders(self):
        companies = self.search(
            [("ml_api_enabled", "=", True), ("ml_api_seller_id", "!=", False)]
        )
        for company in companies:
            try:
                with self.env.cr.savepoint():
                    company.action_ml_sync_orders()
            except Exception:
                _logger.exception(
                    "Mercado Livre order synchronization failed for company %s",
                    company.id,
                )
