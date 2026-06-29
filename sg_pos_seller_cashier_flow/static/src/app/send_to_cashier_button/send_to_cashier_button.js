/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class SendToCashierButton extends Component {
    static template = "sg_pos_seller_cashier_flow.SendToCashierButton";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("pos_notification");
    }

    async onClick() {
        const order = this.pos.get_order();
        const orderlines = order.get_orderlines();
        if (!orderlines.length) {
            this.notification.add(_t("No puedes enviar a Caja un pedido sin líneas."), 3000);
            return;
        }

        await this.orm.call("sg.pos.pending.order", "create_from_pos_order_data", [
            {
                pending_order_id: order.sg_pending_order_id || false,
                customer_note_name: "",
                partner_id: order.get_partner()?.id || false,
                seller_pos_config_id: this.pos.config.id,
                amount_total: order.get_total_with_tax(),
                lines: orderlines.map((line) => {
                    const product = line.get_product();
                    return {
                        product_id: product.id,
                        qty: line.get_quantity(),
                        price_unit: line.get_unit_price(),
                        discount: line.get_discount(),
                        product_uom_id: product.uom_id?.[0] || false,
                        subtotal: line.get_unit_price() * line.get_quantity() * (1 - line.get_discount() / 100),
                    };
                }),
            },
        ]);

        this.pos.removeOrder(order, false);
        this.pos.add_new_order();
        this.notification.add(_t("Pedido enviado a Caja"), 3000);
    }
}

ProductScreen.addControlButton({
    component: SendToCashierButton,
    condition: function () {
        return this.pos.config.sg_pos_flow_role === "seller";
    },
});
