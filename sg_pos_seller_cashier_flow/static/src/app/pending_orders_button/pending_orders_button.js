/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { Order } from "@point_of_sale/app/store/models";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class PendingOrdersPopup extends AbstractAwaitablePopup {
    static template = "sg_pos_seller_cashier_flow.PendingOrdersPopup";
    static defaultProps = {
        cancelText: _t("Cancelar"),
        title: _t("Pedidos Pendientes"),
        orders: [],
    };

    selectOrder(order) {
        this.props.close({ confirmed: true, payload: order });
    }
}

export class PendingOrdersButton extends Component {
    static template = "sg_pos_seller_cashier_flow.PendingOrdersButton";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.notification = useService("pos_notification");
    }

    async onClick() {
        const pendingOrders = await this.orm.call("sg.pos.pending.order", "get_sent_orders_for_pos", [
            this.pos.config.id,
        ]);
        if (!pendingOrders.length) {
            this.notification.add(_t("No hay pedidos pendientes."), 3000);
            return;
        }

        const { confirmed, payload: pendingOrder } = await this.popup.add(PendingOrdersPopup, {
            orders: pendingOrders,
        });
        if (!confirmed || !pendingOrder) {
            return;
        }

        try {
            const loadedOrder = await this.orm.call("sg.pos.pending.order", "load_order_for_cashier", [
                pendingOrder.id,
                this.pos.config.id,
            ]);
            await this.loadPendingOrder(loadedOrder);
            this.notification.add(_t("Pedido cargado en Caja"), 3000);
        } catch (error) {
            this.notification.add(error.message || _t("No se pudo cargar el pedido pendiente."), 5000);
        }
    }

    async loadPendingOrder(pendingOrder) {
        const currentOrder = this.pos.get_order();
        const order = currentOrder?.get_orderlines().length ? this.pos.add_new_order() : currentOrder || this.pos.add_new_order();
        order.sg_pending_order_id = pendingOrder.id;
        order.sg_customer_note_name = pendingOrder.customer_note_name || "";

        if (pendingOrder.partner_id) {
            let partner = this.pos.db.get_partner_by_id(pendingOrder.partner_id);
            if (!partner) {
                await this.pos._loadPartners([pendingOrder.partner_id]);
                partner = this.pos.db.get_partner_by_id(pendingOrder.partner_id);
            }
            if (partner) {
                order.set_partner(partner);
            }
        }

        for (const line of pendingOrder.lines) {
            const product = this.pos.db.get_product_by_id(line.product_id);
            if (!product) {
                throw new Error(_t("Un producto del pedido pendiente no está cargado en el POS."));
            }
            await order.add_product(product, {
                quantity: line.qty,
                price: line.price_unit,
                discount: line.discount,
                merge: false,
                sg_skip_location_suggestion: true,
                sg_suggested_location: {
                    location_id: line.location_id,
                    location_name: line.location_name,
                    available_qty: 0,
                },
            });
        }
    }
}

export class ReturnedOrdersButton extends Component {
    static template = "sg_pos_seller_cashier_flow.ReturnedOrdersButton";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.notification = useService("pos_notification");
    }

    async onClick() {
        const returnedOrders = await this.orm.call("sg.pos.pending.order", "get_returned_orders_for_pos", [
            this.pos.config.id,
        ]);
        if (!returnedOrders.length) {
            this.notification.add(_t("No hay pedidos devueltos."), 3000);
            return;
        }

        const { confirmed, payload: returnedOrder } = await this.popup.add(PendingOrdersPopup, {
            title: _t("Pedidos Devueltos"),
            orders: returnedOrders,
        });
        if (!confirmed || !returnedOrder) {
            return;
        }

        try {
            const loadedOrder = await this.orm.call("sg.pos.pending.order", "load_returned_order_for_seller", [
                returnedOrder.id,
                this.pos.config.id,
            ]);
            await this.loadReturnedOrder(loadedOrder);
            this.notification.add(_t("Pedido devuelto cargado"), 3000);
        } catch (error) {
            this.notification.add(error.message || _t("No se pudo cargar el pedido devuelto."), 5000);
        }
    }

    async loadReturnedOrder(returnedOrder) {
        const currentOrder = this.pos.get_order();
        const order = currentOrder?.get_orderlines().length ? this.pos.add_new_order() : currentOrder || this.pos.add_new_order();
        order.sg_pending_order_id = returnedOrder.id;
        order.sg_customer_note_name = returnedOrder.customer_note_name || "";

        if (returnedOrder.partner_id) {
            let partner = this.pos.db.get_partner_by_id(returnedOrder.partner_id);
            if (!partner) {
                await this.pos._loadPartners([returnedOrder.partner_id]);
                partner = this.pos.db.get_partner_by_id(returnedOrder.partner_id);
            }
            if (partner) {
                order.set_partner(partner);
            }
        }

        for (const line of returnedOrder.lines) {
            const product = this.pos.db.get_product_by_id(line.product_id);
            if (!product) {
                throw new Error(_t("Un producto del pedido devuelto no está cargado en el POS."));
            }
            await order.add_product(product, {
                quantity: line.qty,
                price: line.price_unit,
                discount: line.discount,
                merge: false,
            });
        }
    }
}

export class ReturnToSellerButton extends Component {
    static template = "sg_pos_seller_cashier_flow.ReturnToSellerButton";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("pos_notification");
    }

    async onClick() {
        const order = this.pos.get_order();
        const pendingOrderId = order?.sg_pending_order_id;
        if (!pendingOrderId) {
            return;
        }

        try {
            await this.orm.call("sg.pos.pending.order", "return_to_seller", [
                pendingOrderId,
                this.pos.config.id,
            ]);
            this.pos.removeOrder(order, false);
            this.pos.add_new_order();
            this.notification.add(_t("Pedido devuelto a vendedor"), 3000);
        } catch (error) {
            this.notification.add(error.message || _t("No se pudo devolver el pedido a vendedor."), 5000);
        }
    }
}

ProductScreen.addControlButton({
    component: PendingOrdersButton,
    condition: function () {
        return this.pos.config.sg_pos_flow_role === "cashier";
    },
});

ProductScreen.addControlButton({
    component: ReturnToSellerButton,
    condition: function () {
        const order = this.pos.get_order();
        return this.pos.config.sg_pos_flow_role === "cashier" && Boolean(order?.sg_pending_order_id);
    },
});

ProductScreen.addControlButton({
    component: ReturnedOrdersButton,
    condition: function () {
        return this.pos.config.sg_pos_flow_role === "seller";
    },
});

patch(Order.prototype, {
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.sg_pending_order_id = this.sg_pending_order_id || false;
        return json;
    },

    removeOrderline(line) {
        const result = super.removeOrderline(...arguments);
        this.sg_release_pending_order_if_empty();
        return result;
    },

    async sg_release_pending_order_if_empty() {
        if (
            this.pos.config.sg_pos_flow_role !== "cashier" ||
            !this.sg_pending_order_id ||
            this.get_orderlines().length
        ) {
            return;
        }
        const pendingOrderId = this.sg_pending_order_id;
        this.sg_pending_order_id = false;
        try {
            await this.env.services.orm.call("sg.pos.pending.order", "release_from_cashier", [
                pendingOrderId,
                this.pos.config.id,
            ]);
            this.env.services.pos_notification.add(
                _t("Pedido liberado y devuelto a pendientes"),
                3000
            );
        } catch (error) {
            this.sg_pending_order_id = pendingOrderId;
            this.env.services.pos_notification.add(
                error.message || _t("No se pudo liberar el pedido pendiente."),
                5000
            );
        }
    },
});
