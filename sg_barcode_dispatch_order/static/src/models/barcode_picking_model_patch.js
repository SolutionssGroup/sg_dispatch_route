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
        // Fix 2026-09-30 (conservar la ruta de despacho como el orden base):
        // antes esta función ponía primero las líneas de la ubicación activa
        // y, dentro de esas, la línea "actual" — es decir, la posición en el
        // arreglo cambiaba cada vez que se escaneaba algo. Eso iba contra la
        // idea de que la ruta (sg_dispatch_order) es el orden que no se debe
        // tocar: resaltar la ubicación activa o la línea actual es un asunto
        // puramente visual (ver barcode_line_highlight.xml, que ya lo pinta
        // por sg_active_location_line / sg_current_line / sg_worked_line sin
        // depender de la posición). Por eso ahora el orden del arreglo
        // depende únicamente de sg_dispatch_order (y el id como desempate),
        // nunca de qué se escaneó último.
        const order1 = Number.isFinite(l1.sg_dispatch_order) ? l1.sg_dispatch_order : 999999;
        const order2 = Number.isFinite(l2.sg_dispatch_order) ? l2.sg_dispatch_order : 999999;

        if (order1 < order2) {
            return -1;
        } else if (order1 > order2) {
            return 1;
        }

        if (l1.id && l2.id) {
            return l1.id - l2.id;
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

    /**
     * Fix 2026-09-30: antes se usaba para "subir hasta el tope" asumiendo
     * que la línea resaltada quedaba en la posición 0 tras el .sort().
     * Ahora el arreglo ya no se reordena (ver _sortingMethod y
     * _processBarcode), así que la línea activa puede estar en cualquier
     * parte de la ruta — este método hace scroll hasta SU posición real,
     * no al tope. Reusa el mismo patrón robusto de _sgScrollListToTop
     * (doble requestAnimationFrame en vez de setTimeout fijo, y asignación
     * directa de scrollTop para WebViews viejos) en vez del setTimeout(100)
     * que tenía antes.
     */
    /**
     * Fix 2026-09-30: la barra de arriba (el aviso "Escanear ubicación" /
     * "Escanear producto" que Odoo pinta fija/pegajosa encima de la lista)
     * tapaba la línea recién escaneada, porque el scroll la dejaba justo en
     * el borde superior del contenedor sin descontar esa barra. Aquí se
     * mide en caliente cualquier elemento fixed/sticky que esté por encima
     * de .o_barcode_lines (sin asumir una clase concreta, para no depender
     * de una versión exacta de stock_barcode) y se usa su altura como
     * margen adicional.
     */
    _sgGetStickyHeaderOffset(page) {
        let offset = 0;
        const pageTop = page.getBoundingClientRect().top;
        const container = page.parentElement;
        if (!container) {
            return offset;
        }

        for (const el of container.children) {
            if (el === page) {
                continue;
            }
            const style = window.getComputedStyle(el);
            if (style.position !== "sticky" && style.position !== "fixed") {
                continue;
            }
            const rect = el.getBoundingClientRect();
            if (rect.height <= 0 || rect.top > pageTop + 4) {
                continue;
            }
            offset = Math.max(offset, rect.height);
        }

        return offset;
    },

    _sgScrollCurrentLineToTop() {
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                const page = document.querySelector(".o_barcode_lines");
                // Fix 2026-09-30: antes solo buscaba .o_selected (la clase
                // propia de Odoo, ligada a selectedLineVirtualId). Al
                // escanear una ubicación, selectedLineVirtualId se limpia a
                // propósito (una ubicación puede tener varias líneas, no
                // una sola), así que .o_selected no encontraba nada y el
                // scroll no se movía. Ahora se busca primero por los
                // atributos propios (data-sg-current-line para producto
                // escaneado, data-sg-active-location-line para ubicación
                // escaneada) que sí se marcan en barcode_line_highlight.xml
                // sin depender de la selección interna de Odoo.
                const currentLine =
                    document.querySelector('.o_barcode_line[data-sg-current-line="1"]')
                    || document.querySelector('.o_barcode_line[data-sg-active-location-line="1"]')
                    || document.querySelector(
                        ".o_barcode_line.sg_scanned_line, .o_barcode_line.o_selected, .o_barcode_line.o_highlight"
                    );
                if (!page || !currentLine) {
                    return;
                }

                const stickyOffset = this._sgGetStickyHeaderOffset(page);
                const pageRect = page.getBoundingClientRect();
                const lineRect = currentLine.getBoundingClientRect();
                const top = Math.max(
                    page.scrollTop + lineRect.top - pageRect.top - stickyOffset - 8,
                    0
                );

                page.scrollTop = top;
                if (typeof page.scrollTo === "function") {
                    try {
                        page.scrollTo({ top, left: 0, behavior: "smooth" });
                    } catch (e) {
                        // Algunos WebView viejos no soportan el objeto de opciones;
                        // scrollTop ya garantizó el resultado.
                    }
                }
            });
        });
    },

    /**
     * Sube la lista de líneas hasta el tope, de forma robusta:
     * - espera dos animation frames tras el re-render de Odoo (en vez de un
     *   setTimeout fijo) para no pelear el scroll contra el propio repintado.
     * - fuerza scrollTop = 0 directo (soportado por cualquier WebView,
     *   incluyendo PDAs Android más viejas donde scrollTo({behavior:'smooth'})
     *   a veces no hace nada).
     * - intenta además un scroll suave como mejora visual, sin depender de él.
     */
    _sgScrollListToTop() {
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                const page = document.querySelector(".o_barcode_lines");
                if (!page) {
                    return;
                }
                page.scrollTop = 0;
                if (typeof page.scrollTo === "function") {
                    try {
                        page.scrollTo({ top: 0, left: 0, behavior: "smooth" });
                    } catch (e) {
                        // Algunos WebView viejos no soportan el objeto de opciones;
                        // scrollTop = 0 ya garantizó el resultado.
                    }
                }
            });
        });
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

                // Fix 2026-09-30: escanear una ubicación solo resalta en
                // verde las líneas de esa ubicación (sg_active_location_line,
                // pintado por CSS en barcode_line_highlight.xml). Ya NO se
                // reordena this.currentState.lines — la ruta de despacho
                // (sg_dispatch_order) es el orden que el operador ve siempre,
                // escanee lo que escanee. Antes aquí se hacía
                // `this.currentState.lines.sort(sorter)` seguido de un
                // scroll al tope; ahora solo se refrescan los flags y se
                // hace scroll hasta donde esté esa ubicación en la ruta.
                this._sgApplyActiveLocationFlags(this.sg_active_source_location_id);
                this.trigger("update");
                this._sgScrollCurrentLineToTop();

                return result;
            }

            if (barcodeData.product) {
                const activeLocationId = this.sg_active_source_location_id;

                const lineAtActiveLocation = activeLocationId
                    ? this.currentState.lines.find(
                          (line) =>
                              line.product_id?.id === barcodeData.product.id &&
                              line.location_id?.id === activeLocationId
                      )
                    : false;

                if (activeLocationId && !lineAtActiveLocation) {
                    // Hay una ubicación activa (en verde), pero este producto
                    // no se despacha desde ahí.
                    this.notification(
                        _t("Este producto no pertenece a la ubicación escaneada."),
                        { type: "danger" }
                    );
                    return;
                }

                if (!lineAtActiveLocation) {
                    // Fix 2026-09-30: no hay ninguna ubicación en verde que
                    // corresponda a este producto todavía (no se ha escaneado
                    // ubicación, o la que está activa es de otro producto).
                    // Antes esto bloqueaba sin hacer nada más. Ahora: solo
                    // señala/resalta la línea de este producto y hace scroll
                    // hasta ella — sin sumar cantidad — y pide la ubicación.
                    const anyLine = (this.currentState?.lines || []).find(
                        (line) => line.product_id?.id === barcodeData.product.id
                    );

                    if (!anyLine) {
                        this.notification(
                            _t("Este producto no pertenece a este picking."),
                            { type: "danger" }
                        );
                        return;
                    }

                    this.selectedLineVirtualId = anyLine.virtual_id;
                    this._sgSetCurrentLine(anyLine);
                    this.trigger("update");
                    this._sgScrollCurrentLineToTop();

                    this.notification(
                        _t("Primero debe escanear la ubicación de origen."),
                        { type: "danger" }
                    );
                    return;
                }

                // La ubicación activa (verde) coincide con este producto:
                // aquí sí se suma cantidad, igual que antes.
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
                    this._sgScrollCurrentLineToTop();
                }

                return result;
            }
        }

        return super._processBarcode(barcode);
    },

    async updateLineQty(virtualId, qty = 1) {
        const line = (this.pageLines || []).find((l) => l.virtual_id === virtualId);

        // Fix 2026-09-30: antes esto solo evitaba que Odoo reasignara la
        // ubicación de origen al editar una línea que no fuera la de la
        // ubicación activa, pero seguía dejando tocar la cantidad con el
        // dedo (modal numérico o el botón rápido "+N" que completa de un
        // toque) sin haber escaneado nada. Eso permitía completar un
        // producto a ciegas, sin pasar por la verificación de ubicación.
        // Ahora: la cantidad de una línea solo se puede tocar (de cualquier
        // forma: modal, botón +N) cuando esa línea es a la vez la línea
        // "actual" (ya se escaneó su producto, sg_current_line) Y su
        // ubicación coincide con la ubicación activa en verde
        // (sg_active_source_location_id) — sin importar en qué orden se
        // escanearon las dos cosas.
        if (this.record?.picking_type_code === "outgoing" && line) {
            const activeLocationId = this.sg_active_source_location_id;
            const isReady = Boolean(
                line.sg_current_line
                && activeLocationId
                && line.location_id?.id === activeLocationId
            );

            if (!isReady) {
                this.notification(
                    _t("Primero escanea el producto y la ubicación de esta línea (en cualquier orden) antes de cambiar la cantidad."),
                    { type: "danger" }
                );
                return;
            }

            await this.actionMutex.exec(() =>
                this.updateLine(line, { qty_done: qty, dontUpdateSourceLocation: true })
            );
            this.trigger("update");
            return;
        }

        return super.updateLineQty(virtualId, qty);
    },

});
