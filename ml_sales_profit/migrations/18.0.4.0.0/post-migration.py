# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    """Preserve the meaning of stock already deducted by historical sales."""
    cr.execute(
        "UPDATE ml_listing SET units_per_sale = 1 "
        "WHERE units_per_sale IS NULL OR units_per_sale <= 0"
    )
    cr.execute(
        "UPDATE ml_sale_line SET stock_units = units "
        "WHERE product_tmpl_id IS NOT NULL "
        "AND (stock_units IS NULL OR stock_units = 0)"
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
