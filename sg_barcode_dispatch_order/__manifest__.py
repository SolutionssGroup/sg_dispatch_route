{
    "name": "SG Barcode Dispatch Order",
    "version": "17.0.1.0.0",
    "summary": "Orden personalizado de líneas en Barcode para despacho",
    "description": """
Módulo aislado para trabajar únicamente la lógica visual de orden
en el módulo Barcode, reutilizando sg_dispatch_order enviado por
sg_dispatch_route.
    """,
    "author": "Solutions Group",
    "website": "https://www.solutionsgroup.do",
    "category": "Inventory/Barcode",
    "license": "LGPL-3",
    "depends": [
        "stock_barcode",
        "sg_dispatch_route",
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "sg_barcode_dispatch_order/static/src/models/barcode_model_patch.js",
            "sg_barcode_dispatch_order/static/src/models/barcode_picking_model_patch.js",
            "sg_barcode_dispatch_order/static/src/scss/barcode_highlight.scss",
            "sg_barcode_dispatch_order/static/src/xml/barcode_line_highlight.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
