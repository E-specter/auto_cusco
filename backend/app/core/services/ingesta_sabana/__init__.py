"""Caso de uso: ingesta de sabanas diarias (RF-01, RF-02, RF-03).

Vertical slice de la Fase 1. Por ahora contiene la parte pura del nucleo:

- reglas.py      -- reglas de normalizacion por valor (N-2 a N-6).
- catalogo.py    -- catalogo configurable de columnas de la hoja VENCIDA.
- cabeceras.py   -- mapeo de cabeceras por nombre y alias (N-1).
- normalizador.py -- normalizacion de filas y chequeos de consistencia (N-8).

La lectura del archivo (.xlsb), la persistencia y el endpoint HTTP se
agregaran como adaptadores. Reglas de referencia: docs/sabana-schema.md.
"""
