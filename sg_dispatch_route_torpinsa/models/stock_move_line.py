from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    sg_demand_qty = fields.Float(
        string="Cantidad pedida",
        related="move_id.product_uom_qty",
        readonly=True,
    )

    sg_is_route_root = fields.Boolean(
        string="Sale de la raiz de la ruta",
        compute="_compute_sg_is_route_root",
    )

    @api.depends("location_id", "picking_id.sg_dispatch_route_id.root_location_id")
    def _compute_sg_is_route_root(self):
        for line in self:
            root = line.picking_id.sg_dispatch_route_id.root_location_id
            line.sg_is_route_root = bool(root and line.location_id == root)

    def _get_fields_stock_barcode(self):
        fields_list = super()._get_fields_stock_barcode()
        for name in ("sg_demand_qty", "sg_is_route_root"):
            if name not in fields_list:
                fields_list.append(name)
        return fields_list
