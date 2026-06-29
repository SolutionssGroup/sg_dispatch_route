from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class PosOrder(models.Model):
    _inherit = "pos.order"

    sg_pending_order_id = fields.Many2one(
        "sg.pos.pending.order",
        string="Pedido pendiente POS",
        readonly=True,
        copy=False,
    )

    def _order_fields(self, ui_order):
        fields = super()._order_fields(ui_order)
        fields["sg_pending_order_id"] = ui_order.get("sg_pending_order_id") or False
        return fields

    def _process_order(self, order, draft, existing_order):
        order_id = super()._process_order(order, draft, existing_order)
        if draft:
            return order_id

        pos_order = self.browse(order_id)
        pending_order = pos_order.sg_pending_order_id
        if not pending_order:
            return order_id

        if pending_order.state in ("paid", "cancel", "returned"):
            raise UserError("Este pedido pendiente no se puede facturar desde su estado actual.")
        if pending_order.state != "in_cashier":
            raise UserError("El pedido pendiente debe estar En Caja para poder facturarse.")

        vals = {"state": "paid"}
        config = pos_order.session_id.config_id
        if config and config.sg_pos_flow_role == "cashier":
            vals["cashier_pos_config_id"] = config.id
        pending_order.write(vals)
        return order_id

    def _sg_pending_order_line_by_pos_line(self):
        self.ensure_one()
        if not self.sg_pending_order_id:
            return {}

        pending_lines = self.sg_pending_order_id.line_ids.sorted("id")
        pending_by_pos_line = {}
        used_pending_line_ids = set()
        for pos_line in self.lines.sorted("id"):
            pending_line = pending_lines.filtered(
                lambda line: line.id not in used_pending_line_ids
                and self._sg_pending_line_matches_pos_line(line, pos_line)
            )[:1]
            if pending_line:
                pending_by_pos_line[pos_line.id] = pending_line
                used_pending_line_ids.add(pending_line.id)
        return pending_by_pos_line

    def _sg_pending_line_matches_pos_line(self, pending_line, pos_line):
        self.ensure_one()
        product = pos_line.product_id
        qty_rounding = product.uom_id.rounding
        currency_rounding = self.currency_id.rounding
        discount_rounding = 0.00001
        return (
            pending_line.product_id == product
            and float_compare(pending_line.qty, pos_line.qty, precision_rounding=qty_rounding) == 0
            and float_compare(pending_line.price_unit, pos_line.price_unit, precision_rounding=currency_rounding) == 0
            and float_compare(pending_line.discount, pos_line.discount, precision_rounding=discount_rounding) == 0
        )
