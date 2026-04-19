from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_is_zero, float_compare


class SgDispatchRoute(models.Model):
    _name = "sg.dispatch.route"
    _description = "Ruta de despacho"
    _order = "warehouse_id, sequence, id"

    name = fields.Char(
        string="Nombre",
        required=True,
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
    )

    sequence = fields.Integer(
        string="Secuencia",
        default=10,
    )

    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Almacén",
        required=True,
    )

    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Tipo de operación",
        domain="[('warehouse_id', '=', warehouse_id)]",
        required=True,
    )

    root_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación raíz",
        required=True,
        domain="[('usage', '=', 'internal')]",
    )

    strategy = fields.Selection(
        [
            ("max_qty", "Mayor cantidad disponible"),
        ],
        string="Estrategia",
        required=True,
        default="max_qty",
    )

    exclude_line_ids = fields.One2many(
        "sg.dispatch.route.exclude.line",
        "route_id",
        string="Ubicaciones excluidas",
    )

    note = fields.Text(
        string="Notas",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )

    excluded_location_ids = fields.Many2many(
        "stock.location",
        compute="_compute_excluded_location_ids",
        string="Resumen ubicaciones excluidas",
        store=False,
    )

    _sql_constraints = [
        (
            "sg_dispatch_route_name_warehouse_unique",
            "unique(name, warehouse_id, company_id)",
            "Ya existe una ruta con este nombre para ese almacén en esta compañía.",
        ),
    ]

    @api.depends("exclude_line_ids.location_id")
    def _compute_excluded_location_ids(self):
        for route in self:
            route.excluded_location_ids = route.exclude_line_ids.mapped("location_id")

    @api.constrains("root_location_id")
    def _check_root_location_internal(self):
        for route in self:
            if route.root_location_id and route.root_location_id.usage != "internal":
                raise ValidationError(_("La ubicación raíz debe ser de tipo interna."))

    @api.constrains("picking_type_id", "warehouse_id")
    def _check_picking_type_warehouse(self):
        for route in self:
            if route.picking_type_id and route.warehouse_id:
                if route.picking_type_id.warehouse_id != route.warehouse_id:
                    raise ValidationError(
                        _("El tipo de operación debe pertenecer al mismo almacén de la ruta.")
                    )

    @api.constrains("exclude_line_ids", "root_location_id")
    def _check_excluded_locations_under_root(self):
        for route in self:
            if not route.root_location_id:
                continue

            root_path = route.root_location_id.parent_path or ""
            root_id = route.root_location_id.id

            for line in route.exclude_line_ids:
                location = line.location_id
                if not location:
                    continue

                if location.usage != "internal":
                    raise ValidationError(_("Solo puedes excluir ubicaciones internas."))

                same_location = location.id == root_id
                is_child = (location.parent_path or "").startswith(root_path)

                if not same_location and not is_child:
                    raise ValidationError(
                        _(
                            "La ubicación excluida '%s' no pertenece al árbol de la ubicación raíz '%s'."
                        )
                        % (location.display_name, route.root_location_id.display_name)
                    )

    def _get_excluded_location_ids(self):
        self.ensure_one()

        excluded_locations = self.exclude_line_ids.mapped("location_id")
        excluded_all_ids = set()

        for ex_loc in excluded_locations:
            child_locations = self.env["stock.location"].search([
                ("id", "child_of", ex_loc.id),
                ("usage", "=", "internal"),
            ])
            excluded_all_ids.update(child_locations.ids)

        return excluded_all_ids

    def get_candidate_locations(self, product=False):
        """
        Devuelve todas las ubicaciones internas válidas dentro del árbol de la raíz,
        excluyendo las ubicaciones bloqueadas y sus hijas.
        """
        self.ensure_one()

        domain = [
            ("id", "child_of", self.root_location_id.id),
            ("usage", "=", "internal"),
        ]
        locations = self.env["stock.location"].search(domain)

        excluded_all_ids = self._get_excluded_location_ids()
        if excluded_all_ids:
            locations = locations.filtered(lambda loc: loc.id not in excluded_all_ids)

        return locations

    def get_child_candidate_locations(self, product=False):
        """
        Devuelve solo las hijas/subhijas válidas de la raíz.
        La raíz NO entra aquí.
        """
        self.ensure_one()

        locations = self.get_candidate_locations(product=product)
        return locations.filtered(lambda loc: loc.id != self.root_location_id.id)

    def get_root_fallback_location(self):
        """
        Devuelve la ubicación raíz si no está excluida.
        Esta ubicación solo se usa al final, cuando las hijas no alcanzan.
        """
        self.ensure_one()

        if not self.root_location_id or self.root_location_id.usage != "internal":
            return self.env["stock.location"]

        excluded_all_ids = self._get_excluded_location_ids()
        if self.root_location_id.id in excluded_all_ids:
            return self.env["stock.location"]

        return self.root_location_id

    def _get_available_qty_in_location(self, product, location):
        """Cantidad disponible en la UoM base del producto para una ubicación exacta."""
        self.ensure_one()

        quants = self.env["stock.quant"].search([
            ("product_id", "=", product.id),
            ("location_id", "=", location.id),
        ])

        qty_available = sum(quants.mapped("quantity")) - sum(quants.mapped("reserved_quantity"))
        return max(qty_available, 0.0)

    def get_locations_sorted_by_available_qty(self, product, locations=None):
        self.ensure_one()

        result = []
        locations = locations if locations is not None else self.get_candidate_locations(product)

        for location in locations:
            qty_available = self._get_available_qty_in_location(product, location)
            if float_compare(
                qty_available,
                0.0,
                precision_rounding=product.uom_id.rounding,
            ) > 0:
                result.append({
                    "location": location,
                    "available_qty": qty_available,
                })

        result.sort(key=lambda x: x["available_qty"], reverse=True)
        return result

    def get_allocation_plan(self, product, needed_qty):
        """
        Plan de asignación:

        1) Primero usa solo ubicaciones hijas válidas, ordenadas de mayor a menor.
        2) Si aún falta cantidad, usa la ubicación raíz al final.
        3) Nunca usa ubicaciones excluidas.

        Devuelve algo como:
        [
            {"location": loc_hija_1, "qty": 27.0},
            {"location": loc_hija_2, "qty": 3.0},
        ]
        """
        self.ensure_one()

        if float_is_zero(needed_qty, precision_rounding=product.uom_id.rounding):
            return []

        remaining_qty = needed_qty
        plan = []

        # 1) Hijas primero
        child_locations = self.get_child_candidate_locations(product=product)
        child_items = self.get_locations_sorted_by_available_qty(
            product=product,
            locations=child_locations,
        )

        for item in child_items:
            available_qty = item["available_qty"]
            take_qty = min(available_qty, remaining_qty)

            if float_compare(
                take_qty,
                0.0,
                precision_rounding=product.uom_id.rounding,
            ) <= 0:
                continue

            plan.append({
                "location": item["location"],
                "qty": take_qty,
            })

            remaining_qty -= take_qty

            if float_compare(
                remaining_qty,
                0.0,
                precision_rounding=product.uom_id.rounding,
            ) <= 0:
                return plan

        # 2) Luego la raíz
        root_location = self.get_root_fallback_location()
        if root_location:
            root_available_qty = self._get_available_qty_in_location(product, root_location)

            if float_compare(
                root_available_qty,
                0.0,
                precision_rounding=product.uom_id.rounding,
            ) > 0:
                take_qty = min(root_available_qty, remaining_qty)

                if float_compare(
                    take_qty,
                    0.0,
                    precision_rounding=product.uom_id.rounding,
                ) > 0:
                    plan.append({
                        "location": root_location,
                        "qty": take_qty,
                    })

        return plan

    @api.model
    def get_applicable_route(self, warehouse, picking_type):
        domain = [
            ("active", "=", True),
            ("warehouse_id", "=", warehouse.id),
            ("company_id", "=", warehouse.company_id.id),
        ]
        if picking_type:
            domain.append(("picking_type_id", "=", picking_type.id))
        return self.search(domain, order="sequence, id", limit=1)