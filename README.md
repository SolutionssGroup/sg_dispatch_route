# SG Dispatch Modules - Odoo 17

## Módulos incluidos

### sg_dispatch_route
Módulo de lógica de despacho por rutas.
Incluye:
- definición de rutas de despacho por almacén
- exclusión de ubicaciones
- generación y uso de sg_dispatch_order
- preparación de líneas para picking y barcode

### sg_barcode_dispatch_order
Módulo aislado para personalizar el orden visual de líneas en el módulo Barcode.
Incluye:
- extensión del modelo frontend de Barcode
- prioridad de orden usando sg_dispatch_order
- separación respecto al módulo principal para facilitar mantenimiento y pruebas

## Dependencias
- stock
- sale_stock
- stock_barcode
- sg_dispatch_route

## Entorno
- Odoo 17
- Docker

## Orden de instalación
1. Instalar sg_dispatch_route
2. Instalar sg_barcode_dispatch_order
3. Limpiar assets si se actualiza JS
4. Reiniciar Odoo

## Objetivo
Permitir que la lógica de despacho genere un orden de picking y que ese orden se refleje dentro del módulo de Código de Barras.
