from odoo import fields, models
from odoo.tools.float_utils import float_compare, float_is_zero


class StockMove(models.Model):
    _inherit = "stock.move"

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
        package_id=None,
        owner_id=None,
        strict=True,
    ):
        """
        En Odoo 17, este método recibe:
            (need, location_id, package_id=None, owner_id=None, strict=True)

        Si el move fue preparado por la ruta de despacho, obligamos a Odoo
        a reservar estrictamente en la ubicación exacta del move y no en
        ubicaciones hijas o padres.
        """
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
            need,
            location_id,
            package_id=package_id,
            owner_id=owner_id,
            strict=strict,
        )

    def _sg_required_qty_in_product_uom(self):
        self.ensure_one()
        return self.product_uom._compute_quantity(
            self.product_uom_qty,
            self.product_id.uom_id,
        )

    def _sg_get_next_dispatch_order(self):
        """
        Busca el próximo orden disponible dentro del picking.

        Antes el orden se reiniciaba en 10 por cada producto.
        Eso provocaba muchos movimientos con sg_dispatch_order = 10
        y el Barcode terminaba reordenando visualmente por su cuenta.

        Ahora el orden es único y progresivo en todo el picking:
        10, 20, 30, 40...
        """
        self.ensure_one()

        order_step = 10
        picking = self.picking_id

        if not picking:
            return order_step

        existing_orders = [
            move.sg_dispatch_order
            for move in picking.move_ids
            if move.sg_dispatch_order
            and move.sg_dispatch_order != 9999
            and move.id != self.id
        ]

        if not existing_orders:
            return order_step

        return max(existing_orders) + order_step

    def _sg_apply_dispatch_route(self, route):
        """
        Divide el movimiento en varios moves según la ruta física de despacho.

        Regla:
        - primero ubicaciones hijas válidas
        - hijas ordenadas de más lejos a más cerca
        - si las hijas no completan, completar con ubicación padre/raíz
        - mantener las líneas del mismo producto juntas
        - asignar sg_dispatch_order único y progresivo por picking

        Importante:
        Si NO hay disponibilidad al momento de aplicar la ruta, NO marcamos
        el move como procesado. Esto permite reintentar más adelante con
        'Comprobar disponibilidad'.
        """
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

        required_qty_base = self._sg_required_qty_in_product_uom()
        if float_is_zero(required_qty_base, precision_rounding=base_rounding):
            self.sg_dispatch_route_processed = True
            return False

        allocation_plan = route.get_allocation_plan(product, required_qty_base)

        # Si no hay disponibilidad válida, no marcamos como procesado.
        if not allocation_plan:
            return False

        total_allocated_base = sum(line["qty"] for line in allocation_plan)
        first_line = allocation_plan[0]

        first_qty_move_uom = product.uom_id._compute_quantity(
            first_line["qty"],
            self.product_uom,
            rounding_method="HALF-UP",
        )

        order_step = 10
        next_order = self._sg_get_next_dispatch_order()

        # 1) El move original toma la primera ubicación del plan.
        self.write({
            "location_id": first_line["location"].id,
            "product_uom_qty": first_qty_move_uom,
            "sg_dispatch_route_processed": True,
            "sg_dispatch_order": next_order,
        })

        next_order += order_step

        # 2) Crear copias para las demás ubicaciones del plan.
        # Estas quedan justo debajo del mismo producto.
        for line in allocation_plan[1:]:
            qty_move_uom = product.uom_id._compute_quantity(
                line["qty"],
                self.product_uom,
                rounding_method="HALF-UP",
            )

            if float_is_zero(qty_move_uom, precision_rounding=move_rounding):
                continue

            self.copy({
                "location_id": line["location"].id,
                "product_uom_qty": qty_move_uom,
                "sg_dispatch_route_processed": True,
                "sg_dispatch_order": next_order,
            })

            next_order += order_step

        # 3) Si todavía falta cantidad después de hijas y raíz disponible,
        # dejamos un move pendiente en la raíz para que la demanda no se pierda.
        remaining_base = required_qty_base - total_allocated_base
        if float_compare(remaining_base, 0.0, precision_rounding=base_rounding) > 0:
            remaining_qty_move_uom = product.uom_id._compute_quantity(
                remaining_base,
                self.product_uom,
                rounding_method="HALF-UP",
            )

            if not float_is_zero(remaining_qty_move_uom, precision_rounding=move_rounding):
                fallback_location = route.get_root_fallback_location()
                if fallback_location:
                    self.copy({
                        "location_id": fallback_location.id,
                        "product_uom_qty": remaining_qty_move_uom,
                        "sg_dispatch_route_processed": True,
                        "sg_dispatch_order": next_order,
                    })

        return True

    def _sg_prepare_dispatch_route_before_assign(self):
        """
        Aplica la ruta justo antes de reservar, incluso cuando Odoo
        llama _action_assign directamente sobre stock.move.
        """
        for move in self:
            if move.state in ("done", "cancel"):
                continue

            if move.sg_dispatch_route_processed:
                continue

            if move.move_line_ids:
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
