# Plan de ejecución del motor de texto enriquecido (T-MTE-C1)

Propuesta del 2026-09-29, a la espera de la confirmación de `architec`. Contrasta `docs/motor-texto-enriquecido.md` con el código de HEAD `61647cd`.

## 1. Contraste del diseño con el código

Lo que se sostiene tal cual: extender `mapeo_campos` (`GeneradorCargas` ya compila una vez y aplica por fila, y junta los errores por fila), el valor crudo de una referencia simple (`plantillas.valor_crudo`), la huella v1 (`campana.huella_speech` sobre las partes), `numero_valido` para el enlace, `LARGO_NUMERO_WHATSAPP = 9`, `FORMATO_VENCIMIENTO = "%d/%m/%Y"` (10 caracteres, lo mismo que `dd/mm/aaaa`), las exclusiones `falta_titular` y `falta_vencimiento` fuera del mensaje (`campana.py:169-174`), y las piezas para medir (`scripts/medir_campana_mowa_mes.py`, `medir_generacion.py`).

Lo que no se sostiene o necesita precisión:

| # | Punto del diseño | Qué dice el código | Propuesta |
|---|---|---|---|
| D1 | §4.2: la conversión final a texto usa `exportadores/comunes.a_texto` | `plantillas.aplicar` usa `str(valor)`. Verificado: `[@b]` con `True` da `"True"`; `a_texto(True)` da `"1"`. Además, el núcleo no puede importar de `adapters/` | La conversión implícita del motor es la de hoy (`str`), para cumplir RF-54. `a_texto` sigue siendo solo de los exportadores. Quien quiera otro formato usa una función de formato |
| D2 | §4.2 y RF-43: tipos `texto`, `numero`, `fecha`, `nulo` | El catálogo tiene `TipoDato.BOOLEANO` (`TipoCampo.BOOLEANO` y los `*_aplica`) | Agregar `booleano` al sistema de tipos, sin funciones propias por ahora. Si no, esos campos quedan sin tipo en el catálogo del motor. Toca la redacción de RF-43 |
| D3 | §7: `RANGOS_SEGMENTO` se mueve al núcleo | `RangoSegmento.segmento` es el `StrEnum` `Segmento` de MOWA MES, y lo usan `api/mowa_mes.py`, `api/mowa_mes_campanas.py`, `speech.py` y `segmentos.py` | El núcleo define `RangoDias(clave: str, etiqueta, desde, hasta)` y la tabla por defecto. MOWA MES conserva su enum `Segmento` y arma `RANGOS_SEGMENTO` a partir de la tabla del núcleo, con una prueba de que las claves coinciden con el enum. Los datos viven en un solo lugar y la API de MOWA MES no cambia |
| D4 | §9: la definición registra `proteger_formulas` | Los exportadores reciben `Tabla` y `OpcionesArchivo`, no la definición | La marca viaja en `OpcionesArchivo.proteger_formulas` (verdadero por defecto). La definición la guarda y el servicio la pasa a las opciones. Así B3 no depende de B2 |
| D5 | §9 CSV: apóstrofo en todo texto que empieza con `=`, `+`, `-`, `@`, tabulación o retorno | En CSV, todo sale como texto. Un importe `financiero` negativo (`-1,234.56`), un entero negativo y un teléfono armado como `+51[@telefono]` llevarían apóstrofo y romperían la carga en la plataforma | No proteger los valores que no son `str` en la tabla ni los textos que son solo un número (`^[+-]?\d[\d.,]*$`): Excel los lee como número, no como fórmula. Es un ajuste a una decisión del usuario: lo decide `architec` o lo consulta |
| D6 | RF-54 frente a RF-53 | Verificado: hoy el XLSX escribe `=1+1` como fórmula viva (`<f>1+1</f>`), también en los archivos de MOWA MES | La protección cambia el resultado solo en los textos peligrosos. Dejarlo escrito como excepción a RF-54, no como regresión |
| D7 | Bytes de los archivos de MOWA MES | `archivo_carga.py` usa `exportador_xlsx`, y la división por bytes reales depende de lo que escribe. Hoy los textos salen como `inlineStr` | B3 solo cambia las celdas peligrosas. Las demás tienen que salir byte a byte iguales: prueba sobre un archivo de MOWA MES antes y después |
| D8 | §11 M1: la API no cambia | `previsualizar` devuelve además `ejemplo`, con marcadores (`XXXXXXXX`, `dd/mm/yyyy`) y no con valores evaluados | La prueba de oro de B5 compara mensaje, largo máximo y `ejemplo`. En M1, `ejemplo` puede seguir con el camino actual. En B6, el motor necesita un modo de marcadores por nodo para reproducirlo |
| D9 | §4.1: ida y vuelta texto → expresión → texto | Un nodo `texto` con `[@` no tiene representación en la sintaxis de texto. Los argumentos entre comillas pueden tener `]` o `\|`, y la expresión regular de hoy no los admite | La sintaxis de texto necesita un analizador léxico con comillas y un escape para `[@`. La garantía es texto → expresión → texto. En sentido contrario, una expresión que no se pueda escribir como texto se informa, no se deforma |
| D10 | §4.3 obligatoria vacía | MOWA MES considera vacío un titular de solo espacios (`campana._vacio`) | En B6, "vacía" para una variable obligatoria tiene que coincidir con `_vacio`, o cambia la exclusión |
| D11 | §8 valor crudo | Solo la referencia simple conserva el tipo | Conservar el tipo final también cuando la columna es un solo nodo `variable` con funciones (por ejemplo, `redondear(2)` en una columna `numero`). Hoy funcionaría pasando por texto, pero es frágil |
| D12 | Alcance | `mowa_mes/nombre_archivo.py` tiene otro minilenguaje de plantillas (`{...}`) | Fuera del alcance. Queda como candidato a consumidor futuro, sin tocarlo |

Nada de esto invalida el diseño. D1, D2, D5 y D6 cambian su texto o su redacción; lo demás son precisiones para los devs.

## 2. Cortes y orden

`dev_backend_motor_texto_enriquecido` es una sola sesión, así que "en paralelo" solo aplica entre backend y experiencia (F1).

| Orden | Corte | Depende de | Notas |
|---|---|---|---|
| 1 | **B1** núcleo | — | Incluye D1, D2 y D9. Toda plantilla de las pruebas actuales pasa por el motor sin cambios |
| 1' | **F1** experiencia (designer) | diseño | Puede empezar ya contra §4 a §10; se ajusta cuando esté B4a |
| 2 | **B5** M1 con oro | B1 | Incluye D8. Coordinación con `coordinador_modulo_mowa_mes` |
| 3 | **B3** exportación segura | — | Independiente del motor. Incluye D4 a D7 (D5 después de la respuesta de architec). Pruebas de `/archivos-carga` y de MOWA MES en verde |
| 4 | **B2** columnas y segmentación | B1 | Incluye D3 y D11. **También toca MOWA MES** (`segmentos.py`, `entities/mowa_mes.py`): coordinación con `coordinador_modulo_mowa_mes` |
| 5 | **B4a** contrato del motor: catálogo, validación y previsualización, `CodigoTexto` con prueba espejo, OpenAPI | B1, B2 | Desbloquea F2 |
| 6 | **B4b** persistencia: definiciones guardadas y versionadas, migración con ida y vuelta, `/archivos-carga` con definición guardada, OpenAPI | B4a | Desbloquea F3 |
| 7 | **F2** editor | B4a, F1 | |
| 7' | **B6** M2 backend | B5, B4a | En paralelo con F2 |
| 8 | **F3** constructor | B4b, F1 | |
| 9 | **F4** MOWA MES M2 frontend | B6, F2 | Coordinación con `coordinador_modulo_mowa_mes` |
| 10 | **C2** revisión integral | todo | |

Cambios respecto de la sugerencia de architec: B3 va antes que B2 porque es independiente y corto, y B4 se parte en B4a y B4b para que el editor (F2) no espere a la persistencia.

## 3. Verificación de cada corte (criterio de listo)

- Worktree desde HEAD, `backend/scripts/verificar.ps1 -ConBase` contra `auto_cusco_test`.
- B1: propiedades con semilla fija (sintaxis ida y vuelta, `primeros`, `sin_tildes`) y todas las plantillas de `test_mapeo_*` y `test_generacion_cargas*` por el motor.
- B5: oro de los 6 segmentos (mensaje, largo y ejemplo), con titular corto, largo, con tildes, de solo espacios y vacío, y con y sin WhatsApp; corchetes sueltos en las partes. `medir_campana_mowa_mes.py` con 46 000 filas, a no más de 10 % sobre el actual. Mutación a mano en worktree.
- B3: leer de vuelta CSV y XLSX; bytes idénticos del archivo de MOWA MES sin textos peligrosos.
- B4a y B4b: contrato regenerado, prueba espejo de códigos, migración con ida y vuelta.
- Frontend: `npm run verificar` con `$env:PLAYWRIGHT_PUERTO` propio, y axe en los estados nuevos.

## 4. Pendientes del usuario (no bloquean el arranque)

Tabla de rangos por defecto, codificación SMS y días ajustados fuera de MOWA MES, según §14 del diseño. Se suma D5 si architec decide consultarlo.
