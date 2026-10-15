/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import LineComponent from "@stock_barcode/components/line";
import { sgOpenPickDialog } from "../components/sg_pick_dialog";

/**
 * Torpinsa: tocar una linea de un picking de salida abre el modal de
 * recogida de ESA linea.
 */
patch(LineComponent.prototype, {
    select(ev) {
        const model = this.env.model;
        if (model?.record?.picking_type_code === "outgoing") {
            ev.stopPropagation();
            sgOpenPickDialog(this.env.services.dialog, model, this.line);
            return;
        }
        return super.select(ev);
    },
});
