# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    """Mark products with an existing composition as kits without moving stock."""
    cr.execute(
        "UPDATE product_template AS product "
        "SET ml_is_kit = TRUE "
        "WHERE EXISTS ("
        "SELECT 1 FROM ml_product_component AS component "
        "WHERE component.product_tmpl_id = product.id"
        ")"
    )
