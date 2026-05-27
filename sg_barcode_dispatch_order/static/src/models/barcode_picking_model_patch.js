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

                let result;
                this._sg_block_split_on_location_scan = true;
                try {
                    result = await super._processBarcode(barcode);
                } finally {
                    this._sg_block_split_on_location_scan = false;
                }

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
        }

        return super._processBarcode(barcode);
    },
});
