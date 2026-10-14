from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_confirm(self):
        res = super().action_confirm()
        self.filtered(
            lambda p: p.picking_type_code == "outgoing"
        )._sg_torpinsa_plan_route()
        return res

    def _sg_prepare_dispatch_route_moves(self):
        # Sin reparto en Comprobar disponibilidad: ya se hizo al confirmar.
        return set()

    def _sg_torpinsa_plan_route(self):
        """Parte cada linea por ubicacion segun la ruta, SIN reservar."""
        planned_qty = {}
        for picking in self.filtered(lambda p: p.state not in ("done", "cancel")):
            route = picking._sg_get_applicable_dispatch_route()
            picking.sg_dispatch_route_id = route.id or False
            if not route:
                continue

            candidates = picking.move_ids.filtered(
                lambda m: m.state in ("confirmed", "waiting", "partially_available")
                and not m.move_line_ids
                and not m.sg_dispatch_route_processed
                and m.product_id.type == "product"
                and m.product_uom_qty > 0
            )
            for move in candidates:
                move._sg_apply_dispatch_route(route, planned_qty=planned_qty)

            picking._sg_torpinsa_renumber(route)

    def _sg_torpinsa_renumber(self, route):
        """
        Orden global de la lista: por ubicacion (nivel, tramo, posicion de
        mayor a menor), la raiz siempre al final y, dentro de la misma
        ubicacion, por producto. Asi las lineas de una ubicacion quedan juntas.
        """
        self.ensure_one()
        root = route.get_root_fallback_location()
        moves = self.move_ids.filtered(lambda m: m.state not in ("done", "cancel"))
        moves = moves.sorted(key=lambda m: (m.product_id.default_code or "", m.id))
        ordered = sorted(
            moves,
            key=lambda m: (
                0 if (root and m.location_id.id == root.id) else 1,
                m.location_id._sg_route_sort_key(),
            ),
            reverse=True,
        )
        for index, move in enumerate(ordered, start=1):
            if move.sg_dispatch_order != index * 10:
                move.sg_dispatch_order = index * 10
