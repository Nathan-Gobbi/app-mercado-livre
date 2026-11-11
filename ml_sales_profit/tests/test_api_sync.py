# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from unittest.mock import patch

from .common import MlSalesProfitCase


class TestApiSync(MlSalesProfitCase):
    @staticmethod
    def _order(status="paid", quantity=1):
        return {
            "id": 200000000001,
            "status": status,
            "date_created": "2026-09-28T10:00:00.000-03:00",
            "cancel_detail": {"code": "buyer_cancelled"}
            if status == "cancelled"
            else None,
            "order_items": [
                {
                    "quantity": quantity,
                    "unit_price": 200.0,
                    "item": {
                        "id": "MLB123",
                        "title": "Fake Shock Kit",
                        "seller_sku": "TST001",
                        "listing_type_id": "gold_pro",
                    },
                }
            ],
        }

    @staticmethod
    def _page(order):
        return {
            "paging": {"total": 1, "offset": 0, "limit": 50},
            "results": [order],
        }

    def setUp(self):
        super().setUp()
        self.product.ml_stock_qty = 10
        self.company.write(
            {
                "ml_api_enabled": True,
                "ml_api_seller_id": "123456",
                "ml_api_initial_sync_days": 30,
            }
        )

    def _sync(self, order):
        with patch.object(
            type(self.company),
            "_ml_api_request",
            autospec=True,
            return_value=self._page(order),
        ):
            self.company.action_ml_sync_orders()

    def test_paid_order_is_idempotent_and_updates_quantity(self):
        self._sync(self._order(quantity=1))
        line = self.env["ml.sale.line"].search(
            [("api_order_item_key", "=", "200000000001:MLB123:")]
        )
        self.assertEqual(len(line), 1)
        self.assertEqual(line.source, "api")
        self.assertEqual(line.listing_id, self.premium)
        self.assertEqual(line.units, 1)
        self.assertEqual(line.revenue, 200)
        self.assertEqual(self.product.ml_stock_qty, 9)

        self._sync(self._order(quantity=1))
        self.assertEqual(len(line), 1)
        self.assertEqual(self.product.ml_stock_qty, 9)

        self._sync(self._order(quantity=3))
        self.assertEqual(line.units, 3)
        self.assertEqual(self.product.ml_stock_qty, 7)

    def test_cancelled_order_restores_stock(self):
        self._sync(self._order(quantity=2))
        self.assertEqual(self.product.ml_stock_qty, 8)

        self._sync(self._order(status="cancelled", quantity=2))
        self.assertFalse(
            self.env["ml.sale.line"].search(
                [("sale_number", "=", "200000000001"), ("source", "=", "api")]
            )
        )
        self.assertEqual(self.product.ml_stock_qty, 10)

    def test_unknown_sku_does_not_change_stock(self):
        order = self._order()
        order["order_items"][0]["item"]["seller_sku"] = "UNKNOWN"
        self._sync(order)
        line = self.env["ml.sale.line"].search([("sku", "=", "UNKNOWN")])
        self.assertEqual(line.profit_status, "not_found")
        self.assertFalse(line.stock_deducted)
        self.assertEqual(self.product.ml_stock_qty, 10)

    def test_missing_order_item_fields_are_loaded_from_item_api(self):
        order = self._order()
        order["order_items"][0]["item"] = {
            "id": "MLB123",
            "title": "Fake Shock Kit",
        }
        item = {
            "id": "MLB123",
            "seller_custom_field": "TST001",
            "listing_type_id": "gold_pro",
        }
        with patch.object(
            type(self.company),
            "_ml_api_request",
            autospec=True,
            side_effect=[self._page(order), item],
        ) as request_mock:
            self.company.action_ml_sync_orders()
        self.assertEqual(request_mock.call_count, 2)
        line = self.env["ml.sale.line"].search(
            [("api_order_item_key", "=", "200000000001:MLB123:")]
        )
        self.assertEqual(line.listing_id, self.premium)
        self.assertEqual(self.product.ml_stock_qty, 9)

    def test_authorization_url_has_state(self):
        self.company.write(
            {
                "ml_api_client_id": "123",
                "ml_api_client_secret": "secret",
                "ml_api_redirect_uri": "http://localhost:18069/ml/oauth/callback",
            }
        )
        url = self.company._ml_authorization_url()
        self.assertIn("client_id=123", url)
        self.assertIn("state=", url)
        self.assertTrue(self.company.ml_api_oauth_state)
