from odoo import _, fields, models


class SgDispatchReservationCleanupWizard(models.TransientModel):
    _name = "sg.dispatch.reservation.cleanup.wizard"
    _description = "Limpieza controlada de reservas de despacho"

    picking_type_code = fields.Selection(
        [
            ("outgoing", "Salida"),
            ("incoming", "Recepción"),
            ("internal", "Transferencia interna"),
        ],
        string="Tipo de operación",
        default="outgoing",
        required=True,
    )
    picking_ids = fields.Many2many(
        "stock.picking",
        string="Traslados específicos",
        domain="[('state', 'not in', ('done', 'cancel')), "
        "('picking_type_code', '=', picking_type_code), "
        "('company_id', '=', company_id)]",
    )
    dry_run = fields.Boolean(
        string="Simulación",
        default=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )
    summary = fields.Text(
        string="Resultado",
        readonly=True,
    )

    def _get_candidate_pickings(self):
        self.ensure_one()

        domain = [
            ("state", "not in", ("done", "cancel")),
            ("picking_type_code", "=", self.picking_type_code),
            ("company_id", "=", self.company_id.id),
        ]
        if self.picking_ids:
            domain.append(("id", "in", self.picking_ids.ids))

        return self.env["stock.picking"].search(domain)

    def _format_summary(self, summary_lines, executed=False):
        self.ensure_one()

        title = (
            _("Ejecución completada. Reservas liberadas:")
            if executed
            else _("Simulación. Reservas que se liberarían:")
        )

        if not summary_lines:
            return _(
                "No se encontraron reservas elegibles para liberar con los filtros actuales."
            )

        lines = [title, ""]
        for line in summary_lines:
            lines.append(
                _(
                    "%(picking)s | %(sale_reference)s | %(product)s | "
                    "%(location)s | %(reserved_qty)s %(uom)s | %(move_state)s"
                )
                % line
            )
        return "\n".join(lines)

    def action_simulate(self):
        for wizard in self:
            pickings = wizard._get_candidate_pickings()
            summary_lines = pickings._sg_manual_reservation_cleanup_summary(
                picking_type_code=wizard.picking_type_code
            )
            wizard.write({
                "dry_run": True,
                "summary": wizard._format_summary(summary_lines, executed=False),
            })
        return self._reopen()

    def action_execute(self):
        for wizard in self:
            pickings = wizard._get_candidate_pickings()
            summary_lines = pickings._sg_manual_reservation_cleanup(
                picking_type_code=wizard.picking_type_code
            )
            wizard.write({
                "dry_run": False,
                "summary": wizard._format_summary(summary_lines, executed=True),
            })
        return self._reopen()

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
