"""Constantes de la prueba de exportacion segura (B3), congeladas en HEAD 3e567d7.

Se calcularon con los exportadores TAL COMO ESTABAN, antes de tocar el codigo (worktree limpio en
3e567d7; solo existia el archivo de datos). Comparar contra ellas es comparar contra el
comportamiento de hoy, no una funcion consigo misma.

- XLSX: `huella_xlsx` (todas las partes del zip, sin las marcas de tiempo de `core.xml`, que
  cambian en cada escritura) y `largo_xlsx_sin_core` (el largo menos el `core.xml` COMPRIMIDO, que
  mide entre 233 y 236 bytes segun la hora): de ese largo depende la division por bytes de MOWA
  MES. El largo bruto no se congela: cambia de una corrida a otra.
- CSV y JSON: SHA-256 de los bytes, que son deterministas.
"""

XLSX_GENERICO_SIN_IGUAL = (
    "85f57bf0fa3646bc5139d43f4b9460558a090058c071f37dadadccbd3608d625",
    5110,
)
XLSX_MOWA_SIN_IGUAL = (
    "1192098ad4a4d86b17ece3ce2ae71cc45bff9ed60d497aa3a5addf9db841e07f",
    4878,
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
