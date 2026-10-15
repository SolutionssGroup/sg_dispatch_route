from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    sg_demand_qty = fields.Float(
        string="Cantidad pedida",
        related="move_id.product_uom_qty",
        readonly=True,
    )

    def _get_fields_stock_barcode(self):
        fields_list = super()._get_fields_stock_barcode()
        if "sg_demand_qty" not in fields_list:
            fields_list.append("sg_demand_qty")
        return fields_list
