from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _sg_prepare_dispatch_route_before_assign(self):
        # Torpinsa no reserva: la ruta se calcula una sola vez al confirmar
        # (stock_picking.py::_sg_torpinsa_plan_route). Si algo dispara una
        # reserva, se respeta el plan ya hecho y no se vuelve a partir.
        return
