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

## 19. Revisión de B6 (2026-10-04)

Worktree `auto_cusco_mte_b6`, sobre `01e11c5`.
- **Backend:** ruff limpio, 1927 pruebas en verde y el oro de B5 en verde (reproducido por el coordinador).
- **Bloquea el commit:** con el contrato nuevo, `npm run tipos` da 20 errores en cuatro archivos de pruebas del frontend de MOWA MES (`e2e/api-falsa-mowa-mes.ts`, `e2e/mowa-mes-campana.spec.ts`, `tests/nucleo/mowa-mes.test.ts` y `tests/nucleo/mowa-mes-campana.test.ts`). Son del equipo de MOWA MES. Se pidió que los adapte `dev_frontend_modulo_mowa_mes` en el mismo worktree, solo tipos y datos nuevos, para que entren en el mismo commit.
- **Revisiones en curso:** `coordinador_modulo_mowa_mes` (§13) y los consumidores (designer y dev_frontend, para F4).
- **Pendiente para F4:** el aviso «segmento según días de atraso a la fecha de corte». En B6, la v2 recibe `dias_atraso_ajustados` (a la fecha de envío) como variable, y el ejemplo la evalúa con el inicio del rango.
- **Revisión de designer (2026-10-04):**
  - Visto bueno, salvo un punto: `ProblemaSpeechRespuesta.codigo` es un texto libre que puede venir de `CodigoTexto` o de `CodigoMowaMes`, y los dos comparten `telefono_invalido`. Se agrega el discriminador `catalogo: "texto" | "mowa_mes"`, y `campo` pasa a Literal.
  - Orden: primero el ajuste del backend y después los fixtures de MOWA MES.
- **Pendiente, como corte aparte:** `CodigoTexto` como enum en el OpenAPI, para que la compilación del frontend atrape un código mal escrito. Afecta las respuestas de B4a y B4b.
- **Fixtures de MOWA MES (2026-10-04):** `dev_frontend_modulo_mowa_mes` adaptó los cuatro archivos de pruebas, con tipos, Vitest y Playwright en verde. Además encontró que `astro check` falla en `src/pages/mowa-mes/configuracion.astro:1278`: `largo_maximo` ahora puede ser `null`, y `npm run tipos` no revisa los `.astro`. `coordinador_modulo_mowa_mes` autorizó un arreglo mínimo en esa pantalla, que es suya: con `null` muestra «—», con su prueba. La interfaz completa de `sin_maximo` queda para F4. B6 lleva entonces cinco archivos del frontend de MOWA MES.
- **Pendiente:** el contrato definitivo, con `catalogo` y `campo` en Literal. Después, la pasada final con `npm run verificar` completo.
- **B6 devuelto por architec (2026-10-04):** 5 de 104 pruebas de integración fallan; 3 son de MOWA MES y ya existían. Causa probable: `expresiones` es JSONB sin `none_as_null`, así que un `None` se guarda como `'null'::jsonb` y no como NULL. El CHECK nuevo rechaza entonces guardar una v1, y acepta una v2 sin expresiones. Habría roto el guardado del speech en la base de trabajo del usuario.
  - Arreglo: lo hace el dev en el mismo worktree, con una prueba de SQL crudo y una revisión de las demás pruebas `@postgres`.
  - **Lección para los briefs que tocan persistencia:** como los devs no pueden correr las pruebas con base (decisión del usuario), deben compilar con el dialecto de PostgreSQL las sentencias que escriben columnas nulas, JSON o con zona horaria, y revisar los literales. En B4b y B6 los fallos con base aparecieron recién en architec.

## 20. F2 en dos cortes y ruta de prueba (2026-10-06)

F2 no había arrancado; antes solo existía el estado del editor (`5ffeddf` y `e207c46`). Se entrega en dos cortes:
- **F2a, sin interfaz:** cliente del motor con caché por contexto, la API falsa encadenable, `variantes.ts`, `expresion.ts` alineado con los tipos generados, las etiquetas `campo.<nombre>` con su prueba, y `.table__detalle` y `.marca-vacio`.
- **F2b, los componentes:** `EditorTexto`, `VariantesSegmento` y los selectores, con Playwright y axe.

**Ruta de prueba de F2b, aprobada por architec, con condiciones:**
1. Se inyecta con `injectRoute` solo cuando una variable de entorno está activa.
2. Una comprobación de que el build de producción no la contiene.
3. Sin navegación, sin `nav.*` y con `noindex`.
4. Playwright la activa en su configuración.
5. Una línea en `testing.md` §4.
6. El build con la ruta sale a otro directorio (por ejemplo, `dist-pruebas`), del que Playwright levanta el preview. `npm run build` produce `dist/` sin la ruta.
7. Los componentes no saben que están en una ruta de prueba: nada de ramas de modo prueba.

## 21. Estado de la cola (2026-10-15)

- **F3** entregado a architec, sin verificar todavía: se quedó sin margen de uso. El worktree `auto_cusco_mte_f3` queda congelado.
- **B11** revisado por el coordinador y por dev_frontend. Incluye el ajuste de designer a su API falsa del motor; sin él, `npm run tipos` falla.
- **Esperan la aprobación del usuario** (designer): `designer-nav.patch` (navegación de `/columnas`), `designer-ui-lectura` (`.input:read-only` y `controlMuestra` en `montarVariantes`) y el ajuste de la API falsa de B11.
- **Después:** un corte chico de dev_frontend (quitar la regla CSS provisoria y usar como muestra un producto del segmento elegido) y luego F4.
- **Mejora posible, no pedida:** una muestra por `segmento` concreto en la previsualización. Hoy, si ninguno de los 5 productos de la selección cae en el segmento elegido, se usa el primero y se avisa.

## 22. F5, pantalla «Generar carga», y B12 (2026-10-15)

**Origen:** hallazgo de C2. Ninguna pantalla usaba `/archivos-carga`, así que una definición guardada no se podía usar para generar un archivo desde la interfaz. El usuario eligió hacer la pantalla dentro del motor (consultado por architec). Es la «Pantalla de generación» que `planning.md` tenía pendiente en la Fase 3.

**B12 (backend, antes de F5):** `/archivos-carga` no expone las exclusiones de la segmentación (`CargaGenerada.exclusiones`, código `sin_segmento`, RF-50), que el generador ya calcula.
- La previsualización tiene que traerlas: cantidad y, por fila, el código de `CodigoTexto` y el detalle.
- La descarga, una cabecera de resumen `X-Carga-Excluidos`, declarada en el contrato y en CORS, igual que las demás.
- Sin datos personales nuevos.

**F5 (dev_frontend; experiencia de designer):**
- Elegir una definición guardada y su versión (`api-definiciones.ts`).
- Elegir la fecha de corte y la selección con `SelectorSeleccion`.
- Elegir el formato (XLSX, CSV o JSON), con las opciones de `/archivos-carga/formatos`. `proteger_formulas` viene de la definición y no se edita aquí.
- Previsualizar (`/archivos-carga/previsualizacion` con `definicion_guardada`).
- Descargar con `descargas.ts` y leer las cabeceras `X-Carga-*`.
- Mostrar el aviso de selección insuficiente (`suficiente`, RF-08), los errores por fila y las exclusiones por segmento (B12).
- Solo frontend, sobre contratos que ya existen, más B12.
- Antes de programar, dev_frontend escribe el plan de la pantalla y designer lo aprueba, como en F3.
- La entrada de navegación es de designer.

**Cierre:** C2 se cierra después de F5.
- **Navegación de F5 (designer):** va en «Flujo diario», como tercer paso: «Cargas · Cartera · Generar carga». Designer la agrega con un parche sobre F5. **Duda de nombre que designer le lleva al usuario:** «Cargas» (las sábanas que entran) frente a «Generar carga» (el archivo que sale). Recomienda mantener los dos nombres y que la intro de la página lo aclare; la alternativa es renombrar «Cargas» a «Sábanas».
- **Plan de F5 (dev_frontend, `plan-f5.md` en su worktree), pendiente de la aprobación de designer.**
  - El contrato encaja sin cambios: los filtros y el orden del selector son la misma sintaxis que `/cartera`, la selección guardada se resuelve a filtros y la cantidad es un campo propio de la pantalla.
  - G-1: los tipos de B12, antes de programar las exclusiones.
  - G-2, sumado a B12: `/archivos-carga/formatos` da por opción el tipo, el valor por defecto y los valores permitidos. El frontend no fija listas propias.
  - G-3 (¿se corta la generación al cancelar?) y G-4 (¿cuándo se marca `usada_en`?): preguntados al dev backend; si no hay cambio, van como límites conocidos.
- **G-3 y G-4, respondidos por el dev backend con una prueba real (2026-10-16):**
  - `POST /archivos-carga` no se corta al cerrarse la conexión: corre entero en un hilo.
  - `usada_en` se marca después de generar y exportar bien, pero antes de enviar el cuerpo. Si el cliente cancela, la versión puede quedar marcada sin entrega. Nunca se marca si la generación falla ni en la previsualización.
  - Los dos quedan como límites conocidos. Mitigación en F5: un aviso después de cancelar y no permitir otra descarga mientras haya una en curso.
- **Designer aprobó el plan de F5:** ruta `/generar-carga`, al final de «Flujo diario». La navegación va en un parche de designer sobre F5.

## 23. F5 entregada (2026-10-16)

- Worktree `auto_cusco_mte_f5`, sobre `ad56a11`. El coordinador comprobó los tipos, Vitest 786 y `build:produccion`; dev_frontend corrió `generar-carga.spec` (35) y axe (11) con un worker.
- **Orden de entrada:**
  1. el cambio de designer que agrega la `etiqueta` por opción a `selector-patron-fecha.ts` (aplicado en el worktree de F5 solo para programar), como commit propio;
  2. F5;
  3. el parche de navegación de designer, «Generar carga» al final de «Flujo diario».
- Pendiente antes de architec: la revisión de experiencia de designer.
- **Revisión de experiencia de F5 (designer, 2026-10-16):** 2 puntos para antes del commit («no alcanzan» como `.notice--info`, y el grupo de problemas con un botón «Ver los N» y `.table--apilable`) y 4 menores, pasados a dev_frontend. La API falsa no debe devolver exclusiones si la definición no tiene segmentación.
- **Parches de designer y orden de entrada sobre F5** (todos esperan la aprobación del usuario):
  1. `designer-nav.patch` (`/columnas`);
  2. `designer-selector-etiqueta.patch`;
  3. F5;
  4. `designer-nav-generar.patch` (se apila sobre el 1).

  Aparte: `designer-ui-lectura` (con el arreglo de foco) y el ajuste de la API falsa de B11.

## 24. Aprobación del usuario (2026-10-17)

El usuario aprobó directamente, en la sesión del coordinador, los cinco cambios de designer: `designer-nav.patch`, `designer-nav-generar.patch`, `designer-ui-lectura` (con `controlMuestra` y el arreglo de foco), `designer-selector-etiqueta` y el ajuste de la API falsa de B11. Decidió además **mantener los nombres «Cargas» y «Generar carga»**, con la intro de `/generar-carga` que los distingue.

Orden de commits pasado a architec:
1. nav de `/columnas`;
2. ui-lectura;
3. etiqueta;
4. F5;
5. nav de «Generar carga»;
6. B11.

Después, el corte chico de dev_frontend en `/columnas` y el cierre de C2.
- **Prueba intermitente (2026-10-17, aviso de MOWA MES):** `accesibilidad.spec.ts:414` (`/columnas`, versión antigua, tema claro) falló una vez por contraste en `thead[data-previa-cabecera]` dentro de una corrida completa; aislada pasa. Hipótesis: axe midió con la vista previa atenuada mientras esperaba la respuesta. El arreglo va en el corte chico de dev_frontend: esperar a que la vista previa esté al día, con una marca observable (`aria-busy` o `data-pendiente`), antes de correr axe. Se revisa el mismo patrón en `/generar-carga`.

## 25. Cierre (2026-10-19)

- El corte final de F3 entró en `e0d2b47` (Playwright completo 369/369). C2 cerrada: RF-42 a RF-54 cumplidos (`revision-c2.md`).
- **Queda en curso:** `fijarNotaMuestra` (designer), aprobado por el usuario el 2026-10-19. Entra después de `e0d2b47`, seguido de un ajuste mínimo de dev_frontend.
- **Pendientes del usuario desde el diseño:** tabla de rangos por defecto, codificación SMS y días ajustados fuera de MOWA MES. **Pendiente de producto:** renombrar una definición guardada. **Mejora posible:** una muestra por segmento concreto.

## 26. Plan de C3: decisiones del usuario del 2026-10-19 (b12d384), para aprobación de architec

### Contraste con el código

- `segmentacion.dias_ajustados(dias_atraso, fecha_corte, fecha_envio)` ya existe en el núcleo (B2), y `CriterioCalculado.variable_dias` decide qué variable se usa. Hoy el valor por defecto es `dias_atraso` (`VARIABLE_DIAS_POR_DEFECTO`), y el núcleo no conoce la fecha de envío: «el módulo aporta la variable ya ajustada».
- **Cada versión guardada fija `variable_dias` explícito** (B4b guarda la definición resuelta). Las existentes dicen `"dias_atraso"`, y una versión no se modifica nunca.
- El contexto `cartera` no tiene `fecha_envio` ni `dias_atraso_ajustados`. El contexto `mowa_mes.speech` sí tiene `dias_atraso_ajustados`, pero en la previsualización usa `dias_atraso` sin ajuste (comentario en `plataformas/mowa_mes/contexto_texto.py`).
- `/archivos-carga` y `/texto-enriquecido/previsualizacion` no reciben una fecha de envío.

### Decisión a escalar (D-C3-1): versiones guardadas antes de RF-55

Las versiones existentes guardan `variable_dias: "dias_atraso"`. Opciones:
- **(a)** Siguen segmentando sin ajuste, porque son inmutables y reproducibles. Solo las versiones nuevas usan `dias_atraso_ajustados` por defecto, y `/columnas` avisa en una versión antigua: «segmenta sin ajustar a la fecha de envío; guarda una versión nueva para usar el ajuste».
- **(b)** Al generar, `dias_atraso` en `variable_dias` se interpreta como ajustado. Cumple «en todas las cargas», pero cambia el resultado de versiones ya usadas.
- **(c)** Una migración de datos que reescribe `variable_dias` solo en las versiones no usadas. Las usadas quedan como (a).

Recomendación del coordinador: **(a)**. Respeta la inmutabilidad (RF-51), y antes de decidir architec puede contar cuántas versiones hay en `auto_cusco`. Si no hay ninguna, (a) y (b) dan lo mismo.

### Cortes

| Corte | Qué | Depende | Revisión |
|---|---|---|---|
| **B14** | RF-56: `PATCH /definiciones-columnas/{id}` con `{nombre}`. No crea versión, actualiza `actualizado_en` y responde 409 `nombre_repetido` (normalizado). Prueba `@postgres` | — | consumidores |
| **B15** | M3: el backend rechaza crear o editar una v1 (`partes`), con un 400 con código. Las v1, incluido el Speech original, se siguen leyendo, usando en campañas y convirtiendo con `como-v2`. Huellas 17 y 92 intactas | — | **MOWA MES (§13)** y consumidores |
| **B13** | RF-55: `fecha_envio` en `/archivos-carga` (y su previsualización) y en `/texto-enriquecido/previsualizacion` con una muestra de cartera. Por defecto es hoy en Lima (`ahora_en_lima`); anterior a la fecha de corte da 400 con código y las dos fechas. Contexto `cartera`: `fecha_envio` (constante, plegada por B7) y `dias_atraso_ajustados` por producto. `variable_dias` por defecto pasa a `dias_atraso_ajustados` en las definiciones nuevas, según D-C3-1. La previsualización de `mowa_mes.speech` ajusta a la fecha de envío, y MOWA MES conserva su regla de campaña (RF-MM-15). Rendimiento con 46 000 filas (architec) | D-C3-1 | MOWA MES (por su contexto), consumidores |
| **F7** | Renombrar en `/columnas` (RF-56) | B14, designer | designer |
| **F8** | M3: fuera el editor de dos partes de `/mowa-mes/configuracion`; las v1 en solo lectura con «Convertir a v2»; el aviso del segmento con producto real pasa a «a la fecha de envío» | B15, designer | **MOWA MES (§13)**, designer |
| **F6** | «Fecha de envío» en `/generar-carga` (por defecto hoy) y la fecha visible en la vista previa de `/generar-carga` y de `/columnas` (allí, «hoy») | B13, designer | designer |

**Orden** (un solo dev backend): B14 → B15 → B13. En frontend: F7 en cuanto entre B14, F8 tras B15 y F6 tras B13. Designer fija la experiencia de F6, F7 y F8 antes de que se programen, como en F3 y F5.

### GSM-7 (RF-MM-27, T-MM-B9 de MOWA MES)

Si `coordinador_modulo_mowa_mes` consulta, la recomendación es una función del motor `a_gsm7` (familia texto, con cota que no crece) más la normalización al generar, en MOWA MES. Ojo con el oro de B5 (`test_mowa_mes_speech_oro`):
- si la normalización se aplica después de `ConstructorMensajes`, en la campaña, el oro sigue igual;
- si se aplica dentro, hay que actualizar las constantes congeladas, y es un cambio decidido según RF-54.

Hay que acordarlo antes de que lo programen.

**Aprobado por architec (2026-10-19).**
- **D-C3-1 = (a).** architec contó en `auto_cusco`, con una consulta de solo lectura: **0 definiciones, 0 versiones y 0 usadas**. No hace falta migración.
  - Las versiones nuevas usan `dias_atraso_ajustados` por defecto, y ninguna guardada se reinterpreta.
  - Para las que se creen antes de que entre B13, `/columnas` muestra un aviso breve en una versión que segmenta sin ajuste.
- **B13:** «hoy» en hora de Lima, con la zona como constante en un solo lugar. La medición con 46 000 filas la corre architec, antes y después.
- **GSM-7 (condición de architec):** la normalización va ANTES de medir el largo (la exclusión por más de 160, la advertencia por 150 y la cota de la previsualización se miden sobre el texto normalizado, RF-MM-19). Que cambien las constantes del oro de B5 está aceptado (RF-54). Si se hace como `a_gsm7`, MOWA MES la aplica al final de cada segmento, sin que el usuario la agregue.

### B16: GSM-7 del motor (acordado con `coordinador_modulo_mowa_mes`, su `plan.md` §6)

- **`a_gsm7`** (función del motor, familia texto, con cota):
  - NFD sin marcas combinantes, igual que `conciliacion.normalizar_mensaje` pero sin el strip;
  - después borra lo que queda fuera del alfabeto básico y de la tabla extendida de 3GPP TS 23.038;
  - conserva los extendidos (`€ [ ] { } \ ~ ^ |` y el salto de página) y los saltos de línea.
- **`largo_gsm7(texto)`** (núcleo): cuenta 2 por cada carácter extendido. La usan la cota y el control de 150 y 160 de MOWA MES.
- **Pruebas que pide MOWA MES:**
  - aplicar la función por pieza da lo mismo que aplicarla al segmento entero, siempre que se aplique después de `primeros(8)`;
  - la cota se mide en unidades GSM-7: exacta para el texto fijo, y las variables cuentan 1 por carácter (supuesto documentado);
  - una propiedad: con variables sin extendidos, `largo_gsm7(mensaje) <= cota`;
  - el Speech original conserva su cota («9 a 30» sigue en 156).
- **Oro de B5:** afirma `salida_nueva == a_gsm7(constante congelada)`, en lugar de reemplazar las constantes (cambio decidido, RF-54).
- **Reparto:** B16 es de dev_backend_motor. Encima va el corte de `dev_backend_modulo_mowa_mes`: aplicar la función en `speech.py`, medir en `campana.py`, la previsualización, el contrato y la conciliación.
- **Orden en el equipo del motor:** B14 → B15 → B16 → B13. B16 arranca cuando architec apruebe el plan de MOWA MES.

### Avance de C3 (2026-10-19)

- **Sección 10 de la interfaz** (experiencia de F6, F7 y F8): aprobada por el usuario en la sesión del coordinador. Designer la entrega como commit de documentación.
- **B14** (renombrar) entregado a architec. Agrega `PATCH` a `allow_methods` de CORS. dev_frontend lo revisa como consumidor.
- **B15** (M3, backend) listo y revisado. **Entra junto con F8:** hoy `configuracion.astro` todavía crea y edita versiones v1, y con B15 solo ese botón daría 400. Pasa por la §13 de MOWA MES, y designer revisa el texto de `version_v1_retirada`.
- **B16** (GSM-7) lanzado, con la transliteración que decidió el usuario (RF-MM-27, `204b3dc`): NFD → transliterar (“ ” « » → ", ‘ ’ → ', … → ..., – — → -, ° º → o, ª → a) → borrar lo que quede fuera de GSM-7. Incluye una función que devuelve los caracteres borrados, para el B9 de MOWA MES, y la cota sobre el texto ya transliterado.
- **F8** (2026-10-20): visto bueno §13 de MOWA MES, con un ajuste. El texto nuevo del aviso del segmento con producto real («ajustados a hoy… en la campaña se ajustan a su fecha de envío») **pasa a F6**, porque recién es cierto con B13; F8 conserva el texto actual. También se quita `mowaMes.speech.inmutable.original` si quedó sin uso. **Orden:** B15 y enseguida F8, rebasado sobre B15 y sin su copia del parche.

### Cierre de C3 (2026-10-24)

Todos los cortes del motor de C3 están en `main`: B14 (`3cdb54f`), F7 (`eb97a55`), B16 (`535a61b`), B15 (`32bfebf`), F8 (`3fe79af`), B13 (`5ce9834`) y F6 (`19adb4c`). La revisión de cierre está en `revision-c3.md`. De MOWA MES quedan `b9b`, que mide el editor en GSM-7 (las líneas del motor ya revisadas), y T-MM-F7. Los dos son de `coordinador_modulo_mowa_mes`.

## 27. Plan del mapeador de encabezados (T-MAP-C1), para aprobación de architec

Sobre `90fec9e`. El diseño es `docs/mapeador-encabezados.md` (RF-57 a RF-63). Abajo va lo que el código confirma, lo que no encaja (con una propuesta para cada caso) y los cortes.

### Contraste con el código

- `ingesta_sabana/cabeceras.py`: `mapear_cabeceras` asigna, de izquierda a derecha, el primer campo libre cuyo patrón cumple `fullmatch` sobre `normalizar_cabecera`. `describir_mapeo` guarda `columnas`, `desconocidas` y `faltantes`, con posiciones en base 1. `formato.mapeo` no sale en el contrato: solo se guarda.
- `LectorCalamine.leer_hoja(contenido, hoja)` lee una hoja fija. `carga.hoja` se guarda con la versión, y `procesar_carga` vuelve a leer el archivo guardado (`obtener_archivo`) con esa hoja.
- `POST /cargas` recibe `hoja` como campo del formulario (por defecto `VENCIDA`). El límite es `TAMANO_MAXIMO_BYTES` = 64 MB, en `api/cargas.py`.
- Las etiquetas `campo.<nombre>` existen en `es.json` para 40 de los 45 campos. **Faltan:** `documento`, `vencimiento_operativo`, `pagare_duplicado`, `validador` y `cod_tipo_basilea`.
- La mayoría de los alias son literales. Varios tienen metacaracteres: `dni ?/ ?ruc`, `pagare2?`, `saldosoles(...)?`, `cuotas apro(badas)?`, `cod\.? ?tipo basilea`, `tipo ?basilea`, `segmento fina?n?ciero` y `cant\.? ?paralelos`. Según §3.2, esos alias no entran en la similitud.

### Lo que no encaja, con una propuesta para cada caso

- **M-1 (defecto del diseño): encabezados repetidos y mapeo recordado.** La sábana trae dos «Pagare», que se normalizan igual: el primero va a `pagare` y el segundo a `pagare_duplicado`. Si se recuerda por `encabezado_normalizado`, el *upsert* deja una sola fila, la última (`pagare` → `pagare_duplicado`). En la carga siguiente, la columna 1 llega como recordada en `pagare_duplicado` y la 2, como `sin_coincidencia`. Falta entonces el obligatorio y **no se puede confirmar**. **Propuesta:** la clave del recordado es (`encabezado_normalizado`, `ocurrencia`), donde `ocurrencia` es 1, 2… entre los encabezados con el mismo normalizado, de izquierda a derecha. `mapeo_recordado` gana esa columna, y el único es (`catalogo_id`, `encabezado_normalizado`, `ocurrencia`). Se prueba con dos «Pagare» confirmados dos veces seguidas.
- **M-2: CSV y JSON al procesar.** `procesar_carga` vuelve a leer el archivo con `carga.hoja`. Para un CSV necesita también el separador y la codificación elegidos, y hoy la versión no los guarda. **Propuesta:** la carga gana `opciones_lectura` (JSONB: formato, hoja, separador y codificación) en la misma migración, y `procesar_carga` lee con eso. `carga.hoja` se mantiene por compatibilidad.
- **M-3: precedencia entre recordado y coincide.** §3.3 dice que un recordado gana a una coincidencia. Pero si el campo «queda tomado por la primera columna en los pasos 1 y 2, de izquierda a derecha», una coincidencia en la columna 2 tomaría el campo antes que un recordado en la columna 5. **Propuesta:** son tres pasadas sobre todas las columnas: primero todos los recordados, después las coincidencias en los campos libres y por último los parecidos. Con una prueba.
- **M-4: contra qué se valida al confirmar.** `POST /cargas/desde-borrador` vuelve a validar, pero el estado de cada columna (por ejemplo, `parecido`) depende de los recordados. Si otro usuario confirma algo en el medio, un análisis nuevo daría otros estados y la validación no coincidiría con lo que se vio. **Propuesta:** el borrador guarda el análisis que se mostró (JSONB `analisis`), y la validación y el recálculo del origen de §3.4 (`90fec9e`) se hacen contra ese análisis, no contra uno nuevo. Re-analizar con otras opciones lo reemplaza.
- **M-5: asignaciones incompletas.** El diseño no dice qué pasa si una columna listada no trae asignación, o si un índice se repite. **Propuesta:** se exige una asignación por cada columna listada, con dos códigos de protección más, `asignacion_faltante` e `indice_repetido`, que la pantalla no produce. Se publican en el enum.
- **M-6: el «coincide» por nombre cambia el camino viejo.** §3.2 suma «es igual a su `nombre` con `_` como espacio». Hoy un encabezado «DIAS ATRASO» queda desconocido (el alias es `dias atraso hoy`), y con la regla nueva coincidiría con `dias_atraso`. Si solo lo hace `analizar`, la prueba de paridad de §9 falla para esos archivos. **Propuesta:** una sola función `coincide(normalizado, campo)` en el mapeador, que usan `analizar` y `mapear_cabeceras`. Hay que decidir entre dos opciones:
  - **(a)** El camino viejo también gana la coincidencia por nombre: es un cambio de comportamiento chico y favorable, y queda un solo criterio. Es la que recomiendo.
  - **(b)** Solo la usa el mapeador, y la paridad se limita a archivos sin esos casos.
- **M-7: forma de `formato.mapeo`.** §5 la reemplaza por `{columnas, origenes, ignoradas}`. **Propuesta:** que el cambio sea aditivo. Se mantienen `columnas`, `desconocidas` y `faltantes` (posiciones en base 1, como hoy) y se agregan `origenes` e `ignoradas`. El camino viejo no cambia, y las versiones viejas se siguen leyendo igual. En la API, `indice` va en base 0, como dice §3.1, y el contrato lo documenta.
- **M-8: `CampoDestino.tipo`.** El mapeador no convierte valores. **Propuesta:** `tipo` es un texto descriptivo (en la sábana, el nombre del `TipoCampo`), así el núcleo del mapeador no importa `entities/sabana.py`. Una prueba de arquitectura lo fija.
- **M-9: las etiquetas que faltan.** Las cinco claves `campo.*` van en F1 o F2. Mientras tanto, la prueba espejo de i18n del catálogo del mapeador las marca.
- **Límite conocido (sin cambio):** los campos cuyos únicos alias tienen metacaracteres se comparan en la similitud solo contra su nombre (`documento`, `pagare_duplicado`, `cod_tipo_basilea`…). Si hace falta, más adelante se agrega a `CampoDestino` una lista de nombres literales para la similitud, sin tocar `alias`.
- **Concurrencia:** confirmar bloquea el borrador (`SELECT … FOR UPDATE`), y un segundo confirmar responde 404. El *upsert* de los recordados usa el único de M-1. Las dos cosas llevan prueba `@postgres` y su doble sin base.

### Cortes

| Corte | Qué | Depende | Revisión |
|---|---|---|---|
| **B1** | Núcleo: `entities/mapeador.py`, `services/mapeador/` (normalización movida, `coincide` único según M-6, similitud, `analizar` en tres pasadas y con ocurrencia, `validar` con los códigos de M-5) y `CATALOGO_SABANA`. Sin infraestructura, con propiedades y prueba de arquitectura | C1 | coordinador |
| **B2** | Lectores: `LectorTablaPort` y `TablaLeida`, CSV (BOM, UTF-8, Latin-1 y Sniffer restringido), JSON y hojas en `LectorCalamine`; `leer_hoja` delega | C1 | coordinador |
| **B3** | Persistencia y API: migración (`borrador_carga_archivo` con `analisis`, `mapeo_recordado` con `ocurrencia` y `carga.opciones_lectura`), vencimiento y limpieza, `/mapeador`, `POST /cargas/desde-borrador` (FOR UPDATE, 422 y 202), `procesar_carga` con mapeo explícito y opciones, `formato.mapeo` aditivo y los enums en el contrato | B1, B2 | coordinador; dev_frontend y designer como consumidores |
| **F1** | Experiencia y `MapeadorEncabezados` (designer), con las cinco etiquetas que faltan. Pasa por el usuario | contrato de B3 | usuario |
| **F2** | `/cargas` en dos pasos | F1 | designer |
| **C2** | Cierre contra RF-57 a RF-63 | todos | architec |

**Orden:** B17 (en curso) → B1 → B2 → B3 → F1 → F2. Hay un solo dev backend. B2 no depende de B1 y se puede revisar aparte. architec corre `-ConBase`, la migración de ida y vuelta, Linux, Playwright y la medición de ingesta con 120 000 filas antes y después de B3.

**Aprobado por architec (2026-10-24).** Aprobó M-1 a M-5 y M-7 a M-9 tal como están, el FOR UPDATE y el límite de los alias. **M-6 = (a)**, decidido por architec por ser técnico y favorable: una sola `coincide` en los dos caminos, y la paridad se reformula para archivos cuyas cabeceras ya coincidían por alias. M-9 va en F1. Los ajustes ya están en `mapeador-encabezados.md` y en `sabana-schema.md` N-1.

**Cierre (2026-10-27):** RF-57 a RF-63 cumplidos, en `revision-map-c2.md`. Hay tres hallazgos de la pasada real, que corrige T-MAP-B5.

## 28. Plan de los campos adicionales (T-CA-C1), para aprobación de architec

Sobre `d4dafb6` (RF-59 ampliado, RF-64 a RF-66). Incluye las restricciones que adelantó `coordinador_modulo_mowa_mes`.

### Contraste con el código

- **El catálogo de la cartera es una constante de módulo:** `seleccion_cartera/campos.py: CAMPOS_CARTERA`, derivada de `CATALOGO_VENCIDA` al importar. La usan, como dato fijo:
  - `campos.tipo_de` y `convertir`, y `expresiones` (filtros y segmentación de la selección, también los de la campaña de MOWA MES);
  - `selecciones/servicio.py`;
  - `contextos_texto.py` (las variables del contexto `cartera` del motor);
  - `generacion_cargas/servicio.py` (las columnas de carga);
  - `texto_enriquecido/tipos.py`.

  RF-66 pide que esos lugares reciban los adicionales «sin código específico»: la constante tiene que pasar a ser un **catálogo que se pide** y que suma lo de la base.
- **Valores por producto:** `carga_fila` tiene una columna tipada por campo base y un JSONB `extras` con las columnas desconocidas. El repositorio de cartera arma los filtros y agregados sobre `_FILA.c[campo]`.
- **El catálogo del mapeador:** `CATALOGO_SABANA` también es fijo, y `CampoDestino` lleva `clave_etiqueta` (i18n), que un adicional no puede tener porque su nombre lo escribe el usuario.
- **El análisis guardado del borrador (M-4)** congela `campos`. Un campo creado mientras se mapea no estaría en ese análisis, y validar daría `campo_desconocido`.

### Propuesta

- **P-1, definiciones.** Una tabla `campo_adicional`:
  - `nombre`: el técnico, único y estable, nunca reutilizado;
  - `catalogo_id`: «sabana_vencida»;
  - `nombre_legible`: único, comparado normalizado como RF-58, también contra nombres y alias base;
  - `tipo`: `texto`, `numero` o `fecha`;
  - `encabezado_origen`: el normalizado, que es su alias literal (T-MAP-B4 lo publica);
  - `archivado` y las marcas de tiempo.

  **Nombre técnico:** `ad_` + un *slug* ASCII del nombre legible y, si choca, `_2`, `_3`… El prefijo lo separa de los campos base, de los que vengan después y de las variables que pone un conector en cada fila (`titular`, `fecha_vencimiento_cuota`, `whatsapp_contacto`, `fecha_envio`, `dias_atraso_ajustados`…). Igual se valida contra una lista de nombres reservados de todos los contextos (restricción 6 de MOWA MES).
- **P-2, valores.** Una columna nueva `carga_fila.adicionales JSONB NULL` (`{nombre: valor}`), escrita SOLO por la ingesta y ya normalizada por tipo:
  - texto: tal cual;
  - número: un texto decimal canónico, nunca float;
  - fecha: ISO.

  Los filtros y agregados leen `(adicionales->>'ad_x')`, con un *cast* según el tipo (`::numeric` o `::date`), que es seguro porque el formato lo garantiza la ingesta. Un valor que no se convierte queda vacío, con la advertencia `valor_no_convertible` en su fila (RF-64). No hace falta índice: las consultas van por una versión, unas 46 000 filas. architec lo mide antes y después.

  Elijo esto frente a una tabla de valores (EAV, una fila por valor), que obliga a uniones en cada filtro y en cada fila generada. La versión que no tiene la columna queda en NULL y se lee vacía (RF-65).
- **P-3, una sola fuente.** `CatalogoCartera` en el núcleo:
  - `campos() -> dict[str, CampoCartera(nombre, tipo, etiqueta | clave_etiqueta, adicional: bool, archivado: bool)]`, que suma los campos base (fijos, como hoy) y los adicionales (desde un puerto, `RepositorioCamposAdicionalesPort`);
  - `tipo_de`, `convertir`, `expresiones`, los contextos del motor, la generación y el repositorio de cartera reciben el catálogo, en lugar de importar `CAMPOS_CARTERA`;
  - una prueba de arquitectura impide volver a importar la constante fuera de `campos.py`;
  - una prueba de «capacidad nueva» comprueba que lo que reciba el catálogo ve los adicionales sin código propio (RF-66).

  `CATALOGO_SABANA` del mapeador se arma igual, como base + adicionales activos. `CampoDestino` gana una `etiqueta` literal opcional, junto a `clave_etiqueta`, y la marca `adicional`.
- **P-4, crear desde el mapeo.** `POST /mapeador/borradores/{id}/campos-adicionales {indice, nombre_legible, tipo}`, en una transacción:
  - crea el campo (409 `nombre_repetido` con el campo con que choca, y 422 si el tipo no es válido);
  - lo agrega a los `campos` del análisis guardado del borrador (así M-4 sigue valiendo);
  - devuelve el análisis y el campo.

  La pantalla asigna esa columna al campo nuevo con origen `manual` y, al confirmar, se recuerda como cualquier asignación (RF-61). Un adicional nunca es obligatorio (RF-64).
- **P-5, el resto del ciclo.**
  - `GET /cartera/campos`, o el catálogo que ya tiene la cartera, con `adicional` y `etiqueta`;
  - `PATCH /campos-adicionales/{nombre}`, para renombrar (RF-65), que no toca el técnico;
  - `POST …/archivar` y `POST …/reactivar`.

  El contrato se regenera con cada corte.
- **P-6, el supuesto de RF-65, que se le propone al usuario:**
  - el **tipo es fijo**: cambiarlo reinterpretaría los valores de versiones ya cargadas. Para otro tipo se crea otro campo;
  - **archivar en lugar de borrar**: deja de ofrecerse en las listas y en el mapeador, ningún dato se borra, el técnico no se reutiliza y se puede reactivar;
  - lo que ya lo referencia sigue funcionando: una selección, una definición guardada o un speech compilan igual, porque el catálogo sigue resolviendo los archivados para leer, y solo no los ofrece. La previsualización avisa «usa un campo archivado», nunca un 500 (restricción 8 de MOWA MES);
  - un recordado hacia un archivado se ignora (B1: un campo fuera del catálogo que se ofrece pasa a la siguiente pasada).

### MOWA MES (restricciones de `coordinador_modulo_mowa_mes`)

**Corrección del alcance, de la §13 de MOWA MES:** el speech de MOWA MES NO sale del catálogo de la cartera. `contexto_texto.py` usa un conjunto fijo, `speech.VARIABLES_V2`: titular, fecha_vencimiento_cuota, whatsapp_contacto y dias_atraso_ajustados. Por eso T-CA-B1 no agrega adicionales al speech, y con RF-66 al pie de la letra NO se ofrecerían, igual que los demás campos base. Ofrecerlos es una decisión del usuario (D-CA-0). D-CA-1 y D-CA-2 solo aplican si la respuesta es sí.

**Lo que ya queda resuelto en el plan:**
- **GSM-7 (2):** se aplica al texto final, nunca a la variable. No hace falta nada propio.
- **Fecha (4):** `formato_fecha` tiene cota. Un **número** NO tiene una función con cota: `formato_numero` y `a_texto` de un número la pierden (cota.py), así que entra en D-CA-1 igual que el texto.
- **Nombres reservados (6):** P-1.
- **El resumen de los filtros (7):** muestra el nombre legible, con `una_linea` y el límite de 100 UTF-16. La campaña guarda los filtros con el técnico, así que renombrar no la cambia. `descripcion_sugerida` y `resumen_filtro` pasan a recibir el catálogo en **T-CA-B1**, con la §13 de MOWA MES. El resumen de los campos base sale igual que hoy.
- **Archivar (8):** P-6.
- **Proceso (9):** como siempre.

**Lo que decide el usuario. Lo llevo con una recomendación, vía architec:**
- **D-CA-0, el speech de MOWA MES ofrece los adicionales:** hoy el speech solo ofrece cuatro variables fijas, y ningún otro campo de la cartera. **Recomiendo SÍ:** RF-64 nace de «una columna en la que quiere enfocar la gestión», y el SMS es donde se gestiona. Con un sí, el corte de MOWA MES arma las variables v2 con los adicionales del catálogo, los lee de `carga_fila.adicionales` en la campaña y en la previsualización, y agrega un valor sintético de ejemplo por tipo. Con un no, D-CA-1 y D-CA-2 no aplican.
- **D-CA-1, la cota de un adicional de texto o número en un speech (1, corregido por la §13 de MOWA):** sin un tope, la advertencia de 150 no sirve. **Recomiendo** exigir un corte que fije el largo, `primeros(n)` (para un número, después de pasarlo a texto), como el titular a 8. La validación al guardar da un problema ubicado que lo sugiere. La fecha con `formato_fecha` ya tiene cota. La alternativa es «sin tope», con solo el control fila por fila (`mensaje_excede_160` excluye).
- **D-CA-2, un adicional vacío en un mensaje (3):** **recomiendo** excluir el producto con un código nuevo, `falta_campo_adicional`, si la expresión del segmento usa ese campo y en esa fila está vacío, igual que `falta_titular`. Va después de falta_vencimiento y antes de mensaje_excede_160, con el nombre técnico (puede haber varios) y el legible en la pantalla. También aplica a un campo archivado. Así nunca sale un SMS con un hueco. La alternativa es dejarlo vacío.
- **D-CA-3, columnas del .xlsx de MOWA MES (5):** **recomiendo** NO agregar columnas al archivo de MES. Un adicional entra solo dentro del texto del speech. RF-54 se mantiene byte a byte.

### Cortes

| Corte | Qué | Depende | Revisión |
|---|---|---|---|
| **T-MAP-B4** | Los alias literales en el catálogo del mapeador (para F3) | — | coordinador, designer |
| **T-CA-B1** | Núcleo: `CatalogoCartera` (base + adicionales), el puerto, el nombre técnico y los reservados, `CampoDestino` con etiqueta literal, todos los consumidores pasan a recibir el catálogo, y las pruebas de arquitectura y de «capacidad nueva». Sin migración: el puerto en memoria | C1 aprobado | coordinador; **MOWA MES (§13)**, porque `expresiones` y la campaña cambian de firma |
| **T-CA-B2** | Persistencia y API: migración (`campo_adicional` y `carga_fila.adicionales`), la ingesta con conversión por tipo y `valor_no_convertible`, el repositorio de cartera con *cast* por tipo, P-4 y P-5, y el contrato | B1 | coordinador, MOWA MES; dev_frontend y designer como consumidores |
| **T-MAP-B5** | Los hallazgos H-1 y H-2 de la revisión del mapeador | B2, porque tocan `similitud.py` y `mapeo_explicito.py` | coordinador |
| **T-CA-F0** | Reglas de interfaz (designer) y la aprobación del usuario | contrato de B2 | usuario |
| **T-CA-F1** | La creación en el mapeador (sobre el componente y F3) y la distinción visual en Cartera, el editor y el constructor | F0 | designer |
| **T-MM-B?** | Lo de MOWA MES, solo si D-CA-0 es sí: variables v2 con los adicionales, sus valores en la campaña y la previsualización, un ejemplo por tipo, D-CA-1 y D-CA-2 (de su equipo) | B2 y las decisiones | MOWA MES |
| **T-CA-C2** | Cierre contra RF-64 a RF-66 | todos | architec |

**Aprobado por architec, y decisiones del usuario del 2026-10-27, todas por la opción recomendada:**
- **P-6:** el tipo es fijo y se archiva en vez de borrar. Ningún dato se borra, el técnico no se reutiliza, se puede reactivar, y lo que ya lo usa sigue funcionando con un aviso.
- **D-CA-0:** SÍ, el speech de MOWA MES ofrece los adicionales.
- **D-CA-1:** se exige `primeros(n)` a un adicional de texto o de número (al de número, después de pasarlo a texto).
- **D-CA-2:** un adicional vacío excluye el producto con `falta_campo_adicional`.
- **D-CA-3:** no se agregan columnas al .xlsx de MES (RF-54 byte a byte).
- **Crear y cancelar:** un campo adicional creado durante el mapeo queda en el catálogo aunque se cancele la carga; si no se quería, se archiva. El formulario lo avisa (decisión del usuario del 2026-10-27).

**§13 de MOWA MES sobre T-CA-B1:** la prueba de oro del mensaje y las pruebas de la campaña y de la descripción sugerida pasan sin cambiar ningún valor esperado. Solo cambian las firmas. D-CA-3 aprobado.

**Orden:** B4 (corto, ya encargado) → CA-B1 → CA-B2 → MAP-B5. F0 puede empezar con el contrato de B2. architec corre `-ConBase`, la migración de ida y vuelta, WSL y la medición de consulta y generación con 46 000 filas, con y sin adicionales, antes y después de B2.

## 29. Plan del filtro de valores y del orden de los filtros (T-FV-C1), para aprobación de architec

Sobre `51f808b` (RF-67 y RF-68). Antes de cualquier código, necesita la aprobación de architec y el visto bueno de `coordinador_modulo_mowa_mes`, porque la campaña usa el mismo selector y guarda los mismos filtros.

### Contraste con el código

- **La lista de valores ya casi existe.** `RepositorioCarteraPostgres._sentencia_de_segmentar` agrupa un campo con sus cantidades sobre los filtros que recibe y ordena por cantidad descendente, con desempate por valor. Los productos sin valor salen como el grupo `NULL`. Sirve para base y adicional (`adicionales ->> 'ad_x'`). Lo que falta es el umbral, cortar en cuanto se pasa y un endpoint propio.
- **«(vacío)» es `NULL`.** La ingesta deja `NULL` el texto vacío o nulo (`reglas.py`, `strip()`), y un adicional que la fila no tiene también se lee `NULL`. El texto vacío `""` no existe en la cartera.
- **Excluir hoy no se puede bien.** Solo hay `en` (`columna.in_(...)`) y `distinto` de un valor. Un `NOT IN` en SQL descartaría también los vacíos, y eso es justo lo que hay que evitar.
- **`|` dentro de un valor rompe el filtro.** `parsear_filtro` y `leerFiltro` (frontend) parten los valores por `|` sin forma de escaparlo. Hoy casi no pasa, porque el valor se escribe a mano. Con la lista, el analista marca valores reales sin verlos escritos, y uno con `|` se partiría en silencio.
- **El orden ya se guarda.** `seleccion.filtros` y los filtros de la campaña son arreglos JSONB que conservan el orden, y `selecciones/servicio.py` solo quita los vacíos. La consulta es un AND, así que el orden no cambia el resultado. **Sí cambia** el texto de `descripcion_sugerida` de MOWA MES, que resume los filtros en su orden.
- **El selector es uno solo.** `SelectorSeleccion.astro` y `scripts/selector-seleccion.ts` se usan en Cartera, Columnas y la campaña de MOWA MES.

### Propuesta

- **P-1, el operador de excluir: `no_en` («no es ninguno de»),** para texto, número y fecha, igual que `en` (uno o más valores).
  - `en`: `columna IN (valores)`.
  - `no_en`: `columna IS NULL OR columna NOT IN (valores)`. Un producto sin valor no tiene ninguno de los marcados, así que queda en la selección.
- **P-2, «(vacío)» dentro de la lista marcada.** Se escribe como un **elemento vacío** en la lista de valores (`ad_tipo:en:Primera asignación|`, o `ad_tipo:no_en:|` para «solo excluir los vacíos»). Es lo único que no puede chocar con un valor real, porque la cartera no tiene `""`.
  - `en` con vacío: `columna IN (...) OR columna IS NULL`.
  - `no_en` con vacío: `columna IS NOT NULL AND columna NOT IN (...)`.

  Solo en texto. En número y fecha, un elemento vacío sigue siendo un error (400), como hoy. Lo resume una prueba de propiedad: para cualquier conjunto marcado, `en` y `no_en` parten la cartera sin repetir ni perder productos.
- **P-3, escapar `|`.** En la sintaxis de valores, `\|` es una barra literal y `\\` una barra invertida, en `parsear_filtro` y en `escribirFiltro`/`leerFiltro`. Antes de B1, architec cuenta en la base las selecciones y campañas guardadas con `\` en un filtro. Si hay alguna, se migran en el mismo corte. Si no, no hace falta migración.
- **P-4, el endpoint.** `GET /cartera/valores?fecha_corte=…&campo=…&filtro=…`, donde `filtro` lleva los filtros que están encima, con la sintaxis de siempre. El backend no necesita conocer el orden: la pantalla le manda la cascada.
  - Solo campos de texto, base o adicional, archivados incluidos, para que una selección vieja siga mostrando su lista. Otro tipo responde 400 y una fecha sin versión vigente, 404.
  - Respuesta: `{campo, umbral, ofrece_lista, valores: [{valor: string | null, cantidad}]}`. `null` es «(vacío)».
  - **Si se ofrece la lista se decide sobre la fecha entera** (RF-67: «distintos en la fecha de corte»), no sobre lo filtrado. Así un campo no cambia de control según los filtros de arriba. Se calcula con `LIMIT umbral + 1` sobre los distintos, y si se pasa, `ofrece_lista: false` y `valores: []`. Nunca se devuelven valores de un campo que supera el umbral, como nombres, documentos o teléfonos.
  - La lista contextual es la agrupación de `segmentar` sin el capital, con los filtros de arriba.
- **P-5, el umbral (RF-32).** Va en `Settings` (`umbral_valores_filtro`, 100 por defecto, de 2 a 1000), una sola fuente, y viaja en la respuesta para que la pantalla no lo duplique. Un umbral editable desde la interfaz no lo pide RF-67, y lo dejo fuera.
- **P-6, el orden (RF-68).** No cambia la forma del contrato: el orden de `filtros` es el que se guarda.
  - Se documenta en `selecciones-guardadas.md` y en `consulta-cartera.md` que el orden importa y se conserva.
  - Pruebas de ida y vuelta con un orden no alfabético, en selecciones y en campañas.
  - Una prueba de que dos órdenes dan el mismo `total` y los mismos productos.
- **P-7, el valor marcado que se queda sin productos.** Lo resuelve la pantalla: compara lo marcado con `valores`, y el valor que falta se muestra aparte, con el aviso. El filtro se manda igual, porque `en` con un valor sin productos no rompe nada. El backend no necesita nada propio.

### El supuesto de RF-67, que se le propone al usuario (lo llevo con una recomendación, vía architec)

- **D-FV-1, comparación tal cual.** **Recomiendo confirmarlo.** El valor ya llega con los espacios de los extremos quitados por la ingesta. Unir mayúsculas o tildes obligaría a que `en` y `no_en` comparen distinto que `igual`, y cada consulta llevaría `lower`/`unaccent`, que hoy no se usa. Si el usuario ve «Primera asignación» y «PRIMERA ASIGNACION» como dos valores, lo corrige la sábana, y la lista lo deja a la vista.
- **D-FV-2, orden por cantidad, de mayor a menor.** **Recomiendo confirmarlo,** con desempate alfabético para que la lista no salte entre llamadas, como ya hace `segmentar`. **«(vacío)» va siempre al final,** con su cantidad: está «como una opción más», pero en un lugar fijo, para encontrarlo. Si el usuario prefiere que se ordene con los demás, cambia una línea.

### MOWA MES (para la §13 de `coordinador_modulo_mowa_mes`)

- `resumen_filtro` necesita `no_en` y el vacío. Propongo `tipo de asignación no es Primera asignación/Segunda asignación` y, con vacío, `… en Primera asignación/(vacío)`, con `una_linea` y el límite de 100 UTF-16 de siempre.
- Reordenar los filtros cambia la `descripcion_sugerida` de una campaña nueva, porque resume en el orden de la lista. Lo propongo como esperado: es una sugerencia que el usuario edita. Las campañas ya creadas guardan su descripción y no cambian.
- La campaña guarda los filtros con su sintaxis, así que el escape de P-3 y la migración, si la hay, la alcanzan.
- Las pruebas de oro del mensaje no deberían cambiar: ningún operador existente cambia de significado.

### Medición (architec, con turno y 46 000 filas sintéticas)

Cada lista abierta es una consulta. Antes de cerrar B2, un script `scripts/medir_valores_filtro.py` mide sobre la sábana sintética de 46 000 filas (`generar_sabana_sintetica.py`), con un campo base de texto de unos 10 valores y un adicional de texto de unos 50:

1. la decisión del umbral (`LIMIT umbral + 1`) sobre la fecha entera;
2. la lista sin filtros arriba, y con tres;
3. un campo que supera el umbral (un documento), que tiene que cortar pronto.

**Presupuesto:** menos de 150 ms en el p95 por lista, con las dos consultas. Si no se cumple, la primera opción es guardar en memoria la decisión del umbral por `(carga vigente, campo)`, que no cambia mientras la versión vigente sea la misma. Un índice por adicional no sirve, porque los adicionales son dinámicos.

### Cortes

| Corte | Qué | Depende | Revisión |
|---|---|---|---|
| **T-FV-B1** | Núcleo y SQL: `no_en`, el vacío en `en`/`no_en` (solo texto), el escape de `\|`, `resumen_filtro`, la prueba de propiedad de la partición, las de ida y vuelta del orden, y la migración del escape si la cuenta de P-3 la pide. Contrato: el enum de operadores | C1 aprobado | coordinador; **MOWA MES (§13)** |
| **T-FV-B2** | `GET /cartera/valores`, el umbral en `Settings`, el script de medición y el contrato | B1 | coordinador; architec mide |
| **T-FV-F0** | Reglas de interfaz (designer): la lista (marcar, incluir o excluir, cantidades, «(vacío)», el valor marcado sin productos) y el reordenamiento (arrastrar, teclado, anuncio para lector de pantalla) | este plan aprobado | usuario, vía architec |
| **T-FV-F1** | `seleccion.ts`: `no_en`, el elemento vacío (hoy `escribirFiltro` lo descarta con `filter(Boolean)`) y el escape, con Vitest. Sin interfaz | B1 | coordinador |
| **T-FV-F2** | La lista de valores en `SelectorSeleccion`, en cascada con los filtros de arriba | F0, F1, B2 | designer; MOWA MES, porque la campaña lo usa |
| **T-FV-F3** | Reordenar los filtros arrastrando y con el teclado, con el orden guardado en la selección y en la campaña | F0, F2 | designer; MOWA MES |
| **T-FV-C2** | Cierre contra RF-67 y RF-68 | todos | architec |

**Orden:** B1 → B2, con F0 en paralelo desde la aprobación. F1 puede ir apenas entre B1. F2 y F3 son secuenciales porque tocan el mismo componente. architec corre `-ConBase`, la medición de B2 y el Playwright completo en F2 y F3.

**Aprobado por `architec` el 2026-10-28.** Decisiones del usuario del mismo día: D-FV-1, comparación tal cual; D-FV-2, orden por cantidad con desempate alfabético y «(vacío)» al final. P-3: en `auto_cusco` hay 1 selección y 2 campañas guardadas; ninguna tiene «\» en sus filtros (los «|» que tienen son separadores de «es uno de»), así que el escape no necesita migración. B1 arranca con el visto bueno §13 de `coordinador_modulo_mowa_mes`.
