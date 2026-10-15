/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

/**
 * Torpinsa: despacho guiado sin reserva.
 *
 * La lista de la PDA es solo visual. Toda la recogida pasa por el modal
 * (SgPickDialog): ubicacion -> producto -> cantidad. Este parche se carga
 * DESPUES del de sg_barcode_dispatch_order (ver depends) y lo sustituye para
 * los pickings de salida.
 */
patch(BarcodePickingModel.prototype, {
    get sgIsOutgoing() {
        return this.record?.picking_type_code === "outgoing";
    },

    // La demanda sale del movimiento (no de la reserva, que aqui es 0).
    getQtyDemand(line) {
        if (this.sgIsOutgoing && line && Number.isFinite(line.sg_demand_qty)) {
            return line.sg_demand_qty;
        }
        return super.getQtyDemand(line);
    },

    // Lapiz y +N deshabilitados: la cantidad solo se pone desde el modal.
    lineCanBeEdited(line) {
        if (this.sgIsOutgoing) {
            return false;
        }
        return super.lineCanBeEdited(line);
    },

    // Con el modal abierto el propio modal atiende las lecturas.
    async _processBarcode(barcode) {
        if (this.sgIsOutgoing) {
            if (!this.sgPickSession) {
                this.notification(
                    _t("Toca una línea o presiona Recoger para recoger."),
                    { type: "warning" }
                );
            }
            return;
        }
        return super._processBarcode(barcode);
    },

    async updateLineQty(virtualId, qty = 1) {
        if (this.sgIsOutgoing) {
            return;
        }
        return super.updateLineQty(virtualId, qty);
    },

    async validate() {
        if (this.sgIsOutgoing) {
            const picked = (this.currentState?.lines || []).reduce(
                (total, line) => total + (this.getQtyDone(line) || 0),
                0
            );
            if (!picked) {
                this.notification(
                    _t("Todavía no has recogido nada."),
                    { type: "danger" }
                );
                return;
            }
        }
        return super.validate(...arguments);
    },

    /** Siguiente linea pendiente de la ruta que no se haya visitado ya. */
    sgNextPendingLine(visited = []) {
        return (this.pageLines || []).find(
            (line) =>
                !visited.includes(line.virtual_id) &&
                this.getQtyDemand(line) > this.getQtyDone(line)
        );
    },

    /**
     * Aplica lo recogido en el modal. `qty` es el TOTAL de la linea (Odoo
     * suma, por eso se manda la diferencia). Si la ubicacion leida no es la
     * del plan, la linea pasa a esa ubicacion.
     */
    async sgApplyPick(line, qty, location) {
        if (!line) {
            return;
        }
        const delta = qty - (this.getQtyDone(line) || 0);
        const relocate = Boolean(
            location && line.location_id && location.id !== line.location_id.id
        );
        if (!delta && !relocate) {
            return;
        }
        await this.actionMutex.exec(async () => {
            if (relocate) {
                if (this.lastScanned) {
                    this.lastScanned.sourceLocation = location;
                }
                await this.updateLine(line, { qty_done: delta });
            } else {
                await this.updateLine(line, {
                    qty_done: delta,
                    dontUpdateSourceLocation: true,
                });
            }
        });
        if (relocate && line.location_id?.id !== location.id) {
            // Respaldo: si Odoo no movio la linea, se fuerza en el servidor.
            await this.save();
            if (line.id) {
                await this.orm.write("stock.move.line", [line.id], {
                    location_id: location.id,
                });
            }
            line.location_id = location;
        }
        this.trigger("update");
    },
});
