import logging

from odoo import models


_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _create_move_from_pos_order_lines(self, lines):
        pending_orders = lines.mapped("order_id").filtered("sg_pending_order_id")
        if not pending_orders:
            return super()._create_move_from_pos_order_lines(lines)

        native_lines = lines.filtered(lambda line: not line.order_id.sg_pending_order_id)
        if native_lines:
            super()._create_move_from_pos_order_lines(native_lines)

        for order in pending_orders:
            order_lines = lines.filtered(lambda line: line.order_id == order)
            self._sg_create_move_from_pending_pos_order_lines(order, order_lines)

    def _sg_create_move_from_pending_pos_order_lines(self, order, lines):
        self.ensure_one()

        pending_line_by_pos_line = order._sg_pending_order_line_by_pos_line()
        grouped_lines = {}
        for line in lines.sorted(lambda order_line: (order_line.product_id.id, order_line.id)):
            pending_line = pending_line_by_pos_line.get(line.id)
            location = pending_line.location_id if pending_line and line.product_id.type == "product" else False
            if pending_line and line.product_id.type == "product" and not location:
                _logger.warning(
                    "POS pending order %s line %s has no source location for product %s; using native POS location.",
                    order.sg_pending_order_id.name,
                    pending_line.id,
                    line.product_id.display_name,
                )
            key = (line.product_id.id, location.id if location else False)
            grouped_lines.setdefault(key, self.env["pos.order.line"])
            grouped_lines[key] |= line

        moves = self.env["stock.move"]
        for (product_id, location_id), order_lines in grouped_lines.items():
            vals = self._prepare_stock_move_vals(order_lines[0], order_lines)
            if location_id and order_lines[0].product_id.type == "product":
                vals["location_id"] = location_id
            group_moves = self.env["stock.move"].create(vals)._action_confirm()
            group_moves._add_mls_related_to_order(order_lines, are_qties_done=True)
            moves |= group_moves
        moves.picked = True
        self._link_owner_on_return_picking(lines)
