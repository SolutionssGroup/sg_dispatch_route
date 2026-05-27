/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import BarcodeModel from "@stock_barcode/models/barcode_model";

patch(BarcodeModel.prototype, {
    _sortingMethod(l1, l2) {
        const activeLocationId = this.sg_active_source_location_id;

        const l1InActiveLocation = activeLocationId && l1.location_id?.id === activeLocationId;
        const l2InActiveLocation = activeLocationId && l2.location_id?.id === activeLocationId;

        if (l1InActiveLocation && !l2InActiveLocation) {
            return -1;
        } else if (!l1InActiveLocation && l2InActiveLocation) {
            return 1;
        }

        const order1 = Number.isFinite(l1.sg_dispatch_order) ? l1.sg_dispatch_order : 999999;
        const order2 = Number.isFinite(l2.sg_dispatch_order) ? l2.sg_dispatch_order : 999999;

        if (order1 < order2) {
            return -1;
        } else if (order1 > order2) {
            return 1;
        }

        const sourceLocation1 = l1.location_id.display_name;
        const sourceLocation2 = l2.location_id.display_name;
        if (sourceLocation1 < sourceLocation2) {
            return -1;
        } else if (sourceLocation1 > sourceLocation2) {
            return 1;
        }

        const package1 = l1.package_id.name;
        const package2 = l2.package_id.name;
        if (package1 < package2) {
            return -1;
        } else if (package1 > package2) {
            return 1;
        }

        if (l1.location_dest_id && l2.location_dest_id) {
            const destinationLocation1 = l1.location_dest_id.display_name;
            const destinationLocation2 = l2.location_dest_id.display_name;
            if (destinationLocation1 < destinationLocation2) {
                return -1;
            } else if (destinationLocation1 > destinationLocation2) {
                return 1;
            }
        }

        if (l1.result_package_id && l2.result_package_id) {
            const resultPackage1 = l1.result_package_id.name;
            const resultPackage2 = l2.result_package_id.name;
            if (resultPackage1 < resultPackage2) {
                return -1;
            } else if (resultPackage1 > resultPackage2) {
                return 1;
            }
        }

        const categ1 = l1.product_category_name;
        const categ2 = l2.product_category_name;
        if (categ1 < categ2) {
            return -1;
        } else if (categ1 > categ2) {
            return 1;
        }

        const product1 = l1.product_id.display_name;
        const product2 = l2.product_id.display_name;
        if (product1 < product2) {
            return -1;
        } else if (product1 > product2) {
            return 1;
        }

        return 0;
    },
});
