from odoo import api, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    @api.model
    def _sg_configure_outgoing_reservation_method_manual(self):
        self.flush_model(["code", "reservation_method"])
        self.env.cr.execute(
            """
            UPDATE stock_picking_type
               SET reservation_method = 'manual'
             WHERE code = 'outgoing'
               AND reservation_method IN ('at_confirm', 'by_date')
         RETURNING id
            """
        )
        picking_types = self.browse([row[0] for row in self.env.cr.fetchall()])
        picking_types.invalidate_recordset(["reservation_method"])
        return True
