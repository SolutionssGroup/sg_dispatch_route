/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

/**
 * Traslados internos (picking_type_code "internal"): lo visual del flujo
 * origen -> productos -> destino. La lógica de qué ubicación es origen y cuál
 * destino ya la maneja Odoo (con productos leídos, la siguiente ubicación es
 * destino; al aplicarla Odoo limpia el estado y la siguiente vuelve a ser
 * origen). Aquí solo se pinta:
 * - la ubicación de origen recién leída como una fila vacía en verde,
 * - la línea del último producto leído en naranja, para poner la cantidad,
 * - las líneas ya trabajadas en gris,
 * y se hace scroll para que la fila quede completa bajo la barra de arriba.
 */
patch(BarcodePickingModel.prototype, {
    get sgIntPlaceholderLocation() {
        if (this.record?.picking_type_code !== "internal") {
            return false;
        }
        const location = this.lastScanned?.sourceLocation;
        if (!location || this.previousScannedLines.length) {
            return false;
        }
        return location;
    },

    /**
     * Odoo, en cada updateLine, manda la línea al origen que esté activo
     * (lastScanned.sourceLocation). Es lo que da su origen a una línea
     * nueva, pero también cambiaba el origen de una línea ya trabajada de un
     * movimiento anterior en cuanto se leía el origen del siguiente. Aquí,
     * si la línea ya tiene cantidad, se conserva su origen; una línea nueva
     * (cantidad 0) sigue tomando el origen activo.
     */
    async updateLine(line, args) {
        if (
            this.record?.picking_type_code === "internal"
            && line
            && line.qty_done > 0
        ) {
            args = { ...args, dontUpdateSourceLocation: true };
        }
        return super.updateLine(line, args);
    },

    _sgRefreshInternalFlags() {
        this._sgApplyActiveLocationFlags(this.lastScanned?.sourceLocation?.id || false);
        this._sgSetCurrentLine(this.lastScannedLine || false);
    },

    _sgScrollInternal() {
        if (this.sgIntPlaceholderLocation) {
            this._sgScrollListToTop();
        } else {
            this._sgScrollCurrentLineToTop("product");
        }
    },

    /**
     * Borra una línea de un traslado interno. Odoo no trae botón de borrar
     * en la lista de la PDA. Primero se guarda lo pendiente (para que una
     * línea recién leída ya exista en el servidor y tenga id), luego se
     * borra el stock.move.line y se quita de la lista en pantalla.
     */
    async sgDeleteLine(line) {
        if (!line || this.record?.picking_type_code !== "internal") {
            return;
        }
        await this.save();

        const wanted = line.lines || [line];
        const virtualIds = wanted.map((l) => l.virtual_id);
        const targets = (this.currentState.lines || []).filter(
            (l) => virtualIds.includes(l.virtual_id) || virtualIds.includes(l.dummy_id)
        );

        const ids = targets.map((l) => l.id).filter(Boolean);
        if (ids.length) {
            await this.orm.unlink("stock.move.line", ids);
        }

        for (const target of targets) {
            const index = this.currentState.lines.indexOf(target);
            if (index >= 0) {
                this.currentState.lines.splice(index, 1);
            }
            this.scannedLinesVirtualId = this.scannedLinesVirtualId.filter(
                (id) => id !== target.virtual_id
            );
            if (this.selectedLineVirtualId === target.virtual_id) {
                this.selectedLineVirtualId = false;
            }
        }

        this._sgRefreshInternalFlags();
        this.trigger("update");
    },
});
