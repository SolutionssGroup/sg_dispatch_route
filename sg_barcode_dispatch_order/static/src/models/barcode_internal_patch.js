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
});
