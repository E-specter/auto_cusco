"""Catalogo canonico de codigos de incidencia de la ingesta.

Fuente unica para el backend, para el frontend (que traduce cada codigo a una
frase) y para cualquier reporte futuro. Las severidades no van aqui: el mismo
codigo puede emitirse con severidad distinta segun el contexto (por ejemplo,
una clave vacia bloquea la fila, pero en la columna duplicada del pagare es
solo una advertencia).

tests/test_codigos_incidencia.py falla si la ingesta emite un codigo que no
este en esta lista, o si aqui sobra uno que ya nadie emite. Al agregar un
codigo nuevo hay que sumarlo aqui y a frontend/src/i18n/{es,en}.json.
"""

from typing import Final

CODIGOS_INCIDENCIA: Final[frozenset[str]] = frozenset(
    {
        # Cabeceras del archivo (regla N-1)
        "cabecera_desconocida",
        "cabecera_duplicada",
        "columna_faltante",
        # Clave del producto
        "clave_vacia",
        "clave_no_texto",
        "pagare_repetido",
        "pagare_duplicado_distinto",
        # Documento de identidad (regla N-3)
        "documento_vacio",
        "documento_formato_invalido",
        "documento_solo_ceros",
        "dni_completado_con_ceros",
        "ruc_invalido",
        # Telefono (regla N-4)
        "telefono_vacio",
        "telefono_invalido",
        # Tipos de dato
        "fecha_invalida",
        "booleano_invalido",
        "monto_invalido",
        "entero_invalido",
        "vencimiento_operativo_vacio",
        "vencimiento_operativo_invalido",
        # Consistencia entre campos (regla N-8)
        "cuotas_inconsistentes",
        "dias_atraso_difiere_entidad",
    }
)
