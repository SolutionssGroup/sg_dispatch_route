/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/navbar/navbar";

patch(Navbar.prototype, {
    async closeSession() {
        if (this.pos.config.sg_pos_flow_role !== "seller") {
            return super.closeSession(...arguments);
        }

        const customerDisplay = this.env.services.customer_display;
        customerDisplay?.update({ closeUI: true });

        const syncSuccess = await this.pos.push_orders_with_closing_popup();
        if (!syncSuccess) {
            return;
        }

        const response = await this.env.services.orm.call("pos.session", "close_session_from_ui", [
            this.pos.pos_session.id,
            [],
        ]);
        if (!response.successful) {
            this.notification.add(
                response.message || _t("No se pudo cerrar la sesión de vendedores."),
                5000
            );
            if (response.redirect) {
                this.pos.redirectToBackend();
            }
            return;
        }

        this.pos.redirectToBackend();
    },
});
