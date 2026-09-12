"""Motor de reglas de mapeo y expresion de campos (RF-12).

Modulo nucleo compartido por las cargas digitales (Fase 3) y las VoIP (Fase 4):

- plantillas.py -- interpreta `[@campo]`, valores fijos y concatenaciones.
- formatos.py   -- aplica el tipado explicito: texto, numero, fecha y financiero.
- generador.py  -- convierte productos en filas de salida, juntando los errores
                   por producto en vez de detener la generacion.

No conoce ninguna plataforma: las cabeceras y reglas concretas de cada una
viven en su propio adaptador.
"""
