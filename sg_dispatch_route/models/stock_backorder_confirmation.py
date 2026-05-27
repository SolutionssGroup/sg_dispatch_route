from odoo import models


class StockBackorderConfirmation(models.TransientModel):
    _inherit = "stock.backorder.confirmation"

    def process(self):
        pickings = self.pick_ids
        result = super().process()
        pickings._sg_release_pending_dispatch_reservations()
        return result
