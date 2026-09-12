"""Generacion de archivos de carga a partir de la cartera seleccionada.

Une tres piezas que ya existen por separado:

1. la seleccion de productos de una fecha de corte (`seleccion_cartera`),
2. las reglas de mapeo campo por campo (`mapeo_campos`, RF-12),
3. la escritura del archivo en el formato que pida la plataforma (RF-13,
   adaptadores en `app/adapters/output/exportadores/`).

Cubre RF-09, RF-15 y la parte transversal de RF-13. Las reglas propias de cada
plataforma (SMS, WhatsApp, Cisvox) viven en su definicion de carga, no aqui:
este servicio no conoce ninguna.
"""
