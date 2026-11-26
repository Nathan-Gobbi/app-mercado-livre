# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    """Snapshot legacy deductions without changing any stock balance."""
    cr.execute(
        "UPDATE ml_sale_line SET stock_units = units "
        "WHERE stock_deducted "
        "AND product_tmpl_id IS NOT NULL "
        "AND (stock_units IS NULL OR stock_units = 0)"
    )
    cr.execute(
        "INSERT INTO ml_sale_stock_line ("
        "sale_line_id, product_tmpl_id, quantity, "
        "create_uid, write_uid, create_date, write_date"
        ") SELECT line.id, line.product_tmpl_id, line.stock_units, "
        "1, 1, NOW(), NOW() "
        "FROM ml_sale_line AS line "
        "WHERE line.stock_deducted "
        "AND line.product_tmpl_id IS NOT NULL "
        "AND NOT EXISTS ("
        "SELECT 1 FROM ml_sale_stock_line AS stock_line "
        "WHERE stock_line.sale_line_id = line.id"
        ")"
    )
    cr.execute(
        "UPDATE ml_sale_import AS sale_import "
        "SET total_stock_units = COALESCE(("
        "SELECT SUM(line.stock_units) "
        "FROM ml_sale_import_line_rel AS relation "
        "JOIN ml_sale_line AS line ON line.id = relation.line_id "
        "WHERE relation.import_id = sale_import.id"
        "), 0)"
    )
