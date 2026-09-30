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

## 5. Criterios de `coordinador_modulo_mowa_mes` para sus cortes (2026-09-29)

Congelamiento acordado: nadie más toca `speech.py`, `segmentos.py` ni los rangos de `entities/mowa_mes.py` mientras duren B5 y B2.

- **B5:** el oro cubre, además de los 6 segmentos, los bordes:
  - un segmento con `[whatsapp]` y sin número (`FaltaWhatsapp`, `ejemplo` nulo, `usa_whatsapp` verdadero);
  - `mensaje_excede_150` y `mensaje_excede_160` en sus bordes (`9 a 30` da 156 con el original);
  - titular y vencimiento vacíos, con el mismo orden de exclusiones;
  - el rechazo de `[@` en las partes;
  - un titular de menos de 8 caracteres.

  `speech_huella` de las versiones existentes sin cambios: se compara con el valor del Speech original que da el coordinador de MOWA MES. El rendimiento se mide solo contra `auto_cusco_test` (`$env:DB_NAME = "auto_cusco_test"`).
- **B3:** en XLSX, la protección se hace por tipo de celda y nunca cambia el contenido. Verificado con openpyxl: una celda con el tipo de texto explícito escribe `=1+1` como `inlineStr`, igual que el resto de las celdas. `-`, `+` y `@` ya salían como texto literal, así que solo cambia `=`. El apóstrofo es solo del CSV, y MOWA MES no usa CSV. Prueba: `mensaje` y `dni` del archivo idénticos a lo guardado en `mowa_mes_fila_cargada`.
- **B2:** además de la prueba de claves contra el enum, otra que compare `desde`, `hasta` y `etiqueta` de los 6 rangos con los valores de hoy (S-MM-6: 0 días es Preventiva; más de 120 días queda sin speech). `contratos/openapi.json` sin cambios (`dias_desde` y `dias_hasta` de la previsualización del speech).
- **Huella v1 (B5):** constante del Speech original, sacada del documento (`speech_del_documento()` de `tests/test_speech_original.py`): `297c227cfdd0bb5e1636e08d4ed6cebab971d724c84223acfdb0cfebc2fcf88a`. La comprobó el coordinador de MOWA MES y yo en HEAD `4e7ccc1`. Segunda prueba: varias `PartesSegmento` sintéticas (espacios en los extremos, tildes, `[whatsapp]`, corchetes sueltos, partes vacías) con sus huellas fijadas como constantes **antes** de tocar el código, calculadas en HEAD. Si no, la prueba compara la función consigo misma. La versión del usuario con id 92 se comprueba a mano después de B5 y nunca entra en pruebas.

## 6. Reparto del frontend y lo que B4a tiene que traer (2026-09-29)

Reparto según §8 de `motor-texto-enriquecido-interfaz.md` (F1, commit `05e5885`), aprobado por architec: F2 (componentes compartidos) es de `designer`; F3 (pantalla del constructor) y F4 (integración M2) son de `dev_frontend_motor_texto_enriquecido`. Orden: B4a → F2; F3 espera B4b y F2; F4 espera B6 y F2.

B4a trae, además de §10 del diseño:

- **Catálogo:**
  - el registro de ejemplo;
  - por función: nombre visible y descripción (claves i18n), familia, tipos de entrada y salida, y parámetros con tipo, rango, opciones de los enumerados y si admiten una variable;
  - los patrones de fecha frecuentes con su ejemplo;
  - por contexto: el límite de largo y el umbral de advertencia que aporta el módulo (MOWA MES: 160 y 150), o ninguno.
- **Validación:** `ubicacion` con el índice de nodo, el índice de función y el nombre del parámetro, o nula cuando es de toda la expresión (por ejemplo, un límite de tamaño).
- **Previsualización:**
  - el resultado por nodo, que distingue una variable vacía (nula) de un texto vacío, para la marca punteada de §3 de la interfaz;
  - el largo actual, la cota si existe y, si no, el motivo con su código;
  - los problemas de fila aparte de los de validación.
- **Prueba espejo `CodigoTexto` ↔ `textoEnriquecido.codigo.*`:** los códigos los fija B4a y las claves las agrega designer en F2. Las dos partes entran juntas, en el mismo commit de architec, o la prueba de uno de los dos lados queda en rojo.
- **Muestra de la previsualización de una definición** (resuelto con designer, §5.5 de la interfaz): el pedido recibe una de dos fuentes, y cada fila devuelve su segmento.
  - **«Ejemplos por segmento»** (por defecto, editor y constructor): una fila por segmento, con el registro de ejemplo y un valor sintético de días que cae en cada rango, derivado de la tabla de rangos y no escrito a mano. Va en **B4a**, porque F2 (el selector de variantes) lo necesita.
  - **«Cartera real»** (opcional, constructor): una fecha de corte más una selección con la misma forma que `/cartera` (filtros, orden y cantidad 5), con el mismo orden y desempate que la carga. Usa el recorrido de siempre (`seleccion_cartera/recorrido.py`), no una consulta nueva. Es de solo lectura y no guarda nada. Va en **B4b**, que solo agrega "primeros N de una selección" al endpoint de B4a, que ya acepta un producto real (fecha de corte y pagaré). Decisión de architec.
  - Los primeros 5 sin filtro, descartado: rara vez caen en segmentos distintos.

## 7. Nombres que el frontend ya usa (2026-09-29)

`frontend/src/lib/expresion.ts` (designer, `5ffeddf`) tiene tipos provisionales que pasarán a ser alias de los generados desde el contrato. B1 y B4a respetan estos nombres, o avisan a designer **antes** de entregar:

- `Problema.ubicacion.nodo`: el índice de nodo;
- por función del catálogo, `devuelve`, con el valor `entrada` para las funciones que devuelven el mismo tipo que reciben;
- `obligatoria` en el nodo `variable`.

En `expresion.ts`, el tipo a lo largo de la cadena solo filtra el menú de funciones compatibles a partir del catálogo. La validación sigue siendo del backend (regla 7).

## 8. Brief de B5 (MOWA MES M1), listo para lanzar cuando se acepte B1

**Qué cambia:** solo `plataformas/mowa_mes/speech.py` por dentro, más la unificación de `PREFIJO_WHATSAPP` (j de B1). La constante vive en `entities/texto_enriquecido.py`, para que una entidad no dependa de un servicio; `funciones/enlaces.py` la importa y `entities/mowa_mes.py` la reexporta con el mismo nombre. El oro fija el largo del enlace en 26. No cambian la API, la base de datos, la interfaz, `huella_speech` ni las firmas públicas que usan `campana.py` y `configuracion.py` (`ConstructorMensajes`, `mensaje_de`, `requiere_whatsapp_faltante`, `previsualizar`, `codigo_por_largo`, `whatsapp_valido`, `problemas_de`, `limpiar`).

**Cómo:**
- Cada `PartesSegmento` v1 se convierte a una `Expresion`: variable `titular | primeros(8)`, texto de `parte_1` cortado en `[whatsapp]`, variable del vencimiento con `formato_fecha("dd/mm/aaaa")`, y lo mismo para `parte_2`. `[whatsapp]` pasa a ser una variable de contexto `whatsapp_contacto | enlace_whatsapp`, no un `str.replace`.
- El contexto de la fila aporta `titular`, `fecha_vencimiento_cuota` y `whatsapp_contacto`. Se compila una vez por segmento.
- `FaltaWhatsapp` sigue igual: los segmentos que usan WhatsApp sin número quedan sin compilar.
- El largo máximo sale de `Compilada.cota`. Si una v1 da una cota distinta de la aritmética actual, es un defecto que se reporta; no se ajusta la prueba.
- `ejemplo` puede seguir por el camino actual en M1 (D8).
- El camino viejo (`plantilla_mensaje`, `contexto_fila`) queda en el código hasta cerrar M2, solo como referencia de la prueba de oro.

**Prueba de oro** (con los criterios de `coordinador_modulo_mowa_mes`, §5):
- Los 6 segmentos del Speech original más partes sintéticas: espacios en los extremos, tildes y ñ, corchetes sueltos (`[`, `]`, `[whatsapp` sin cerrar), `[whatsapp]` repetido, partes vacías.
- Titulares: largo, corto (menos de 8), con tildes, con espacios al inicio, y vacío o en blanco (excluidos antes del mensaje).
- Con y sin número de WhatsApp.
- Se compara: mensaje byte a byte contra `plantilla_mensaje` más `GeneradorCargas`; `previsualizar` entero (`largo_maximo`, `codigo`, `usa_whatsapp`, `ejemplo`); los bordes de 150 y 160 (`9 a 30` da 156); el orden de exclusiones de `campana.py` (`falta_titular`, `falta_vencimiento` y `falta_whatsapp`) y el rechazo de `[@`.

**Huellas:** la constante del Speech original `297c227c…fcf88a`, más las huellas de las partes sintéticas **calculadas en HEAD antes de tocar el código** y fijadas como constantes.

**Rendimiento:** lo mide architec, antes (HEAD) y después (el corte), con `medir_campana_mowa_mes.py` sobre 46 000 filas contra `auto_cusco_test`, a no más de 10 % de diferencia. El dev informa el rendimiento del núcleo sin base.

**Verificación:** el dev corre las capas sin base. Las pruebas PostgreSQL se escriben con `@pytest.mark.postgres`, fechas de 2099 y limpieza de lo que crean, pero no se corren: se declaran "postgres escritas, no corridas". Mutación a mano en el worktree sobre la conversión v1 a expresión, la cota y `FaltaWhatsapp`.

**Revisión:** `coordinador_modulo_mowa_mes` revisa antes de que el corte vaya a architec.

**Decisión del usuario (2026-09-30), vale para todos los cortes:** solo architec verifica con base. Nadie copia el `.env` ni pasa credenciales por variables de entorno. architec corre las capas PostgreSQL y el rendimiento al verificar cada corte, y si algo falla devuelve el corte con la salida.

## 9. Arrastres de B5 para B6 (2026-09-30)

- **Borrar el camino viejo:** `plantilla_mensaje`, `contexto_fila`, `CAMPOS_CONTEXTO`, `enlace_whatsapp` de `speech.py` si ya nadie lo usa, y la comparación en vivo contra `GeneradorCargas` de `test_mowa_mes_speech_oro.py`. El oro sigue contra las constantes congeladas en HEAD `11f1184`: los 6 mensajes literales del original y el SHA-256 de la matriz. Pedido de `coordinador_modulo_mowa_mes`.
- **Rendimiento:** si la medición de campaña de architec pasa el 10 %, se abre un corte del núcleo (validar el teléfono una vez por valor, o plegar las variables de contexto constantes al compilar), aparte de B5 y B6.
- **Versión 92 del usuario:** después del commit de B5, `coordinador_modulo_mowa_mes` comprueba a mano que su huella no cambió.
