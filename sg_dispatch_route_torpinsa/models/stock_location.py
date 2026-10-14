import re

from odoo import models

# 1-T4-7 -> nivel 1, tramo 4, posicion 7
_RE_NIVEL_TRAMO_POS = re.compile(r"^\s*(\d+)\s*-\s*T\s*(\d+)\s*-\s*(\d+)\s*$", re.I)
# 3-PI-9, 2-PASILLO-1 -> nivel, nombre, posicion
_RE_NIVEL_NOMBRE_POS = re.compile(r"^\s*(\d+)\s*-\s*([^-\d][^-]*?)\s*-\s*(\d+)\s*$")
# MOSTRADOR-12 -> nombre, posicion
_RE_NOMBRE_POS = re.compile(r"^\s*([^-\d][^-]*?)\s*-\s*(\d+)\s*$")


def sg_route_sort_key(name):
    """
    Clave de ruta de una ubicacion: MAYOR = se visita PRIMERO.

    El orden es numerico (no por texto: T10 va antes que T4) y cada parte
    de mayor a menor, de izquierda a derecha: nivel, tramo, posicion.
    Grupos: 3 = nivel-Tn-posicion, 2 = nivel-nombre-posicion (PA, PASILLO,
    PI), 1 = nombre-posicion (MOSTRADOR-n), 0 = cualquier otro (DESPACHO).
    La ubicacion raiz no pasa por aqui: el llamador la deja siempre al final.
    """
    name = name or ""
    match = _RE_NIVEL_TRAMO_POS.match(name)
    if match:
        nivel, tramo, pos = (int(g) for g in match.groups())
        return (3, nivel, "", tramo, pos)
    match = _RE_NIVEL_NOMBRE_POS.match(name)
    if match:
        return (2, int(match.group(1)), match.group(2).upper(), 0, int(match.group(3)))
    match = _RE_NOMBRE_POS.match(name)
    if match:
        return (1, 0, match.group(1).upper(), 0, int(match.group(2)))
    return (0, 0, name.upper(), 0, 0)


class StockLocation(models.Model):
    _inherit = "stock.location"

    def _sg_route_sort_key(self):
        self.ensure_one()
        return sg_route_sort_key(self.name)
