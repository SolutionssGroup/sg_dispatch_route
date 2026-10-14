from odoo import models


class SgDispatchRoute(models.Model):
    _inherit = "sg.dispatch.route"

    def get_locations_sorted_by_dispatch_route(self, product, locations=None, planned=None):
        # La base ordena por complete_name (texto). Torpinsa: nivel, tramo y
        # posicion como numeros, de mayor a menor.
        result = super().get_locations_sorted_by_dispatch_route(
            product, locations=locations, planned=planned
        )
        result.sort(
            key=lambda x: (x["location"]._sg_route_sort_key(), x["location"].id),
            reverse=True,
        )
        return result
