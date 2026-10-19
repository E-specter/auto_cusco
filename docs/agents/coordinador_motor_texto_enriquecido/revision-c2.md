# Revisión integral del motor de texto enriquecido (T-MTE-C2)

Cerrada el 2026-10-19, sobre `main` en `e0d2b47`. Están en `main` B1 a B12, F1 a F5, los cambios de designer y el corte final de F3 (`e0d2b47`: la muestra por segmento, sin los arreglos provisorios y con la espera de axe). **RF-42 a RF-54: cumplidos.** Queda una mejora en curso, aprobada por el usuario (§2, punto 8).

## 1. Trazabilidad RF → implementación → pruebas

| RF | Qué pide | Dónde quedó | Pruebas principales | Estado |
|---|---|---|---|---|
| RF-42 | Texto fijo, variables y funciones; `[@campo]` sigue igual | B1 (`bbe8570`): sintaxis, evaluador y escape `[@@]`. B2 (`2f0b3b3`): `GeneradorCargas` evalúa con el motor | `test_texto_enriquecido_sintaxis`, `_compatibilidad` (las plantillas de RF-12 dan el mismo texto), `_propiedades`, paridad de B2 en `test_generador_columnas` | Cumplido |
| RF-43 | Variables de la cartera y de contexto, con tipo (incluido booleano) | B1 (tipos, D2) y B4a (`c25801e`): contextos `cartera` y `mowa_mes.speech`, con `origen` | `test_contextos_texto`, `test_texto_enriquecido_catalogo`, prueba de arquitectura (el núcleo no importa plataformas) | Cumplido. El contexto de MOWA MES aporta `whatsapp_contacto` y `dias_atraso_ajustados`; no aporta todavía `fecha_envio` ni `segmento_calculado`, que la lista de RF-43 da como ejemplos no exhaustivos |
| RF-44 | Catálogo mínimo; funciones nuevas sin tocar el núcleo | B1: 23 funciones en `funciones/` con registro | `test_texto_enriquecido_funciones`, `_cota`, `_evaluador`; mutación en B1 | Cumplido. Cómo agregar una función: diseño §16 |
| RF-45 | Vacíos, obligatoria, valor por defecto | B1 (vacíos y obligatoria), B2 (valor por defecto de la columna), B6 (obligatoria en MOWA MES) | `test_texto_enriquecido_evaluador`, `test_generador_columnas`, `test_mowa_mes_speech_v2` | Cumplido |
| RF-46 | Validación al guardar, con ubicación | B4a (validación con ubicación), B4b (`01e11c5`: 400 con problemas ubicados al guardar), B9 (`9fbd47a`: códigos como enum) | `test_api_texto_enriquecido`, `test_api_definiciones_columnas`, `test_contrato_codigo_texto`, prueba espejo i18n | Cumplido. La validación en vivo responde 200 con problemas (decisión de B4a); guardar, 400 |
| RF-47 | Previsualización con ejemplo o producto real, y largo máximo | B4a (ejemplo, ejemplos por segmento, producto real, cota), B4b (primeros N de una selección), F2 y F3 (interfaz) | `test_previsualizar_texto`, `test_api_texto_enriquecido_seleccion`, `editor-texto.spec`, `columnas.spec` | Cumplido. B11 (`8eef33d`) trae el pagaré y la fecha de corte por fila, y el corte chico de F3 usa como muestra un producto del segmento elegido. Límite: si ninguno de los 5 productos de la muestra cae en ese segmento, se usa el primero y se avisa |
| RF-48 | Declarativo, sin `eval`, con límites | B1 (registro cerrado y límites), B4a y B4b (límites expuestos en el catálogo) | `test_texto_enriquecido_arquitectura`, la prueba de entrada maliciosa con tope de tiempo y la de que no se compilan regex por fila | Cumplido |
| RF-49 | Constructor de N columnas | B2 (entidades y generador), F3 (`12f0c89`: `/columnas`) | `test_generador_columnas`, `columnas.spec` (44), `constructor-*.test` | Cumplido. La generación desde la interfaz la agregó F5 (`f023129`, `/generar-carga`) |
| RF-50 | Segmentación calculada por defecto, por campo y política sin segmento | B2 (núcleo de segmentación y tabla de rangos única), F3 | `test_segmentacion`, `test_mowa_mes_rangos_nucleo`, `columnas.spec` | Cumplido |
| RF-51 | Definiciones guardadas, compartidas y versionadas | B4b, F3 | `test_definiciones_columnas_servicio`, `_postgres` (18), `columnas.spec` | Cumplido. Ninguna versión se modifica (decisión de B4b). Pendiente de producto: renombrar una definición |
| RF-52 | Exportación independiente de la definición | Exportadores existentes; B4b (`/archivos-carga` con `definicion_guardada`); B12 (`ad56a11`: exclusiones por segmento y opciones de cada formato); F5 (pantalla «Generar carga») | `test_api_archivos_carga_guardadas`, `test_api_archivos_carga`, `generar-carga.spec` | Cumplido |
| RF-53 | Protección contra fórmulas | B3 (`0772e78`), B10 (`98b4311`), `proteger_formulas` en la definición (B4b) y en `/columnas` | `test_exportacion_segura` (con zlib y zlib-ng) | Cumplido |
| RF-54 | Sin cambios en las cargas actuales | Pruebas de compatibilidad de B1 y paridad de B2 (SHA-256 congelado); oro de MOWA MES en B5, B6 y B8 | `test_texto_enriquecido_compatibilidad`, `test_generador_columnas`, `test_mowa_mes_speech_oro` | Cumplido, con las dos excepciones de seguridad de RF-53 documentadas |

## 2. Hallazgos

1. **No había pantalla para generar una carga.** Ningún archivo del frontend llamaba a `/archivos-carga`. Lo encontró esta revisión el 2026-10-15, y el usuario decidió hacerla dentro del motor: B12 (exclusiones por segmento y opciones de formato) y F5 (`/generar-carga`). **Cerrado.**
2. **Muestra de cartera real por segmento.** Cerrado con B11 (`8eef33d`) y el corte final de F3 (`e0d2b47`). Mejora posible, no pedida: pedir la muestra de un segmento concreto, para cubrirlo aunque ninguno de los 5 productos caiga en él.
3. **Cambios de designer.** Los aprobó el usuario el 2026-10-17 y están en `main`: `53ce1bb`, `206534d`, `8a612a5` y `e2e0084`. **Cerrado.**
4. **Límites conocidos de `/archivos-carga`** (B12, documentados): cancelar una descarga no corta el trabajo del servidor, y `usada_en` puede quedar marcado sin entrega.
5. **Pendientes del usuario desde el diseño (§14):** tabla de rangos por defecto, codificación SMS GSM-7/UCS-2 y días ajustados fuera de MOWA MES. Siguen abiertos; ninguno bloqueó.
6. **Pendiente de producto:** renombrar una definición guardada.
7. **Decisión del usuario del 2026-10-17:** se mantienen los nombres «Cargas» y «Generar carga»; la intro de `/generar-carga` los distingue.
8. **Mejora de accesibilidad en curso (designer), aprobada por el usuario el 2026-10-19:** `fijarNotaMuestra` en `EditorTexto`, para que la nota «ningún producto de la muestra cae en el segmento» quede bajo la vista previa del editor y se anuncie. Hoy, a 1440 px, sale lejos de lo que explica y no se anuncia. Entró en `c64764d`; falta el ajuste mínimo de dev_frontend en `/columnas` para usarla.

## 3. Lecciones del proceso

- Los fallos con base de datos aparecieron solo en la verificación de architec (B4b, B6). Para los cortes que tocan persistencia: compilar con el dialecto de PostgreSQL las sentencias con columnas nulas o JSON.
- Un valor congelado que dependía de la compresión rompió `main` según la versión de Python (B10). Python 3.13 quedó fijado en `backend/.python-version`.
- La revisión de consumidores antes del commit (designer y dev_frontend sobre los contratos) evitó retrabajo en B4a, B4b, B6, F2b y F3.
- Un valor de un catálogo escrito a mano en una prueba pasaba sin que nadie lo notara (`sin_cota`, en MOWA MES): el contrato con enums (B9) lo atrapó. `astro check` no veía asignaciones con tipos anidados: se sumó `tsc --noEmit` a `verificar`.
- Las entregas pasan por el coordinador, y los cortes que tocan MOWA MES, por su coordinador (plan §13). Dos cortes que se saltaron ese circuito se revisaron después del commit.

## 4. Commits del motor

`61647cd` (diseño), `4e7ccc1` (plan C1), `bbe8570` (B1), `527b0e9` (B5), `0772e78` (B3), `b8b9025` (B7), `2f0b3b3` (B2), `c25801e` (B4a), `01e11c5` (B4b), `ee328b0` (B6), `09ba161` (B8), `9fbd47a` (B9), `98b4311` (B10), `2390adc` (Python 3.13), `ad56a11` (B12), `8eef33d` (B11). Frontend: `5ffeddf` y `e207c46` (estado del editor), `d2abbbc` (`tsc` en la verificación), `49b788b` (F2a), `0a1aacb` (F2b), `12f0c89` (F3), `ba9de60` (F4), `53ce1bb`, `206534d` y `8a612a5` (designer), `f023129` (F5), `e2e0084` (navegación de «Generar carga») y `e0d2b47` (cierre de F3). Todos sin push al cerrar esta revisión.
