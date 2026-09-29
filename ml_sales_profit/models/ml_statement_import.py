# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools.spreadsheet import (
    cell,
    clean_text,
    column_index,
    find_header,
    parse_brl_amount,
    parse_statement_date,
)

STATEMENT_HEADER = ["RELEASE_DATE", "TRANSACTION_TYPE", "TRANSACTION_NET_AMOUNT"]
SUMMARY_HEADER = ["INITIAL_BALANCE", "CREDITS", "DEBITS", "FINAL_BALANCE"]


class MlStatementImport(models.Model):
    _name = "ml.statement.import"
    _inherit = ["ml.import.mixin"]
    _description = "Mercado Livre Account Statement Import"
    _order = "date_from desc, id desc"

    line_ids = fields.Many2many(
        comodel_name="ml.statement.line",
        relation="ml_statement_import_line_rel",
        column1="import_id",
        column2="line_id",
        string="Outflows",
        copy=False,
    )
    initial_balance = fields.Monetary(readonly=True, copy=False)
    credits = fields.Monetary(readonly=True, copy=False)
    debits = fields.Monetary(readonly=True, copy=False)
    final_balance = fields.Monetary(readonly=True, copy=False)
    line_count = fields.Integer(compute="_compute_totals", store=True)
    total_outflow = fields.Monetary(
        string="Total Outflows", compute="_compute_totals", store=True
    )

    def _default_name(self):
        return _("Statement")

    def _line_date_field(self):
        return "date"

    @api.depends("line_ids.amount")
    def _compute_totals(self):
        for record in self:
            record.line_count = len(record.line_ids)
            record.total_outflow = sum(record.line_ids.mapped("amount"))

    def _parse_summary(self, rows):
        header_index = find_header(rows, SUMMARY_HEADER)
        if header_index is None or header_index + 1 >= len(rows):
            return {}
        header, values = rows[header_index], rows[header_index + 1]
        summary = {}
        for title in SUMMARY_HEADER:
            index = column_index(header, [title])
            summary[title.lower()] = parse_brl_amount(cell(values, index)) or 0.0
        return summary

    def _parse_rows(self, rows):
        """Return the outflows of the statement, like the original script.

        Only negative amounts are kept, ignoring the transaction types
        configured as excluded and rows without a date.
        """
        header_index = find_header(rows, STATEMENT_HEADER)
        if header_index is None:
            raise UserError(
                _(
                    "This does not look like a Mercado Livre account statement: "
                    "the columns %s were not found.",
                    ", ".join(STATEMENT_HEADER),
                )
            )
        header = rows[header_index]
        date_col = column_index(header, ["RELEASE_DATE"])
        type_col = column_index(header, ["TRANSACTION_TYPE"])
        amount_col = column_index(header, ["TRANSACTION_NET_AMOUNT"])
        reference_col = column_index(header, ["REFERENCE_ID"])
        excluded = set(self.env["ml.statement.excluded.type"].search([]).mapped("name"))
        outflows = []
        for row in rows[header_index + 1 :]:
            amount = parse_brl_amount(cell(row, amount_col))
            transaction_type = clean_text(cell(row, type_col))
            date = parse_statement_date(cell(row, date_col))
            if amount is None or amount >= 0 or not date:
                continue
            if transaction_type in excluded:
                continue
            outflows.append(
                {
                    "date": date,
                    "transaction_type": transaction_type,
                    "reference_id": clean_text(cell(row, reference_col)) or False,
                    "amount": amount,
                }
            )
        return outflows

    def _process_rows(self, rows):
        self.ensure_one()
        outflows = self._parse_rows(rows)
        summary = self._parse_summary(rows)
        Line = self.env["ml.statement.line"]
        references = [o["reference_id"] for o in outflows if o["reference_id"]]
        existing = {
            (line.reference_id, line.transaction_type, line.amount): line
            for line in Line.search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("reference_id", "in", references),
                ]
            )
        }
        lines = Line
        to_create = []
        for outflow in outflows:
            key = (
                outflow["reference_id"],
                outflow["transaction_type"],
                outflow["amount"],
            )
            line = existing.get(key) if outflow["reference_id"] else None
            if line and line not in lines:
                line.write({"date": outflow["date"]})
                lines |= line
            else:
                to_create.append(dict(outflow, company_id=self.company_id.id))
        lines |= Line.create(to_create)
        self.write(dict(summary, line_ids=[fields.Command.set(lines.ids)]))
        self.message_post(body=_("%(count)s outflows imported.", count=len(lines)))

    def _build_report(self, workbook):
        """Rebuild the 'Saídas' sheet of the original script."""
        rows = [
            [line.date, line.transaction_type, line.amount, line.note or ""]
            for line in self.line_ids.sorted(
                lambda line: (line.date, line.transaction_type, line.amount)
            )
        ]
        sheet = self._write_sheet(
            workbook,
            _("Outflows"),
            [
                _("Transaction Date"),
                _("Transaction Type"),
                _("Transaction Amount"),
                _("Note"),
            ],
            rows,
        )
        for column, width in {"A": 18, "B": 55, "C": 18, "D": 40}.items():
            sheet.column_dimensions[column].width = width
        for date_cell in sheet["A"][1:]:
            date_cell.number_format = "dd/mm/yyyy"
        self._format_column(sheet, "C", "#,##0.00")
        stem = os.path.splitext(self.file_name or "")[0] or "extrato"
        return _("outflows_report_%s.xlsx", stem)

    def action_view_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "ml_sales_profit.ml_statement_line_action"
        )
        action.update(
            domain=[("import_ids", "in", self.ids)],
            context={},
            views=[(False, "list"), (False, "pivot"), (False, "graph")],
        )
        return action
