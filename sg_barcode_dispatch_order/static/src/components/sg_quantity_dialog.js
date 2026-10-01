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
        // Fix 2026-09-30: el modal abría con el valor anterior precargado
        // (ej. "5"), y el primer toque de un dígito se lo pegaba detrás en
        // vez de reemplazarlo (tocar "2" daba "52", no "2"). Mientras esto
        // sea true, el próximo dígito empieza un número nuevo de cero.
        this._freshStart = true;
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
        if (this._freshStart) {
            this.state.value = "";
            this._freshStart = false;
        }
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
        this._freshStart = false;
        this.state.value = this.state.value.slice(0, -1);
    }

    onClear() {
        this.state.error = "";
        this._freshStart = false;
        this.state.value = "";
    }

    onConfirm() {
        const totalQty = parseFloat(this.state.value || "0");
        if (isNaN(totalQty) || totalQty < 0) {
            this.state.error = _t("Ingresa una cantidad válida.");
            return;
        }
        // Fix 2026-09-30: este modal no validaba contra la demanda —
        // dejaba escribir y confirmar cualquier número, permitiendo poner
        // más cantidad de la que el producto espera en esta línea. La
        // validación es contra el TOTAL que el usuario quiere dejar en
        // esta línea (lo que escribió), no contra la diferencia.
        if (
            typeof this.props.demandQty === "number"
            && totalQty > this.props.demandQty
        ) {
            this.state.error = _t(
                "No puedes poner más de %s %s — es lo que espera esta línea.",
                this.props.demandQty,
                this.props.uom || ""
            );
            return;
        }
        // Fix 2026-09-30 (causa real de "el modal sigue sumando"):
        // Odoo no fija qty_done al número que se le pasa — se lo SUMA
        // (línea qty_done += args.qty_done, confirmado en el código
        // fuente de stock_barcode: _updateLineQty). Lo que el usuario
        // escribe aquí es el TOTAL que quiere dejar en la línea, no lo
        // que hay que sumarle. Por eso se manda la diferencia (puede
        // ser negativa, para corregir hacia abajo), no el número tal
        // cual.
        const delta = totalQty - (this.props.initialQty || 0);
        this.props.confirm(delta);
        this.props.close();
    }

    onDiscard() {
        this.props.close();
    }
}
