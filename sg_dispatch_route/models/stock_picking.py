from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sg_dispatch_route_id = fields.Many2one(
        "sg.dispatch.route",
        string="Ruta de despacho",
        copy=False,
        readonly=True,
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

            route_applied = False
            for move in candidate_moves:
                if move._sg_apply_dispatch_route(route):
                    route_applied = True

            if route_applied:
                picking._sg_resequence_dispatch_route_moves(route=route)

    def _sg_resequence_dispatch_route_moves(self, route=False):
        """
        Reordena globalmente los movimientos del picking según la ruta física.

        Objetivo:
        - No depender del orden de las líneas de venta.
        - Ordenar ubicaciones hijas de más lejos a más cerca.
        - Si un producto se completa con ubicación padre, dejar esa línea
          debajo del mismo producto.
        - Reasignar sg_dispatch_order y sequence de forma progresiva.
        """
        order_step = 10

        def desc_text(value):
            return tuple(-ord(char) for char in (value or ""))

        for picking in self:
            current_route = route or picking.sg_dispatch_route_id or picking._sg_get_applicable_dispatch_route()
            if not current_route:
                continue

            root_location = current_route.root_location_id

            moves = picking.move_ids.filtered(
                lambda m: m.state not in ("done", "cancel")
                and m.sg_dispatch_route_processed
                and m.product_id
                and m.product_id.type == "product"
            )

            if not moves:
                continue

            group_best_location = {}

            for move in moves:
                location = move.location_id
                if not location:
                    continue

                sale_line_id = move.sale_line_id.id if "sale_line_id" in move._fields and move.sale_line_id else 0
                group_key = (move.product_id.id, sale_line_id)

                is_root = bool(root_location and location.id == root_location.id)
                if is_root:
                    continue

                location_name = location.complete_name or ""
                current_best = group_best_location.get(group_key)
                if current_best is None or location_name > current_best:
                    group_best_location[group_key] = location_name

            def move_sort_key(move):
                location = move.location_id
                location_name = location.complete_name if location else ""

                sale_line_id = move.sale_line_id.id if "sale_line_id" in move._fields and move.sale_line_id else 0
                group_key = (move.product_id.id, sale_line_id)

                group_location_name = group_best_location.get(group_key)
                is_root = bool(root_location and location and location.id == root_location.id)

                if group_location_name:
                    group_rank = 0
                    group_location_sort = group_location_name
                elif not is_root:
                    group_rank = 0
                    group_location_sort = location_name
                else:
                    group_rank = 1
                    group_location_sort = ""

                line_rank = 1 if is_root and group_location_name else 0

                return (
                    group_rank,
                    desc_text(group_location_sort),
                    group_key,
                    line_rank,
                    desc_text(location_name),
                    move.sequence or 0,
                    move.id,
                )

            sorted_moves = moves.sorted(key=move_sort_key)

            next_order = order_step
            for move in sorted_moves:
                move.write({
                    "sg_dispatch_order": next_order,
                    "sequence": next_order,
                })
                next_order += order_step


    def action_assign(self):
        self._sg_prepare_dispatch_route_moves()
        return super().action_assign()

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

        # Ordenar las líneas que se envían al barcode.
        move_line_records_sorted = sorted(
            move_line_records,
            key=lambda ml: (
                ml.get("sg_dispatch_order", 999999),
                ml.get("id", 999999),
            ),
        )
        records["stock.move.line"] = move_line_records_sorted

        # Reordenar también el listado de move_line_ids dentro del picking,
        # para que el frontend reciba el mismo orden desde el registro principal.
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
