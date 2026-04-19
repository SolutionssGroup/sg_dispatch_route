from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SgDispatchRouteExcludeLine(models.Model):
    _name = "sg.dispatch.route.exclude.line"
    _description = "Ubicación excluida de ruta de despacho"
    _order = "id"

    route_id = fields.Many2one(
        "sg.dispatch.route",
        string="Ruta",
        required=True,
        ondelete="cascade",
    )

    location_id = fields.Many2one(
        "stock.location",
        string="Ubicación",
        required=True,
        domain="[('usage', '=', 'internal')]",
    )

    note = fields.Char(
        string="Motivo / Nota",
    )

    company_id = fields.Many2one(
        related="route_id.company_id",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "sg_dispatch_route_exclude_unique",
            "unique(route_id, location_id)",
            "Esa ubicación ya está excluida en esta ruta.",
        ),
    ]

    def name_get(self):
        result = []
        for rec in self:
            name = "%s - %s" % (
                rec.route_id.name or _("Ruta"),
                rec.location_id.display_name or _("Ubicación"),
            )
            result.append((rec.id, name))
        return result

    @api.constrains("location_id")
    def _check_location_is_internal(self):
        for rec in self:
            if rec.location_id and rec.location_id.usage != "internal":
                raise ValidationError(_("Solo se pueden excluir ubicaciones internas."))