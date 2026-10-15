{
    "name": "SG Dispatch Route - Torpinsa",
    "version": "17.0.1.0.0",
    "summary": "Despacho guiado sin reserva para Torpinsa",
    "description": """
Personalizacion exclusiva de Torpinsa sobre sg_dispatch_route:
- La ruta se calcula al confirmar el picking de salida (sin reservar).
- Orden de ruta por nivel, tramo y posicion (numerico, de mayor a menor).
- Se oculta el boton Comprobar disponibilidad.
- El conduce muestra solo lo despachado.
- La app de Codigo de barras ya no filtra por "Preparado" (no hay reservas).
    """,
    "author": "Solutions Group",
    "website": "https://www.solutionsgroup.do",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "depends": [
        "stock_barcode",
        "sg_dispatch_route",
        "sg_barcode_dispatch_order",
    ],
    "data": [
        "views/stock_picking_views.xml",
        "data/barcode_action.xml",
        "views/report_delivery_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sg_dispatch_route_torpinsa/static/src/components/sg_pick_dialog.js",
            "sg_dispatch_route_torpinsa/static/src/components/sg_pick_dialog.xml",
            "sg_dispatch_route_torpinsa/static/src/models/barcode_picking_model_patch.js",
            "sg_dispatch_route_torpinsa/static/src/models/line_component_patch.js",
            "sg_dispatch_route_torpinsa/static/src/models/main_component_patch.js",
            "sg_dispatch_route_torpinsa/static/src/xml/sg_recoger_bar.xml",
            "sg_dispatch_route_torpinsa/static/src/scss/sg_pick.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
