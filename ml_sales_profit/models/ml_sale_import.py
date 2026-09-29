# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools.spreadsheet import (
    cell,
    clean_sku,
    clean_text,
    column_index,
    find_header,
    parse_float,
    parse_ml_date,
)
from .ml_listing import listing_type_from_text

# Column titles of the Mercado Livre sales report. The first title found wins.
SALE_COLUMNS = {
    "sale_number": ["N.º de venda", "Nº de venda"],
    "sale_date": ["Data da venda"],
    "ml_status": ["Estado"],
    "sku": ["SKU"],
    "title": ["Título do anúncio", "Título"],
    "variation": ["Variação", "Variacion", "Varia"],
    "listing_type": ["Tipo de anúncio", "Tipo"],
    "units": ["Unidades"],
    "revenue_ml": ["Receita por produtos", "Receita bruta", "Receita"],
}
REQUIRED_COLUMNS = ["sale_date", "ml_status", "sku", "listing_type", "units"]


class MlSaleImport(models.Model):
    _name = "ml.sale.import"
    _inherit = ["ml.import.mixin"]
    _description = "Mercado Livre Sales Import"
    _order = "date_from desc, id desc"

    line_ids = fields.Many2many(
        comodel_name="ml.sale.line",
        relation="ml_sale_import_line_rel",
        column1="import_id",
        column2="line_id",
        string="Sales",
        readonly=True,
        copy=False,
    )
    line_count = fields.Integer(compute="_compute_totals", store=True)
    not_found_count = fields.Integer(
        string="Sales Without Listing", compute="_compute_totals", store=True
    )
    total_units = fields.Float(
        string="Units Sold",
        compute="_compute_totals",
        store=True,
        digits=(16, 0),
    )
    total_revenue = fields.Monetary(
        string="Revenue", compute="_compute_totals", store=True
    )
    total_gross_profit = fields.Monetary(
        string="Gross Profit", compute="_compute_totals", store=True
    )
    total_net_profit = fields.Monetary(
        string="Net Profit", compute="_compute_totals", store=True
    )
    gross_margin = fields.Float(
        string="Gross Margin (%)",
        compute="_compute_totals",
        store=True,
        digits=(16, 2),
        aggregator=None,
    )
    net_margin = fields.Float(
        string="Net Margin (%)",
        compute="_compute_totals",
        store=True,
        digits=(16, 2),
        aggregator=None,
    )

    def _default_name(self):
        return _("Sales")

    def _line_date_field(self):
        return "sale_date"

    @api.depends(
        "line_ids.units",
        "line_ids.revenue",
        "line_ids.gross_profit",
        "line_ids.net_profit",
        "line_ids.profit_status",
    )
    def _compute_totals(self):
        for record in self:
            lines = record.line_ids
            revenue = sum(lines.mapped("revenue"))
            gross = sum(lines.mapped("gross_profit"))
            net = sum(lines.mapped("net_profit"))
            record.line_count = len(lines)
            record.not_found_count = len(
                lines.filtered(lambda line: line.profit_status == "not_found")
            )
            record.total_units = sum(lines.mapped("units"))
            record.total_revenue = revenue
            record.total_gross_profit = gross
            record.total_net_profit = net
            record.gross_margin = 100 * gross / revenue if revenue else 0.0
            record.net_margin = 100 * net / revenue if revenue else 0.0

    # Processing

    def _parse_rows(self, rows):
        """Return the sales of the spreadsheet as dicts, plus cancelled keys.

        Mirrors the original script: cancelled sales, rows without SKU and
        rows without units are ignored.
        """
        header_index = find_header(rows, ["Data da venda", "SKU", "Unidades"])
        if header_index is None:
            raise UserError(
                _(
                    "This does not look like a Mercado Livre sales report: the "
                    "columns 'Data da venda', 'SKU' and 'Unidades' were not found."
                )
            )
        header = rows[header_index]
        columns = {
            key: column_index(header, titles) for key, titles in SALE_COLUMNS.items()
        }
        missing = [key for key in REQUIRED_COLUMNS if columns[key] is None]
        if missing:
            raise UserError(
                _("Required columns not found in the spreadsheet: %s", missing)
            )
        sales, cancelled = [], set()
        for row in rows[header_index + 1 :]:
            if not any(clean_text(value) for value in row):
                continue
            sku = clean_sku(cell(row, columns["sku"]))
            sale_number = clean_text(cell(row, columns["sale_number"]))
            status = clean_text(cell(row, columns["ml_status"]))
            if "cancel" in status.casefold():
                if sale_number:
                    cancelled.add((sale_number, sku))
                continue
            units = parse_float(cell(row, columns["units"])) or 0.0
            if not sku or units <= 0:
                continue
            sales.append(
                {
                    "sale_number": sale_number or False,
                    "sale_date": parse_ml_date(cell(row, columns["sale_date"])),
                    "ml_status": status,
                    "sku": sku,
                    "title": clean_text(cell(row, columns["title"])),
                    "variation": clean_text(cell(row, columns["variation"])),
                    "listing_type_text": clean_text(cell(row, columns["listing_type"])),
                    "units": units,
                    "revenue_ml": parse_float(cell(row, columns["revenue_ml"])),
                }
            )
        return sales, cancelled

    def _prepare_line_values(self, sale, listings):
        """Cross a sale with its listing, like the original script did."""
        listing_type = listing_type_from_text(sale["listing_type_text"])
        listing = listings.get((sale["sku"], listing_type))
        units = sale["units"]
        revenue_ml = sale["revenue_ml"]
        if revenue_ml is not None:
            revenue, origin = revenue_ml, "direct"
        elif listing:
            revenue, origin = units * listing.price, "rebuilt"
        else:
            revenue, origin = 0.0, "not_found"
        unit_net_profit = listing.net_profit if listing else 0.0
        unit_tax = listing.tax_amount if listing else 0.0
        return {
            "sale_number": sale["sale_number"],
            "sale_date": sale["sale_date"],
            "ml_status": sale["ml_status"],
            "sku": sale["sku"],
            "title": sale["title"],
            "variation": sale["variation"],
            "listing_type": listing_type,
            "listing_id": listing.id if listing else False,
            "product_tmpl_id": listing.product_tmpl_id.id if listing else False,
            "units": units,
            "revenue_ml": revenue_ml or 0.0,
            "revenue": revenue,
            "revenue_origin": origin,
            "unit_tax": unit_tax,
            "unit_net_profit": unit_net_profit,
            "unit_gross_profit": unit_net_profit + unit_tax,
            "profit_status": "ok" if listing else "not_found",
            "company_id": self.company_id.id,
        }

    def _process_rows(self, rows):
        self.ensure_one()
        sales, cancelled = self._parse_rows(rows)
        if not sales:
            raise UserError(_("No valid sale was found in the spreadsheet."))
        listings = {
            (listing.default_code, listing.listing_type): listing
            for listing in self.env["ml.listing"].search(
                [("company_id", "=", self.company_id.id)]
            )
        }
        Line = self.env["ml.sale.line"]
        numbers = {sale["sale_number"] for sale in sales if sale["sale_number"]}
        numbers |= {number for number, _sku in cancelled}
        existing = {
            (line.sale_number, line.sku): line
            for line in Line.search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("sale_number", "in", list(numbers)),
                ]
            )
        }
        # A sale imported before and cancelled afterwards must stop counting
        cancelled_lines = Line.browse(
            [existing[key].id for key in cancelled if key in existing]
        )
        cancelled_lines.unlink()

        lines = Line
        to_create = []
        for sale in sales:
            values = self._prepare_line_values(sale, listings)
            line = existing.get((sale["sale_number"], sale["sku"]))
            if line and line not in lines:
                line.write(values)
                lines |= line
            else:
                to_create.append(values)
        lines |= Line.create(to_create)
        self.line_ids = [fields.Command.set(lines.ids)]
        message = _("%(count)s sales imported.", count=len(lines))
        if cancelled_lines:
            message += " " + _(
                "%(count)s sales imported before were removed because they "
                "were cancelled.",
                count=len(cancelled_lines),
            )
        self.message_post(body=message)

    # Report

    def _period_label(self):
        if not self.date_from:
            return "periodo_indefinido"
        if self.date_from == self.date_to:
            return self.date_from.strftime("%d-%m-%Y")
        return f"{self.date_from.strftime('%d-%m')} a {self.date_to.strftime('%d-%m')}"

    def _build_report(self, workbook):
        """Rebuild the two sheets of the original 'Resumo de vendas' report."""
        lines = self.line_ids.sorted(lambda line: (line.sku, line.id))
        type_names = dict(
            self.env["ml.sale.line"]
            ._fields["listing_type"]
            ._description_selection(self.env)
        )
        origin_names = dict(
            self.env["ml.sale.line"]
            ._fields["revenue_origin"]
            ._description_selection(self.env)
        )
        status_names = dict(
            self.env["ml.sale.line"]
            ._fields["profit_status"]
            ._description_selection(self.env)
        )

        def first_text(values):
            return next((value for value in values if value), "")

        def unique_texts(values):
            seen, result = set(), []
            for value in values:
                if value and value.casefold() not in seen:
                    seen.add(value.casefold())
                    result.append(value)
            return " | ".join(result)

        def percent(value, total):
            return round(100 * value / total, 2) if total else None

        # Sheet 1: stock summary, one row per SKU
        by_sku = defaultdict(lambda: self.env["ml.sale.line"])
        for line in lines:
            by_sku[line.sku] |= line
        stock_rows = [
            [
                sku,
                first_text(group.mapped("title")),
                unique_texts(group.mapped("variation")),
                sum(group.mapped("units")),
                round(sum(group.mapped("revenue")), 2),
            ]
            for sku, group in by_sku.items()
        ]
        stock_rows.sort(key=lambda row: (row[0], row[1]))
        stock_rows.append(
            [
                _("TOTAL"),
                "",
                "",
                sum(row[3] for row in stock_rows),
                round(sum(row[4] for row in stock_rows), 2),
            ]
        )
        sheet = self._write_sheet(
            workbook,
            "Resumo_Estoque",
            [
                _("SKU"),
                _("Listing Title"),
                _("Variations"),
                _("Units Sold"),
                _("Revenue (R$)"),
            ],
            stock_rows,
        )
        self._fit_columns(sheet)
        self._format_column(sheet, "E", "R$ #,##0.00")

        # Sheet 2: financial summary, one row per SKU, variation and type
        groups = defaultdict(lambda: self.env["ml.sale.line"])
        for line in lines:
            groups[(line.sku, line.variation or "", line.listing_type or "")] |= line
        financial_rows = []
        for (sku, variation, listing_type), group in groups.items():
            revenue = sum(group.mapped("revenue"))
            gross = sum(group.mapped("gross_profit"))
            net = sum(group.mapped("net_profit"))
            found = group[0].profit_status == "ok"
            financial_rows.append(
                [
                    sku,
                    first_text(group.mapped("title")),
                    variation,
                    type_names.get(listing_type, ""),
                    sum(group.mapped("units")),
                    round(revenue, 2),
                    round(group[0].unit_tax, 2) if found else None,
                    round(group[0].unit_gross_profit, 2) if found else None,
                    round(group[0].unit_net_profit, 2) if found else None,
                    round(gross, 2),
                    percent(gross, revenue),
                    round(net, 2),
                    percent(net, revenue),
                    ", ".join(
                        sorted({status_names[s] for s in group.mapped("profit_status")})
                    ),
                    ", ".join(
                        sorted(
                            {origin_names[o] for o in group.mapped("revenue_origin")}
                        )
                    ),
                ]
            )
        financial_rows.sort(key=lambda row: (-row[4], row[0]))
        total_revenue = sum(row[5] for row in financial_rows)
        total_gross = sum(row[9] for row in financial_rows)
        total_net = sum(row[11] for row in financial_rows)
        financial_rows.append(
            [
                _("TOTAL"),
                "",
                "",
                "",
                sum(row[4] for row in financial_rows),
                round(total_revenue, 2),
                None,
                None,
                None,
                round(total_gross, 2),
                percent(total_gross, total_revenue),
                round(total_net, 2),
                percent(total_net, total_revenue),
                "",
                "",
            ]
        )
        sheet = self._write_sheet(
            workbook,
            "Resumo_Financeiro",
            [
                _("SKU"),
                _("Listing Title"),
                _("Variation"),
                _("Listing Type"),
                _("Units Sold"),
                _("Revenue (R$)"),
                _("Unit Tax (R$)"),
                _("Unit Gross Profit (R$)"),
                _("Unit Net Profit (R$)"),
                _("Total Gross Profit (R$)"),
                _("Gross Margin (%)"),
                _("Total Net Profit (R$)"),
                _("Net Margin (%)"),
                _("Profit Status"),
                _("Revenue Origin"),
            ],
            financial_rows,
        )
        self._fit_columns(sheet)
        for column in ("F", "G", "H", "I", "J", "L"):
            self._format_column(sheet, column, "R$ #,##0.00")
        for column in ("K", "M"):
            self._format_column(sheet, column, "0.00")
        return _("Sales summary %s.xlsx", self._period_label())

    def action_view_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "ml_sales_profit.ml_sale_line_action"
        )
        action.update(
            domain=[("import_ids", "in", self.ids)],
            context={},
            views=[
                (False, "list"),
                (False, "pivot"),
                (False, "graph"),
                (False, "form"),
            ],
        )
        return action
