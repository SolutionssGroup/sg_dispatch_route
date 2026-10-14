{
    "name": "SG Dispatch Route - Torpinsa",
    "version": "17.0.1.0.0",
    "summary": "Despacho guiado sin reserva para Torpinsa",
    "description": """
Personalizacion exclusiva de Torpinsa sobre sg_dispatch_route:
- La ruta se calcula al confirmar el picking de salida (sin reservar).
- Orden de ruta por nivel, tramo y posicion (numerico, de mayor a menor).
- Se oculta el boton Comprobar disponibilidad.
    """,
    "author": "Solutions Group",
    "website": "https://www.solutionsgroup.do",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "depends": [
        "sg_dispatch_route",
    ],
    "data": [
        "views/stock_picking_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
