from odoo import api, fields, models
from odoo.tools.float_utils import float_is_zero


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sg_dispatch_route_id = fields.Many2one(
        "sg.dispatch.route",
        string="Ruta de despacho",
        copy=False,
        readonly=True,
    )
    sg_sale_order_display_name = fields.Char(
        string="Referencia",
        compute="_compute_sg_sale_order_display_name",
    )

    @api.depends("sale_id.name", "origin", "name")
    def _compute_sg_sale_order_display_name(self):
        for picking in self:
            picking.sg_sale_order_display_name = (
                picking.sale_id.name
                or picking.origin
                or picking.name
            )

    def _sg_get_applicable_dispatch_route(self):
        self.ensure_one()

        warehouse = self.picking_type_id.warehouse_id
        if not warehouse or not self.picking_type_id:
            return self.env["sg.dispatch.route"]

        return self.env["sg.dispatch.route"].get_applicable_route(
            warehouse=warehouse,
            picking_type=self.picking_type_id,
        )

    def _sg_prepare_dispatch_route_moves(self):
        """
        Antes de reservar, divide los moves según la ruta:
        - primero hijas válidas
        - luego raíz si hace falta
        - excluyendo ubicaciones bloqueadas
        """
        for picking in self.filtered(lambda p: p.state not in ("done", "cancel")):
            route = picking._sg_get_applicable_dispatch_route()
            picking.sg_dispatch_route_id = route.id or False

            if not route:
                continue

            candidate_moves = picking.move_ids.filtered(
                lambda m: m.state in ("confirmed", "waiting", "partially_available")
                and not m.sg_dispatch_route_processed
                and not m.move_line_ids
                and m.product_id
                and m.product_id.type == "product"
                and m.product_uom_qty > 0
            )

            for move in candidate_moves:
                move._sg_apply_dispatch_route(route)

    def _sg_release_pending_dispatch_reservations(self):
        """
        Libera reservas que queden pendientes después de validar un despacho.

        Objetivo operativo:
        - La reserva solo sirve para que Barcode pueda trabajar.
        - Lo no despachado no debe quedar secuestrado.
        - Si se genera backorder, debe quedar sin reserva.
        """
        pickings_to_clean = self.env["stock.picking"]

        for picking in self:
            related_pickings = self.search([
                ("backorder_id", "=", picking.id),
                ("state", "not in", ("done", "cancel")),
            ])
            pickings_to_clean |= related_pickings

            if picking.state not in ("done", "cancel"):
                pickings_to_clean |= picking

        moves_to_unreserve = pickings_to_clean.move_ids.filtered(
            lambda m: m.state in ("assigned", "partially_available")
        )

        if moves_to_unreserve:
            moves_to_unreserve._do_unreserve()

        return True

    def _sg_get_manual_reservation_cleanup_moves(self, picking_type_code="outgoing"):
        """
        Devuelve movimientos elegibles para limpieza manual de reservas.

        Esta selección es deliberadamente conservadora:
        - solo pickings abiertos
        - solo el tipo de operación indicado
        - solo movimientos reservados/parcialmente reservados
        - nunca movimientos picked/done/cancel
        """
        eligible_pickings = self.filtered(
            lambda p: p.state not in ("done", "cancel")
            and (
                not picking_type_code
                or p.picking_type_code == picking_type_code
            )
        )

        candidate_moves = eligible_pickings.move_ids.filtered(
            lambda m: m.state in ("assigned", "partially_available")
            and m.state not in ("done", "cancel")
            and not (("picked" in m._fields) and m.picked)
            and m.move_line_ids
        )

        moves_to_clean = self.env["stock.move"]
        for move in candidate_moves:
            reserved_qty = move._sg_get_manual_cleanup_reserved_qty()
            if not float_is_zero(
                reserved_qty,
                precision_rounding=move.product_uom.rounding,
            ):
                moves_to_clean |= move

        return moves_to_clean

    def _sg_manual_reservation_cleanup_summary(self, picking_type_code="outgoing"):
        moves = self._sg_get_manual_reservation_cleanup_moves(
            picking_type_code=picking_type_code
        )
        return moves._sg_manual_reservation_cleanup_summary_lines()

    def _sg_manual_reservation_cleanup(self, picking_type_code="outgoing"):
        moves = self._sg_get_manual_reservation_cleanup_moves(
            picking_type_code=picking_type_code
        )
        summary_lines = moves._sg_manual_reservation_cleanup_summary_lines()

        if moves:
            moves._do_unreserve()
            for picking in moves.picking_id:
                picking_lines = [
                    line
                    for line in summary_lines
                    if line["picking_id"] == picking.id
                ]
                if not picking_lines:
                    continue

                body_lines = [
                    "Reservas liberadas manualmente por %s el %s."
                    % (
                        self.env.user.display_name,
                        fields.Datetime.to_string(fields.Datetime.now()),
                    ),
                    "",
                ]
                for line in picking_lines:
                    body_lines.append(
                        "- %s | %s | %s %s | %s"
                        % (
                            line["product"],
                            line["location"],
                            line["reserved_qty"],
                            line["uom"],
                            line["move_state"],
                        )
                    )

                picking.message_post(body="<br/>".join(body_lines))

        return summary_lines

    def action_assign(self):
        self._sg_prepare_dispatch_route_moves()
        return super().action_assign()

    def button_validate(self):
        result = super().button_validate()

        # Si Odoo abre wizard de backorder, la limpieza se hará al confirmar el wizard.
        if isinstance(result, dict):
            return result

        self._sg_release_pending_dispatch_reservations()
        return result

    def _get_stock_barcode_data(self):
        """
        Reordena la data enviada al módulo de código de barras para que
        respete sg_dispatch_order:
        1) hijas primero
        2) luego la raíz
        """
        data = super()._get_stock_barcode_data()

        records = data.get("records", {})
        move_line_records = records.get("stock.move.line", [])
        picking_records = records.get("stock.picking", [])

        move_line_records_sorted = sorted(
            move_line_records,
            key=lambda ml: (
                ml.get("sg_dispatch_order", 999999),
                ml.get("id", 999999),
            ),
        )
        records["stock.move.line"] = move_line_records_sorted

        order_map = {
            ml.get("id"): index
            for index, ml in enumerate(move_line_records_sorted)
        }

        for picking_vals in picking_records:
            move_line_ids = picking_vals.get("move_line_ids") or []
            picking_vals["move_line_ids"] = sorted(
                move_line_ids,
                key=lambda ml_id: order_map.get(ml_id, 999999),
            )

        return data
