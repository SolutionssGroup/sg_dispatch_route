from odoo import _, fields, models
from odoo.exceptions import UserError


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

    def _action_done(self):
        """
        Red de seguridad final: un traslado interno cuya línea tiene el mismo
        origen y destino no mueve inventario pero queda 'Hecho'. El chequeo de
        stock_picking.button_validate no alcanza: si el traslado se valida
        directo desde borrador (AP/INT/03388, 19-oct-2026), las líneas se crean
        DESPUÉS de ese chequeo, al confirmar (Odoo reserva al confirmar y puede
        tomar la existencia de la misma ubicación de destino, por ejemplo
        Asignación). Aquí las líneas ya son las definitivas, así que se revisa
        justo antes de aplicarlas.
        """
        bad_lines = self.filtered(
            lambda ml: ml.picking_id
            and ml.picking_id.picking_type_id.code == "internal"
            and ml.quantity > 0
            and ml.location_id
            and ml.location_id == ml.location_dest_id
        )
        if bad_lines:
            details = "\n".join(
                "- %s (%s): %s -> %s" % (
                    ml.product_id.display_name,
                    ml.picking_id.name,
                    ml.location_id.display_name,
                    ml.location_dest_id.display_name,
                )
                for ml in bad_lines
            )
            raise UserError(
                _(
                    "No se puede validar: estas líneas tienen el mismo origen y destino "
                    "y no moverían inventario:\n%(lines)s\n\n"
                    "Lea la ubicación de origen correcta y luego la de destino.",
                    lines=details,
                )
            )
        return super()._action_done()
