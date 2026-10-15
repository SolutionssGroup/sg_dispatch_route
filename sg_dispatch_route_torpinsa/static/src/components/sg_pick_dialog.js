/** @odoo-module **/

import { Component, onMounted, onWillDestroy, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";
import { SgQuantityDialog } from "@sg_barcode_dispatch_order/components/sg_quantity_dialog";

/**
 * Modal guiado de recogida (Torpinsa). Tres pasos, en este orden:
 *   1) leer la UBICACION  2) leer el PRODUCTO  3) poner la CANTIDAD.
 * El paso activo va en mamey (con flecha); los completados en verde. El
 * paso 3 es verde solo cuando la cantidad completa lo pedido; si falta, se
 * queda en mamey. No hay reserva: el inventario se descuenta de la
 * ubicacion leida cuando se valida el picking.
 */
export class SgPickDialog extends Component {
    static template = "sg_dispatch_route_torpinsa.SgPickDialog";
    static components = { Dialog };
    static props = {
        model: Object,
        lineVirtualId: String,
        onFinished: { type: Function, optional: true },
        close: Function,
    };

    setup() {
        this.barcode = useService("barcode");
        this.dialog = useService("dialog");
        const line = this.line;
        const done = line ? this.props.model.getQtyDone(line) : 0;
        const alreadyPicked = done > 0;
        this.state = useState({
            locationOk: alreadyPicked,
            productOk: alreadyPicked,
            location: alreadyPicked ? line.location_id : null,
            qty: done,
            error: "",
        });

        this.props.model.sgPickSession = this;
        useBus(this.barcode.bus, "barcode_scanned", (ev) =>
            this.onBarcode(ev.detail.barcode)
        );

        // El Enter con el que la pistola cierra cada lectura no debe
        // "presionar" el boton que tenga el foco.
        this._onKeydown = (ev) => {
            if (ev.key === "Enter") {
                ev.preventDefault();
            }
        };
        onMounted(() => {
            window.addEventListener("keydown", this._onKeydown, true);
            if (document.activeElement && document.activeElement.blur) {
                document.activeElement.blur();
            }
        });
        onWillDestroy(() => {
            window.removeEventListener("keydown", this._onKeydown, true);
            if (this.props.model.sgPickSession === this) {
                this.props.model.sgPickSession = null;
            }
        });
    }

    get okLabel() {
        // Texto fijo: "OK" en el XML se traduce a "De acuerdo".
        return "OK";
    }

    get line() {
        return (this.props.model.pageLines || []).find(
            (l) => l.virtual_id === this.props.lineVirtualId
        );
    }

    get productName() {
        const p = this.line && this.line.product_id;
        return (p && (p.display_name || p.name)) || "";
    }

    get productCode() {
        const p = this.line && this.line.product_id;
        return (p && p.default_code) || "";
    }

    get productBarcode() {
        const p = this.line && this.line.product_id;
        return (p && p.barcode) || "";
    }

    get demand() {
        const line = this.line;
        return line ? this.props.model.getQtyDemand(line) : 0;
    }

    get uom() {
        const line = this.line;
        if (!line) {
            return "";
        }
        return (
            (line.product_uom_id && line.product_uom_id.display_name) ||
            (line.product_uom && line.product_uom.name) ||
            ""
        );
    }

    shortLocation(location) {
        const name = (location && (location.display_name || location.name)) || "";
        return name.split("/").pop();
    }

    get plannedLocation() {
        const line = this.line;
        return line ? this.shortLocation(line.location_id) : "";
    }

    get activeStep() {
        if (!this.state.locationOk) {
            return "location";
        }
        if (!this.state.productOk) {
            return "product";
        }
        return "qty";
    }

    /** Cantidad contada completa lo pedido (10/10). */
    get qtyComplete() {
        return this.state.productOk && this.demand > 0 && this.state.qty >= this.demand;
    }

    /** La flecha apunta al paso que toca; en cantidad, solo mientras falte. */
    get arrowStep() {
        if (this.activeStep === "qty" && this.qtyComplete) {
            return null;
        }
        return this.activeStep;
    }

    stepClass(step) {
        const isDone =
            (step === "location" && this.state.locationOk) ||
            (step === "product" && this.state.productOk) ||
            (step === "qty" && this.qtyComplete);
        if (isDone) {
            return "sg_pick_step is_done";
        }
        return this.activeStep === step
            ? "sg_pick_step is_active"
            : "sg_pick_step is_wait";
    }

    get canConfirm() {
        return this.state.locationOk && this.state.productOk && this.state.qty > 0;
    }

    get displayQty() {
        return String(Number(Number(this.state.qty).toFixed(4)));
    }

    fail(message) {
        this.state.error = message;
    }

    async onBarcode(barcode) {
        this.state.error = "";
        let data;
        try {
            data = await this.props.model._parseBarcode(barcode);
        } catch (e) {
            data = {};
        }
        const line = this.line;
        if (!line || !data) {
            return;
        }

        if (!this.state.locationOk) {
            if (data.location) {
                return this.onLocationRead(data.location, line);
            }
            if (data.product) {
                return this.fail(_t("Primero lee la ubicación."));
            }
            return this.fail(_t("Código no reconocido."));
        }

        if (data.location) {
            return this.fail(_t("La ubicación ya fue leída."));
        }
        if (!data.product) {
            return this.fail(_t("Código no reconocido."));
        }
        if (data.product.id !== line.product_id.id) {
            return this.fail(_t("Ese no es el producto de esta línea."));
        }
        if (!this.state.productOk) {
            this.state.productOk = true;
        }
        const step = data.quantity || 1;
        if (this.demand > 0 && this.state.qty + step > this.demand) {
            return this.fail(_t("Ya completaste lo pedido."));
        }
        this.state.qty += step;
    }

    onLocationRead(location, line) {
        if (location.id !== line.location_id.id) {
            // Solo se recoge de la ubicacion planificada: se dirige al operador.
            return this.fail(
                _t(
                    "Ubicación incorrecta: leíste %s. Ve a %s.",
                    this.shortLocation(location),
                    this.plannedLocation
                )
            );
        }
        this.state.location = location;
        this.state.locationOk = true;
    }

    /** Tocar el campo de cantidad abre un teclado numerico en modal. */
    onOpenKeypad() {
        if (!this.state.productOk) {
            return;
        }
        this.dialog.add(SgQuantityDialog, {
            productName: this.productName,
            initialQty: this.state.qty,
            demandQty: this.demand,
            uom: this.uom,
            confirm: (delta) => {
                this.state.error = "";
                this.state.qty = Math.max(0, this.state.qty + delta);
            },
        });
    }

    async onConfirm() {
        if (!this.canConfirm) {
            return;
        }
        const line = this.line;
        const qty = this.state.qty;
        const onFinished = this.props.onFinished;
        const model = this.props.model;
        this.props.close();
        await model.sgApplyPick(line, qty);
        if (onFinished) {
            onFinished();
        }
    }

    onClose() {
        this.props.close();
    }
}

/**
 * Abre el modal para una linea. Con `chain` (boton Recoger), al terminar
 * abre solo la siguiente linea pendiente de la ruta.
 */
export function sgOpenPickDialog(dialogService, model, line, chain = false, visited = []) {
    if (!line) {
        return;
    }
    const seen = [...visited, line.virtual_id];
    dialogService.add(SgPickDialog, {
        model,
        lineVirtualId: line.virtual_id,
        onFinished: chain
            ? () => {
                  const next = model.sgNextPendingLine(seen);
                  if (next) {
                      sgOpenPickDialog(dialogService, model, next, true, seen);
                  }
              }
            : undefined,
    });
}
