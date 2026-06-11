{
    "name": "SG Dispatch Route",
    "version": "17.0.1.0.0",
    "summary": "Rutas de despacho por almacén con exclusión de ubicaciones internas",
    "description": """
Módulo para definir rutas de despacho por almacén.
Permite:
- definir una ubicación raíz por almacén
- excluir ubicaciones internas del flujo
- preparar una lógica de despacho basada en disponibilidad
    """,
    "author": "Solutions Group",
    "website": "https://www.solutionsgroup.do",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "sale_stock",
        "stock_barcode",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/menu.xml",
        "views/dispatch_route_views.xml",
        "views/stock_location_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_picking_type_views.xml",
        "views/stock_move_line_views.xml",
        "wizards/dispatch_reservation_cleanup_wizard_views.xml",
        "data/sequence.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
