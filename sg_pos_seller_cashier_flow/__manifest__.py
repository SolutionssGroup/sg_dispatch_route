{
    "name": "SG POS Seller Cashier Flow",
    "version": "17.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Flujo POS vendedores y caja con pedidos pendientes",
    "author": "Solutions Group",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
        "stock",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/pos_config_views.xml",
        "views/stock_location_views.xml",
        "views/pos_pending_order_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "sg_pos_seller_cashier_flow/static/src/app/pos_location_suggestion/pos_location_suggestion.js",
            "sg_pos_seller_cashier_flow/static/src/app/pos_location_suggestion/pos_location_suggestion.xml",
            "sg_pos_seller_cashier_flow/static/src/app/send_to_cashier_button/send_to_cashier_button.js",
            "sg_pos_seller_cashier_flow/static/src/app/send_to_cashier_button/send_to_cashier_button.xml",
            "sg_pos_seller_cashier_flow/static/src/app/pending_orders_button/pending_orders_button.js",
            "sg_pos_seller_cashier_flow/static/src/app/pending_orders_button/pending_orders_button.xml",
            "sg_pos_seller_cashier_flow/static/src/app/hide_payment_button/hide_payment_button.xml",
            "sg_pos_seller_cashier_flow/static/src/app/seller_close_session/seller_close_session.js",
        ],
    },
    "installable": True,
    "application": False,
}
