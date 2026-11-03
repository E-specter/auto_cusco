"""La plataforma `mowa_mes` y la definicion de su archivo de carga (RF-MM-37, RF-72).

El archivo de RF-MM-10 tiene tres columnas fijas, en este orden: `numero` (entero), `mensaje` y
`dni` (texto, con sus ceros a la izquierda). Aqui se declaran una sola vez:

- `REGLAS_MOWA_MES`: las reglas de plataforma (RF-72). `mowa_mes` NO esta en el registro publico de
  plataformas (decision del usuario, 2026-11-02): el constructor de columnas no la ofrece, porque
  sacaria archivos de MES sin speech, sin exclusiones, sin supervisores y fuera del limite
  mensual. Las reglas existen para validar `DEFINICION_MOWA_MES` con las mismas funciones que
  valida cualquier definicion con plataforma (`problemas_de_plataforma`).
- `DEFINICION_MOWA_MES`: la definicion que usa el escritor del archivo
  (`adapters/output/plataformas/mowa_mes/archivo_carga.py`). Vive en codigo, no en la base: una
  campana tiene que ser reproducible y el formato lo exige MES.

El `mensaje` NO se construye aqui: llega hecho (speech v2, GSM-7 y el tope de 160 los aplica
`campana.evaluar_producto`), asi que las tres columnas son referencias directas a los campos de la
fila (`FilaCarga.celdas()`). El valor de una referencia directa no se vuelve a interpretar: un `[@`
dentro del mensaje es dato.
"""

from app.core.entities.mapeo import CampoSalida, DefinicionCarga, TipoSalida
from app.core.entities.plataformas import ColumnaFija, ReglasPlataforma
from app.core.entities.texto_enriquecido import TipoValor

PLATAFORMA = "mowa_mes"

REGLAS_MOWA_MES = ReglasPlataforma(
    clave=PLATAFORMA,
    etiqueta="MOWA MES",
    columnas_fijas=(
        ColumnaFija(1, "numero", None, TipoSalida.NUMERO),
        ColumnaFija(2, "mensaje", None, TipoSalida.TEXTO),
        ColumnaFija(3, "dni", None, TipoSalida.TEXTO),
    ),
    admite_mas_columnas=False,
)

DEFINICION_MOWA_MES = DefinicionCarga(
    nombre=PLATAFORMA,
    campos=(
        CampoSalida("numero", "[@numero]", TipoSalida.NUMERO),
        CampoSalida("mensaje", "[@mensaje]", TipoSalida.TEXTO),
        CampoSalida("dni", "[@dni]", TipoSalida.TEXTO),
    ),
)

# Las variables de la fila de entrada (`FilaCarga.celdas()`) con su tipo: `numero` entra entero.
TIPOS_DE_LA_FILA = {
    "numero": TipoValor.NUMERO,
    "mensaje": TipoValor.TEXTO,
    "dni": TipoValor.TEXTO,
}
