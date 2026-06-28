import unicodedata

from odoo import api, models
from odoo.tools.safe_eval import safe_eval


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    def _sg_normalize_dispatch_type_name(self, value):
        value = unicodedata.normalize("NFKD", value or "")
        value = value.encode("ascii", "ignore").decode("ascii")
        return value.strip().lower()

    def _sg_is_inprotec_dispatch_type(self):
        self.ensure_one()

        warehouse = self.warehouse_id
        warehouse_names = {
            self._sg_normalize_dispatch_type_name(warehouse.name),
            self._sg_normalize_dispatch_type_name(warehouse.code),
        }
        display_name = self._sg_normalize_dispatch_type_name(self.display_name)
        operation_name = self._sg_normalize_dispatch_type_name(self.name)
        display_operation_name = (
            display_name.split(":", 1)[1].strip()
            if ":" in display_name
            else ""
        )

        return (
            self.code == "outgoing"
            and operation_name in (
                "delivery orders",
                "despachos",
                "ordenes de entrega",
            )
            and (
                any("inprotec" in name for name in warehouse_names)
                or display_name.startswith("inprotec:")
                or display_operation_name == operation_name
                and display_name.startswith("inprotec")
            )
        )

    def get_action_picking_tree_ready(self):
        action = super().get_action_picking_tree_ready()

        if not self._sg_is_inprotec_dispatch_type():
            return action

        context = action.get("context") or {}
        if isinstance(context, str):
            context = safe_eval(context)
        else:
            context = dict(context)

        for search_default in (
            "search_default_available",
            "search_default_to_do_transfers",
            "search_default_picking_type_id",
            "search_default_my_transfers",
            "search_default_my_picking",
            "search_default_user_id",
            "search_default_responsible",
            "search_default_assigned_to_me",
        ):
            context.pop(search_default, None)

        context.pop("default_user_id", None)

        context.update({
            "default_picking_type_id": self.id,
            "default_company_id": self.company_id.id,
        })

        action.update({
            "domain": [
                ("picking_type_id", "=", self.id),
                ("state", "=", "assigned"),
            ],
            "context": context,
        })
        return action

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
