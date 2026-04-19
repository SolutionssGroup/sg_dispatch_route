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

            for move in candidate_moves:
                move._sg_apply_dispatch_route(route)

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
