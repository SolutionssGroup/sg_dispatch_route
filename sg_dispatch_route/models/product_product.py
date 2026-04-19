from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _sg_get_dispatch_route_from_context(self):
        """
        Busca la ruta de despacho aplicable.
        Prioridad:
        1) almacén en contexto
        2) primer almacén de la compañía actual
        3) primer almacén disponible

        Esto permite que qty_available / free_qty / virtual_available
        salgan filtrados incluso en pantallas donde Odoo no envía
        explícitamente el contexto warehouse.
        """
        warehouse_id = self.env.context.get("warehouse") or self.env.context.get("warehouse_id")
        warehouse_model = self.env["stock.warehouse"]

        warehouse = False
        if warehouse_id:
            warehouse = warehouse_model.browse(warehouse_id)
            if not warehouse.exists():
                warehouse = False

        if not warehouse:
            warehouse = warehouse_model.search(
                [("company_id", "=", self.env.company.id)],
                order="id",
                limit=1,
            )

        if not warehouse:
            warehouse = warehouse_model.search([], order="id", limit=1)

        if not warehouse or not warehouse.out_type_id:
            return self.env["sg.dispatch.route"]

        return self.env["sg.dispatch.route"].get_applicable_route(
            warehouse=warehouse,
            picking_type=warehouse.out_type_id,
        )

    def _sg_get_excluded_qty_map(self, route):
        """
        Devuelve por producto:
        - qty_excluded: cantidad a mano en ubicaciones excluidas
        - free_excluded: cantidad libre en ubicaciones excluidas
        """
        result = {
            product.id: {
                "qty_excluded": 0.0,
                "free_excluded": 0.0,
            }
            for product in self
        }

        if not route:
            return result

        excluded_location_ids = list(route._get_excluded_location_ids())
        if not excluded_location_ids:
            return result

        quants = self.env["stock.quant"].search([
            ("product_id", "in", self.ids),
            ("location_id", "in", excluded_location_ids),
        ])

        for quant in quants:
            vals = result.setdefault(quant.product_id.id, {
                "qty_excluded": 0.0,
                "free_excluded": 0.0,
            })
            vals["qty_excluded"] += quant.quantity
            vals["free_excluded"] += max(quant.quantity - quant.reserved_quantity, 0.0)

        return result

    def _compute_quantities_dict(
        self,
        lot_id=None,
        owner_id=None,
        package_id=None,
        from_date=False,
        to_date=False,
    ):
        """
        Ajusta las cantidades visibles del producto para que las ubicaciones
        excluidas de la ruta NO cuenten como disponible principal.
        """
        res = super()._compute_quantities_dict(
            lot_id=lot_id,
            owner_id=owner_id,
            package_id=package_id,
            from_date=from_date,
            to_date=to_date,
        )

        route = self._sg_get_dispatch_route_from_context()
        if not route:
            return res

        excluded_qty_map = self._sg_get_excluded_qty_map(route)

        for product in self:
            product_res = res.get(product.id)
            if not product_res:
                continue

            excluded_vals = excluded_qty_map.get(product.id, {})
            qty_excluded = excluded_vals.get("qty_excluded", 0.0)
            free_excluded = excluded_vals.get("free_excluded", 0.0)

            if qty_excluded:
                product_res["qty_available"] = max(
                    product_res.get("qty_available", 0.0) - qty_excluded,
                    0.0,
                )
                product_res["virtual_available"] = max(
                    product_res.get("virtual_available", 0.0) - qty_excluded,
                    0.0,
                )

            if free_excluded:
                product_res["free_qty"] = max(
                    product_res.get("free_qty", 0.0) - free_excluded,
                    0.0,
                )

        return res
