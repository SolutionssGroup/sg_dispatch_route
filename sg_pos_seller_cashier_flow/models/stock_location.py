import re

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class StockLocation(models.Model):
    _inherit = "stock.location"

    _SG_POS_LOCATION_CODE_RE = re.compile(r"^\s*(\d+)\s*-\s*T(\d+)\s*-\s*(\d+)\s*$", re.IGNORECASE)

    sg_pos_pick_priority = fields.Integer(
        string="Prioridad picking POS",
        default=False,
        help="Menor número positivo = más cercana a despacho. 0 o vacío se deja al final.",
    )

    @api.model
    def _get_pos_location_distance_key(self, location):
        match = self._SG_POS_LOCATION_CODE_RE.match(location.name or "")
        if match:
            level, section, position = (int(value) for value in match.groups())
            return (0, level, section, position, "", location.complete_name or location.display_name or "")

        priority = location.sg_pos_pick_priority
        priority_key = priority if priority > 0 else 0
        return (
            1,
            priority <= 0,
            priority_key,
            location.complete_name or location.display_name or "",
        )

    @api.model
    def get_pos_suggested_location(self, product_id, seller_pos_config_id=False):
        config = self.env["pos.config"].browse(seller_pos_config_id)
        if not config.exists():
            raise UserError("No se encontró la configuración POS del vendedor.")
        if config.sg_pos_flow_role != "seller":
            raise UserError("La sugerencia de ubicación solo aplica en POS Vendedores.")

        product = self.env["product.product"].browse(product_id)
        if not product.exists():
            raise UserError("No se encontró el producto.")

        quants = self.env["stock.quant"].sudo().search(
            [
                ("product_id", "=", product.id),
                ("location_id.usage", "=", "internal"),
            ]
        )
        quantities_by_location = {}
        for quant in quants:
            available_qty = quant.quantity - quant.reserved_quantity
            if float_compare(available_qty, 0.0, precision_rounding=product.uom_id.rounding) <= 0:
                continue
            location = quant.location_id
            quantities_by_location.setdefault(location, 0.0)
            quantities_by_location[location] += available_qty

        candidates = [
            (location, available_qty)
            for location, available_qty in quantities_by_location.items()
            if float_compare(available_qty, 0.0, precision_rounding=product.uom_id.rounding) > 0
        ]
        if not candidates:
            return {
                "location_id": False,
                "location_name": "",
                "available_qty": 0.0,
            }

        location, available_qty = sorted(
            candidates,
            key=lambda item: self._get_pos_location_distance_key(item[0]),
        )[0]
        return {
            "location_id": location.id,
            "location_name": location.complete_name or location.display_name,
            "available_qty": available_qty,
        }
