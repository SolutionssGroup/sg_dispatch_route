/** @odoo-module **/

import { onMounted, onPatched } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import MainComponent from "@stock_barcode/components/main";
import { sgOpenPickDialog } from "../components/sg_pick_dialog";

patch(MainComponent.prototype, {
    setup() {
        super.setup(...arguments);
        // Pickings de salida: no se agregan productos desde la PDA.
        const hideAddProduct = () => {
            if (this.env.model?.record?.picking_type_code !== "outgoing") {
                return;
            }
            for (const button of document.querySelectorAll("button")) {
                if (/^\s*\+?\s*(agregar producto|add product)\s*$/i.test(button.textContent || "")) {
                    button.style.display = "none";
                }
            }
        };
        if (this.env.model) {
            useBus(this.env.model, "sg-exit-list", () => this.sgExitToList());
        }
        onMounted(hideAddProduct);
        onPatched(hideAddProduct);
    },

    // Sale a la lista de operaciones (migas de pan anteriores).
    sgExitToList() {
        const config = this.env.config;
        const action = this.env.services && this.env.services.action;
        if (config && typeof config.historyBack === "function") {
            config.historyBack();
        } else if (action && typeof action.restore === "function") {
            action.restore();
        } else {
            window.history.back();
        }
    },

    // Boton "Recoger": abre la primera linea pendiente y, al dar OK,
    // sigue solo con la siguiente de la ruta.
    onSgRecoger() {
        const model = this.env.model;
        const next = model.sgNextPendingLine([]);
        if (!next) {
            this.notification.add(_t("No hay líneas pendientes por recoger."), {
                type: "warning",
            });
            return;
        }
        sgOpenPickDialog(this.dialog, model, next, true);
    },

    async onOpenProductPage(line) {
        const model = this.env.model;
        if (model?.record?.picking_type_code === "outgoing" && line) {
            sgOpenPickDialog(this.dialog, model, line);
            return;
        }
        return super.onOpenProductPage(line);
    },
});
