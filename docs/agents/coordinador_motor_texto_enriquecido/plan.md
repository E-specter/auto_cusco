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

## 10. B7: plegar las variables de contexto constantes (2026-09-30)

**Por qué:** en B5, la medición de architec con 46 000 filas dio previsualizar +9 % (de 5,06 s a 5,52 s) y crear +2 %. Queda dentro del 10 %, pero justo. Una causa conocida: `enlace_whatsapp` valida el teléfono (RF-02) en cada fila, aunque el número de contacto es el mismo en toda la campaña. Hay que hacerlo antes de B6, que suma la lectura de v1 y v2.

**Qué:**
- `evaluador.compilar` acepta, opcionalmente, un mapa de **constantes**: variables cuyo valor se conoce al compilar y es el mismo para todas las filas.
- Un nodo `variable` cuya variable es constante, y cuyos argumentos variables también lo son o son literales, se evalúa **una vez al compilar** y queda como texto fijo en la compilada.
- Los problemas de esa evaluación se informan al compilar, con su ubicación, en lugar de repetirse por fila.
- Sin constantes, todo sigue igual que hoy.

**Invariantes:**
- `Compilada.cota` no cambia por plegar. Si el valor plegado mide menos que la cota del nodo, se conserva la cota del nodo, que es la que ve el usuario. Ejemplo: en `previsualizar`, el enlace mide 26 con o sin número.
- El resultado de evaluar es idéntico con plegado y sin plegado para cualquier fila.
- `Resultado.valor` (D11) no cambia.
- Sin `eval`, y las constantes pasan por la misma comprobación de tipos que las variables.

**MOWA MES:**
- `ConstructorMensajes` compila con `{whatsapp_contacto: número}` como constante.
- `previsualizar` sigue sin constantes, porque calcula el largo sin depender del número.
- Consecuencia a documentar: un número inválido se detecta al construir, con `MensajeNoGenerable` o un error equivalente, y ya no por fila. Sigue siendo inalcanzable, porque configuración y campaña validan antes.
- El oro de B5 (constantes congeladas, matriz de 4 992 casos y huellas) sigue en verde sin tocarlo.

**Pruebas:**
- Propiedad con semilla fija: para expresiones y filas aleatorias, evaluar con y sin constantes da el mismo texto, el mismo valor y los mismos problemas (salvo que los plegados se informan al compilar).
- La cota es igual con y sin plegado.
- Microbench `medir_mensajes_mowa_mes.py`: tiene que acercarse a HEAD antes de B5, unos 2,8 µs por fila.
- Architec repite `medir_campana_mowa_mes.py`.
- Mutación a mano en el worktree.

**Condición de architec para B7 (2026-09-30): sin cambiar la semántica por segmento.**
- Un segmento que usa `[whatsapp]` sin número sigue sin compilarse y lanza `FaltaWhatsapp` solo si se le pide un mensaje. Los demás segmentos se generan igual.
- Con el número en `None`, no se pasa como constante. Un segmento que no lo usa compila igual que hoy.
- Si el plegado da un problema al compilar (por ejemplo, un número inválido, que hoy es inalcanzable), el problema queda en **ese** segmento: se guarda y se lanza `MensajeNoGenerable` al pedirle un mensaje, sin romper el constructor ni los demás segmentos.
- El oro de B5 sigue en verde sin tocarlo.

**Criterios de `coordinador_modulo_mowa_mes` para B7**, con una prueba cada uno:
- Una campaña cuyos productos no caen en segmentos con `[whatsapp]` se sigue generando.
- "Sin número" sigue siendo `_sin_whatsapp`, no un error.
- Previsualizar el speech con un número inválido sigue respondiendo el 400 de hoy, no un 500 ni `MensajeNoGenerable`.
- El plegado depende solo del valor constante de la campaña: dos filas del mismo segmento dan mensajes distintos solo por titular y vencimiento.
- El oro de B5 queda intacto, y architec vuelve a medir previsualizar y crear.

**B5 cerrado para MOWA MES (2026-09-30):** sobre `63f845d`, las huellas de la versión 17 (Speech original) y de la 92 (v1 del usuario) siguen iguales. Lo comprobó `coordinador_modulo_mowa_mes`, solo leyendo.

## 11. Cierre de B3, B7 y B2 (2026-09-30, decisiones de architec mientras el coordinador estuvo desconectado)

- **B3** (`0772e78`): con las dos correcciones de la revisión (largo del XLSX sin `core.xml` y cabeceras del CSV protegidas).
- **B7** (`b8b9025`): aprobado **sin** un camino rápido en el evaluador.
  - Campaña con 46 000 filas contra `auto_cusco_test`: previsualizar de 7,40 s a 7,56 s y crear de 6,17 s a 6,23 s, dentro del ruido.
  - El ahorro (-23,5 %) solo se ve en el A/B de mensajes.
  - Los problemas plegados quedan en `Compilada.problemas_plegados` y cada fila los repite.
- **B2** (`2f0b3b3`): aprobado con las cuatro condiciones de architec, todas cumplidas:
  - paridad sobre la `CargaGenerada` entera, con SHA-256 congelado en `b8b9025`;
  - un solo tipado (`formatos.convertir`);
  - `medir_generacion.py` con 60 000 y 120 000 filas, igual o mejor;
  - D3 con una sola tabla (`entities/segmentacion.py` y `services/segmentacion.py`) y prueba de claves contra el enum `Segmento`.

  Aceptado además:
  - en la ruta de compatibilidad, los topes crecen con la plantilla (RF-54);
  - una plantilla `[@a b]` da otro texto de error, pero sigue siendo 400.

  Visto bueno de `coordinador_modulo_mowa_mes`. Su congelamiento de `speech.py`, `segmentos.py` y los rangos terminó con `2f0b3b3`.

## 12. B4a (lanzado por architec el 2026-09-30; desde el 2026-10-01 la entrega vuelve a pasar por el coordinador)

**Alcance:**
- `GET /texto-enriquecido/catalogo`, `POST /texto-enriquecido/validacion` y `POST /texto-enriquecido/previsualizacion`;
- `CodigoTexto` con prueba espejo contra `textoEnriquecido.codigo.*`;
- `contratos/openapi.json` y `contrato-api.d.ts` regenerados en la misma entrega.

**Requisitos:** los de §6 (pedidos de designer y las cuatro precisiones), los nombres de §7 y §10 del diseño. Las filas sintéticas por segmento van en B4a; "primeros N de una selección" queda para B4b.

**Commit conjunto:** los códigos de B4a y las claves i18n de designer entran en el mismo commit de architec, coordinados con designer.

**Al revisar la entrega, mirar en especial:**
- la ubicación (`nodo`, `funcion`, `parametro`), nula para toda la expresión;
- `devuelve` / `entrada`;
- `obligatoria`;
- por contexto, el límite y la advertencia (160 y 150 en MOWA MES);
- en la previsualización, un nodo nulo distinto de un texto vacío;
- el motivo con código cuando no hay cota;
- los problemas de fila separados de los de validación;
- la forma JSON con `{"variable": ...}` y su validación estructural (`expresion_invalida`, anunciado en §16);
- los errores 4xx que extienden `detail` (`contrato-api.md` §3);
- que el frontend no tenga que reimplementar nada.

## 13. Circuito de revisión con MOWA MES (2026-10-01)

Todo corte que toque código, pruebas o documentación de MOWA MES pasa, **con su worktree y antes de ir a architec**, por la revisión de `coordinador_modulo_mowa_mes`. Sin su visto bueno, el coordinador no lo entrega.

- Aplica a **B6 y F4** (speech v2: API, base de datos e interfaz de MOWA MES), y a cualquier corte futuro que toque `plataformas/mowa_mes/`, `entities/mowa_mes*.py`, `adapters/output/plataformas/mowa_mes/`, `api/mowa_mes*.py` o `frontend/src/pages/mowa-mes/`.
- B3 y B7 se commitearon sin esa revisión previa. B3 por un descuido del coordinador; B7, mientras el coordinador estuvo desconectado. La revisión se hizo después del commit, sobre `2f0b3b3`: 299 pruebas en verde y huellas 17 y 92 sin cambios. No hubo nada que deshacer.

**Decisiones de B4a confirmadas al dev (2026-10-01):**
- `/validacion` y `/previsualizacion` responden 200 con `problemas` aunque la expresión sea inválida. Lo estructuralmente imposible que Pydantic acepta va como `expresion_invalida` con su ubicación. El 422 queda solo para un cuerpo ilegible. Los 400 con `codigo` y `ubicacion` son para guardar (B4b).
- Contexto desconocido, producto inexistente o fecha sin versión vigente: 404 que extiende `DetalleError` con `codigo` (en `CodigoTexto`), para que la interfaz lo ubique bajo su campo.
- Contextos `cartera` y `mowa_mes.speech`:
  - el registro vive fuera del motor, en la capa que compone;
  - el proveedor de MOWA MES vive en su paquete;
  - si se crea o se toca un archivo de MOWA MES, aplica §13.
- Los motivos de "sin cota" son códigos de `CodigoTexto`.
- `/archivos-carga` no se toca en B4a.
- i18n: el dev manda a designer la lista de claves con borradores en es y en. Designer escribe los diccionarios y todo entra en el mismo commit.
- **Contextos (corregido el 2026-10-01, a partir de una nota de `coordinador_modulo_mowa_mes`):**
  - en el núcleo, solo un `ContextoTexto` genérico y un registro por nombre, sin imports de `plataformas/` (con prueba de arquitectura);
  - `cartera` lo provee el núcleo;
  - `mowa_mes.speech` lo declara MOWA MES en `plataformas/mowa_mes/contexto_texto.py`;
  - el registro se arma en la capa de composición, con una línea por contexto, así que un canal nuevo no edita el núcleo (RF-31).

  B4a crea un archivo de MOWA MES, así que **pasa por la revisión de §13**. La primera versión, un módulo del núcleo que importaba de MOWA MES, invertía la dependencia.

  Aprobado por architec, con dos precisiones:
  - el registro se arma donde hoy se cablean las dependencias de la API (`app/main.py` o las dependencias de `app/api`), sin imports con efectos secundarios;
  - la prueba de arquitectura cubre `services/texto_enriquecido/` y el registro genérico.
- **i18n:** el dev mandó a designer 105 claves por idioma (24 códigos, 23 funciones con nombre y descripción, 21 parámetros, 6 familias, 5 marcas de fecha, 2 contextos y 2 variables).

## 14. Frontend en espera de B4a (2026-10-01)

`dev_frontend_motor_texto_enriquecido` prepara sin código de producto:
- lectura de `configuracion.astro`, `api-mowa-mes.ts`, la api falsa de e2e y `expresion.ts`;
- un plan de F3 y F4 en su carpeta (`plan-f3-f4.md`), con pantallas, estados, Playwright, Vitest y axe;
- dudas para designer, que pasan antes por el coordinador.

Puede adelantar el estado puro del constructor (`src/lib/constructor-columnas.ts`, con Vitest) con tipos provisionales tomados de las entidades de B2. El estado de las variantes por segmento lo acuerda antes con designer (`VariantesSegmento`).

Ruta propuesta: `/columnas` («Columnas de carga»). La navegación es de designer.

## 15. Contrato de B4b y B6: respuestas a C-1 a C-10 de `dev_frontend_motor_texto_enriquecido` (2026-10-01)

Requisitos para los briefs de B4b y B6. Si el backend encuentra que alguno no se sostiene, lo plantea antes de forzarlo.

| # | Decisión | Corte |
|---|---|---|
| C-1 | Las columnas viajan como lista ordenada. `orden` es un entero explícito en el almacenamiento y en la respuesta. La columna se identifica por su posición en la lista del pedido; el nombre es único dentro de la definición y se valida. El frontend asocia esa posición con su propio id local | B4b |
| C-2 | El problema de una definición extiende la ubicación con `columna` (índice en el pedido) y `segmento` (clave, o `null` para el contenido por defecto), además de `nodo`, `funcion` y `parametro`. Los problemas de un campo de la definición (`nombre`, `segmentacion`) llevan `campo`. Al guardar: 400 que extiende `DetalleError` con esa ubicación | B4b |
| C-3 | `/definiciones-columnas` expone `formato_fecha` con las marcas legibles (`dd/mm/aaaa`). El backend traduce. El `strftime` sigue solo en la definición en línea de `/archivos-carga` (RF-54) | B4b |
| C-4 | Una definición guardada guarda solo expresiones. Si al guardar llega una plantilla `[@…]`, se convierte. Lo que devuelve la API es siempre expresión | B4b |
| C-5 | B6 ofrece crear una v2 **a partir de una v1**: el backend convierte cada segmento con `expresion_de` y lo devuelve como borrador v2. La versión lleva `formato` (`v1` o `v2`), y una v1 se sigue leyendo con sus partes, en solo lectura | B6 |
| C-6 | La previsualización en vivo del editor usa `POST /texto-enriquecido/previsualizacion` con `contexto=mowa_mes.speech`, que trae el largo, la cota, el límite y la advertencia. Los niveles por segmento de la configuración (`Cabe`, `Más de 150`, `Más de 160`, `Falta WhatsApp`, con los códigos de `CodigoMowaMes`) los devuelve `/mowa-mes/speech/previsualizacion`, ampliado para v2, porque son reglas de MOWA MES | B6 |
| C-7 | El listado trae id, nombre, versión vigente, cantidad de versiones, `actualizado_en` y si la vigente está usada. La paginación sigue el patrón de las selecciones guardadas | B4b |
| C-8 | Cada versión trae `usada_en` (patrón del speech), y además `usos` si B4b registra cada carga generada con una definición guardada, que conviene hacer. La interfaz muestra «usada» con `usada_en` aunque `usos` no venga | B4b |
| C-9 | Los límites se exponen en el catálogo: los del motor (nodos, funciones por nodo y largo de los literales) en **B4a**; los de columnas por definición y variantes, en **B4b**. La interfaz no ofrece lo que el backend rechazaría | B4a y B4b |
| C-10 | `proteger_formulas` y `segmentacion` viajan en la definición. El servicio pasa `proteger_formulas` a `OpcionesArchivo` (D4) | B4b |

**Aprobado por architec (2026-10-01), con dos condiciones:**
- **B6, C-5:** una v2 creada a partir de una v1 produce **los mismos mensajes y largos** que esa v1. La prueba recorre el Speech original y las 12 versiones sintéticas del oro de B5, sobre la misma matriz. La v2 es una versión nueva con huella propia; la v1 queda intacta e inmutable.
- **B4b, C-8:** si se registra cada carga generada con una definición guardada, solo se guardan metadatos (versión, fecha de corte, fecha y hora, cantidad de filas y formato). Nunca filas ni datos de la cartera. Si `usos` no aporta algo que la interfaz vaya a mostrar, alcanza con `usada_en`.

**F3-a** (2026-10-02, sin commit): `frontend/src/lib/constructor-columnas.ts` y sus 64 pruebas de Vitest, en verde en el árbol principal. Tiene tipos provisionales con las respuestas C-1 a C-10, un id estable que nunca sale hacia el backend, y las variantes solo se transportan. Al revisar B4a, `dev_frontend_motor_texto_enriquecido` y designer revisan el OpenAPI y `contrato-api.d.ts` como consumidores antes de que vaya a architec.

**Respuestas de designer a D-1 a D-12** (`1f7dacd`, interfaz §8 y §9):
- F2 suma `lib/variantes.ts` (la frontera de D-1), los selectores de variable y de patrón de fecha, la API falsa del motor, y `.table__detalle` y `.marca-vacio` en `ui.css`.
- `/columnas` va en una tercera sección de navegación, «Configuración», aprobada por el usuario. Designer agrega la entrada cuando la página exista.

**Revisión de B4a (2026-10-02):**
- El dev la entregó directo a architec. Se corrigió la ruta y architec esperó las tres revisiones: la del coordinador, la de `coordinador_modulo_mowa_mes` (por `plataformas/mowa_mes/contexto_texto.py`) y la de los consumidores (designer y dev_frontend).
- Ajustes antes del commit:
  - `origen` en cada variable del catálogo, y tipos cerrados con `Literal` (designer);
  - la clave del segmento en cada fila de "ejemplos por segmento", que venía `null` (coordinador);
  - un titular de ejemplo claramente sintético, el docstring del segmento de un producto real (días de la sábana, sin ajuste) y una prueba con `dias_atraso` en `None` (MOWA MES).
- Designer aprueba o edita el bloque `textoEnriquecido.*` de los diccionarios, que redactó el dev.
- Los cambios del usuario en `backend/pyproject.toml` y `uv.lock` (dependencias mcp y fastmcp) no entran en ningún corte del motor.

**Pendiente para B6 y F4** (pedido de `coordinador_modulo_mowa_mes`): en la previsualización con un producto real, el editor le dice al usuario «segmento según días de atraso a la fecha de corte». El segmento de un producto real sale de los días de la sábana, sin el ajuste a la fecha de envío.
- **Revisión de dev_frontend como consumidor (2026-10-02):**
  - `/previsualizacion` acepta la forma de definición del **constructor** (`columnas` con `orden`, `segmentacion`, `proteger_formulas` y `formato_fecha` con marcas que traduce el backend). Es el mismo modelo que B4b va a guardar.
  - Un formato de fecha sin marcas válidas es un problema de su columna, no un texto literal.
  - La forma en línea de `/archivos-carga`, con `strftime`, no cambia.
  - Una columna nueva vacía da problemas con `columna`, nunca un 500.
  - Para B4b: la expresión de respuesta va con tipos cerrados.
  - Para B6: los niveles por segmento siguen saliendo de `/mowa-mes/speech/previsualizacion` (C-6), no de la cota en la página.
  - Nombres visibles de las variables de cartera: lo decide designer.
- **Nombres de las variables de cartera** (decisión de designer, 2026-10-02):
  - en F2 se crea un juego compartido `campo.<nombre>` en es y en, que usan `/cartera`, el selector de variables y el constructor;
  - el cliente usa `clave_nombre` si viene; si no y el origen es `cartera`, `campo.<nombre>`; si tampoco hay, el nombre técnico con espacios;
  - una prueba de Vitest contra el catálogo de campos del backend exige que no falte ni sobre ninguna etiqueta;
  - el catálogo de B4a no cambia.

**B4a entregado a architec (2026-10-02)** con las tres revisiones: coordinador, `coordinador_modulo_mowa_mes` (sin condiciones) y consumidores (designer y dev_frontend, sin observaciones al backend). Falta `-ConBase`, que corre architec.

Nota para F2: los modelos de entrada aceptan claves extra (para informarlas como problema), así que los tipos generados llevan firma de índice y solo admiten `type`, no `interface`. dev_frontend ya ajustó `constructor-columnas.ts`; designer tiene que ajustar `expresion.ts`.

## 16. Brief de B4b (2026-10-02)

**Base:** `c25801e` (B4a en main). RF-51 (definiciones guardadas y versionadas) y lo que queda de RF-46 y RF-47.

**Persistencia:**
- Tablas de definición y de versión, con una migración que hace ida y vuelta y `alembic check` limpio. Patrón de las selecciones guardadas y del speech:
  - nombre único normalizado;
  - definiciones compartidas;
  - una versión usada (`usada_en`) no se modifica: un cambio crea otra versión.
- Se guarda la forma del constructor de B4a: columnas con `orden`, expresiones (nunca plantillas; una plantilla que llega se convierte), `formato_fecha` con marcas, `segmentacion` y `proteger_formulas`.

**Endpoints:**
- `GET` y `POST /definiciones-columnas`, `GET /definiciones-columnas/{id}` y `POST /definiciones-columnas/{id}/versiones`.
- El listado trae id, nombre, versión vigente, cantidad de versiones, `actualizado_en` y si la vigente está usada (C-7).
- Al guardar, un 400 que extiende `DetalleError` con los problemas ubicados (columna, segmento, campo, nodo, función y parámetro; C-2).
- La expresión de respuesta va con tipos cerrados (`'texto' | 'variable'`).
- Límites de columnas por definición y de variantes en el catálogo (C-9).

**/archivos-carga:**
- Acepta una definición guardada (id y versión), además de la definición en línea, que no cambia (RF-54).
- Al generar con una guardada, marca `usada_en`. Si se registran usos (C-8), solo metadatos: versión, fecha de corte, fecha y hora, cantidad de filas y formato. Nunca filas ni datos de la cartera. Si nada en la interfaz lo muestra, alcanza con `usada_en`.
- `proteger_formulas` de la definición pasa a `OpcionesArchivo` (D4).

**Previsualización:** se agrega la muestra "primeros N de una selección". Es una fecha de corte más una selección con la forma de `/cartera` (o una selección guardada), con N acotado (5 por defecto), el mismo orden y desempate que la carga, y `seleccion_cartera/recorrido.py`. Solo lectura.

**Pruebas:**
- núcleo y API;
- PostgreSQL escritas con `@pytest.mark.postgres`, fechas de 2099 y limpieza de lo que crean, no corridas;
- migración con ida y vuelta (la corre architec);
- contrato y tipos regenerados;
- prueba espejo si aparecen códigos nuevos, con designer;
- mutación a mano en worktree.

**Revisiones antes de architec:** el coordinador y los consumidores (designer y dev_frontend sobre el contrato). Si toca archivos de MOWA MES, también §13.

**Decisiones de diseño de B4b aceptadas (2026-10-02):**
- Tablas `definicion_columnas` y `definicion_columnas_version`. Se guarda la definición **resuelta**, con la tabla de rangos y la variable de días explícitas.
- Versiones inmutables por construcción: solo `POST /{id}/versiones`, y `usada_en` es informativo. Se agrega `GET /{id}?version=N`. El nombre no cambia entre versiones. El listado no se pagina y va ordenado por nombre.
- Se valida siempre contra `cartera`. Límites: 100 columnas por definición y 50 variantes por columna, en el catálogo.
- `plantilla` no se expone en HTTP: el lector la convierte, pero el modelo mantiene `expresion` obligatoria.
- Solo `usada_en`, sin tabla de usos.
- `/archivos-carga` recibe `definicion` (en línea) o `definicion_guardada {id, version?}`, exactamente una de las dos, con un 400 con código si no. Se marca `usada_en` al generar el archivo, y `proteger_formulas` pasa a `OpcionesArchivo`. Precaución: afloja un tipo que usa la consola de cargas, así que se corren `contrato:comprobar`, `astro check` y Vitest antes de entregar.
- Muestra `primeros_de_seleccion` (cantidad de 1 a 5) y `disponibles` en la respuesta.
- Códigos nuevos: `definicion_no_encontrada`, `version_no_encontrada`, `nombre_repetido` (409) y `seleccion_no_encontrada`. Sus claves i18n van con designer.

## 17. `tsc --noEmit` en la verificación del frontend (2026-10-03)

dev_frontend encontró, con mutaciones, que `astro check` no detecta una asignación incompatible cuando el tipo está anidado (por ejemplo, `LlamadaFuncion` vuelta a `interface`). `tsc --noEmit -p tsconfig.json` sí la detecta.

architec lo adoptó y comprobó que en `e207c46` pasa limpio, en unos 5 s. Lo implementa designer:
- `npm run verificar` corre `tsc --noEmit` después de `astro check`;
- el workflow de CI del frontend hace lo mismo;
- se menciona en `testing.md` §4 y en la skill `verificar`;
- la prueba de la regresión va en el mensaje del commit.

La guarda de dev_frontend que lee el código fuente queda solo para sus propios archivos y sale de `expresion.ts` en F3.

**Revisión de B4b por dev_frontend (2026-10-03):** sin observaciones al backend.
- Confirmado: las definiciones guardadas se validan solo contra `cartera`, y F3 no ofrece selector de contexto.
- Para designer (§5.1 de la interfaz):
  - el hint «se crea la versión N+1» se ve siempre, porque todo guardado crea una versión;
  - el nombre es de solo lectura después de crear la definición.
- **Pendiente de producto:** renombrar una definición guardada. Hoy no se puede, porque el nombre no cambia entre versiones. No bloquea.

## 18. Borrador del brief de B6 (MOWA MES M2, backend), para lanzar cuando B4b esté en main

**Toca MOWA MES:** pasa por `coordinador_modulo_mowa_mes` con su worktree antes de architec (§13).

**Persistencia:**
- `mowa_mes_speech_version` gana `formato` (`v1` por defecto en las filas existentes) y `expresiones` (JSONB, una expresión por segmento; nula en las v1).
- Migración con ida y vuelta.
- Las v1, incluido el Speech original, no se tocan: conservan `partes` y su huella (`huella_speech`).
- Se mantiene el patrón actual: editable hasta que se usa (`usada_en`) y después inmutable.

**Huella v2:** SHA-256 de la forma canónica de las expresiones por segmento. El 409 de crear una campaña funciona igual para v1 y v2.

**Crear v2 desde v1 (C-5):**
- El backend convierte cada segmento con `expresion_de` y lo devuelve como borrador v2 (por ejemplo, `GET /mowa-mes/speech/{id}/como-v2`; la forma la decide el dev).
- **Condición de architec:** la v2 creada desde una v1 produce los mismos mensajes y largos que esa v1. La prueba recorre el Speech original y las 12 versiones sintéticas del oro de B5, sobre la misma matriz.
- La v2 es una versión nueva, con `basada_en_id` y huella propia.

**Campaña:**
- `ConstructorMensajes` acepta v1 (por `expresion_de`, como hoy) o v2 (expresiones guardadas), con `whatsapp_contacto` constante (B7).
- `FaltaWhatsapp`, `MensajeNoGenerable` y el orden de exclusiones no cambian.

**Exclusiones `falta_titular` y `falta_vencimiento` en v2: PROPUESTA A CONFIRMAR con `coordinador_modulo_mowa_mes`, y con el usuario si hace falta, porque es una regla de MOWA MES.**
- Hoy se aplican siempre.
- En v2 se aplicarían si la expresión del segmento usa esa variable marcada `obligatoria`. La conversión desde v1 las marca obligatorias, así que da lo mismo que hoy.
- Una v2 que no use el titular dejaría de excluir a los productos sin titular.
- Lo "vacío" de una variable obligatoria coincide con `campana._vacio` (D10).

**Previsualización (C-6):**
- `/mowa-mes/speech/previsualizacion` acepta v2 y devuelve, por segmento: largo máximo (la cota), el nivel con los códigos de `CodigoMowaMes` (Cabe, 150, 160, Falta WhatsApp) y el ejemplo.
- Una expresión sin cota se informa como "sin máximo calculable", con su motivo. En la campaña, el control por fila del 160 sigue igual.

**Contexto `mowa_mes.speech`:**
- Ya trae `titular`, `fecha_vencimiento_cuota`, `whatsapp_contacto` y `dias_atraso_ajustados`. Si v2 necesita más, crece en `plataformas/mowa_mes/contexto_texto.py`.
- Pendiente para F4: el aviso «segmento según días de atraso a la fecha de corte» en la previsualización con un producto real.

**Limpieza de M1 (§9):**
- Se borran `plantilla_mensaje`, `contexto_fila`, `CAMPOS_CONTEXTO` y lo que nadie use, y las pruebas `test_en_vivo_*`.
- El oro sigue contra las constantes congeladas (6 mensajes y el SHA-256 de la matriz).

**Pruebas:**
- de punta a punta contra `auto_cusco_test` (las corre architec): crear una v2 desde la interfaz o la API, generar una campaña y conciliarla;
- las PostgreSQL escritas, no corridas;
- architec repite la medición de la campaña con 46 000 filas;
- contrato regenerado;
- mutación a mano en el worktree.

**B6, exclusiones en v2: DECIDIDO por el usuario (2026-10-03, consultado por `coordinador_modulo_mowa_mes`).** `falta_titular` y `falta_vencimiento` se aplican solo si la expresión del segmento usa la variable. Coincide con RF-MM-13 («le falta un dato que el speech necesita»). Condiciones, cada una con su prueba:

1. El orden de exclusiones no cambia (`telefono_invalido`, `falta_documento`, `sin_speech`, `falta_titular`, `falta_vencimiento`, `mensaje_excede_160`). Lo único nuevo: las dos del medio se saltean si el segmento no usa la variable. Se prueba en los dos sentidos: una v2 sin titular carga un producto sin titular, y una v2 con titular lo excluye igual que hoy.
2. "Usa la variable" se decide sobre la expresión compilada (nodos variables, también como argumento de una función), nunca buscando el nombre en el texto fijo.
3. Si el segmento no usa el titular y el producto no lo tiene, el mensaje sale sin huecos: ni "None" ni un vacío en medio. Se prueba con el texto exacto.
4. Una v2 convertida desde una v1 marca las dos variables como obligatorias y da los mismos mensajes, largos, exclusiones y orden que la v1, en la matriz de oro completa.
5. architec registra la decisión en §6 de `requerimientos-mowa-mes.md` y precisa RF-MM-13 para v2.

Además, para la revisión de MOWA MES:
- las huellas 17 y 92 sin cambios;
- el 409 (`huella_cambiada`) para una v2 cambiada entre previsualizar y crear;
- las constantes congeladas del oro se quedan;
- con un speech sin cota, `mensaje_excede_160` sigue excluyendo por fila sobre el mensaje real.
