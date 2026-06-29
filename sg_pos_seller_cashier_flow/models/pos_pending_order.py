from odoo import api, fields, models
from odoo.exceptions import UserError


class PosPendingOrder(models.Model):
    _name = "sg.pos.pending.order"
    _description = "Pedido pendiente POS para caja"
    _order = "create_date desc"

    name = fields.Char(
        string="Número",
        required=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("sg.pos.pending.order") or "Nuevo",
    )
    customer_note_name = fields.Char(string="Nombre informativo")
    partner_id = fields.Many2one("res.partner", string="Cliente")
    seller_id = fields.Many2one("res.users", string="Vendedor", default=lambda self: self.env.user)
    seller_pos_config_id = fields.Many2one("pos.config", string="POS vendedor")
    cashier_pos_config_id = fields.Many2one("pos.config", string="POS caja")
    state = fields.Selection(
        [
            ("sent", "Pendiente en Caja"),
            ("in_cashier", "En Caja"),
            ("returned", "Devuelto a Vendedor"),
            ("paid", "Facturado"),
            ("cancel", "Cancelado"),
        ],
        string="Estado",
        default="sent",
        required=True,
    )
    amount_total = fields.Float(string="Total", digits="Product Price")
    line_ids = fields.One2many("sg.pos.pending.order.line", "pending_order_id", string="Líneas")

    def _export_for_pos(self, include_lines=True):
        self.ensure_one()
        values = {
            "id": self.id,
            "name": self.name,
            "customer_note_name": self.customer_note_name or "",
            "partner_id": self.partner_id.id or False,
            "seller_name": self.seller_id.name or "",
            "amount_total": self.amount_total,
            "state": self.state,
            "create_date": fields.Datetime.to_string(self.create_date),
        }
        if include_lines:
            values["lines"] = [
                {
                    "product_id": line.product_id.id,
                    "qty": line.qty,
                    "price_unit": line.price_unit,
                    "discount": line.discount,
                    "location_id": line.location_id.id or False,
                    "location_name": line.location_id.complete_name or line.location_id.display_name or "",
                        }
                for line in self.line_ids
            ]
        return values

    @api.model
    def get_sent_orders_for_pos(self, cashier_pos_config_id=False):
        config = self.env["pos.config"].browse(cashier_pos_config_id)
        if not config.exists():
            raise UserError("No se encontró la configuración POS de Caja.")
        if config.sg_pos_flow_role != "cashier":
            raise UserError("Solo un POS con rol Caja puede cargar pedidos pendientes.")

        pending_orders = self.search([("state", "=", "sent")], order="create_date asc")
        return [pending_order._export_for_pos(include_lines=False) for pending_order in pending_orders]

    @api.model
    def get_returned_orders_for_pos(self, seller_pos_config_id=False):
        config = self.env["pos.config"].browse(seller_pos_config_id)
        if not config.exists():
            raise UserError("No se encontró la configuración POS del vendedor.")
        if config.sg_pos_flow_role != "seller":
            raise UserError("Solo un POS con rol Vendedores puede recuperar pedidos devueltos.")

        returned_orders = self.search([("state", "=", "returned")], order="write_date asc")
        return [pending_order._export_for_pos(include_lines=False) for pending_order in returned_orders]

    @api.model
    def load_order_for_cashier(self, pending_order_id, cashier_pos_config_id=False):
        config = self.env["pos.config"].browse(cashier_pos_config_id)
        if not config.exists():
            raise UserError("No se encontró la configuración POS de Caja.")
        if config.sg_pos_flow_role != "cashier":
            raise UserError("Solo un POS con rol Caja puede cargar pedidos pendientes.")

        self.env.cr.execute(
            """
                UPDATE sg_pos_pending_order
                   SET state = 'in_cashier',
                       cashier_pos_config_id = %s,
                       write_date = NOW(),
                       write_uid = %s
                 WHERE id = %s
                   AND state = 'sent'
             RETURNING id
            """,
            (config.id, self.env.uid, pending_order_id),
        )
        row = self.env.cr.fetchone()
        if not row:
            pending_order = self.browse(pending_order_id)
            if not pending_order.exists():
                raise UserError("No se encontró el pedido pendiente.")
            if pending_order.state == "in_cashier":
                raise UserError("Este pedido ya está cargado en otra Caja.")
            if pending_order.state in ("paid", "cancel"):
                raise UserError("Este pedido ya no se puede cargar.")
            raise UserError("Este pedido ya no está pendiente en Caja.")
        return self.browse(row[0])._export_for_pos()

    @api.model
    def load_returned_order_for_seller(self, pending_order_id, seller_pos_config_id=False):
        config = self.env["pos.config"].browse(seller_pos_config_id)
        if not config.exists():
            raise UserError("No se encontró la configuración POS del vendedor.")
        if config.sg_pos_flow_role != "seller":
            raise UserError("Solo un POS con rol Vendedores puede recuperar pedidos devueltos.")

        pending_order = self.browse(pending_order_id)
        if not pending_order.exists():
            raise UserError("No se encontró el pedido devuelto.")
        if pending_order.state != "returned":
            raise UserError("Solo se pueden recuperar pedidos devueltos a Vendedor.")
        return pending_order._export_for_pos()

    @api.model
    def return_to_seller(self, pending_order_id, cashier_pos_config_id=False):
        config = self.env["pos.config"].browse(cashier_pos_config_id)
        if not config.exists():
            raise UserError("No se encontró la configuración POS de Caja.")
        if config.sg_pos_flow_role != "cashier":
            raise UserError("Solo un POS con rol Caja puede devolver pedidos a Vendedor.")

        pending_order = self.browse(pending_order_id)
        if not pending_order.exists():
            raise UserError("No se encontró el pedido pendiente.")
        if pending_order.state == "paid":
            raise UserError("Un pedido facturado no se puede devolver.")
        if pending_order.state == "cancel":
            raise UserError("Un pedido cancelado no se puede devolver.")
        if pending_order.state != "in_cashier":
            raise UserError("Solo se pueden devolver pedidos que están en Caja.")

        pending_order.write(
            {
                "state": "returned",
                "cashier_pos_config_id": config.id,
            }
        )
        return True

    @api.model
    def release_from_cashier(self, pending_order_id, cashier_pos_config_id=False):
        config = self.env["pos.config"].browse(cashier_pos_config_id)
        if not config.exists():
            raise UserError("No se encontró la configuración POS de Caja.")
        if config.sg_pos_flow_role != "cashier":
            raise UserError("Solo un POS con rol Caja puede liberar pedidos pendientes.")

        pending_order = self.browse(pending_order_id)
        if not pending_order.exists():
            raise UserError("No se encontró el pedido pendiente.")
        pending_order.invalidate_recordset(["state", "cashier_pos_config_id"])
        if pending_order.state == "paid":
            raise UserError("Un pedido facturado no se puede liberar.")
        if pending_order.state == "cancel":
            raise UserError("Un pedido cancelado no se puede liberar.")
        if pending_order.state != "in_cashier":
            return True

        pending_order.write(
            {
                "state": "sent",
                "cashier_pos_config_id": False,
            }
        )
        return True

    @api.model
    def create_from_pos_order_data(self, order_data):
        config = self.env["pos.config"].browse(order_data.get("seller_pos_config_id"))
        if not config.exists():
            raise UserError("No se encontró la configuración POS del vendedor.")
        if config.sg_pos_flow_role != "seller":
            raise UserError("Solo un POS con rol Vendedores puede enviar pedidos a Caja.")

        lines_data = order_data.get("lines") or []
        if not lines_data:
            raise UserError("No puedes enviar a Caja un pedido sin líneas.")

        line_commands = []
        for line in lines_data:
            product = self.env["product.product"].browse(line.get("product_id"))
            if not product.exists():
                raise UserError("Una línea del pedido no tiene producto válido.")
            line_commands.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "qty": line.get("qty") or 0.0,
                        "price_unit": line.get("price_unit") or 0.0,
                        "discount": line.get("discount") or 0.0,
                        "product_uom_id": line.get("product_uom_id") or product.uom_id.id,
                        "location_id": line.get("location_id") or False,
                        "subtotal": line.get("subtotal") or 0.0,
                    },
                )
            )

        pending_order_id = order_data.get("pending_order_id")
        vals = {
            "customer_note_name": order_data.get("customer_note_name") or "",
            "partner_id": order_data.get("partner_id") or False,
            "seller_id": self.env.user.id,
            "seller_pos_config_id": config.id,
            "cashier_pos_config_id": False,
            "amount_total": order_data.get("amount_total") or 0.0,
            "state": "sent",
            "line_ids": [(5, 0, 0)] + line_commands,
        }
        if pending_order_id:
            pending_order = self.browse(pending_order_id)
            if not pending_order.exists():
                raise UserError("No se encontró el pedido pendiente a actualizar.")
            if pending_order.state == "paid":
                raise UserError("Un pedido facturado no se puede editar ni reenviar.")
            if pending_order.state == "cancel":
                raise UserError("Un pedido cancelado no se puede reenviar.")
            if pending_order.state not in ("returned", "sent"):
                raise UserError("Solo se pueden actualizar pedidos pendientes o devueltos a Vendedor.")
            pending_order.write(vals)
        else:
            vals["line_ids"] = line_commands
            pending_order = self.create(vals)
        return {"id": pending_order.id, "name": pending_order.name}

    def action_cancel(self):
        for pending_order in self:
            if pending_order.state == "paid":
                raise UserError("Un pedido facturado no se puede cancelar.")
        self.write({"state": "cancel"})

    def action_mark_paid(self):
        for pending_order in self:
            if pending_order.state in ("cancel", "returned"):
                raise UserError("Este pedido no se puede marcar como facturado desde su estado actual.")
        self.write({"state": "paid"})


class PosPendingOrderLine(models.Model):
    _name = "sg.pos.pending.order.line"
    _description = "Línea de pedido pendiente POS"

    pending_order_id = fields.Many2one(
        "sg.pos.pending.order",
        string="Pedido pendiente",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    product_uom_id = fields.Many2one("uom.uom", string="UdM")
    qty = fields.Float(string="Cantidad", default=1.0)
    price_unit = fields.Float(string="Precio unitario", digits="Product Price")
    discount = fields.Float(string="Descuento (%)")
    location_id = fields.Many2one("stock.location", string="Ubicación seleccionada")
    subtotal = fields.Float(string="Subtotal", compute="_compute_subtotal", store=True)

    @api.depends("qty", "price_unit", "discount")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.price_unit * (1 - (line.discount or 0.0) / 100.0)

    @api.model_create_multi
    def create(self, vals_list):
        pending_order_ids = [vals.get("pending_order_id") for vals in vals_list if vals.get("pending_order_id")]
        if pending_order_ids:
            locked_orders = self.env["sg.pos.pending.order"].browse(pending_order_ids).filtered(
                lambda order: order.state not in ("sent", "returned")
            )
            if locked_orders:
                raise UserError("Solo se pueden modificar líneas de pedidos pendientes o devueltos a Vendedor.")
        return super().create(vals_list)

    def _check_pending_order_can_update_lines(self):
        locked_lines = self.filtered(
            lambda line: line.pending_order_id.state not in ("sent", "returned")
        )
        if locked_lines:
            raise UserError("Solo se pueden modificar líneas de pedidos pendientes o devueltos a Vendedor.")

    def write(self, vals):
        if vals:
            self._check_pending_order_can_update_lines()
        return super().write(vals)

    def unlink(self):
        self._check_pending_order_can_update_lines()
        return super().unlink()
