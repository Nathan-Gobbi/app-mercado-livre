# Copyright 2026 Nathan Gobbi
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MlProductComponent(models.Model):
    _name = "ml.product.component"
    _description = "Mercado Livre Product Kit Component"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Kit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    component_product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Component",
        required=True,
        ondelete="restrict",
        index=True,
    )
    quantity = fields.Float(required=True, default=1.0, digits=(16, 2))

    _sql_constraints = [
        (
            "product_component_uniq",
            "unique(product_tmpl_id, component_product_tmpl_id)",
            "A component can only appear once in a kit.",
        )
    ]

    @api.constrains("product_tmpl_id", "component_product_tmpl_id", "quantity")
    def _check_component(self):
        for line in self:
            if not line.product_tmpl_id.ml_is_kit:
                raise ValidationError(_("Enable 'Is a Kit' before adding products."))
            if line.quantity <= 0:
                raise ValidationError(
                    _("Component quantity must be greater than zero.")
                )
            if line.product_tmpl_id == line.component_product_tmpl_id:
                raise ValidationError(_("A product cannot be a component of itself."))
            if line.component_product_tmpl_id.ml_is_kit:
                raise ValidationError(_("A kit cannot be used as a component."))
            if line.product_tmpl_id.ml_parent_component_ids:
                raise ValidationError(
                    _("A product used as a component cannot become a kit.")
                )
