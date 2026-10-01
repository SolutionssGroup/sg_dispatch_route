/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import LineComponent from "@stock_barcode/components/line";

/**
 * Fix 2026-09-30: tocar el cuerpo de una línea con el dedo llama a
 * select(ev) -> env.model.selectLine(line). Ese mismo método lo usa
 * también, internamente, el procesamiento normal de un escaneo — por
 * eso el candado no se puso en selectLine/lineCanBeSelected (bloquearlo
 * ahí habría roto el escaneo también). Aquí se bloquea solo el toque
 * manual del componente, para pickings de salida: el operador solo
 * puede señalar una línea leyendo su ubicación o su producto, nunca
 * tocándola directamente.
 */
patch(LineComponent.prototype, {
    select(ev) {
        if (this.env.model?.record?.picking_type_code === "outgoing") {
            ev.stopPropagation();
            return;
        }
        return super.select(ev);
    },
});
