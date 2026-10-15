/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Tras validar con backorder, el aviso de la PDA llega con el HTML escapado
 * ("<div> <p>&lt;div&gt;...") y se pinta como texto. Este servicio limpia el
 * texto de los avisos que traen etiquetas visibles; los botones (enlace a
 * la orden parcial) no se tocan.
 */
const LOOKS_BROKEN = /&lt;|&gt;|<\/?(div|p|br)\b/i;

export function sgCleanNotificationText(text) {
    if (!text || !LOOKS_BROKEN.test(text)) {
        return null;
    }
    let current = text;
    for (let i = 0; i < 3 && /&lt;|&gt;|&amp;|<\/?[a-z]/i.test(current); i++) {
        const doc = new DOMParser().parseFromString(
            current.replace(/<br\s*\/?>/gi, "\n"),
            "text/html"
        );
        current = doc.body.textContent || "";
    }
    const lines = [];
    for (const piece of current.split(/\n+/)) {
        const line = piece.replace(/\s+/g, " ").trim();
        if (line && !lines.includes(line)) {
            lines.push(line);
        }
    }
    return lines.join("\n");
}

function cleanNode(node) {
    if (!node || node.nodeType !== 1) {
        return;
    }
    const targets = node.matches?.(".o_notification_content")
        ? [node]
        : [...node.querySelectorAll?.(".o_notification_content") || []];
    for (const target of targets) {
        if (target.childElementCount) {
            continue;
        }
        const cleaned = sgCleanNotificationText(target.textContent);
        if (cleaned) {
            target.textContent = cleaned;
            target.style.whiteSpace = "pre-line";
        }
    }
}

registry.category("services").add("sg_notification_cleaner", {
    start() {
        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                for (const added of mutation.addedNodes) {
                    cleanNode(added);
                }
                if (mutation.type === "characterData") {
                    cleanNode(mutation.target.parentElement);
                }
            }
        });
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true,
        });
    },
});
