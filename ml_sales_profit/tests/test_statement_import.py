# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import date

from odoo.exceptions import UserError

from .common import MlSalesProfitCase, read_report, statement_file, xlsx


class TestStatementImport(MlSalesProfitCase):
    def _rows(self):
        return [
            ["01-07-2026", "Pix enviado Fake Person", "9001", "-3.000,00", "0"],
            ["01-07-2026", "Liberação de dinheiro", "9002", "397,92", "0"],
            ["02-07-2026", "Pagamento Fake Store", "9003", "-21,90", "0"],
            # Ignored by default
            [
                "03-07-2026",
                "Dinheiro retido Reclamações e devoluções",
                "9004",
                "-50,00",
                "0",
            ],
            ["", "Without date", "9005", "-1,00", "0"],
        ]

    def _import(self, rows):
        statement = self.env["ml.statement.import"].create(
            {"file": statement_file(rows), "file_name": "account_statement-x.xlsx"}
        )
        statement.action_process()
        return statement

    def test_process(self):
        statement = self._import(self._rows())
        self.assertEqual(statement.line_count, 2)
        self.assertEqual(statement.line_ids.mapped("reference_id"), ["9001", "9003"])
        self.assertAlmostEqual(statement.total_outflow, -3021.9)
        self.assertEqual(statement.date_from, date(2026, 7, 1))
        self.assertEqual(statement.name, "Statement 01/07/2026 - 02/07/2026")
        self.assertRecordValues(
            statement,
            [
                {
                    "initial_balance": 100.0,
                    "credits": 50.0,
                    "debits": -30.0,
                    "final_balance": 120.0,
                }
            ],
        )
        self.assertEqual(statement.line_ids[0].outflow_amount, 3000.0)

    def test_excluded_types_are_configurable(self):
        self.env["ml.statement.excluded.type"].search([]).active = False
        statement = self._import(self._rows())
        self.assertEqual(statement.line_count, 3)

    def test_reimport_keeps_notes(self):
        first = self._import(self._rows())
        first.line_ids[0].note = "Transfer to my bank"
        second = self._import(self._rows())
        self.assertEqual(first.line_ids, second.line_ids)
        self.assertEqual(second.line_ids[0].note, "Transfer to my bank")

    def test_report(self):
        statement = self._import(self._rows())
        statement.line_ids[1].note = "Parts"
        statement.action_download_report()
        self.assertEqual(
            statement.report_file_name, "outflows_report_account_statement-x.xlsx"
        )
        rows = read_report(statement.report_file)["Outflows"]
        self.assertEqual(rows[1][1:], ["Pix enviado Fake Person", -3000, None])
        self.assertEqual(rows[2][1:], ["Pagamento Fake Store", -21.9, "Parts"])

    def test_wrong_file(self):
        statement = self.env["ml.statement.import"].create(
            {"file": xlsx([["foo"]]), "file_name": "x.xlsx"}
        )
        with self.assertRaises(UserError):
            statement.action_process()
