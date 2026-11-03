# Plan T-MM-B15, paso 2 (M2): el archivo de MOWA MES sale del constructor compartido

Autor: `dev_backend_modulo_mowa_mes`. Base: `main` en 7d7d7ff (el oro del paso 1 ya está). Solo lectura y este plan: nada en `app/` ni en `tests/`. Lo pedido: RF-MM-37 y RF-72, igual byte a byte, sin migración si se puede, speech, exclusiones y división en MOWA.

## 0. Lo primero que hay que decidir: `GeneracionCargasService.generar` no puede recibir filas ya evaluadas

`GeneracionCargasService.generar` (`core/services/generacion_cargas/servicio.py:87-118`) recibe `fecha_corte, definicion, filtros, orden, cantidad, fecha_envio`, **lee la cartera él mismo** (`SeleccionPaginada(self._consulta, ...)`, línea 108) y arma la `Tabla` con `GeneradorCargas`. En cambio, las filas de MOWA ya salen evaluadas de su propio armado (`campana.py:296-391`). Hay tres formas de acercarlas (§1). Lo que SÍ se comparte en cualquiera de ellas, y es lo que hoy MOWA arma a mano en `archivo_carga.py:16-25`:

- la `DefinicionCarga` (columnas, orden, tipos) y las `ReglasPlataforma` (RF-72);
- `GeneradorCargas` (fila de entrada → celdas tipadas con `formatos.convertir`);
- el exportador común (`exportador_xlsx.exportar` con `OpcionesArchivo`).

**Pregunta 0 (para el coordinador y la §13):** ¿alcanza con «el generador (`GeneradorCargas`) y el exportador comunes» o se exige literalmente `GeneracionCargasService`? Recomiendo lo primero (diseño D1).

## 1. Qué tramo pasa por lo compartido y qué queda en MOWA

### Se queda en MOWA, sin tocar (todo antes de la fila)
| Qué | Dónde hoy |
|---|---|
| Exclusiones de RF-MM-13, en su orden, y la advertencia de documento no estándar | `campana.py:202-268` (`evaluar_producto`) |
| Speech v2 por segmento, GSM-7 (RF-MM-27) y el tope de 160 | `campana.py:244-252` (`constructor.mensaje_de`, `largo_gsm7`, `codigo_por_largo`); `speech.py` |
| Faltas de WhatsApp por segmento, errores de creación | `campana.py:325-335`, `_errores` (547) |
| Supervisores al inicio (RF-MM-12): el mensaje y el documento del primer producto | `campana.py:336`, `_filas_supervision` (573-598), `supervision.filas_supervision` |
| División por filas y por bytes | `campana.py:406-408` (`division.dividir(..., self._escritor)`), `division.py` |
| Huella del speech, costo, límite mensual, nombres de archivo | `campana.py` |

### Pasa por lo compartido (solo el último paso: filas → Tabla → .xlsx)
Hoy: `escribir_archivo_carga(filas)` (`adapters/output/plataformas/mowa_mes/archivo_carga.py:16-25`) arma `Tabla(nombre="mowa_mes", cabeceras=CABECERAS_CARGA, filas=tuple(f.celdas() ...))` y llama `exportador_xlsx.exportar(tabla, OpcionesArchivo(hoja="Hoja1", con_cabeceras=True))`. Lo inyecta la API en `api/mowa_mes_campanas.py:117`.

### Diseños
**D1 — Definición + generador + exportador comunes, el escritor sigue siendo el de MOWA (recomendado).** Un módulo nuevo del paquete de MOWA, `core/services/plataformas/mowa_mes/plataforma.py`, declara `REGLAS_MOWA_MES` (§2) y `DEFINICION_MOWA_MES` (`DefinicionCarga` con tres `CampoSalida`). `archivo_carga.escribir_archivo_carga(filas)` conserva nombre y firma, pero ahora: `GeneradorCargas(DEFINICION_MOWA_MES, TIPOS_DE_LA_FILA).generar(f.celdas() for f in filas)`, con `TIPOS_DE_LA_FILA = {"numero": TipoValor.NUMERO, "mensaje": TipoValor.TEXTO, "dni": TipoValor.TEXTO}` (el segundo argumento es el mapa nombre → tipo, no una tupla de nombres; así `numero` entra como entero) → `Tabla` → `exportador_xlsx.exportar(tabla, OpcionesArchivo(hoja=HOJA_CARGA, con_cabeceras=True, columnas_texto=DEFINICION.columnas_texto, proteger_formulas=DEFINICION.proteger_formulas))`. Si la generación trae un solo `ErrorGeneracion`, el escritor lanza (nunca escribe un archivo con una celda alterada).
- *Pros:* la forma del archivo (columnas, orden, tipos) tiene UNA fuente, la misma que valida RF-72; el cableado de la API, `division.dividir`, `campana.py` y `FilaCarga` no cambian; el oro del paso 1 no cambia ni en su cableado (`test_la_api_cablea…` sigue verde); riesgo bajo y diff pequeño.
- *Contras:* no usa la CLASE `GeneracionCargasService` (que lee cartera): usa lo que ella envuelve.

**D2 — D1 + extraer de `GeneracionCargasService` una función pública «definición + productos → Tabla».** El servicio compartido se refactoriza para que `generar` y MOWA usen la misma función. *Pros:* un único camino «definición + productos → Tabla» (WhatsMKT, T-HI-B5, también arma sus filas por su cuenta y probablemente lo necesita); es lo más cercano a la letra de RF-MM-37. *Contras:* toca el servicio compartido de `/archivos-carga` (otro dueño; §13 con herramientas) para un uso que hoy solo es mío. **Si el coordinador de herramientas ya quiere esa función para WhatsMKT, D2; si no, D1 y se extrae después.**

**D3 — Todo en el generador (el `mensaje` como columna segmentada con las expresiones del speech como `variantes`, exclusiones como `FilaExcluida`, GSM-7 como `salida`). Rechazado.** (i) RF-MM-13 tiene 11 códigos de exclusión en orden fijo, con campos adicionales y `FaltaWhatsapp` agregada por segmento; el generador solo conoce `FilaExcluida` por segmento sin dato y `ErrorGeneracion`. (ii) GSM-7 y los 150/160 se aplican al texto ya evaluado ANTES de medir; en generación el generador no aplica `salida` (solo en la previsualización, `detallar_fila`). (iii) Los supervisores heredan el mensaje del primer producto cargado. (iv) `whatsapp_contacto` es una constante de MOWA que `GeneracionCargasService` no recibe. Contradice «speech, exclusiones y división siguen en MOWA» y es riesgo alto sobre un archivo que se usa a diario.

### Cómo se expresan `numero`, `mensaje` y `dni` (D1/D2)
Tres `CampoSalida`, en este orden, `nombre` = la cabecera: `numero` (`plantilla="[@numero]"`, `tipo=NUMERO`), `mensaje` (`"[@mensaje]"`, `TEXTO`), `dni` (`"[@dni]"`, `TEXTO`); ninguno con `celda_texto`. La «fila de producto» que reciben es `FilaCarga.celdas()` (`mowa_mes_campana.py:122`: `numero` ya entero, `mensaje` y `dni` texto), así que no cambia `FilaCarga`. El `mensaje` NO se construye en la definición: llega hecho (speech v2 + GSM-7 + tope de 160 ya aplicados en `evaluar_producto`); la plantilla `[@mensaje]` es una referencia directa y el valor no se vuelve a interpretar (un `[@` dentro del mensaje es dato).
- **Exclusiones: ANTES del generador** (en `evaluar_producto`, como hoy). El generador solo ve filas válidas.
- **Supervisores: ANTES**, `_filas_supervision` antepone las filas al inicio de la lista; el escritor recibe la lista ya ordenada.
- **División sobre la Tabla:** `division.dividir` sigue llamando al escritor con cada tramo de `FilaCarga` (`campana.py:406`); cada llamada genera su propia `Tabla`. El escritor se llama una vez por tramo y de nuevo si un tramo se parte por bytes (como hoy).

## 2. Dónde viven las `ReglasPlataforma` de `mowa_mes` y cómo llegan al registro
- **Dónde:** `core/services/plataformas/mowa_mes/plataforma.py` (nuevo, en el paquete de MOWA): `REGLAS_MOWA_MES = ReglasPlataforma(clave="mowa_mes", etiqueta="MOWA MES", columnas_fijas=(ColumnaFija(1,"numero",…,NUMERO), ColumnaFija(2,"mensaje",…,TEXTO), ColumnaFija(3,"dni",…,TEXTO)), admite_mas_columnas=False)`, sin `tipo_resto`, sin `encabezado_por_posicion`, sin `celda_texto`.
- **Cómo llega:** el núcleo no conoce a MOWA: `RegistroPlataformas` queda intacto (`definiciones_columnas/plataformas.py`). Se registra en la raíz de composición, `api/definiciones_columnas.py:71`. Ya acordado entre coordinadores: WhatsMKT (T-WM-B2) la deja como `RegistroPlataformas([REGLAS_WHATSMKT])` y `mowa_mes` va en esa misma lista, `RegistroPlataformas([REGLAS_WHATSMKT, REGLAS_MOWA_MES])` (la API importa el paquete de MOWA, como `campanas` ya importa sus adaptadores). El que entre segundo a main suma la suya sin reemplazar la otra y resuelve el choque en el rebase.
- **Contenido de las columnas fijas para el constructor** (`contenido_por_defecto`): `numero` → `[@telefono]`, `dni` → `[@documento_numero]`, `mensaje` → sin contenido. `contenido_editable`: ver Pregunta 2.

## 3. Qué cambia para el usuario: preguntas, con mi recomendación
Si `mowa_mes` queda en el registro, `GET /definiciones-columnas/plataformas` lo lista y el constructor lo ofrecería.
- **P1 — ¿Registrar `mowa_mes` en el registro público?** *Recomiendo SÍ.* Es lo que dice RF-72 («cada plataforma registra sus reglas»), no cambia el contrato (la respuesta ya es una lista de plataformas) ni hay migración, y no rompe pruebas: `test_plataformas_definiciones.py` sustituye el registro (`:433`, `:461`). *Consecuencia a decidir:* el constructor ofrecería crear definiciones «MOWA MES» (3 columnas fijas, sin más) con la cartera como origen; **la campaña NO las lee** (usa la definición del código). Una definición guardada sería para generar un archivo con la forma de MOWA fuera de una campaña (sin speech, sin exclusiones, sin supervisores). *Alternativa:* no listarla (no hay bandera para ocultarla; habría que agregarla al núcleo). Pregunta para el usuario: ¿ese archivo «con la forma de MOWA» sin campaña es deseable, o confunde?
- **P2 — ¿La definición de la campaña se guarda en la base o se arma en código?** *Recomiendo código:* una campaña tiene que ser reproducible y su formato lo exige MES; si fuera editable, un usuario podría romper el archivo. Cero migración. *Contra:* la «definición mowa_mes» de la base (P1) y la del código son cosas distintas con el mismo nombre; el docs lo dirá.
- **P3 — `contenido_editable` de las fijas en el constructor:** *recomiendo* editable en `numero` y `dni` (elegir otro campo de la cartera) y en `mensaje` (la plantilla propia del usuario). No afecta a la campaña.

## 4. El riesgo para el byte a byte, y cómo se comprueba
Qué podría cambiar un byte, cada uno con su control:
1. **Tipo de `numero`:** `GeneradorCargas` lo pasa por `formatos.convertir` (`mapeo_campos/formatos.py:43-58`); con un `int` de entrada devuelve el mismo `int` (rama `crudo` entero), y si llegara texto, `Decimal` → `int`. Hoy es `int(self.numero)`. *Control:* oro (`ARCHIVOS_CONGELADOS`) + `XLSX_MOWA_SIN_IGUAL`. Si un día fuera Decimal no entero saldría otro valor: el escritor lo trata como error.
2. **`mensaje` y `dni` como texto:** rama `TEXTO` devuelve `texto = str(crudo)` (atajo `directa`, `generador.py:266-268`); un `dni` con ceros se conserva. Un mensaje vacío o `None` no ocurre (el speech siempre da texto). Si `valor_por_defecto` es `None` no sustituye nada.
3. **Hoja `Hoja1` y cabeceras:** la `DefinicionCarga` no trae la hoja, es una opción del exportador: sigue siendo la constante `HOJA_CARGA` en el escritor de MOWA; las cabeceras son los `nombre` de los campos en el mismo orden que `CABECERAS_CARGA`. *Control:* una prueba que exige `DEFINICION_MOWA_MES` ⇒ cabeceras == `CABECERAS_CARGA` (así una sola fuente no puede divergir).
4. **`celda_texto` / `columnas_texto`:** vacío (ninguna columna con `celda_texto`): sin `number_format="@"`, que cambiaría `styles.xml` y `sheet1.xml`.
5. **Protección de fórmulas:** en XLSX no es opción; el exportador escribe un texto que empieza con `=` como texto literal (`_celda`, `exportador_xlsx.py:122`). Se pasa `proteger_formulas` solo por coherencia. *Control:* `test_exportacion_segura` (casos con `=` en `FILAS_MOWA_*`).
6. **Orden y cantidad de filas:** `GeneradorCargas.generar` devuelve una fila por entrada y solo descarta si hay segmentación (no hay). *Control:* el escritor exige `len(tabla.filas) == len(filas)` y que no haya `errores`.
7. **Orden de columnas y de claves:** la `Tabla` usa `cabeceras` para ordenar; `comunes.columnas` las lee por nombre.
8. **El exportador:** la MISMA función `exportador_xlsx.exportar`; no se modifica.
9. **Rendimiento:** pasar 46 000 filas por el generador añade evaluación por celda; hay que medirlo con `scripts/medir_campana_mowa_mes.py` antes/después (el escritor se llama por tramo, y otra vez si el tramo se parte por bytes). Si el costo fuera relevante, la rama `directa` ya evita evaluar la expresión.
*Cómo se prueba el byte a byte:* el oro del paso 1 (`ARCHIVOS_CONGELADOS`, 3 archivos, huella + largo sin comprimir) y `XLSX_MOWA_SIN_IGUAL` **no se tocan**; la única edición posible de una prueba es cómo arma el servicio si cambia el cableado (con D1 no cambia: `escribir_archivo_carga` conserva su nombre y su módulo).

## 5. Pruebas y mutación
- **Capas sin base (todas):** el oro del archivo (`test_mowa_mes_archivo_oro`), `test_exportacion_segura`, `test_mowa_mes_speech_oro`, `test_generador_paridad`, `test_mowa_mes_division`, `test_mowa_mes_campana` y la suite de MOWA; más pruebas nuevas: (a) `REGLAS_MOWA_MES` válidas y `DEFINICION_MOWA_MES` pasa `problemas_de_plataforma` y cualquier cambio (una columna de más, otro orden, otro tipo) lo viola; (b) cabeceras == `CABECERAS_CARGA`; (c) el escritor lanza si el generador da un error o cambia el número de filas; (d) `GET /definiciones-columnas/plataformas` con el registro real lista `mowa_mes` con sus tres fijas.
- **Con base:** ninguna nueva (no hay migración); `-ConBase` repetiría las existentes de MOWA.
- **Mutación (sobre el armado nuevo):** `plataforma.py` (tipo `numero` a TEXTO, `dni` a NUMERO, cambiar el orden o el nombre de una columna, `celda_texto=True`, `admite_mas_columnas=True`), `archivo_carga.py` (hoja distinta, `columnas_texto` no vacío, ignorar los errores del generador, descartar una fila), y el registro en `api/definiciones_columnas.py` (no registrar). Todas deben morir sin base en: oro, `test_exportacion_segura`, las pruebas nuevas.
- **Contrato:** no cambia: `GET /definiciones-columnas/plataformas` ya responde `list[ReglasPlataformaRespuesta]` con `columnas_fijas` (`api/definiciones_columnas.py:258-283`, `:367`); registrar otra plataforma cambia datos, no el esquema, y no hay que regenerar `openapi.json`. Se comprueba con `exportar_openapi --comprobar` en el turno.
- **Turno:** pytest -m "not postgres" de las 7 anteriores + nuevas, medición opcional del rendimiento, mutaciones en copia descartable, ruff.

## 6. Resumen de lo que pido decidir antes de escribir código
0. D1, D2 o D3 (recomiendo **D1**; D2 si herramientas quiere esa función para WhatsMKT).
1. P1: ¿registrar `mowa_mes` en el registro público? (recomiendo sí).
2. P2: ¿la definición de la campaña en código? (recomiendo sí).
3. P3: ¿`contenido_editable` de las fijas? (recomiendo sí).
4. §13 con `coordinador_herramientas_implementadas`: si D2 (la función «definición + productos → Tabla» compartida). El registro conjunto en `api/definiciones_columnas.py` ya está acordado (§2). Lo abierto es el punto 3: si se ve en el constructor (P1) y si se guarda en la base (P2).

## 7. Ajustes del coordinador (a incluir al escribir el código, tras la luz verde)
Decisiones salvo que architec diga otra cosa: P1 `mowa_mes` registrado y visible; P2 definición en código, sin migración; P3 fijas editables con los contenidos por defecto de §2. Falta el OK de architec a D1 y la §13 de herramientas (uso de `GeneradorCargas`, si quieren D2). Mientras tanto, nada de código.
1. **Rendimiento con números:** `scripts/medir_campana_mowa_mes.py` antes y después, con 46 000 filas (base de pruebas `_test`, en turno). Si sale más de un 10 % más lento, se reporta ANTES de entregar.
2. **El mensaje no se reinterpreta:** una `FilaCarga` con `«[@titular] {x}»` en `mensaje` sale literal en la celda del `.xlsx` leído. El escritor no puede depender de que GSM-7 transliteré los corchetes.
3. **Tipos de celda en el `.xlsx` leído:** `numero` numérico; `dni` texto, con ceros a la izquierda y un `ZZCE…`.
4. **Errores del escritor sin datos:** si el generador falla o cambia la cantidad de filas, el mensaje del error NO lleva valores de las filas (teléfono, dni ni mensaje); solo el código o la posición. Prueba que lo exige (con una fila que lleve esos valores).
5. **Segundo argumento de `GeneradorCargas`:** el mapa nombre → tipo (ya corregido en §1), no una tupla.
6. **WhatsMKT B2:** si al entrar a main ya está, `mowa_mes` se suma a la lista sin reemplazarla; antes se revisa si alguna prueba de WhatsMKT espera la lista exacta de plataformas.
7. **Docs:** `docs/mowa-mes.md`, en la parte del archivo de carga: «sale de la definición `mowa_mes` (RF-MM-37)»; y una sección nueva con lo de este corte.
8. **Mutación:** en una copia descartable, nunca en el worktree de entrega.

## 8. §13 con herramientas: D1 aprobado, D2 descartado (notas para escribir el código)
- **Diseño: D1.** Se usa `GeneradorCargas.generar()` y se lee `errores` y las filas. NO se usa `detallar_fila` (es de la previsualización).
- **Campos de origen exactos:** `GeneradorCargas` se construye con `numero`, `mensaje` y `dni` (el mapa nombre → tipo de §1), para que `[@mensaje]` valide contra ellos.
- **Prueba extra de que el mensaje no se reinterpreta:** un mensaje con `«[@telefono]»` literal sale igual en la celda; van esa y la de `«[@titular] {x}»` (§7, punto 2).
- **Rendimiento:** herramientas quiere ver la medición con 46 000 filas, antes y después (§7, punto 1).
- **P1 cambia a «lo decide el usuario», y el coordinador recomendó NO registrar `mowa_mes` en la API pública.** `REGLAS_MOWA_MES` se quedan en `plataforma.py`, y una prueba valida `DEFINICION_MOWA_MES` contra ellas con `problemas_de_plataforma`. **En suspenso** hasta que haya respuesta del usuario: el registro en `api/definiciones_columnas.py` (§2, y el punto 6 de §7 sobre WhatsMKT) y la prueba de `GET /definiciones-columnas/plataformas`. Si el usuario elige mostrarla, se agregan las dos.

## 9. Lo decidido y lo escrito (luz verde del coordinador, 2026-11-02)
Este apartado manda sobre §2, §3 y §6 donde se contradigan.
- **D1** (architec y herramientas); **D2 descartado**. **P1 = «No, solo la campaña»** (decisión del usuario, consultado por architec): `mowa_mes` NO entra en el `RegistroPlataformas`; no se toca `api/definiciones_columnas.py` y no hay prueba de `GET /plataformas`. `REGLAS_MOWA_MES` y `DEFINICION_MOWA_MES` viven en `plataforma.py` y una prueba valida la definición contra las reglas con `problemas_de_plataforma`. **P2:** en código, sin migración. **P3:** ya no aplica (no sale en el constructor): `contenido_por_defecto=None` y `contenido_editable` por defecto.
- **Escrito (sin correr nada, falta el turno):** `core/services/plataformas/mowa_mes/plataforma.py` (nuevo); `adapters/output/plataformas/mowa_mes/archivo_carga.py` (`GeneradorCargas` + exportador común + `ArchivoCargaInvalido` sin datos de las filas); `tests/test_mowa_mes_plataforma.py` y `tests/test_mowa_mes_archivo_carga.py` (nuevos); `docs/mowa-mes.md` (§33 y la fila del archivo) y `docs/requerimientos-mowa-mes.md` (viñeta de RF-MM-37, fila de la sección 6 y registro de cambios). `ARCHIVOS_CONGELADOS` y `XLSX_MOWA_SIN_IGUAL` no se tocan; el cableado de la API tampoco.
- **Falta, con turno:** medición con 46 000 filas antes (en `main`) y después; `pytest -m "not postgres"` (oro del archivo, las 4 de oro, `test_mowa_mes_campana`, las pruebas nuevas y `test_*mowa_mes*`); la mutación en copia descartable; ruff; `exportar_openapi --comprobar`.
