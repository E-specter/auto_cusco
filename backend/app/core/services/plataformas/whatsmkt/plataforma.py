"""Las reglas de la plataforma `whatsmkt` para una definicion de columnas (RF-WM-09 a RF-WM-11).

Es el registro declarativo de RF-72: el constructor de columnas no conoce WhatsMKT, lee estas
reglas. La definicion de una carga de WhatsMKT lleva:

- como primera columna, `número` (con tilde), fija: texto con `51[@telefono]`, en celda de texto
  (RF-73), que no se borra ni se mueve (RF-WM-10);
- despues, una columna por macro, de tipo texto, identificada por su POSICION y no por su
  nombre (RF-WM-11): la segunda columna es la macro 1, la tercera la macro 2... El encabezado por
  defecto es `[$MARCRO{n}$]` (con la errata `MARCRO` del archivo que funciono, S-WM-5), que se
  renumera solo al reordenar porque es nada mas un valor por defecto.

DU-WM-1 (provisional): no hay tope de macros.
"""

from app.core.entities.mapeo import TipoSalida
from app.core.entities.plataformas import ColumnaFija, ReglasPlataforma

CLAVE = "whatsmkt"
ETIQUETA = "WhatsMKT"
COLUMNA_NUMERO = "número"
PREFIJO_PAIS = "51"  # Peru: unico pais de WhatsMKT (P-9)
ENCABEZADO_MACRO = "[$MARCRO{n}$]"

REGLAS_WHATSMKT = ReglasPlataforma(
    clave=CLAVE,
    etiqueta=ETIQUETA,
    columnas_fijas=(
        ColumnaFija(
            posicion=1,
            nombre=COLUMNA_NUMERO,
            contenido_por_defecto=f"{PREFIJO_PAIS}[@telefono]",
            tipo=TipoSalida.TEXTO,
            celda_texto=True,
            contenido_editable=True,
        ),
    ),
    encabezado_por_posicion=ENCABEZADO_MACRO,
    tipo_resto=TipoSalida.TEXTO,
    admite_mas_columnas=True,
)
