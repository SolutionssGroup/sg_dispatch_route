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

        required_qty_base = self._sg_required_qty_in_product_uom()
        if float_is_zero(required_qty_base, precision_rounding=base_rounding):
            self.sg_dispatch_route_processed = True
            return False

        allocation_plan = route.get_allocation_plan(product, required_qty_base)

        if not allocation_plan:
            return False

        total_allocated_base = sum(line["qty"] for line in allocation_plan)
        first_line = allocation_plan[0]

        first_qty_move_uom = product.uom_id._compute_quantity(
            first_line["qty"],
            self.product_uom,
            rounding_method="HALF-UP",
        )

        product_block = self.product_id.id * 100000
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

        for index, line in enumerate(allocation_plan[1:], start=2):
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
                "sg_dispatch_order": _get_dispatch_order(line, index),
            })

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
                    fallback_index = len(allocation_plan) + 1

                    self.copy({
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

    def _sg_prepare_dispatch_route_before_assign(self):
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
