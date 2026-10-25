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
- 2026-10-24 (T-MTE-B18): los datos de prueba traian un telefono que podia ser real y pasaron al
  rango sintetico 900000xxx. Cambiaron SOLO las huellas de las salidas que llevan ese
  telefono (el XLSX generico, los cuatro CSV y los dos JSON); `XLSX_MOWA_SIN_IGUAL` y los largos
  no cambian. Se recalcularon con los exportadores de main SIN tocarlos, y para cada una se
  comprobo que devolver el telefono viejo en los bytes de la salida (en cada parte del zip, en el
  XLSX) reproduce EXACTAMENTE la huella anterior: lo unico que se movio es el telefono.
"""

XLSX_GENERICO_SIN_IGUAL = (
    "5ad35c5176548d90ac8ec74d1078daf2347b5697cbd4301c65da826244b143a7",
    18330,
)
XLSX_MOWA_SIN_IGUAL = (
    "ae4510e26e92184891c7b49c6ba5a3ccd3a9349c1c7d20a97c42718c5bac52f2",
    17332,
)

# CSV con las opciones por defecto, y con `;` y `utf-8-sig`.
CSV_SIN_IGUAL = "343d47272bd6c6dd2347e00eec8b33414b8b2b54b23b8e1704eb4a87f89d5d64"
CSV_SIN_IGUAL_PUNTO_Y_COMA_CON_BOM = (
    "33d5d7df7d02f86842a9d2e67931ee5269ce29046083df559ef17d06da728b11"
)
CSV_PELIGROSA = "a9c31b1a58528732e2aa25ab2175c39fb92250adcd19a71bdd58d04fd79d3970"
CSV_PELIGROSA_PUNTO_Y_COMA_CON_BOM = (
    "fcb73d4e26c89b997f2624a3f5d7815a733f79e5840bbfe0725473f5a6e2165d"
)

JSON_SIN_IGUAL = "296bfddf785874ad9957d199f9e0a94aef891b83723c18c30837bd75dcd90964"
JSON_PELIGROSA = "a926232f24f60453b5e990494dc5232bf2f6422ccaa43f1e0e96881900cb0b12"
