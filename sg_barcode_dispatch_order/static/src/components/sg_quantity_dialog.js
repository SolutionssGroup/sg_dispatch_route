/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Modal chico de solo cantidad para despacho (sg_barcode_dispatch_order).
 *
 * Reemplaza, para pickings de salida, la pantalla completa de Odoo
 * (onOpenProductPage) que se abría al tocar el lápiz de una línea.
 * Esa pantalla muestra imagen, nombre y más campos del producto además
 * del teclado — aquí solo se pide un número y se confirma.
 */
export class SgQuantityDialog extends Component {
    static template = "sg_barcode_dispatch_order.SgQuantityDialog";
    static components = { Dialog };
    static props = {
        productName: { type: String, optional: true },
        initialQty: { type: Number, optional: true },
        demandQty: { type: Number, optional: true },
        uom: { type: String, optional: true },
        close: Function,
        confirm: Function,
    };

    setup() {
        this.state = useState({
            value: this._formatInitial(this.props.initialQty),
            error: "",
        });
    }

    _formatInitial(qty) {
        if (!qty) {
            return "";
        }
        // quita ceros/decimales sobrantes (3.0 -> "3")
        return String(Number(qty.toFixed(4)));
    }

    get displayValue() {
        return this.state.value || "0";
    }

    onDigit(d) {
        this.state.error = "";
        if (d === "." && this.state.value.includes(".")) {
            return;
        }
        if (d === "." && this.state.value === "") {
            this.state.value = "0.";
            return;
        }
        this.state.value += d;
    }

    onBackspace() {
        this.state.error = "";
        this.state.value = this.state.value.slice(0, -1);
    }

    onClear() {
        this.state.error = "";
        this.state.value = "";
    }

    onConfirm() {
        const qty = parseFloat(this.state.value || "0");
        if (isNaN(qty) || qty < 0) {
            this.state.error = _t("Ingresa una cantidad válida.");
            return;
        }
        this.props.confirm(qty);
        this.props.close();
    }

    onDiscard() {
        this.props.close();
    }
}
