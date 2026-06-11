/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

patch(BarcodePickingModel.prototype, {
    get groupedLines() {
        const lines = [...super.groupedLines];
        lines.sort(this._sortingMethod.bind(this));
        return lines;
    },

    get pageLines() {
        const lines = [...super.pageLines];
        lines.sort(this._sortingMethod.bind(this));
        return lines;
    },

    shouldSplitLine(line) {
        if (this._sg_block_split_on_location_scan) {
            return false;
        }
        return super.shouldSplitLine(line);
    },

    _sortingMethod(l1, l2) {
        const activeLocationId = this.sg_active_source_location_id;
        const l1InActiveLocation = activeLocationId && l1.location_id?.id === activeLocationId;
        const l2InActiveLocation = activeLocationId && l2.location_id?.id === activeLocationId;

        if (l1InActiveLocation && !l2InActiveLocation) {
            return -1;
        } else if (!l1InActiveLocation && l2InActiveLocation) {
            return 1;
        }

        if (l1InActiveLocation && l2InActiveLocation) {
            if (l1.sg_current_line && !l2.sg_current_line) {
                return -1;
            } else if (!l1.sg_current_line && l2.sg_current_line) {
                return 1;
            }

            const order1 = Number.isFinite(l1.sg_dispatch_order) ? l1.sg_dispatch_order : 999999;
            const order2 = Number.isFinite(l2.sg_dispatch_order) ? l2.sg_dispatch_order : 999999;

            if (order1 < order2) {
                return -1;
            } else if (order1 > order2) {
                return 1;
            }

            return (l1.id || 0) - (l2.id || 0);
        }

        return super._sortingMethod(l1, l2);
    },

    _sgApplyActiveLocationFlags(locationId) {
        for (const line of this.currentState?.lines || []) {
            line.sg_active_location_line = Boolean(
                locationId && line.location_id?.id === locationId
            );
        }
    },

    _sgFindCurrentProductLine(productId) {
        const activeLocationId = this.sg_active_source_location_id;
        const selectedLine = this.selectedLine;

        if (
            selectedLine?.product_id?.id === productId &&
            selectedLine.location_id?.id === activeLocationId
        ) {
            return selectedLine;
        }

        return (this.currentState?.lines || []).find(
            (line) =>
                line.product_id?.id === productId &&
                line.location_id?.id === activeLocationId
        );
    },

    _sgGetProductLocationLines(productId) {
        const activeLocationId = this.sg_active_source_location_id;
        return (this.currentState?.lines || []).filter(
            (line) =>
                line.product_id?.id === productId &&
                line.location_id?.id === activeLocationId
        );
    },

    _sgGetPendingLine(lines, scannedQty = 1) {
        const pendingLines = lines.filter(
            (line) => this.getQtyDemand(line) > this.getQtyDone(line)
        );
        return pendingLines.find(
            (line) => scannedQty <= this.getQtyDemand(line) - this.getQtyDone(line)
        ) || pendingLines[0];
    },

    _sgGetScannedQty(barcodeData) {
        if (barcodeData.packaging) {
            return this._retrievePackagingData(barcodeData).quantity || 1;
        }
        return barcodeData.quantity || 1;
    },

    _sgSetCurrentLine(currentLine) {
        for (const line of this.currentState?.lines || []) {
            if (line === currentLine) {
                line.sg_current_line = true;
                line.sg_worked_line = false;
            } else if (line.sg_current_line) {
                line.sg_current_line = false;
                line.sg_worked_line = true;
            } else {
                line.sg_current_line = false;
            }
        }
    },

    async _processBarcode(barcode) {
        const barcodeData = await this._parseBarcode(barcode);

        if (this.record?.picking_type_code === "outgoing") {
            if (barcodeData.location) {
                const existsInPicking = this.currentState.lines.some(
                    (line) => line.location_id?.id === barcodeData.location.id
                );

                if (!existsInPicking) {
                    this.notification(
                        _t("La ubicación escaneada no pertenece a este picking."),
                        { type: "danger" }
                    );
                    return;
                }

                this.selectedLineVirtualId = false;

                if (this.lastScanned) {
                    this.lastScanned.product = false;
                    this.lastScanned.lot = false;
                    this.lastScanned.packageId = false;
                    this.lastScanned.sourceLocation = false;
                }

                this.sg_active_source_location_id = barcodeData.location.id;
                this._sgApplyActiveLocationFlags(this.sg_active_source_location_id);

                let result;
                this._sg_block_split_on_location_scan = true;
                try {
                    result = await super._processBarcode(barcode);
                } finally {
                    this._sg_block_split_on_location_scan = false;
                }

                this._sgApplyActiveLocationFlags(this.sg_active_source_location_id);

                const sorter = this._sortingMethod.bind(this);

                if (this.currentState?.lines) {
                    this.currentState.lines.sort(sorter);
                }

                this.trigger("update");

                setTimeout(() => {
                    const page = document.querySelector(".o_barcode_lines");
                    if (page) {
                        page.scrollTo({ top: 0, left: 0, behavior: "smooth" });
                    }
                }, 100);

                return result;
            }

            if (barcodeData.product && !this.sg_active_source_location_id) {
                this.notification(
                    _t("Primero debe escanear la ubicación de origen."),
                    { type: "danger" }
                );
                return;
            }

            if (
                barcodeData.product &&
                this.sg_active_source_location_id &&
                !this.currentState.lines.some(
                    (line) =>
                        line.product_id?.id === barcodeData.product.id &&
                        line.location_id?.id === this.sg_active_source_location_id
                )
            ) {
                this.notification(
                    _t("Este producto no pertenece a la ubicación escaneada."),
                    { type: "danger" }
                );
                return;
            }

            if (barcodeData.product && this.sg_active_source_location_id) {
                const productLines = this._sgGetProductLocationLines(barcodeData.product.id);
                const scannedQty = this._sgGetScannedQty(barcodeData);
                const pendingLine = this._sgGetPendingLine(productLines, scannedQty);

                if (!pendingLine) {
                    this.notification(
                        _t("La cantidad esperada de este producto en la ubicación escaneada ya está completa."),
                        { type: "danger" }
                    );
                    return;
                }

                const remainingQty = this.getQtyDemand(pendingLine) - this.getQtyDone(pendingLine);

                if (scannedQty > remainingQty) {
                    this.notification(
                        _t("La cantidad escaneada excede la cantidad pendiente de este producto en la ubicación escaneada."),
                        { type: "danger" }
                    );
                    return;
                }

                this.selectedLineVirtualId = pendingLine.virtual_id;

                const result = await super._processBarcode(barcode);
                const currentLine = this._sgFindCurrentProductLine(barcodeData.product.id);

                if (currentLine) {
                    this._sgApplyActiveLocationFlags(this.sg_active_source_location_id);
                    this._sgSetCurrentLine(currentLine);
                    this.trigger("update");
                }

                return result;
            }
        }

        return super._processBarcode(barcode);
    },
});
