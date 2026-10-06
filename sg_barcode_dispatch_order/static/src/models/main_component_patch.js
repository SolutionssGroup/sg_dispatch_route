/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import MainComponent from "@stock_barcode/components/main";
import { SgQuantityDialog } from "../components/sg_quantity_dialog";

/**
 * Fix 2026-09-30: el lápiz de una línea llama a onOpenProductPage(line),
 * que abre la pantalla completa de Odoo (imagen, nombre, lote, paquete,
 * cantidad...). Para despacho (picking_type_code "outgoing") esto se
 * reemplaza por un modal chico que solo pide la cantidad — el resto de
 * esa pantalla no aplica al flujo de despacho de Inprotec.
 *
 * Reusa el mismo guardián que ya tiene updateLineQty
 * (sg_barcode_picking_model_patch.js): solo se puede tocar la cantidad
 * cuando la línea ya tiene producto y ubicación leídos
 * (lineCanBeEdited, extendido ahí con esa misma regla).
 */
patch(MainComponent.prototype, {
    async onOpenProductPage(line) {
        const model = this.env.model;

        const pickingType = model?.record?.picking_type_code;

        // Traslados internos: mismo modal chico para poner la cantidad, pero
        // sin tope contra la demanda (un traslado abierto se arma leyendo, no
        // tiene cantidad esperada) y sin la regla de producto+ubicación.
        if (pickingType === "internal" && line) {
            this.dialog.add(SgQuantityDialog, {
                productName: line.product_id?.display_name,
                initialQty: model.getQtyDone(line),
                uom: line.product_uom?.name,
                confirm: (qty) => {
                    model.updateLineQty(line.virtual_id, qty);
                },
            });
            return;
        }

        if (pickingType === "outgoing" && line) {
            if (!model.lineCanBeEdited(line)) {
                this.notification.add(
                    _t("Primero escanea el producto y la ubicación de esta línea (en cualquier orden) antes de cambiar la cantidad."),
                    { type: "danger" }
                );
                return;
            }

            this.dialog.add(SgQuantityDialog, {
                productName: line.product_id?.display_name,
                initialQty: model.getQtyDone(line),
                demandQty: model.getQtyDemand(line),
                uom: line.product_uom?.name,
                confirm: (qty) => {
                    model.updateLineQty(line.virtual_id, qty);
                },
            });
            return;
        }

        return super.onOpenProductPage(line);
    },
});
