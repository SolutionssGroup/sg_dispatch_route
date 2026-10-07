from odoo import fields, models
from odoo.tools.float_utils import float_compare, float_is_zero


class StockMove(models.Model):
    _inherit = "stock.move"

    # Nota (fix 2026-09-30): este flag YA NO decide si un move puede volver
    # a partirse/replanificarse — eso ahora lo decide únicamente
    # `not move_line_ids` (ver _sg_prepare_dispatch_route_moves y
    # _sg_prepare_dispatch_route_before_assign). Su único uso real hoy es
    # marcar, para _update_reserved_quantity, que este move ya pasó por
    # get_allocation_plan() al menos una vez y por tanto su location_id debe
    # respetarse en modo estricto (strict=True) en vez de dejar que Odoo
    # busque en cualquier ubicación. No lo uses como "ya no hace falta
    # tocarlo": un move con este flag en True puede seguir sin haber
    # reservado nada.
    sg_dispatch_route_processed = fields.Boolean(
        string="Ruta de despacho procesada",
        default=False,
        copy=False,
        readonly=True,
    )

    sg_dispatch_order = fields.Integer(
        string="Orden ruta despacho",
        default=9999,
        copy=False,
        index=True,
    )

    def _update_reserved_quantity(
        self,
        need,
        location_id,
        quant_ids=None,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=True,
    ):
        self.ensure_one()

        if (
            self.sg_dispatch_route_processed
            and self.picking_id
            and self.picking_id.sg_dispatch_route_id
            and self.location_id
        ):
            location_id = self.location_id
            strict = True

        return super()._update_reserved_quantity(
            need=need,
            location_id=location_id,
            quant_ids=quant_ids,
            lot_id=lot_id,
            package_id=package_id,
            owner_id=owner_id,
            strict=strict,
        )

    def _do_unreserve(self):
        """
        Al liberar una reserva (botón 'Anular reserva', limpieza de backorders,
        etc.), la decisión de ubicación que tomó la ruta de despacho para estos
        movimientos queda obsoleta: puede haber cambiado el stock disponible en
        los tramos desde que se calculó. Se resetea sg_dispatch_route_processed
        para que el próximo 'Comprobar disponibilidad' vuelva a correr
        get_allocation_plan() desde cero, en vez de quedar pegado para siempre
        a la ubicación (a menudo la raíz AP/Stock) que se decidió la primera vez.
        """
        moves_to_reprocess = self.filtered("sg_dispatch_route_processed")

        result = super()._do_unreserve()

        if moves_to_reprocess:
            moves_to_reprocess.write({"sg_dispatch_route_processed": False})

        return result

    def _sg_required_qty_in_product_uom(self):
        self.ensure_one()
        return self.product_uom._compute_quantity(
            self.product_uom_qty,
            self.product_id.uom_id,
        )

    def _sg_get_manual_cleanup_reserved_qty(self):
        self.ensure_one()

        move_lines = self.move_line_ids
        if "picked" in move_lines._fields:
            move_lines = move_lines.filtered(lambda ml: not ml.picked)

        reserved_qty = sum(move_lines.mapped("quantity"))
        if self.product_id and self.product_id.uom_id != self.product_uom:
            reserved_qty = self.product_id.uom_id._compute_quantity(
                reserved_qty,
                self.product_uom,
                rounding_method="HALF-UP",
            )

        return reserved_qty

    def _sg_manual_reservation_cleanup_summary_lines(self):
        summary_lines = []
        for move in self:
            picking = move.picking_id
            sale_reference = (
                picking.sale_id.name
                if "sale_id" in picking._fields and picking.sale_id
                else picking.origin
                or picking.name
            )
            summary_lines.append({
                "picking_id": picking.id,
                "picking": picking.name,
                "sale_reference": sale_reference,
                "product": move.product_id.display_name,
                "location": move.location_id.display_name,
                "reserved_qty": move._sg_get_manual_cleanup_reserved_qty(),
                "uom": move.product_uom.name,
                "move_state": move.state,
            })
        return summary_lines

    def _sg_apply_dispatch_route(self, route):
        self.ensure_one()

        if not route:
            return False

        if self.state in ("done", "cancel"):
            return False

        if self.move_line_ids:
            return False

        if not self.product_id or self.product_id.type != "product":
            self.sg_dispatch_route_processed = True
            return False

        product = self.product_id
        base_rounding = product.uom_id.rounding
        move_rounding = self.product_uom.rounding
        original_location = self.location_id
        original_product_uom_qty = self.product_uom_qty

        required_qty_base = self._sg_required_qty_in_product_uom()
        if float_is_zero(required_qty_base, precision_rounding=base_rounding):
            self.sg_dispatch_route_processed = True
            return False

        allocation_plan = route.get_allocation_plan(product, required_qty_base)

        if not allocation_plan:
            return False

        planned_lines = []
        remaining_qty_move_uom = original_product_uom_qty
        for line in allocation_plan:
            qty_move_uom = product.uom_id._compute_quantity(
                line["qty"],
                self.product_uom,
                rounding_method="HALF-UP",
            )
            qty_move_uom = min(qty_move_uom, remaining_qty_move_uom)
            if float_is_zero(qty_move_uom, precision_rounding=move_rounding):
                continue

            planned_lines.append((line, qty_move_uom))
            remaining_qty_move_uom -= qty_move_uom
            if float_compare(
                remaining_qty_move_uom,
                0.0,
                precision_rounding=move_rounding,
            ) <= 0:
                remaining_qty_move_uom = 0.0
                break

        if not planned_lines:
            return False

        first_line, first_qty_move_uom = planned_lines[0]

        # sg_dispatch_order es int4: product.id * 100000 desborda con ids > 21474.
        picking_product_ids = sorted(
            set(self.picking_id.move_ids.product_id.ids) | {product.id}
        )
        product_block = (picking_product_ids.index(product.id) + 1) * 100000
        order_step = 10
        parent_offset = 9000

        root_location = route.get_root_fallback_location()

        def _get_dispatch_order(line, index):
            location = line["location"]
            is_parent_location = (
                root_location
                and location.id == root_location.id
            )

            base_order = (
                product_block + parent_offset
                if is_parent_location
                else product_block
            )

            return base_order + (index * order_step)

        self.write({
            "location_id": first_line["location"].id,
            "product_uom_qty": first_qty_move_uom,
            "sg_dispatch_route_processed": True,
            "sg_dispatch_order": _get_dispatch_order(first_line, 1),
        })

        # copy() deja el move nuevo en "draft" (Odoo resetea el estado). Un move
        # draft no se reserva y deja el picking completo en draft; al validar
        # desde la PDA Odoo lo confirma y re-asigna en pleno Validar. Se hereda
        # el estado del padre para que el tramo nazca en el mismo estado.
        parent_state = self.state

        for index, (line, qty_move_uom) in enumerate(planned_lines[1:], start=2):
            self.copy({
                "state": parent_state,
                "location_id": line["location"].id,
                "product_uom_qty": qty_move_uom,
                "sg_dispatch_route_processed": True,
                "sg_dispatch_order": _get_dispatch_order(line, index),
            })

        if not float_is_zero(
            remaining_qty_move_uom,
            precision_rounding=move_rounding,
        ):
            fallback_location = route.get_root_fallback_location() or original_location
            fallback_index = len(planned_lines) + 1

            self.copy({
                "state": parent_state,
                "location_id": fallback_location.id,
                "product_uom_qty": remaining_qty_move_uom,
                "sg_dispatch_route_processed": True,
                "sg_dispatch_order": (
                    product_block
                    + parent_offset
                    + (fallback_index * order_step)
                ),
            })

        return True

    def _sg_release_phantom_reservations(self, products):
        """
        El despacho de Inprotec es instantáneo: se comprueba disponibilidad,
        se despacha en el momento, se valida. Una reserva que sigue viva
        después de eso (en cualquier otro picking de salida) no representa
        trabajo en curso real para este negocio — es una reserva fantasma
        que solo ensucia la existencia libre que ve el próximo "Comprobar
        disponibilidad". Por eso, antes de repartir la demanda de estos
        productos, se sueltan TODAS sus reservas de salida vigentes, sin
        importar en qué picking estén, para que get_allocation_plan() calcule
        siempre contra existencia limpia.

        Deliberadamente amplio: puede soltar una reserva de un picking que
        otra persona tenga abierto en su propia PDA en este mismo instante.
        Es el comportamiento pedido explícitamente para este negocio — no
        es un descuido.

        Alcance: solo pickings de salida (picking_type_id.code == "outgoing")
        de la misma compañía. No toca recepciones ni transferencias internas.
        """
        if not products:
            return

        stray_moves = self.env["stock.move"].search([
            ("product_id", "in", products.ids),
            ("state", "in", ("assigned", "partially_available")),
            ("picking_id.picking_type_id.code", "=", "outgoing"),
            ("company_id", "=", self.env.company.id),
        ])

        if stray_moves:
            stray_moves._do_unreserve()

    def _sg_prepare_dispatch_route_before_assign(self):
        # Fix 2026-09-30: ver el comentario equivalente en
        # stock_picking.py::_sg_prepare_dispatch_route_moves. No se excluye
        # aquí por sg_dispatch_route_processed: ese flag no distingue entre
        # "ya reservó algo" y "se le calculó un plan que terminó en 0
        # reservado". `not move.move_line_ids` sí distingue eso, y es el
        # único guardián que necesitamos para no volver a partir un move que
        # ya logró reservar.
        # La liberación de reservas fantasma NO va aquí: este método corre en
        # cada _action_assign, incluido el que Odoo dispara al confirmar/validar
        # desde la PDA, y ahí borraría los move lines que la PDA ya cargó
        # ("Registro faltante: stock.move.line"). Solo corre al pulsar
        # "Comprobar disponibilidad" (stock_picking.py::_sg_prepare_dispatch_route_moves).
        planned_move_ids = set(self.env.context.get("sg_route_planned_move_ids") or ())
        for move in self:
            if move.state in ("done", "cancel"):
                continue

            if move.move_line_ids:
                continue

            # Ya los repartió stock_picking.py::_sg_prepare_dispatch_route_moves
            # en este mismo "Comprobar disponibilidad".
            if move.id in planned_move_ids:
                continue

            picking = move.picking_id
            if not picking:
                continue

            route = picking._sg_get_applicable_dispatch_route()
            picking.sg_dispatch_route_id = route.id or False

            if not route:
                continue

            if not move.product_id or move.product_id.type != "product":
                move.sg_dispatch_route_processed = True
                continue

            if move.product_uom_qty <= 0:
                move.sg_dispatch_route_processed = True
                continue

            move._sg_apply_dispatch_route(route)

    def _action_assign(self, force_qty=False):
        self._sg_prepare_dispatch_route_before_assign()
        return super()._action_assign(force_qty=force_qty)
