"""Constantes de la prueba de exportacion segura (B3), congeladas en HEAD 3e567d7.

Se calcularon con los exportadores TAL COMO ESTABAN, antes de tocar el codigo (worktree limpio en
3e567d7; solo existia el archivo de datos). Comparar contra ellas es comparar contra el
comportamiento de hoy, no una funcion consigo misma.

- XLSX: `huella_xlsx` (todas las partes del zip, sin las marcas de tiempo de `core.xml`, que
  cambian en cada escritura) y `largo_sin_comprimir_sin_core` (la suma del largo SIN comprimir de
  todas las partes menos `core.xml`). El largo comprimido no se congela: depende de la
  implementacion de zlib (el clasico y el zlib-ng de CPython 3.14 en Windows difieren en unos
  bytes con las mismas partes) y la division por bytes de MOWA MES mide el tamano real en cada
  corrida. En B10 el largo pasa de comprimido (5110 y 4878) a sin comprimir (18331 y 17333): los
  exportadores no cambiaron (la huella sigue siendo la de HEAD 3e567d7) y el nuevo largo da lo
  mismo en CPython 3.13.14 (zlib) y 3.14.7 (zlib-ng).
- 2026-10-20 (a154df6): las dos funciones deshacian el salto de linea del sistema en las hojas.
  openpyxl escribe la hoja en un archivo temporal de texto, y en Windows el LF de un valor salia
  CR LF: las constantes de B10 (18331 y 17333) eran las de Windows, y en Linux, donde corre el CI,
  daban un byte menos por valor con salto de linea. Los exportadores no cambiaron.
- Desde B17 los exportadores escriben LF en la hoja en todos los sistemas (el XLSX deshace ese
  CR LF al terminar) y las dos funciones YA NO NORMALIZAN NADA: comparan los bytes reales. Los
  valores de abajo, los de a154df6, dan lo mismo en Windows y en Linux sin ninguna normalizacion
  en la prueba; esa es la prueba de B17 en las huellas.
- CSV y JSON: SHA-256 de los bytes, que son deterministas.
"""

XLSX_GENERICO_SIN_IGUAL = (
    "5664ff029719e92decffc9763dcf552db7a2d70398e5c6f05cb390f7a6c4b16b",
    18330,
)
XLSX_MOWA_SIN_IGUAL = (
    "ae4510e26e92184891c7b49c6ba5a3ccd3a9349c1c7d20a97c42718c5bac52f2",
    17332,
)

# CSV con las opciones por defecto, y con `;` y `utf-8-sig`.
CSV_SIN_IGUAL = "d8dbb429c27ddd9439a316dc6e3a1e5b29aac92c4fb2def9a91b3ab510f92a84"
CSV_SIN_IGUAL_PUNTO_Y_COMA_CON_BOM = (
    "645a98b00b69b9e6ae1a9bdb7a04c2deb8eab808ba6312ad9a8527dc98e0b4e7"
)
CSV_PELIGROSA = "375bc476d335da003e35bf6a9e8cb7bbf4e5f7234a97394a54ac320b7d09c6d2"
CSV_PELIGROSA_PUNTO_Y_COMA_CON_BOM = (
    "6863ab75bb9fb3a3112e1503a5f0054c060cf6dd477269b057d3079e3c48c4db"
)

JSON_SIN_IGUAL = "b15717f080710ace032dbc3a83f954526c1f85f801f5c713876dae25e56ecd77"
JSON_PELIGROSA = "b2a09be9da82dd3308ea6e687e62199414185c57ba45cc1539aa84f7fa20fd5a"
