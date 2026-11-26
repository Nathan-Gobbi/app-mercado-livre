# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    """Replace the old product/type uniqueness with listing SKU/type."""
    cr.execute(
        "ALTER TABLE ml_listing "
        "DROP CONSTRAINT IF EXISTS ml_listing_product_type_uniq"
    )
