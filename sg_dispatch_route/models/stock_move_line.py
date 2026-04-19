from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"
    _order = "sg_dispatch_order, id"

    sg_dispatch_order = fields.Integer(
        string="Orden ruta despacho",
        related="move_id.sg_dispatch_order",
        store=True,
        readonly=True,
        index=True,
    )

    def _get_fields_stock_barcode(self):
        fields_list = super()._get_fields_stock_barcode()
        if "sg_dispatch_order" not in fields_list:
            fields_list.append("sg_dispatch_order")
        return fields_list
