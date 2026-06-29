/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { Order, Orderline } from "@point_of_sale/app/store/models";

patch(Orderline.prototype, {
    setup() {
        super.setup(...arguments);
        const options = arguments[1] || {};
        this.sg_suggested_location_id = this.sg_suggested_location_id || false;
        this.sg_suggested_location_name = this.sg_suggested_location_name || "";
        this.sg_suggested_location_qty = this.sg_suggested_location_qty || 0;
        if (options.sg_suggested_location) {
            this.set_sg_suggested_location(options.sg_suggested_location);
        }
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.sg_suggested_location_id = json.sg_suggested_location_id || false;
        this.sg_suggested_location_name = json.sg_suggested_location_name || "";
        this.sg_suggested_location_qty = json.sg_suggested_location_qty || 0;
    },

    set_sg_suggested_location(location) {
        this.sg_suggested_location_id = location?.location_id || false;
        this.sg_suggested_location_name = location?.location_name || "";
        this.sg_suggested_location_qty = location?.available_qty || 0;
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.sg_suggested_location_id = this.sg_suggested_location_id || false;
        json.sg_suggested_location_name = this.sg_suggested_location_name || "";
        json.sg_suggested_location_qty = this.sg_suggested_location_qty || 0;
        return json;
    },

    getDisplayData() {
        const data = super.getDisplayData(...arguments);
        const showLocation = this.pos.config.sg_pos_flow_role === "seller";
        data.sgSuggestedLocationName = showLocation ? this.sg_suggested_location_name || "" : "";
        data.sgSuggestedLocationQty = showLocation ? this.sg_suggested_location_qty || 0 : 0;
        return data;
    },
});

patch(Order.prototype, {
    async add_product(product, options = {}) {
        const line = await super.add_product(product, options);
        const orderline = this.get_selected_orderline() || line;
        if (options.sg_suggested_location && orderline) {
            orderline.set_sg_suggested_location(options.sg_suggested_location);
        }
        if (this.pos.config.sg_pos_flow_role !== "seller" || options.sg_skip_location_suggestion) {
            return line;
        }

        if (!orderline || orderline.get_product()?.id !== product.id) {
            return line;
        }

        try {
            const suggestion = await this.env.services.orm.call(
                "stock.location",
                "get_pos_suggested_location",
                [product.id, this.pos.config.id]
            );
            orderline.set_sg_suggested_location(suggestion);
            if (!suggestion.location_id) {
                this.env.services.pos_notification.add(
                    _t("Producto sin existencia en ubicación"),
                    3000
                );
            }
        } catch (error) {
            this.env.services.pos_notification.add(
                error.message || _t("No se pudo sugerir ubicación para el producto."),
                5000
            );
        }
        return line;
    },
});
