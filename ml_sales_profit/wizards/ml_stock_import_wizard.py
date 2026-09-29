# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.ml_listing import listing_type_from_text
from ..tools.spreadsheet import (
    cell,
    clean_code,
    clean_sku,
    clean_text,
    column_index,
    find_header,
    parse_float,
    read_rows,
    referenced_rows,
)

_logger = logging.getLogger(__name__)

try:
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover
    _logger.debug("Cannot import openpyxl")

STOCK_COLUMNS = {
    "sku": ["SKU"],
    "name": ["Produto"],
    "manufacturer_code": ["Código"],
    "barcode": ["EAN"],
    "ncm": ["NCM"],
    "cost": ["Custo"],
    "listing_type": ["Tipo"],
    "price": ["Venda"],
    "net_amount": ["V. Liquido", "V. Líquido", "Valor Liquido"],
    "packaging_cost": ["Embalagem"],
    "stock": ["Estoque"],
    "stock_difference": ["Diferença Estoque"],
    "net_profit": ["Lucro Liquido", "Lucro Líquido"],
    "stock_value": ["Valor"],
}


class MlStockImportWizard(models.TransientModel):
    """Load products and listings from the stock spreadsheet.

    The spreadsheet has one row per listing: the first row of a product
    holds its data (name, EAN, cost, stock...) and the following rows, with
    the same SKU, hold its other listing types.
    """

    _name = "ml.stock.import.wizard"
    _description = "Import Mercado Livre Stock Spreadsheet"

    file = fields.Binary(string="Spreadsheet", required=True)
    file_name = fields.Char()

    def _read_rows(self):
        """Return the values and the formulas of the sheet."""
        content = base64.b64decode(self.file or b"")
        try:
            return (
                read_rows(content, sheet_name="Estoque"),
                read_rows(content, sheet_name="Estoque", formulas=True),
            )
        except Exception as error:
            raise UserError(
                _("Could not read the spreadsheet. Is it a .xlsx file?\n%s", error)
            ) from error

    def _cost(self, index, rows, formulas, columns):
        """Cost of the row, or of the row its formulas take the cost from.

        Color variants often leave the cost empty and their formulas use the
        cost of another row, like ``=I139-($F$138+J139+K139)``.
        """
        cost = parse_float(cell(rows[index], columns["cost"]))
        if cost is not None or columns["cost"] is None:
            return cost
        letter = get_column_letter(columns["cost"] + 1)
        for key in ("net_profit", "stock_value"):
            formula = cell(formulas[index], columns[key])
            for row_number in referenced_rows(formula, letter):
                if row_number - 1 != index and row_number - 1 < len(rows):
                    cost = parse_float(cell(rows[row_number - 1], columns["cost"]))
                    if cost is not None:
                        return cost
        return None

    def _product_values(self, row, columns, cost):
        values = {
            "name": clean_text(cell(row, columns["name"])),
            "ml_manufacturer_code": clean_code(cell(row, columns["manufacturer_code"]))
            or False,
            "ml_ncm": clean_code(cell(row, columns["ncm"])) or False,
        }
        if cost is not None:
            values["standard_price"] = cost
        stock = parse_float(cell(row, columns["stock"]))
        if stock is not None:
            values["ml_stock_qty"] = stock
            difference = parse_float(cell(row, columns["stock_difference"]))
            values["ml_min_stock_qty"] = (
                stock - difference if difference is not None else 0.0
            )
        return values

    def _set_barcode(self, product, barcode, warnings):
        if not barcode or product.barcode == barcode:
            return
        duplicate = self.env["product.product"].search(
            [("barcode", "=", barcode), ("product_tmpl_id", "!=", product.id)],
            limit=1,
        )
        if duplicate:
            warnings.append(
                _(
                    "EAN %(barcode)s of %(product)s is already used by "
                    "%(other)s and was not set.",
                    barcode=barcode,
                    product=product.display_name,
                    other=duplicate.display_name,
                )
            )
            return
        product.barcode = barcode

    def action_import(self):
        self.ensure_one()
        rows, formulas = self._read_rows()
        header_index = find_header(rows, ["SKU", "Produto", "Tipo", "Venda"])
        if header_index is None:
            raise UserError(
                _(
                    "The columns 'SKU', 'Produto', 'Tipo' and 'Venda' were not "
                    "found in the spreadsheet."
                )
            )
        header = rows[header_index]
        columns = {
            key: column_index(header, titles) for key, titles in STOCK_COLUMNS.items()
        }
        Product = self.env["product.template"].with_context(active_test=False)
        Listing = self.env["ml.listing"].with_context(active_test=False)
        company = self.env.company
        products, listings = Product, Listing
        warnings = []
        products_by_sku = {}
        current = Product
        for index in range(header_index + 1, len(rows)):
            row = rows[index]
            sku = clean_sku(cell(row, columns["sku"]))
            name = clean_text(cell(row, columns["name"]))
            # A row repeating the SKU of the row above is one more listing of
            # the same product, even when it has a name
            if name and not (sku and sku == current.default_code):
                cost = self._cost(index, rows, formulas, columns)
                values = self._product_values(row, columns, cost)
                product = products_by_sku.get(sku) or (
                    Product.search([("default_code", "=", sku)], limit=1)
                    if sku
                    else Product.search(
                        [("name", "=", name), ("default_code", "=", False)], limit=1
                    )
                )
                if product:
                    product.write(values)
                else:
                    product = Product.create(dict(values, default_code=sku or False))
                self._set_barcode(
                    product, clean_code(cell(row, columns["barcode"])), warnings
                )
                products |= product
                current = product
                if sku:
                    products_by_sku[sku] = product
            elif sku:
                current = products_by_sku.get(sku) or Product.search(
                    [("default_code", "=", sku)], limit=1
                )
            if not current:
                continue
            listing_type = listing_type_from_text(cell(row, columns["listing_type"]))
            price = parse_float(cell(row, columns["price"]))
            if not listing_type or price is None:
                continue
            listing_values = {
                "price": price,
                "net_amount": parse_float(cell(row, columns["net_amount"])) or 0.0,
                "packaging_cost": parse_float(cell(row, columns["packaging_cost"]))
                or 0.0,
            }
            listing = Listing.search(
                [
                    ("product_tmpl_id", "=", current.id),
                    ("listing_type", "=", listing_type),
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )
            if listing:
                listing.write(listing_values)
            else:
                listing = Listing.create(
                    dict(
                        listing_values,
                        product_tmpl_id=current.id,
                        listing_type=listing_type,
                        company_id=company.id,
                    )
                )
            listings |= listing

        message = _(
            "%(products)s products and %(listings)s listings imported.",
            products=len(products),
            listings=len(listings),
        )
        if warnings:
            message += "\n" + "\n".join(warnings)
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "ml_sales_profit.product_template_action"
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Stock spreadsheet imported"),
                "message": message,
                "type": "warning" if warnings else "success",
                "sticky": bool(warnings),
                "next": action,
            },
        }
