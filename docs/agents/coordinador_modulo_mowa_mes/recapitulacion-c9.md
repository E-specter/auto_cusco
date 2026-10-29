# Recapitulación de MOWA MES, mejoras y reutilización del código (T-MM-C9)

> **Escrita el 2026-10-29 sobre `bbba3a1`.** Solo lectura: no se corrió ninguna prueba para este documento. Los conteos de pruebas salen de leer los archivos (`def test_`, `it(`, `test(`) y no cuentan las parametrizaciones. Es la base para la conversación con el usuario: **se propone, el usuario decide.**

Coordinador: `coordinador_modulo_mowa_mes`. Pedido por `architec`. La parte C se repartió en solo lectura: el backend a `dev_backend_modulo_mowa_mes` y el frontend a `dev_frontend_modulo_mowa_mes`. La síntesis es mía.

**Uso real** (conteos de la base de trabajo, sacados por `architec`): 2 campañas creadas, 0 reportes de enviados importados y 21 sábanas vigentes (del 8/09 al 27/10). **El seguimiento y la conciliación nunca se usaron en la práctica.** Las causas posibles van en B como hipótesis, no como hechos.

**Capas** (nombres de `.claude/skills/verificar/SKILL.md`):
- **Nú**: núcleo, con dobles.
- **Ad**: adaptadores.
- **API**: `TestClient`.
- **PG**: integración contra PostgreSQL, `@postgres`, la corre `architec` con `-ConBase`.
- **E2E**: Playwright.
- **Ti**: tipos, con `astro check` y `tsc`.
- **Co**: contratos (OpenAPI ↔ tipos y catálogos espejo).
- **Pr**: propiedades. El proyecto no tiene Hypothesis; hay pruebas «de propiedad» escritas a mano, con entradas generadas.
- **Mu**: mutación, solo a mano, en cada corte.
- **A11y**: axe en `accesibilidad.spec.ts`.
- **Re**: rendimiento, solo a mano, con `scripts/medir_*_mowa_mes.py`.
- **Mi**: migraciones de ida y vuelta, a mano.

No existen en el proyecto la regresión visual, la seguridad automatizada ni la cobertura.

---

## A. Recapitulación por parte

### A.1 Configuración del conector (límite, WhatsApp, tarifa, límites por archivo y plantilla)

- **Qué hace:** guarda lo que toda campaña toma por defecto: el límite mensual de SMS, el WhatsApp de contacto, la tarifa por SMS, los registros y bytes por archivo y la plantilla del nombre de archivo. Cada bloque se guarda por separado.
- **RF:** RF-MM-01 (límite), RF-MM-11 (límites por archivo), RF-MM-16 (WhatsApp), RF-MM-23 (tarifa, por defecto S/ 0.02) y RF-MM-25 (plantilla).
- **Backend:** `core/services/plataformas/mowa_mes/configuracion.py`, `core/entities/mowa_mes.py`, `core/ports/repositorio_mowa_mes_port.py`, `adapters/persistence/repositorio_mowa_mes_postgres.py` y `api/mowa_mes.py` (`GET`/`PUT /mowa-mes/configuracion`).
- **Frontend:** `pages/mowa-mes/configuracion.astro`, `lib/api-mowa-mes.ts` y `lib/mowa-mes.ts`.
- **Pruebas:**
  - API: `test_api_mowa_mes_configuracion.py`, 40.
  - PG: `test_mowa_mes_configuracion_postgres.py`, 12.
  - Nú del frontend: `mowa-mes.test.ts`, 74, compartida con otras partes.
  - E2E: `mowa-mes-configuracion.spec.ts`, 42.
  - A11y, Ti y Co.
- **Decisiones vigentes:** la campaña congela la tarifa al crearse (RF-MM-24), y el `400` de la configuración trae el campo (§16.2.1 de `mowa-mes.md`).
- **Pendientes:** ninguno abierto.

### A.2 Speech v1 y v2, con el motor de texto enriquecido

- **Qué hace:** arma el mensaje de cada producto según el segmento por días de atraso ajustados a la fecha de envío. Las versiones son trazables. Las v1, el «Speech original» incluido, quedan en solo lectura y se pueden convertir a v2. Las v2 son expresiones del motor, con funciones, cotas y variables de contexto, entre ellas los campos adicionales.
- **RF:** RF-MM-14 a RF-MM-19 y RF-MM-27, más RF-43 y RF-55 del motor, en la parte de MOWA. Decisión M3: la v1 retirada.
- **Backend:**
  - del módulo: `plataformas/mowa_mes/speech.py` (636 líneas), `contexto_texto.py`, `segmentos.py` y `configuracion.py` (guardar, previsualizar y convertir);
  - API: `api/mowa_mes.py` (`/speech`, `/speech/previsualizacion`, `/speech/{id}/como-v2`);
  - del motor: `core/services/texto_enriquecido/*`.
- **Frontend:** `configuracion.astro` (2117 líneas en total) y `lib/mowa-mes-speech-v2.ts`, más los componentes del motor `EditorTexto` y `VariantesSegmento`, con `scripts/editor-texto.ts`.
- **Pruebas:**
  - Nú:
    - `test_mowa_mes_speech.py`, 37;
    - `test_mowa_mes_speech_v2.py`, 48;
    - **oro:** `test_mowa_mes_speech_oro.py`, 37, más los datos congelados `oro_mowa_mes_*.py`;
    - `test_mowa_mes_speech_constantes.py`, 12;
    - `test_mowa_mes_problema_speech.py`, 8;
    - `test_mowa_mes_rangos_nucleo.py`, 12;
    - `test_speech_original.py`, 2.
  - API: `test_api_mowa_mes_speech_v2.py`, 35.
  - PG: `test_mowa_mes_speech_v2_postgres.py`, 21.
  - Vitest: `mowa-mes-speech-v2.test.ts`, 22.
  - E2E: `mowa-mes-speech-v2.spec.ts`, 16, y la configuración.
  - Mu a mano en cada corte.
- **Decisiones vigentes:**
  - las huellas de las versiones 17 (Speech original) y 92 (v1 del usuario) no cambian;
  - las pruebas de oro solo cambian con autorización, línea por línea;
  - S-MM-5 (con «diferentes horas», la fecha más temprana) y S-MM-6 (`dias_ajustados = 0` es Preventiva) están confirmados.
- **Pendiente:** «el 150 y el 160 en frases por código» (`revision-c4.md` §6). Los textos de `mensaje_excede_150` y `mensaje_excede_160` llevan los números escritos.

### A.3 Supervisores (gestiones digitales)

- **Qué hace:** los registros de supervisión por procedencia van al inicio del primer archivo, con su documento por posición.
- **RF:** RF-37 a RF-41 (generales) y RF-MM-12.
- **Backend:**
  - general, no de MOWA: `core/services/gestiones_digitales/supervision.py` y `servicio.py`, `core/entities/gestiones_digitales.py`, `adapters/persistence/repositorio_supervision_postgres.py` y `api/supervisores.py`;
  - MOWA solo lo consume en `campana.py`.
- **Frontend:** el bloque de supervisores de `configuracion.astro`.
- **Pruebas:**
  - Nú: `test_gestiones_digitales.py`, 12.
  - PG: dentro de `test_mowa_mes_configuracion_postgres.py` y de `test_mowa_mes_campanas_postgres.py`.
  - E2E: la configuración.
- **Pendientes:** ninguno.

### A.4 Calendario y feriados

- **Qué hace:** calcula el siguiente día gestionable, de lunes a viernes sin feriados. La regla trae los 16 feriados de ley, con la Semana Santa calculada, y los días no laborables adicionales se registran a mano, visibles para todos.
- **RF:** RF-MM-08. Cierra S-MM-4 (decisión del usuario del 2026-10-26).
- **Backend:**
  - general: `core/services/calendario/reglas.py` y `servicio.py`, `core/entities/calendario.py`, `adapters/persistence/repositorio_calendario_postgres.py` y `api/calendario.py`;
  - MOWA lo usa para la fecha de envío.
- **Frontend:** la sección de calendario de `configuracion.astro`.
- **Pruebas:**
  - Nú: `test_calendario.py`, 12.
  - PG: dentro de `test_mowa_mes_configuracion_postgres.py`.
  - E2E: la configuración.
- **Pendiente:** si se aprueba un feriado nuevo o un traslado a lunes, hay que ajustar la regla, que es código.

### A.5 Campaña: selección → previsualización → creación → archivos

- **Qué hace:**
  - toma la base de una selección guardada en una fecha de corte, con el selector compacto: la fecha y la selección, sin editor de filtros;
  - evalúa cada producto: un solo motivo de exclusión, en el orden del catálogo, más advertencias;
  - previsualiza con paginación, muestra, exclusiones, cifras, consumo del límite, costo y nombre del primer archivo;
  - crea con la huella del speech, que da un 409 si el speech cambió, y genera los `.xlsx`.
- **RF:** RF-MM-03 a RF-MM-13, RF-MM-26 y RF-MM-09 (con RF-08 de la selección).
- **Backend:**
  - del módulo: `plataformas/mowa_mes/campana.py` (582 líneas), `core/entities/mowa_mes_campana.py` (360), `core/ports/repositorio_campanas_mowa_mes_port.py` y `adapters/persistence/repositorio_campanas_mowa_mes_postgres.py` (474);
  - API: `api/mowa_mes_campanas.py` (1054);
  - salida: `adapters/output/plataformas/mowa_mes/archivo_carga.py` (20).
- **Frontend:** `pages/mowa-mes/campana.astro` (1620), `lib/mowa-mes-campana.ts` (343) y `SelectorSeleccion modo="compacto"`.
- **Pruebas:**
  - Nú: `test_mowa_mes_campana.py`, 54.
  - API: `test_api_mowa_mes_campanas.py`, 33.
  - PG: `test_mowa_mes_campanas_postgres.py`, 29.
  - Ad: `test_exportacion_segura.py`, 32, que incluye el `.xlsx` de MES idéntico byte a byte salvo los textos peligrosos.
  - Vitest: `mowa-mes-campana.test.ts`, 49.
  - E2E: `mowa-mes-campana.spec.ts`, 44, y `mowa-mes-campana-orden.spec.ts`, 5.
  - A11y.
  - Re: medido el 2026-09-14, `mowa-mes.md` §13, con `scripts/medir_campana_mowa_mes.py`.
- **Decisiones vigentes:**
  - S-MM-2: superar el límite se advierte y exige confirmación, sin bloquear;
  - E-1: enviado es el estado `enviado`;
  - E-2: un documento no estándar se carga con advertencia;
  - S-MM-8: sin documento, se excluye;
  - S-MM-7: el límite se imputa al mes de envío;
  - el 409 viene estructurado;
  - hay un lock global de creación;
  - el orden de los filtros es el de la selección guardada (T-FV-F3).
- **Pendientes:** ninguno abierto. El supuesto S-MM-1 (sin API con MES, todo por archivos) sigue vigente.

### A.6 División por límites y nombre de archivo

- **Qué hace:**
  - divide la carga en archivos que respeten a la vez 50 000 registros y 2 MB reales, con la supervisión en el primero;
  - nombra cada archivo con una plantilla de texto fijo y variables: `{campana}`, `{archivo}`, `{total}`, `{cantidad}`, fechas y descripción. Agrega un sufijo automático si hay más de un archivo, y nunca repite un nombre.
- **RF:** RF-MM-11, RF-MM-12 y RF-MM-25.
- **Backend:** `plataformas/mowa_mes/division.py` (78) y `nombre_archivo.py` (167).
- **Frontend:** `lib/mowa-mes-plantilla.ts` (50) y el campo de plantilla en la configuración y en la campaña.
- **Pruebas:**
  - Nú: `test_mowa_mes_division.py`, 7, y `test_mowa_mes_nombre_archivo.py`, 46, este con pruebas de propiedad escritas a mano: dos archivos nunca repiten nombre, y el sufijo sobrevive al recorte.
  - PG: los nombres guardados con cada archivo.
- **Decisiones vigentes:** §16.1 y §16.2 de `mowa-mes.md`, aprobadas por `architec` el 2026-09-28.
- **Pendientes:** ninguno.

### A.7 Costos

- **Qué hace:**
  - el costo estimado es cargados × la tarifa vigente, y se congela al crear;
  - el costo real es enviados (E-1) × la tarifa de la campaña. Sale de la conciliación y no se guarda;
  - cada costo lleva su estado: `calculado`, `pendiente` o `no_disponible`. La pantalla decide por el estado, nunca por un `null`.
- **RF:** RF-MM-23 y RF-MM-24.
- **Backend:** `plataformas/mowa_mes/costos.py` (62) y `core/entities/mowa_mes_costo.py` (68).
- **Frontend:** las cifras de la campaña y del seguimiento.
- **Pruebas:** Nú `test_mowa_mes_costos.py`, 12; PG, el costo del mes; E2E del seguimiento.
- **Pendientes:** ninguno. Como no hay reportes importados, el costo real **nunca se vio con datos reales**.

### A.8 GSM-7

- **Qué hace:** normaliza cada mensaje al alfabeto básico de GSM-7. Translitera según una tabla fija, también los extendidos (`€` pasa a `EUR`, `[` a `(`…), y borra lo que no tiene equivalente. Mide el largo en unidades GSM-7 **antes** de aplicar los 150 y los 160. Las pantallas dicen qué se borra.
- **RF:** RF-MM-27 y RF-MM-19. S-MM-9 cerrado por el usuario el 2026-10-26.
- **Backend:** la función vive en el motor (`texto_enriquecido`: `a_gsm7`, `largo_gsm7`), y MOWA la aplica al final de cada segmento en `speech.py` y en `campana.py`.
- **Frontend:** `lib/mowa-mes-gsm7.ts` (101).
- **Pruebas:**
  - Nú: `test_mowa_mes_speech_gsm7.py`, 24; `test_texto_enriquecido_gsm7.py`, 45; `test_texto_enriquecido_gsm7_grafemas.py`, 25. Las tres tienen entradas generadas a mano.
  - Vitest: `mowa-mes-gsm7.test.ts`, 23.
  - E2E: `mowa-mes-gsm7.spec.ts`, 16.
- **Pendientes:** ninguno.

### A.9 Descripción de campaña

- **Qué hace:** la descripción es de una sola línea y de hasta 100 unidades UTF-16. Se sugiere desde los filtros, en su orden, acortada por filtros enteros. El pegado normaliza los saltos sin partir pares sustitutos y se puede deshacer con Ctrl+Z. Tiene un botón «Copiar».
- **RF:** RF-MM-04. Cierra S-MM-3 (2026-10-27).
- **Backend:** `campana.py` (`descripcion_sugerida`, `resumen_filtro`) y `una_linea`, en las entidades.
- **Frontend:** `campana.astro` y `lib/mowa-mes-campana.ts`.
- **Pruebas:**
  - Nú: `test_mowa_mes_descripcion.py`, 16, y `test_mowa_mes_descripcion_una_linea.py`, 19.
  - Vitest de la campaña.
  - E2E: `mowa-mes-campana-descripcion.spec.ts`, 40, con 360 px y axe.
  - Mu: 14 en el backend y 10 en el frontend, en C7.
- **Pendiente:** `\v`, `\f` y U+0085 pasan tal cual (`revision-c7.md` §6). Si MES los rechaza, hay que preguntarle al usuario. La mitad de par sustituto suelta (T-API-B1) ya está resuelta.

### A.10 Campos adicionales y avisos de archivados

- **Qué hace:**
  - el speech v2 lee los adicionales, y uno de texto o de número exige `primeros(n)`;
  - un adicional vacío que el mensaje usa excluye el producto con `falta_campo_adicional`, que nombra el campo;
  - el editor y la previsualización de la campaña avisan cuando el speech lee un campo archivado: desde que se archivó, las sábanas nuevas no lo traen, y esos productos quedan fuera.
- **RF:** RF-64 a RF-66 en la parte de MOWA, y D-CA-0 a D-CA-3.
- **Backend:** `speech.py`, `campana.py`, `contexto_texto.py`, `configuracion.py` y la migración `e9b3d2a7c561`, ya aplicada en `auto_cusco`.
- **Frontend:** `lib/mowa-mes-seguimiento.ts` (`detalleDeExclusion`, `listaDeCampos`, `avisoDeCamposArchivados`), las tres páginas y los componentes del motor.
- **Pruebas:**
  - Nú: `test_mowa_mes_adicionales.py`, 37, y `test_mowa_mes_archivados_campana.py`, 14.
  - API: `test_api_mowa_mes_adicionales.py`, 12.
  - Mi y SQL: `test_mowa_mes_exclusion_campos_migracion.py`, 5.
  - PG: `test_mowa_mes_exclusion_campos_postgres.py`, 3.
  - Vitest: exclusión con detalle, 9; aviso, 8; guarda i18n, 1.
  - E2E: `mowa-mes-adicionales.spec.ts`, 25.
  - Mu: 15, 5, 8 y 5 en B12, F11, B13 y F12.
- **Pendientes:** ninguno. T-MAP-F6, el espacio duro antes de «›», entró en `c453f7e`.

### A.11 Seguimiento: reporte de enviados, conciliación y límite mensual

- **Qué hace:**
  - importa el reporte «Campañas de enviados» de MES en `.xlsx`, con columnas fijas;
  - lo asocia a una campaña por su id de MES y concilia las cargadas contra el reporte: cargados, enviados, no enviados, filas sin correspondencia y conteo por estado;
  - muestra el consumo del límite y el costo del mes.
- **RF:** RF-MM-20 a RF-MM-22, RF-MM-01 y RF-MM-02.
- **Backend:**
  - del módulo: `plataformas/mowa_mes/reportes.py` (84), `conciliacion.py` (107) y `core/entities/mowa_mes_reporte.py` (94, con `COLUMNAS_REPORTE`);
  - lector: `adapters/input/lector_reporte_mowa_mes.py` (111), con python-calamine y un tope de 32 MB;
  - API: `api/mowa_mes_campanas.py` (el reporte, la conciliación y `/limite-mensual`).
- **Frontend:** `pages/mowa-mes/seguimiento.astro` (1116) y `lib/mowa-mes-seguimiento.ts` (153).
- **Pruebas:**
  - Ad: `test_lector_reporte_mowa_mes.py`, 8, con archivos en memoria.
  - Nú: `test_mowa_mes_conciliacion.py`, 17.
  - API: `test_api_mowa_mes_conciliacion_v2.py`, 2.
  - PG: `test_mowa_mes_conciliacion_v2_postgres.py`, 2.
  - Vitest: `mowa-mes-seguimiento.test.ts`, 11.
  - E2E: `mowa-mes-seguimiento.spec.ts`, 22.
  - A11y.
- **Pendientes:** el tope de 32 MB del reporte (`revision-c4.md` §6). Y lo principal: **la parte nunca se usó** (0 reportes), así que el formato real del reporte de MES no se probó nunca contra el lector.

---

## B. Mejoras y agregados

**Puntaje** (fórmula de `engineering:tech-debt`): (Impacto + Riesgo) × (6 − Esfuerzo), cada uno de 1 a 5. El máximo es 50. **❓** marca lo que necesita una decisión del usuario o una regla de MES que no está en `requerimientos-mowa-mes.md`: va como pregunta, no se inventa.

**Hipótesis de por qué no se usó el seguimiento.** Ninguna está comprobada:
- (h1) las 2 campañas fueron de prueba y nunca se subieron a MES;
- (h2) el reporte que descarga MES no coincide con el formato que espera el lector (columnas, nombre u orden, `.xls` o `.csv`), y la importación falla;
- (h3) nada lleva de la campaña creada a su seguimiento, y la importación es un paso que se olvida;
- (h4) asociar el reporte exige el id de MES, que el operador tiene que copiar de la web de MES, y no está claro dónde encontrarlo.

### B.1 Defectos o riesgos

| # | Mejora | I | R | E | Puntaje | ❓ |
|---|---|---|---|---|---|---|
| D-1 | **Validar el lector con el reporte real de MES.** Hoy exige las columnas de `COLUMNAS_REPORTE` con su nombre exacto y solo acepta `.xlsx`, y nunca se probó con un archivo real. Pedirle al usuario **solo la fila de cabecera** de un reporte real, sin datos, más el formato del archivo. Con eso, una prueba de adaptador con esa cabecera, replicada con datos sintéticos. Si no coincide, aplicar C (mapeador de encabezados) | 4 | 4 | 2 | **32** | ❓ cabecera y formato reales |
| D-2 | **El tope de 32 MB del reporte.** No se sabe cuánto pesa un reporte mensual real. Si lo supera, la importación falla con un 413 | 2 | 2 | 1 | **20** | ❓ tamaño típico |
| D-3 | **`\v`, `\f` y U+0085 en la descripción.** Pasan tal cual al campo de MES | 1 | 2 | 1 | **15** | ❓ si MES los rechaza |
| D-4 | **Los textos de `mensaje_excede_150` y `mensaje_excede_160`** llevan los números escritos, mientras los límites son constantes del código (`LARGO_ADVERTENCIA` y `LARGO_MAXIMO`, `entities/mowa_mes.py:29-30`). Si cambia la constante, el texto miente. Que el número salga del valor | 1 | 1 | 1 | **10** | |

### B.2 Pulido de experiencia

| # | Mejora | I | R | E | Puntaje | ❓ |
|---|---|---|---|---|---|---|
| P-1 | **Al crear la campaña, la lista de lo que hay que hacer en MES**: los archivos para subir y cada input listo para copiar (tipo de carga, salida, herramientas, programación y descripción, que ya tiene «Copiar»). Ataca (h1) y (h3) | 3 | 2 | 2 | **20** | |
| P-2 | **En el seguimiento, las campañas sin reporte importado a la vista**, con «Pendiente del reporte» y el paso siguiente («Importa el reporte de enviados de MES»), y un enlace desde la campaña creada. Ataca (h3) | 3 | 2 | 2 | **20** | |
| P-3 | **Explicar dónde está el id de MES al importar el reporte**, con un hint y un ejemplo sintético. Ataca (h4) | 2 | 2 | 1 | **20** | ❓ cómo se ve en la web de MES |
| P-4 | **Editar los filtros desde la campaña.** Hoy el selector es compacto: para cambiar un filtro hay que ir a Cartera, guardar la selección y volver | 3 | 1 | 3 | **12** | ❓ decisión de producto |
| P-5 | **Partir `configuracion.astro`** (2117 líneas: configuración, supervisores, calendario y speech v1/v2) en componentes por bloque. Lo mismo, en menor medida, `campana.astro` (1620). Es mantenibilidad más que algo que se vea. Ver C | 2 | 2 | 3 | **12** | |

### B.3 Huecos contra los RF

La trazabilidad de C2 a C8 no deja ningún RF del módulo sin implementación. Los huecos son de **validación con datos reales** y de extensibilidad:

| # | Hueco | I | R | E | Puntaje | ❓ |
|---|---|---|---|---|---|---|
| H-1 | **RF-MM-02, RF-MM-21 y RF-MM-22, sin validar de punta a punta con MES.** Cargados frente a enviados, la asociación y la conciliación están probadas con reportes sintéticos que siguen el formato del RF, no el de un archivo real. Se cierra junto con D-1, y no suma puntaje aparte | — | — | — | (D-1) | ❓ |
| H-2 | **RF-31: un segundo conector hoy copiaría código.** Ver el cierre de C | 3 | 2 | 3 | **15** | |
| H-3 | **RF-57 no alcanza al reporte de enviados:** sin hoja a elegir, sin `.xlsb` ni `.csv`. RF-MM-20 dice `.xlsx`, así que hoy cumple, pero es frágil si MES cambia. Ver C y D-1 | 2 | 3 | 2 | **20** | ❓ formato real |

### B.4 Funciones nuevas

| # | Función | I | R | E | Puntaje | ❓ |
|---|---|---|---|---|---|---|
| N-1 | **Repetir una campaña:** los mismos inputs, otra fecha de corte o de envío | 3 | 1 | 2 | **16** | ❓ si se quiere |
| N-2 | **Resumen mensual:** consumo, costo estimado y real, y campañas por mes, con el mes anterior al lado | 2 | 1 | 2 | **12** | ❓ si se quiere |
| N-3 | **Segundo conector (WhatsApp, RF-10) sobre lo común**, después de las extracciones de C | 4 | 2 | 4 | **12** | ❓ prioridad frente a la Fase 5 |
| N-4 | **Integración por API con MES** (S-MM-1): subir los archivos y traer el reporte sin pasos manuales. Eliminaría (h1) a (h4) | 4 | 3 | 5 | **7** | ❓ si MES ofrece API |

**Las 5 de mayor puntaje:**
1. D-1, validar el lector con el reporte real (32);
2. P-1, la lista para MES al crear (20);
3. P-2, las pendientes de reporte a la vista (20);
4. P-3, dónde está el id de MES (20);
5. H-3 y D-2, empatados a 20: formatos y tope del reporte.

Las tres primeras atacan lo único que el uso real muestra: el seguimiento no se usó.

---

## C. Evaluación del código que solo existe dentro del módulo

**Cómo se hizo:**
- Cada dev leyó su lado en solo lectura sobre `bbba3a1`; los dos usaron grep y leyeron los bloques repetidos.
- Yo comprobé en el código las afirmaciones que más pesan:
  - el enlace de WhatsApp duplicado;
  - la apertura de Calamine copiada;
  - `normalizar_nombre` repetido tres veces;
  - la copia literal de `textoDeCodigo`;
  - `modules.md:67`.
- **Escala de costo:** 1 son horas, 2 alrededor de un día, 3 dos o tres días, 4 una semana y 5 más.
- **Límites:**
  - Las «copias idénticas» se contaron con grep, sin `diff`. Algunas tienen variantes de una línea, como `avisar` y `celda`.
  - Las páginas se leyeron por secciones, no línea por línea.
  - `api/mowa_mes*.py` se leyó solo en su estructura.

**Qué ya se reutiliza bien, sin copiar:**
- **Backend:**
  - el motor de texto: compilar, `a_gsm7`, `largo_gsm7` y la medida y la salida del contexto;
  - el exportador XLSX con la protección contra fórmulas (RF-53);
  - supervisión (`services/gestiones_digitales/`);
  - la segmentación del núcleo (`services/segmentacion.py`, RF-50);
  - la selección y los filtros de la cartera;
  - el calendario.
- **Frontend:**
  - `request`, `ApiError` y `NetworkError` de `lib/api.ts`;
  - `descargarArchivo`, `format.ts` e `i18n.ts`;
  - `SelectorSeleccion` en modo compacto;
  - `montarVariantes` y `montarEditor` del motor;
  - los tokens.

**El editor del speech no tiene armado propio:** lo de MOWA son 149 líneas de adaptación de datos (`lib/mowa-mes-speech-v2.ts`).

### C.1 Tabla

| Pieza de MOWA | Equivalente general | ¿Duplica? Evidencia | ¿2.º conector? | Recomendación | Costo y riesgo |
|---|---|---|---|---|---|
| **Lector del reporte**: `adapters/input/lector_reporte_mowa_mes.py:66-78` (apertura con Calamine, solo la primera hoja, sin mirar el formato) | `LectorTablaPort`. `lector_calamine.py:52-70` abre igual; `core/services/lectura_tabla.py:32-90` despacha por extensión y firma (xlsx, xlsb, xls, ods, csv, tsv, json); `entities/lectura_tabla.py:17-96` trae `OpcionesLectura` (RF-57) | **Sí**: unas 20 líneas calcadas. Le faltan `.xlsb`, `.csv`, la hoja a elegir y las advertencias de lectura | Sí: WhatsApp y VoIP también traen reportes | **Reusar la general.** El lector de MES solo aplica encima sus 8 columnas y `_dni`, `_fecha` y `_mes_id`. El puerto propio (`core/ports/lector_reporte_port.py:8`) pasa a recibir el nombre del archivo | 2, riesgo medio-bajo: cambia la firma del puerto, y las pruebas del lector tienen que seguir verdes sin tocarlas |
| **Columnas fijas del reporte**: `entities/mowa_mes_reporte.py:9-18` (`COLUMNAS_REPORTE`) y `_normalizar_cabecera`, en `lector_reporte_mowa_mes.py:24-26` | El mapeador de encabezados (RF-60): `mapeador/similitud.py:29-32` (`normalizar_cabecera`), alias, similitud y mapeo del usuario | **La normalización sí**: es la tercera variante de la misma función. **El mapeador completo no hace falta hoy**: las columnas de MES son un contrato del proveedor | La normalización sí. El mapeador, solo si el reporte del proveedor cambia de columnas | **Reusar `normalizar_cabecera`**, que es una línea. **Dejar** la exigencia exacta: un mapeador abierto podría confundir `estado` con otra columna. Si D-1 muestra que el reporte real difiere, se revisa | 1, riesgo bajo: NFD con `lower` contra NFKD con `casefold` difieren en casos raros. El mapeador completo costaría 4, y no lo recomiendo |
| **División por límites**: `plataformas/mowa_mes/division.py` (78 líneas: por filas y por bytes reales, recursiva) | No hay | No duplica, pero **el algoritmo no es de MES**: partir una carga con tope de filas y de bytes sirve para cualquier plataforma | Sí | **Extraer a común** como `dividir(filas, escribir, max_filas, max_bytes)`. Los números y los tipos quedan en MOWA | 2, riesgo bajo: la lógica no cambia, y las mutaciones de la división tienen que seguir muertas |
| **Plantilla del nombre de archivo**: `plataformas/mowa_mes/nombre_archivo.py` (167 líneas; regex `{x}` en `:43` y su propio saneador en `:44`). En el frontend, `lib/mowa-mes-plantilla.ts` e `insertarVariable` (`mowa-mes.ts:336-370`) | El motor usa `[@x]` y expresiones; el saneador está en `exportadores/comunes.py:20-51`. El `insertarVariable` del motor es otra cosa con el mismo nombre | **En parte**: es un segundo motor de plantillas con otra sintaxis, y un tercer saneador de nombres | Sí: todo conector que genere archivos numerados | **Extraer a común** «plantilla de nombre con variables cerradas, saneado y partes». MOWA solo declara sus variables y su extensión. En el frontend, renombrar a `insertarMarcador` | 3 (2 si se deja `{x}`), riesgo medio: hay plantillas guardadas en la base y el contrato describe la sintaxis |
| **`resumen_filtro`**: `campana.py:138-166` | No hay | No duplica | Sí: cualquier descripción automática a partir de los filtros | **Extraer** `resumen_filtro` a `seleccion_cartera`, porque es del filtro. **Dejar** `descripcion_sugerida` y su límite de 100 | 2, riesgo bajo: las frases tienen pruebas |
| **`enlace_whatsapp`**: `speech.py:139-140`, sin validar | `texto_enriquecido/funciones/enlaces.py:11-15`, que valida el número | **Sí**: dos constructores del mismo enlace. Además, el motor importa `gestiones_digitales.supervision`, una dependencia al revés | Sí (RF-10) | **Reusar el del motor** y mover `numero_valido` a un módulo común | 1-2, riesgo bajo: con un número inválido, el motor rechaza. El número ya se valida al guardar la configuración |
| **Archivo de carga**: `adapters/output/plataformas/mowa_mes/archivo_carga.py:7-20` | `exportador_xlsx` y `ExportadorTablaPort` | **No**: son 20 líneas sobre el exportador. Es el mejor ejemplo de reuso del módulo | — | **Dejar.** Opcional: recibir el exportador por el puerto, para poder probarlo con un doble | 1, sin riesgo |
| **GSM-7**: vive en el motor (`texto_enriquecido/gsm7.py`). En el frontend, `lib/mowa-mes-gsm7.ts` (101 líneas) y los niveles de 150 y 160 (`mowa-mes.ts:59-82`, claves `mowaMes.speech.nivel.*`) | Es el equivalente general | No duplica. **No es una regla de MES, sino de cualquier SMS.** WhatsApp no la usa, y VoIP no tiene texto | Otro SMS sí | **Dejar en el backend.** En el frontend, extraer con claves neutras **cuando exista el segundo SMS**. `conciliacion.normalizar_mensaje` (`conciliacion.py:36-39`) repite el primer paso: que lo importe | 2 (frontend) y 1 (conciliación), riesgo bajo |
| **Segmentos y calendario**: `plataformas/mowa_mes/segmentos.py` (38 líneas, una fachada) | `services/segmentacion.py` y `services/calendario/` | **No** en lo esencial. Queda un resto: `fecha_en_lima` (`campana.py:194`) contra `fecha_envio.hoy_en_lima` | Sí, y ya se reusa | **Dejar.** Mover `fecha_en_lima` si se toca | 1 |
| **Supervisores y calendario en la pantalla**: `configuracion.astro:837-1166` (unas 330 líneas) y `:1825-2053` (unas 230), más `mowa-mes.ts:164-282` y `api-mowa-mes.ts:105-112` y `:142-151` | `modules.md:67`: un conector siguiente «reutiliza calendario y supervisión». Sus rutas (`/supervisores` y `/calendario/*`) no cuelgan de `/mowa-mes` | **No duplica, pero está en el lugar equivocado**: lo común vive en la pantalla que dice «MOWA MES» | **Sí, seguro** (RF-37 a RF-41 y RF-MM-08) | **Extraer a una pantalla común**, por ejemplo `/configuracion/supervision` y `/configuracion/calendario`. Es lo que primero necesitaría cualquier conector | 4-5, riesgo medio: mueve rutas, navegación, specs y docs |
| **Costos y tarifa**: `plataformas/mowa_mes/costos.py` y `entities/mowa_mes_costo.py`, más las columnas de `MowaMesConfiguracion` (`modelos.py:451`) | No hay | No duplica | Otro SMS sí. VoIP cobra por minuto | **Dejar.** Extraer la aritmética (`cantidad × tarifa`, `texto_decimal`) cuando exista el segundo SMS | 2, riesgo bajo |
| **Catálogos de códigos y espejo i18n**: `CodigoMowaMes`/`TIPO_CODIGO` (`entities/mowa_mes.py:82-127`) y `test_codigos_mowa_mes.py`. En el frontend, `traducirCodigo` (`mowa-mes.ts:115`) | `CodigoTexto`, `CodigoMapeo`, `CODIGOS_INCIDENCIA` con sus espejos. En el frontend, `textoDeCodigo` (`generar-carga-mensajes.ts:28`), del que `textoDeCodigoDelMotor` (`mowa-mes-speech-v2.ts:99`) es **copia literal** | **Sí, el patrón**: «enum + clave por código + prueba espejo» está hecho 3 o 4 veces, cada una recorriendo el JSON a su modo | Sí: cada conector trae su catálogo | **Extraer** un ayudante de prueba (`tests/ayudas/espejo_i18n.py`) y, en el frontend, `traducirPorPrefijo(prefijo, codigo, respaldo)`. Borrar `textoDeCodigoDelMotor`. Los enums quedan separados | 2 (backend) y 1 (frontend), riesgo bajo: solo pruebas y una función. Las pruebas de oro no se tocan |
| **Copias chicas del backend**: `normalizar_nombre` ×3 (`entities/definiciones_columnas.py:24`, `repositorio_selecciones_postgres.py:26`, `repositorio_mowa_mes_postgres.py:32`) y `_vacio`/`vacia` ×4 (`campana.py:199`, `segmentacion.py`, `lector_reporte_mowa_mes.py:29`, `adapters/input/celdas.py:7`) | Ninguna tiene hogar común | **Sí**: 7 copias | Sí | **Extraer:** `core/entities/nombres.py` y una `vacia` en el núcleo, que el adaptador reexporta | 1 cada una, riesgo bajo |
| **Helpers de DOM del frontend**: `mensajeDeError` ×5 (`campana.astro:522`, `configuracion.astro:580`, `seguimiento.astro:305`, `columnas.astro:574`, `selector-seleccion.ts:810`), `ocupado` ×4, `$` ×6, `conJson` ×6 (`api-mowa-mes.ts:70`, `api-definiciones.ts:23`, `api-mapeador.ts:21`…), `paginar` (`mowa-mes.ts:284-322`, genérico) y `appendBreakable` (copia declarada de `cargas.astro:945`) | No hay | **Sí**: unas 200 líneas copiadas entre MOWA y el resto del sitio | Sí | **Extraer a `lib/`.** Lo de MOWA es solo una parte: estas copias ya existen entre las pantallas generales | 1-2, riesgo bajo |
| **Paginador y tablas del frontend**: `pintarPaginador` (`campana.astro:956`, `seguimiento.astro:439`) contra los de `cartera.astro:671` y `cargas.astro:919`; `tabla`, `celda`, `vacio` y `cifra` | `.table`, `.empty` y `.stat` de `ui.css` | **Sí**: 4 implementaciones del mismo «desde–hasta de total», con atributos distintos | Sí | **Extraer** a `lib/tabla-dom.ts` y unificar los atributos | 3-4, riesgo medio: toca 4 pantallas y 4 specs |
| **Cáscara de página en CSS**: `.mm`, `.mm__head`, `.mm__title`, `.mm__intro` y `.mm__grid` (`mowa-mes.css:9-60`), contra `console.css:9`, `cartera.css:8-47`, `generar-carga.css:8` y `columnas.css:20`. Además `.stat__value.muted` (`mowa-mes.css:565`) redefine una clase de `ui.css:486` | `ui.css` | **Sí**: 4 o 5 copias idénticas. La de `.stat__value` es una fuga: un estilo global declarado en el módulo | Sí | **Extraer** una clase de página a `ui.css`, decisión de `designer`. Mover `.stat__value.muted` | 3 (cáscara, riesgo medio por axe y visual) y 1 (fuga) |
| **API falsas de e2e**: `json` ×13, `siguiente` ×4 y `montarSeleccion` ×4 | `e2e/api-falsa.ts` | **Sí** | Sí | **Extraer** a `e2e/apoyo.ts` | 1, riesgo bajo: solo pruebas |
| **Persistencia de campañas**: siete tablas `MowaMes*` (`modelos.py:529-678`) y `repositorio_campanas_mowa_mes_postgres.py` (474 líneas, inserción por lotes) | No hay. El repositorio de cargas inserta todo de una vez | No duplica hoy, pero otro SMS copiaría siete tablas idénticas con otro nombre | Sí: campaña, archivo, filas, exclusiones y reporte son conceptos de cualquier canal | **Dejar las tablas** hasta que exista el segundo caso. Entonces, una columna `plataforma` en vez de copiar tablas. Extraer ya el ayudante `insertar_por_lotes` | 1 (ayudante) y 5 (tablas), riesgo alto en lo segundo: datos de cobranza y migración |
| **Versiones de speech**: `MowaMesSpeechVersion` (`modelos.py:489-527`) y `repositorio_mowa_mes_postgres.py` | `DefinicionCargaGuardada/Version` y `repositorio_definiciones_postgres.py`: «versiones con nombre, únicas, inmutables una vez usadas» | **El patrón, dos veces** | Sí | **Dejar** hasta el segundo caso: unificar hoy sería adivinar la forma. Las semánticas difieren, por ejemplo en `basada_en_id` | 4, riesgo medio-alto |
| **Conciliación y API**: `conciliacion.py`, `reportes.py`, `api/mowa_mes.py` (775 líneas) y `api/mowa_mes_campanas.py` (1054) | `api/respuestas.py` y `api/errores.py` ya son compartidos | No duplica. La clave número+DNI+mensaje y los estados son de MES | Cada conector trae los suyos | **Dejar.** Una tabla común de «excepción → HTTP» sería prematura con un solo conector | — |
| **Selección en la campaña**: el cableado de `EVENTO_SELECCION` (`campana.astro:1556-1584`) y `seleccionUsable` (`campana.astro:632`) | El mismo cableado en `columnas.astro` y en `scripts/generar-carga.ts:835-872`; `motivoInactivo` está en `lib/generar-carga.ts` | Unas 30 líneas en 3 pantallas, y la misma lógica con otros textos | Sí | **Dejar** el componente. Extraer el cableado y el motivo, sin el texto, si se toca una cuarta vez | 2, riesgo bajo-medio |

### C.2 Las extracciones más rentables

Ordenadas por beneficio sobre costo, con el riesgo bajo primero:

1. **El lector del reporte sobre `LectorTablaPort`** (costo 2). Gana `.csv`, `.xlsb`, la hoja a elegir y las advertencias de RF-57, y borra 20 líneas calcadas. Va de la mano de D-1, la mejora de mayor puntaje: si el reporte real de MES viene en otro formato, ya se lee.
2. **La limpieza barata de copias que ya existen**, sin esperar a RF-31:
   - en el backend, `normalizar_nombre`, `vacia`, `normalizar_cabecera` y `enlace_whatsapp` (unos 2 días);
   - en el frontend, `mensajeDeError`, `ocupado`, `$`, `conJson`, `paginar`, `traducirPorPrefijo` y el apoyo de e2e (3 o 4 días).
   El riesgo es bajo, y quita duplicados que hoy comparten MOWA y las pantallas generales.
3. **`division.py` a común** (costo 2). El algoritmo ya es genérico, solo está tipado a MOWA, y lo necesita cualquier conector que genere archivos con topes.

**Después, cuando se decida un segundo conector:**
- supervisores y calendario en una pantalla común (4-5), que es lo primero que necesitaría;
- la plantilla del nombre de archivo (3);
- el paginador, las tablas y la cáscara de CSS (3-4, con `designer`).

**No tocar hasta tener el segundo caso real:** las tablas de campañas, las versiones de speech, la conciliación y los routers.

### C.3 La prueba de RF-31: qué tendría que copiar o tocar hoy un segundo conector

**Nada del módulo está parametrizado por conector.** Un segundo SMS copiaría hoy:
- **Backend** (unas 5800 líneas):
  - las cuatro entidades `mowa_mes*` (unas 855 líneas) y los dos puertos;
  - todo `plataformas/mowa_mes/` (unas 2150 líneas);
  - el lector y el archivo de carga;
  - los dos repositorios (688 líneas) y siete tablas con su migración;
  - los dos routers (1829 líneas);
  - el registro de su contexto en `api/texto_enriquecido.py:75`;
  - el contrato y las pruebas espejo.
- **Frontend** (unas 6300 líneas, más los specs):
  - las tres páginas (4853 líneas);
  - la capa `lib` y la API (1462);
  - el CSS (619);
  - unas 386 claves por idioma;
  - las API falsas (unas 1580 líneas) y unas 6000 líneas de specs.
- **Supervisores y calendario no tendrían dónde vivir,** salvo enlazar a la pantalla «MOWA MES».

**Estimación honesta, en días de agente con verificación completa y turnos de máquina.** Son órdenes de magnitud, del ±50 %. Salen de las líneas y de lo que costaron los cortes anteriores, no de una medición.

| Camino | Backend | Frontend | Total |
|---|---|---|---|
| **Copiar y adaptar hoy** un segundo SMS | 6-9 | 13-16 | **≈ 19-25** |
| **Extraer primero** lo de C.2 y lo de «cuando se decida un segundo conector» | unos 8 de extracción, y después 3-5 para el conector | unos 9-10 de extracción, y después 6-8 para el conector | **unos 17-18 antes, más 9-13 por conector** |
| **WhatsApp** (RF-10): no tiene GSM-7 ni el tope de 160, tiene plantillas aprobadas y otros estados | 8-12, o 5-8 con las extracciones | parecido al SMS, menos GSM-7 | **un poco más que otro SMS** |

**Lectura:**
- Con **un solo** conector más, copiar y extraer cuestan parecido, pero copiar deja dos copias que mantener.
- La extracción se paga **desde el segundo conector adicional**, por ejemplo WhatsApp y VoIP.
- **Mi recomendación:** hacer ahora solo C.2, la limpieza barata más el lector y la división: unos 8-10 días, con riesgo bajo, y valen aunque no llegue ningún conector. Dejar lo demás para cuando el usuario decida cuál es el segundo conector.
- Esa decisión es del usuario ❓, igual que las reglas de la plataforma nueva (formato de carga, reporte y topes), que se levantan con él y no se inventan.
