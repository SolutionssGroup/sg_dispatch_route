from odoo import fields, models
from odoo.exceptions import UserError


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
