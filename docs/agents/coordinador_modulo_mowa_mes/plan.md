# Plan de ejecución del módulo `mowa_mes` (T-MM-C1)

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Fecha: 2026-09-13.

Fuentes: `docs/requerimientos-mowa-mes.md` (RF-MM-01 a RF-MM-22), `docs/atomics-requirements.md` §10 (RF-37 a RF-41), `docs/modules.md` §5.1, `docs/architecture.md`, `backend/AGENTS.md`, `frontend/AGENTS.md`, `docs/testing.md`, `docs/contrato-api.md`.

## 1. Diseño de `modules.md` §5.1: confirmado, con estas precisiones

La tabla de piezas de §5.1 se mantiene. Lo que sigue la baja a decisiones concretas dentro del módulo. Nada cambia requerimientos ni contratos compartidos. Lo que sí toca un módulo existente está en la sección 4 (consultas).

### 1.1 Selección (RF-MM-09)

- La base de la campaña es `fecha_corte` + `filtros` + `orden` + `cantidad`, con la misma sintaxis de `/cartera`. Opcionalmente trae `seleccion_id` si vino de una selección guardada. La campaña guarda **la copia** de filtros, orden y cantidad con la que se generó, no solo la referencia, porque la selección guardada puede cambiar.
- Los productos se leen con `ConsultaCarteraService`, por páginas y con el mismo orden y desempate por pagaré que `/cartera`, `/cartera/resumen` y `/archivos-carga`. No se escribe una consulta propia. El recorrido paginado ya existe como `_SeleccionPaginada` en `generacion_cargas/servicio.py` (ver consulta C-2).

### 1.2 Speech sobre el motor de mapeo (RF-MM-14 a RF-MM-19)

- **Días ajustados y segmento:** en el núcleo del conector (`plataformas/mowa_mes/`). `dias_ajustados = dias_atraso + (fecha_envio - fecha_corte).days`. Los rangos de los segmentos son datos de la versión de speech por defecto, no `if` sueltos. S-MM-5 y S-MM-6 se implementan tal como están.
- **Mensaje:** se construye con `GeneradorCargas` (RF-12), que ya recibe el catálogo de campos como parámetro. El conector le pasa un **contexto de fila derivado** con campos propios (`titular_8`, la fecha de vencimiento en `dd/mm/yyyy` y `whatsapp`), y la plantilla del segmento queda `[@titular_8]` + parte 1 + `[@vencimiento]` + parte 2. El motor de mapeo **no se modifica**.
- `[whatsapp]` se reemplaza por `https://wa.me/+51<número de la campaña>` antes de compilar. Al guardar una versión se valida que sus partes no contengan `[@`, para que el texto del usuario no se interprete como referencia.
- **WhatsApp sin configurar** (ajuste de `architec`): si algún segmento con productos en la campaña usa `[whatsapp]` y no hay número, la previsualización lo marca como error y la creación responde `400`. Nunca se genera un enlace roto. Del mismo modo, sin supervisores configurados la campaña no se crea (RF-37).
- `titular` ya viene recortado por N-2 en la ingesta. `[titular 8]` son los primeros 8 caracteres del valor guardado.
- **Largo:** `len()` del mensaje final. Si pasa de 160, se excluye. Si pasa de 150, se advierte. La previsualización de una versión calcula el largo máximo por segmento con el titular de 8 caracteres, la fecha de 10 y el enlace de WhatsApp configurado.
- **Versiones:** `Speech original` se siembra en la migración con el texto exacto de RF-MM-18. Una versión usada por alguna campaña es inmutable, y editarla crea otra.

### 1.3 Exclusiones y advertencias (RF-MM-13, RF-MM-19, RF-MM-01)

Catálogo de códigos compartido con el frontend. Se traducen por código en i18n (`mowaMes.*`), como las incidencias de ingesta, con una prueba de contrato entre el catálogo del backend y lo que se emite.

| Código | Tipo | Cuándo |
|---|---|---|
| `telefono_invalido` | exclusión | Sin teléfono o fuera de RF-02 |
| `falta_documento` | exclusión | Sin documento (C-4 aprobada, supuesto S-MM-8) |
| `sin_speech` | exclusión | `dias_ajustados > 120` o `dias_atraso` vacío |
| `falta_titular` | exclusión | Titular vacío |
| `falta_vencimiento` | exclusión | Fecha de vencimiento de cuota vacía |
| `mensaje_excede_160` | exclusión | Mensaje de más de 160 caracteres |
| `mensaje_excede_150` | advertencia | Se carga, pero se advierte |
| `limite_mensual_excedido` | advertencia | La campaña superaría el límite del mes. Crear exige confirmación (S-MM-2) |

- Cada producto excluido lleva **un solo motivo**: el primero que falla, en el orden de la tabla.
- Un teléfono repetido no es motivo de exclusión.

**Ampliación en B4 (aprobada por el coordinador, 2026-09-13):** claves i18n `mowaMes.codigo.<codigo>`; advertencia `id_sin_correspondencia` (C-5); errores de campaña `falta_whatsapp`, `sin_supervisores` y `sin_productos_cargables`. Además:

- 2 MB = 2 000 000 bytes, y los límites de archivo solo se pueden editar hacia abajo.
- Las opciones deshabilitadas de RF-MM-03, 05 y 06 responden `400`.
- Los archivos de la previsualización se estiman por filas, marcado como estimación; la cantidad real sale al crear.
- Crear responde `409` si la versión de speech cambió desde la previsualización. La creación envía la versión y su marca.

**`PUT /mowa-mes/configuracion` (decisión del coordinador, 2026-09-14, B7):** un campo omitido conserva su valor y `whatsapp_contacto: null` explícito lo borra. Antes, omitirlo también borraba, por una asimetría accidental del modelo de entrada.

Aprobada por `architec` con tres condiciones:
- La regla se documenta en la descripción del endpoint como actualización parcial.
- Un `null` explícito en un campo que no admite `null` (los límites) responde `422`.
- No se extiende a otros `PUT`: `/supervisores` sigue siendo reemplazo completo.

**Código en los 409 de `POST /mowa-mes/campanas` (corte propio después de F5, condiciones de `architec`, 2026-09-16):**

- **Modelo de error propio del endpoint** (`detail` más `codigo`: `huella_cambiada` o `limite_excedido`), declarado en `responses` del POST. `DetalleError` no cambia, porque otros 409 ya lo consumen. Si los códigos entran en `CodigoMowaMes`, se agregan sus claves i18n y la prueba del catálogo.
- **Orden del backend sin cambios:** primero la huella y después el límite, documentado en `mowa-mes.md`.
- **Frontend:** decide por el código. Un 409 sin código conocido se trata como huella: bloquea Crear y pide previsualizar.
- **Entrega conjunta:** backend y frontend en el mismo corte, con prueba y mutación de cada lado.

### 1.4 Supervisión transversal (RF-37 a RF-41), en `gestiones_digitales/`

- El núcleo no conoce MOWA. Recibe la lista de supervisores de la campaña (`numero`, `procedencia`), el orden de procedencias, la primera fila válida y los nombres de las columnas de número y documento. Devuelve las filas de supervisión, con los DNIs secuenciales desde `00000001` por procedencia y los demás campos copiados de la fila plantilla.
- Si no hay productos cargables, no hay supervisión ni carga. La creación responde con error y la previsualización lo informa.
- Los supervisores por defecto y las procedencias se persisten y se editan desde Configuración. El número se valida con RF-02. La migración **no siembra números**, y las pruebas usan el rango `900000xxx`.
- La campaña guarda la copia de los supervisores con los que se generó.
- La posición es propia de MOWA (RF-MM-12): la supervisión va al inicio del primer archivo, y eso lo decide el conector, no el núcleo transversal.

### 1.5 Archivo de carga y división (RF-MM-10, RF-MM-11)

- Se escribe con el exportador XLSX existente: hoja `Hoja1`, `numero` como entero, `mensaje` y `dni` como texto (el exportador conserva los ceros a la izquierda).
- **División:** primero por 50 000 registros, contando la supervisión dentro del primer archivo. Después se mide el tamaño real en bytes del `.xlsx` escrito y, si pasa de 2 MB, el tramo se parte hasta que cumpla. Los límites son configuración, con estos valores por defecto. Cada archivo conserva el orden.
- **Almacenamiento:** los bytes de cada archivo se guardan en PostgreSQL al crear la campaña, para que la descarga sea idéntica aunque después cambie la versión vigente de la sábana. Ver consulta C-6.

### 1.6 Límite mensual (RF-MM-01)

- El límite (2 500 000 por defecto) y el WhatsApp de contacto por defecto viven en una configuración persistida del conector y se editan desde la API (RF-32), no desde `.env`.
- Los cargados del mes cuentan productos y supervisión, porque todas son filas que MES envía. El mes de imputación está pendiente de la consulta C-1.

### 1.7 Calendario laboral (RF-MM-08), en `calendario/`

- Transversal. Siguiente día gestionable desde una fecha: de lunes a viernes, sin feriados.
- **Los feriados se calculan por regla para cualquier año** (ajuste de `architec`): los nacionales de fecha fija, más Jueves y Viernes Santo derivados de la fecha de Pascua.
- La tabla persistida guarda solo las excepciones: días no laborables decretados que se agregan y feriados que se retiran por un cambio de ley. No se siembran fechas de un año.
- Prueba mínima: 2026 da 2 y 3 de abril, y otro año calcula bien su Semana Santa. Ver RF-MM-08 y S-MM-4 actualizados.
- La fecha de generación se toma en la zona `America/Lima`.

### 1.8 Reporte de enviados y conciliación (RF-MM-20 a RF-MM-22)

- **Lectura:** con `python-calamine` en `adapters/input/`, validando las 8 columnas. Si falta una o no hay filas, se rechaza con el motivo.
- **Importación:** el usuario elige la campaña del sistema y sube el archivo. El `id` de MES se lee del archivo. Si ese `id` ya estaba importado, se responde `409` y solo se reemplaza con `reemplazar=true`.
- **Conciliación:** emparejamiento multiconjunto por (`numero`, `dni`, mensaje normalizado), porque un mismo teléfono puede repetir mensaje. La normalización quita los signos diacríticos (NFD sin marcas combinantes) y recorta los extremos (ver consulta C-3 para la `ñ`).
- **Cifras por campaña:** cargados, enviados, cargados no enviados, filas del reporte sin correspondencia y conteo por `estado`, con productos y supervisión por separado, más el total.

### 1.9 Persistencia (orientativa, la decide backend y la revisa el coordinador)

`calendario_feriado`, `supervisor_digital` (lista por defecto), `mowa_mes_configuracion`, `mowa_mes_speech_version`, `mowa_mes_campana` (inputs, copia de la selección, versión de speech, WhatsApp, copia de supervisores, programación y cifras), `mowa_mes_archivo` (orden, filas, bytes y contenido), `mowa_mes_fila_cargada` (archivo, posición, numero, dni, mensaje y si es supervisión), `mowa_mes_exclusion` (pagaré, código), `mowa_mes_reporte` (`id` de MES único, campaña) y `mowa_mes_reporte_fila`.

Condiciones de la migración: una sola migración nueva, revisada a mano, `alembic check` limpio y la ida y vuelta `upgrade` → `downgrade -1` → `upgrade`.

### 1.10 API (`app/api/mowa_mes.py`, prefijo `/mowa-mes`, más `/calendario` y `/supervisores` transversales)

- **Configuración:** `GET`/`PUT /mowa-mes/configuracion`, `GET /calendario/feriados?anio=` (de ley calculados más excepciones), `GET`/`POST /calendario/excepciones` y `DELETE /calendario/excepciones/{fecha}` (tipos `agregado`/`retirado`; así quedó en B6a por el ajuste de feriados calculados), `GET /calendario/siguiente-dia-gestionable`, `GET`/`PUT /supervisores` (lista por defecto y procedencias).
- **Speech:** `GET /mowa-mes/speech`, `GET /mowa-mes/speech/{id}`, `POST /mowa-mes/speech` (versión nueva), `PUT /mowa-mes/speech/{id}` (solo si no se usó; si se usó, `409`), `POST /mowa-mes/speech/previsualizacion` (largo máximo por segmento).
- **Campaña:** `POST /mowa-mes/campanas/previsualizacion` (sin persistir: cifras, muestra, exclusiones paginadas, advertencias, descripción sugerida, archivos previstos y consumo del límite), `POST /mowa-mes/campanas` (`201`; `409` si supera el límite sin `confirmar_limite`), `GET /mowa-mes/campanas`, `GET /mowa-mes/campanas/{id}`, `GET /mowa-mes/campanas/{id}/exclusiones`, `GET /mowa-mes/campanas/{id}/archivos/{n}` (binario, con el resumen en cabeceras `X-*` declaradas en el contrato), `GET /mowa-mes/limite-mensual`.
- **Reporte:** `POST /mowa-mes/campanas/{id}/reportes` (multipart), `GET /mowa-mes/campanas/{id}/conciliacion`.

Todas las respuestas heredan de `ModeloRespuesta`, los errores usan `DetalleError` y los montos viajan como texto.

## 2. Secuencia

```
Backend:  B1 calendario ─┐
          B2 supervisión ┼─► B6a contrato de configuración ─► B4 campaña ─► B5 reporte ─► B6b contrato completo + docs/mowa-mes.md ─► B7 E2E
          B3 speech ─────┘        │                                                       │
Frontend: F1 (hecho vía designer) │                                                       │
                                  └─► F4 Configuración                                    ├─► F3 Seguimiento
                                                                                          └─► F2 Campaña (además espera el selector de designer) ─► F5
```

- **El contrato va en dos cortes**, para no dejar al frontend parado hasta el final. **B6a** cubre configuración, feriados, supervisores y speech, y desbloquea F4. **B6b** cubre campaña, archivos, reporte y conciliación, y desbloquea F3 y F2. Cada corte es una entrega completa: `openapi.json` y `npm run contrato` regenerados, `verificar.ps1 -ConBase` en verde. Pasa por el coordinador y después por `architec`, que commitea.
- Con las rutas y reglas de `designer`, el frontend va F4 → F3 → F2 → F5. F2 espera además el commit del selector de selección de `designer`.
- B7 corre después de B6b. Los escenarios Playwright se acuerdan con frontend sobre `e2e/api-falsa-mowa-mes.ts`.

## 3. Criterio de listo por entrega

- **Backend:** `.\scripts\verificar.ps1 -ConBase` en verde. Pruebas de núcleo con dobles, adaptadores (xlsx generado y releído; reporte sintético), API con `TestClient` y `postgres` (fechas 2099, limpieza). Migración revisada con ida y vuelta, `alembic check` limpio y contrato comprobado. Rendimiento: una generación con volumen sintético de unas 46 000 filas medida y reportada (división y 2 MB).
- **Frontend:** `npm run verificar` en verde, Vitest para `src/lib`, Playwright con `e2e/api-falsa-mowa-mes.ts`, i18n es/en completo y accesibilidad revisada.
- **En todos los casos:** datos sintéticos, ningún valor de `archivos_anexo_chat/`, ningún número real. Cada capa que aplica y no corrió se nombra con su motivo.

## 4. Consultas escaladas a `architec` (no bloquean B1 a B3)

**Resueltas el 2026-09-13.** Las decisiones ya están en `requerimientos-mowa-mes.md` y `modules.md` §5.1.

- **C-1:** se aprueba el mes de la fecha de envío de RF-MM-15 (supuesto S-MM-7).
- **C-2:** se aprueba extraer el recorrido a `seleccion_cartera/`, por ejemplo `recorrido.py`, sin cambiar su comportamiento. El `monkeypatch` de `LIMITE_MAXIMO` y el espía de `consultar` en `test_generacion_cargas_postgres.py::test_la_paginacion_real_no_repite_ni_salta_productos` y en `test_generacion_cargas.py` se mudan al módulo nuevo, y la prueba tiene que seguir fallando si se rompe `LIMIT`/`OFFSET`.
- **C-3:** NFD sin marcas combinantes ya convierte `ñ` en `n`. Se aplica por igual al mensaje cargado y al enviado.
- **C-4:** se excluye con `falta_documento`, justo después de `telefono_invalido` (supuesto S-MM-8).
- **C-5:** cada `id` se asocia a la campaña elegida, con su conteo por separado. Un `id` que no coincide con ninguna fila cargada de la campaña se advierte.
- **C-6:** los archivos se guardan en PostgreSQL.

**Decisiones del usuario del 2026-09-14 (vía `architec`):**

- **E-1:** enviados = filas emparejadas con estado `enviado`. Cualquier otro estado cuenta como cargado no enviado y va en `por_estado`.
- **E-2:** un documento que no sea DNI (8) ni RUC (11) se carga igual y se advierte con el código `documento_no_estandar` y su cantidad. No es exclusión. El catálogo pasa a 13 códigos.
- **S-MM-7 y S-MM-8:** confirmados.

Consultas originales:

| ID | Pregunta | Propuesta del coordinador | Bloquea |
|---|---|---|---|
| C-1 | ¿El consumo del límite mensual se imputa al mes de generación de la carga o al mes de envío programado? | Mes de la fecha de envío que usa RF-MM-15 | B4 (límite) |
| C-2 | ¿Se puede sacar `_SeleccionPaginada` de `generacion_cargas/servicio.py` a una pieza pública de `seleccion_cartera/` para reutilizarla, sin cambiar su comportamiento? | Sí, con las pruebas actuales en verde | B4 |
| C-3 | ¿La normalización de la conciliación convierte `ñ` en `n`? La evidencia solo muestra tildes | Normalizar también `ñ`/`Ñ` → `n`/`N`: no afecta la correspondencia legítima y cubre el caso si MES la quita | B5 |
| C-4 | Un producto sin documento, ¿se excluye o se carga con `dni` vacío? RF-MM-13 no lo lista | Excluir con el código `falta_documento` | B4 |
| C-5 | Un reporte con más de un `id` de MES en el mismo archivo, ¿se rechaza o se asocia cada `id` por separado? | Asociar cada `id` a la campaña elegida | B5 |
| C-6 | Los archivos generados, ¿se guardan en PostgreSQL o en `data/output/gestiones/`? | PostgreSQL: descarga reproducible y sin archivos sensibles sueltos en disco | B4 |

## 5. Agregados del 2026-09-28 (RF-MM-23 a RF-MM-26; T-MM-B8, T-MM-F6, T-MM-C3)

Delegados por `architec` el 2026-09-28, con los requerimientos commiteados en `93b7ca6`.

### 5.1 Cortes y orden

1. **F6-A, solo frontend (RF-MM-26):** paginación de la muestra (20 filas) y de las exclusiones (100) de la previsualización, 10 por página con `.pager`, más el total y el aviso cuando hay más de 100. Base: `93b7ca6`. No depende del backend.
2. **B8, backend (RF-MM-23 a 25):** tarifa, costos, plantilla de nombre, migración, contrato y `docs/mowa-mes.md`. Se hace en paralelo con F6-A, se verifica en un worktree y se commitea después.
3. **F6-B, frontend (RF-MM-23 a 25):** sobre el contrato de B8. Tarifa y plantilla en Configuración; plantilla y nombre resultante en Campaña; costos en la previsualización y en Seguimiento.
4. **C3:** revisión contra RF-MM-23 a 26.

### 5.2 Decisiones técnicas dentro del módulo (informadas a `architec`)

- **Montos en el contrato:** como texto decimal, igual que los montos de `/cartera` (`consulta-cartera.md` §6). La tarifa se envía con sus decimales, hasta 4, y los costos con precisión completa. El frontend los muestra con `formatMonto`: costos con 2 decimales y la tarifa con los que tenga. En el backend todo es `Decimal`, nunca `float`.
- **Redondeo:** se guarda el valor exacto (cargados × tarifa). El costo del mes suma los valores exactos y solo se redondea al mostrar, con redondeo a la mitad hacia arriba.
- **Nombre con `{archivo}` agregado y el límite de 120:** el recorte se aplica a la parte de la plantilla, de modo que el sufijo `_{archivo}de{total}` nunca se corte y los archivos de una campaña no repitan nombre.
- **Content-Disposition:** el nombre resuelto se guarda tal cual, en UTF-8. El encabezado lleva `filename` en ASCII, con el mismo criterio que `exportadores/comunes.py`, y además `filename*` en UTF-8 (RFC 5987), para que un navegador moderno descargue el nombre exacto.

### 5.3 Respuestas de `architec` (2026-09-28)

- **Decisiones técnicas de 5.2:** aprobadas. Se documentan en `mowa-mes.md` con el corte.
- **D-1:** `{campana}` se muestra como un marcador visible, y el nombre se marca como estimado si usa `{total}` o `{archivo}`. La campaña creada muestra los nombres reales.
- **D-2:** el costo del mes omite las campañas sin tarifa e indica cuántas quedaron fuera.
- **D-3:** el costo real no se guarda. Sale de la conciliación vigente (E-1) por la tarifa congelada.
- **Encargos listos para enviar:** `briefs-agregados.md`.

### 5.4 Costo real en el listado (2026-09-28)

`architec` aprobó la opción (iii), con apoyo de `designer`: la campaña guarda un conteo derivado, `enviados_conciliados` (E-1). Se escribe en la misma transacción que importa o reemplaza el reporte. Sin reportes es `NULL` (pendiente), nunca 0. No se hace backfill: las campañas anteriores no tienen tarifa. El costo real se calcula al leer como conteo × tarifa congelada, así que el listado lleva estimado y real por fila. Hay una prueba postgres de consistencia contra la conciliación, con su mutación. RF-MM-24 no cambia.

## 6. Mensaje en GSM-7 (RF-MM-27, RF-MM-19 ampliado; T-MM-B9, T-MM-F7, T-MM-C4), 2026-10-19

Decisión del usuario del 2026-10-19 (b12d384). Plan para aprobación de `architec`.

### 6.1 Lo que encontré en el código

- El `mensaje` de cada producto se arma y se mide en un solo lugar: `campana.py`, `constructor.mensaje_de(...)` seguido de `codigo_por_largo(len(mensaje))`. Las filas de supervisión copian `plantilla.mensaje`, así que heredan lo que salga de ahí.
- La campaña guarda ese `mensaje` en `FilaCarga`, y la conciliación lo compara con el del reporte de MES. `conciliacion.normalizar_mensaje` ya quita los diacríticos (NFD sin marcas combinantes) de los dos lados, y además recorta los espacios de los extremos.
- El Speech original solo tiene `á`, `é`, `í` y `ó` (lo confirman las constantes de `oro_mowa_mes_congelados.py`). Al normalizarlo, el largo no cambia: `9 a 30` sigue llegando a 156 y se sigue advirtiendo.
- Las huellas de las versiones guardadas (17 y 92) no deben cambiar: la versión se guarda tal como se escribió.

### 6.2 Diseño propuesto (T-MM-B9)

1. **Función del motor `a_gsm7` y función del núcleo `largo_gsm7(texto)`.** Lo acordé con `coordinador_motor_texto_enriquecido` y lo aceptó `architec`.
   - `a_gsm7` es de la familia texto y vive en el registro, con su cota:
     - primero quita los diacríticos (NFD sin marcas combinantes), igual que la conciliación;
     - después translitera los signos con equivalente simple (decisión del usuario, 204b3dc): `“ ” « »`→`"`, `‘ ’`→`'`, `…`→`...`, `– —`→`-`, `° º`→`o`, `ª`→`a`. `N°` sale `No` y `don’t` sale `don't`;
     - por último borra lo que siga fuera del alfabeto básico y de la tabla extendida de GSM-7 (3GPP TS 23.038), por ejemplo un emoji;
     - los extendidos (`€ [ ] { } \ ~ ^ |` y el salto de página) se conservan.
   - `largo_gsm7` cuenta 2 cada extendido (S-MM-9). Lo usan la cota y el control de 160.
2. **MOWA MES aplica `a_gsm7` como último paso fijo de cada segmento**, sin que el usuario la agregue. Se hace sobre el texto ya evaluado, no colgando la función de cada variable (precisado en la revisión de B16, 2026-10-21):
   - compilar las v1 y las v2 con `medida=largo_gsm7_normalizado`;
   - evaluar, aplicar `a_gsm7` al texto y medir con `largo_gsm7`;
   - sacar `caracteres_borrados` del texto evaluado antes de normalizar.
   La cota de la función `a_gsm7` del catálogo es 3 por carácter (tope verdadero del motor); el supuesto de «1 por carácter en las variables» es de MOWA MES. Antes de medir, la campaña pasa a `codigo_por_largo(largo_gsm7(mensaje))`. Así el archivo XLSX, la fila guardada, la supervisión, la previsualización de la campaña y la conciliación ven todos el mismo texto.
   - Condición de `architec`: se normaliza ANTES de medir los 150, los 160 y la cota (RF-MM-19).
   - Lo que exijo de la implementación, que elige el motor:
     - el texto final es igual a `a_gsm7` del texto completo;
     - la cota está en unidades GSM-7: exacta para el texto fijo, y las variables cuentan su cota a 1 por carácter. Es un supuesto documentado, porque un dato con un extendido puede pasarla, y el control exacto sigue siendo el de cada fila;
     - una prueba de propiedad: con variables sin extendidos, `largo_gsm7(mensaje) <= cota`.
3. **Previsualización del speech** (largo máximo por segmento):
   - el `ejemplo` sale normalizado;
   - la cota pasa a contarse en unidades GSM-7: el texto fijo se normaliza y cada extendido suma 1;
   - las variables siguen contando 1 por carácter, porque el control exacto sigue siendo el de cada fila;
   - la respuesta agrega lo que F7 necesita para avisar, sin que el frontend tenga que recalcular nada: por ejemplo, `caracteres_quitados` por segmento (los caracteres del texto fijo que se borran; los transliterados no cuentan) y un indicador de si el texto cambió. El nombre y la forma los cierra backend con dev_frontend y designer.
   - Hay que regenerar `contratos/openapi.json` y `contrato-api.d.ts`.
4. **Conciliación sin cambios de código.** Los mensajes nuevos ya salen normalizados, y `normalizar_mensaje` es idempotente sobre ellos. Las campañas anteriores, con tildes guardadas, siguen conciliando como hoy. Se prueba con:
   - las pruebas de conciliación actuales, intactas;
   - una regresión nueva: una campaña generada después del cambio (con un emoji borrado, una `«` transliterada y un extendido) concilia contra un reporte con el mismo texto;
   - una campaña anterior, con tildes, sigue conciliando igual.
5. **Prueba de oro, actualizada a propósito (RF-54):** en lugar de reemplazar las constantes, la prueba pasa a afirmar que la salida nueva es igual a `a_gsm7(constante congelada)`, mensaje por mensaje y con el SHA de la matriz recalculado así. Eso prueba que la única diferencia con el camino de antes es la normalización. Las constantes de 3e567d7 quedan como referencia histórica.
6. **Pruebas de `a_gsm7`:**
   - tabla de casos: `ñ`→`n`, `ü`→`u`, un caso por signo de la tabla de transliteración, emoji borrado, extendidos conservados que cuentan 2, saltos de línea conservados;
   - propiedades con Hypothesis: idempotencia, salida siempre dentro de GSM-7, y `largo_gsm7(a_gsm7(x)) <= 2 * len(x)`;
   - mutaciones: no borrar fuera de GSM-7, borrar en vez de transliterar, transliterar antes de quitar diacríticos, contar el extendido como 1, normalizar después de medir.
7. **Rendimiento:** el costo es lineal y chico por fila. La medición con 46 000 filas y `-ConBase` la corre `architec`.

**Agregado a B9 (2026-10-22, hallazgo de designer, acordado con `coordinador_motor_texto_enriquecido`).**
- El editor v2 muestra su propio largo, calculado por los endpoints genéricos del motor. Ahora el contexto `mowa_mes.speech` mide igual que la tabla.
- `ContextoTexto` gana `medida` (por defecto `len`) y `salida` (por defecto la identidad). Son campos de comportamiento, fuera del catálogo y del contrato.
- `contexto_speech()` declara `medida=largo_gsm7_normalizado` y `salida=a_gsm7`.
- `salida` se aplica a todas las salidas de texto: la muestra, los ejemplos, el producto real y la selección. Los problemas siguen ubicados sobre la expresión escrita.
- Pruebas:
  - paridad: cartera sigue con `len` y sin salida;
  - con «…» y con un extendido en el texto fijo, el editor y la tabla dan el mismo número.
- `caracteres_borrados` no va en la previsualización del motor. Las líneas del motor las revisa su coordinador. Con B13, entra primero el que esté listo antes, y el otro se rebasa.

### 6.3 Frontend (T-MM-F7), espera B9

- Textos de designer (2026-10-22):
  - el largo sigue diciendo «caracteres», y la nota de cálculo explica la unidad una sola vez (los extendidos cuentan 2 y «…» cuenta 3);
  - los invisibles llevan su nombre (11 en es y en), y el resto un genérico, «carácter invisible U+XXXX»;
  - los elementos se separan con « · ».

- La previsualización de la campaña ya muestra el `mensaje` que devuelve el backend, así que ahí basta con el aviso.
- En el editor del speech (v1 en solo lectura y v2), el ejemplo y los largos ya vienen normalizados del backend. Falta el aviso de los caracteres que se borran (los transliterados no se señalan).
- La experiencia está fijada por designer en `motor-texto-enriquecido-interfaz.md` §10.2 y §10.4 (2026-10-19):
  - un hint fijo de GSM-7, en v1 y en v2;
  - una línea por segmento, solo cuando hay borrados: «Al enviar se borran: …». Cada carácter va en mono, sin repetir, y los invisibles por su nombre. No bloquea guardar. En una v2 es un `.notice--warning` bajo el editor; en una v1 va en la celda «Estado». Quitar las tildes no se señala.
  - El hint fijo de GSM-7 (`mowaMes.speech.gsm7`) entra en F7 y no en F8: hasta B9 la carga no normaliza, y la pantalla no puede prometerlo antes (acordado con `coordinador_motor_texto_enriquecido`, 2026-10-20).
  - Entra también en F7, después de F8 (hallazgo de designer, 2026-10-20): por debajo de 64rem, la tarjeta apilada del speech la abre el segmento, seguido de «Largo máximo» y «Estado». Es `data-orden="1"` también en la celda del segmento, y se actualiza el comentario, porque la v1 ya no se escribe. Lleva una prueba Playwright del orden visual de la primera tarjeta.
  - Para B9: los caracteres borrados van por segmento, sin repetir, en el orden en que aparecen y sin contar los diacríticos. El nombre de un invisible lo pone el frontend (o el backend devuelve el punto de código, a acordar en B9).

### 6.4 Consultas

- Con `coordinador_motor_texto_enriquecido`: resuelto (6.2, punto 1, y 6.5).
- A `architec`, sobre los signos tipográficos: el usuario respondió «transliterar» (RF-MM-27, 204b3dc). Ver 6.2, punto 1. Plan §6 aprobado por `architec` el 2026-10-19.

### 6.5 Reparto y orden

- **Corte del motor** (`dev_backend_motor_texto_enriquecido`, lo revisa su coordinador y pasa por §13 conmigo): `a_gsm7` en el registro, con su cota; `largo_gsm7`; las pruebas de la función; y el oro de B5 actualizado con el cambio declarado (RF-54), que es su prueba.
- **B9** (`dev_backend_modulo_mowa_mes`, sobre el corte del motor): `a_gsm7` como último paso en `expresion_de` y al compilar las v2; la medida en `campana.py`; los campos nuevos de la previsualización; el contrato; la regresión de conciliación; i18n de los códigos si los hay; y las mutaciones.
- **Orden del motor** (un solo dev, acordado el 2026-10-19): B14 → B15 (M3, `speech.py` y la API) → **B16** (`a_gsm7`, `largo_gsm7`, la propiedad de la cota y el oro) → B13. B9 va encima de B16, que ya incluye B15, así que nadie rebasa contra un `speech.py` a medio cambiar. B16 arranca cuando `architec` apruebe este §6.
- Después: F7 (frontend, con designer), C4 (mi revisión) y `architec`.

### 6.6 Estado al 2026-10-24

- **Entraron:**
  - B16 del motor (535a61b), con `a_gsm7` y la normalización;
  - B15 y F8, M3 (32bfebf y 3fe79af);
  - B13 del motor (5ce9834);
  - **T-MM-B9** (8894874), la base;
  - F6 del motor (19adb4c), con `avisoSegmento`;
  - **T-MM-B9, segunda parte** (0de6f47), medida y salida del contexto del speech.
- **Medición de B9** (46 000 filas): previsualizar +9 % y crear +11 %, unos 10 µs por mensaje. `architec` lo aceptó.
- **T-MM-B9c, atajo para el texto ya simple: probado y descartado.** El ahorro (~1 µs por mensaje, ~0,05 s por campaña) queda dentro del ruido de ±0,3 s. Las corridas del dev con y sin atajo (3 alternadas) lo confirman: 6,5 a 7,8 µs por fila con el atajo y 5,9 a 7,5 sin él. Si algún día interesa recuperar los ~9 µs restantes, el paso es una tarea de diagnóstico sin código: un perfil con cProfile de crear campaña con unas 5 000 filas, antes y después de B9. Hoy no es prioridad.
- **T-MM-F7** entró en `97ebfe0` (Playwright 442/442).
- **T-MM-C4 cerrada:** `revision-c4.md`.

## 7. Campos adicionales en el speech (D-CA-0 a D-CA-2; T-MM-B12, T-MM-F11, T-MM-C8), 2026-10-27

Decisiones del usuario del 2026-10-27, en `d999698`, en la §28 del plan del motor y en el registro de cambios de RF-65. Plan sobre `fb1d72b` (T-CA-B1), para aprobación de `architec`. Se escribe antes de T-CA-B2: cuando B2 entre, ajusto lo que cambie su contrato y arranco.

### 7.1 Lo que ya da el motor y no se repite

- **El catálogo:** `CatalogoCartera.campos()` trae cada adicional con su tipo, su `etiqueta` y `archivado`, archivados incluidos para que lo que ya los usa resuelva. `archivados_entre(nombres)` dice cuáles de los usados están archivados.
- **Los valores:** las filas de la consulta traen cada adicional rotulado con su nombre técnico y ya tipado (`str`, `Decimal` o `date`; `repositorio_cartera_postgres._columnas_producto`). La campaña y la previsualización lo leen de `producto["ad_x"]`, sin código de lectura propio.
- **La cota:** el código `sin_cota_variable` ya existe en `CodigoTexto`, con su texto es/en: «Limítala con “Primeros caracteres”». Es exactamente lo que pide D-CA-1, así que no hay código ni traducción nuevos para eso.
- **GSM-7:** se aplica al texto final y no a la variable (RF-MM-27). Sin cambio.
- **D-CA-3:** el .xlsx de MES no gana columnas. RF-54 byte a byte, sin cambio.

### 7.2 D-CA-0: el speech v2 ofrece los adicionales (T-MM-B12)

- **`speech.py`.** `VARIABLES_V2` sigue siendo la constante de hoy. Una función, `adicionales_de(catalogo) -> dict[str, TipoValor]`, lee `campos()` una sola vez y devuelve los adicionales, archivados incluidos. Las v2 se compilan con `{**VARIABLES_V2, **adicionales}`. Las variables de la fila no chocan nunca con un adicional, porque los nombres reservados y el prefijo `ad_` lo impiden desde T-CA-B1.
- **Firmas.** Reciben `adicionales: Mapping[str, TipoValor]` como argumento de palabra clave, con valor por defecto vacío: `problemas_de`, `compilar_expresion`, `previsualizar_v2`, `ConstructorMensajes` y `mensaje_de`, que recibe además los valores de la fila. Así una v1, y cada llamada que existe hoy, compila igual, y **las pruebas de oro no se tocan** (7.6). Si falta pasar los adicionales en un camino de producción, la v2 que los usa da `variable_desconocida`, y lo atrapan las pruebas de punta a punta de 7.6.
- **Quién pasa el catálogo:**
  - `configuracion.py`, al guardar, convertir y previsualizar el speech. El servicio recibe el catálogo de la API (`crear_catalogo_cartera`).
  - `campana.py`, que arma el constructor con `self._consulta.catalogo`. `evaluar_producto` pasa los valores de los adicionales que usa el segmento.
  - `contexto_texto.py`, con `contexto_speech(catalogo)`: sus variables son las v2 más los adicionales, con origen `cartera`, y con la etiqueta y la marca de archivado que B2 le agregue a `VariableContexto`, igual que el contexto `cartera`.
  - `api/texto_enriquecido.py`, una línea de composición.
- **Ejemplos sintéticos.** Una tabla con un valor por tipo: texto `ZONA SINTETICA`, número `Decimal("1250.50")` y fecha `date(2026, 10, 5)`. La usan el `_EJEMPLO` del contexto y la muestra de `previsualizar_v2`. `_registro_de_producto` toma el valor del producto de la muestra. Un segmento que no usa adicionales da el mismo ejemplo que hoy, porque las claves de más no cambian el texto.

### 7.3 D-CA-1: el tope obligatorio en un adicional de texto o de número (T-MM-B12)

- **Al validar una v2** (`_problemas_de_v2`, que se usa al guardar y al previsualizar): cada nodo variable que lee un adicional de texto o de número, como base o como argumento, se compila solo, como `Expresion((nodo,))`. Si su `cota` es `None`, sale este problema:

      ProblemaSpeech(segmento, "expresion", detalle, Problema(SIN_COTA_VARIABLE, detalle, nodo=i, nombre="ad_x"))

  Queda ubicado en ese nodo, y el editor ya ubica los problemas del motor por nodo.
- **Se usa la cota del motor, no se busca la palabra `primeros`.** Vale cualquier cadena que el motor acote: `ad_texto | primeros(12)`, o `ad_numero | a_texto | primeros(6)` para un número «después de pasarlo a texto». La regla es por nodo: si el mismo nodo lee también el titular sin tope, el usuario acota el nodo entero (un `primeros(n)` al final lo resuelve). Lo digo porque es la generalización fiel de D-CA-1 y no hace falta decidir nada aparte.
- **No aplica a una fecha:** D-CA-1 nombra solo texto y número, y la fecha con `formato_fecha` ya tiene cota. El titular, la fecha de vencimiento y los días siguen como hoy, sin tope obligatorio.
- **Al guardar,** `_validos` ya lanza `SpeechInvalido` con los problemas: la versión no se guarda hasta que se corrija.

### 7.4 D-CA-2: `falta_campo_adicional` (T-MM-B12)

- **`entities/mowa_mes.py`:** `FALTA_CAMPO_ADICIONAL = "falta_campo_adicional"`, de tipo `EXCLUSION`, va justo después de `FALTA_VENCIMIENTO`, porque el orden de la clase es el orden de evaluación.
- **`ConstructorMensajes.adicionales_usados(segmento) -> tuple[str, ...]`:** son los adicionales que lee la expresión del segmento, en el orden de sus nodos (`variables_usadas` ∩ adicionales). En una v1 no hay ninguno.
- **`evaluar_producto`,** después de `falta_vencimiento` y antes del WhatsApp y de los 160:

      faltan = tuple(n for n in constructor.adicionales_usados(seg) if _vacio(producto.get(n)))

  Si falta alguno, devuelve `Exclusion(pagare, FALTA_CAMPO_ADICIONAL, campos=faltan)`. Se usa el mismo `_vacio` del titular (`None` o un texto en blanco). También aplica a un archivado, porque sigue en `campos()`. Un adicional vacío que el segmento no usa no excluye nada.
- **`Exclusion`** gana `campos: tuple[str, ...] = ()`, con los nombres técnicos: puede ser más de uno.
- **Persistencia.** Una migración: `mowa_mes_exclusion.campos` como `text[] NULL`, encadenada después de la de B2. La escribe el dev y la aplica `architec`. El repositorio la escribe y la lee, y una fila antigua da `()`.
- **API y contrato.** `ExclusionRespuesta` gana `campos: [{nombre, etiqueta}]`. El nombre legible se resuelve al leer, con el catálogo: si el usuario renombra el campo, cambia lo que se muestra pero no lo guardado. Se regenera `contratos/openapi.json`.
- **Textos.** El texto es/en de `mowaMes.codigo.falta_campo_adicional` lo pone F11 (7.7). La prueba espejo del frontend lee la clase de códigos.

### 7.5 El aviso de campo archivado (T-MM-B12)

- `previsualizar_speech_v2` devuelve además `campos_archivados`, que es `catalogo.archivados_entre(...)` de las variables que usan las expresiones. Va en la respuesta de la API. Es un aviso, nunca bloquea y nunca da un 500 (restricción 8). Guardar una versión que use un archivado se permite, porque el campo sigue resolviendo, y el editor no lo ofrece.
- No lo pongo en la previsualización de la campaña: la campaña genera bien con un archivado, y el lugar para corregirlo es el speech. Es la pregunta P-2 de 7.9.

### 7.6 Pruebas

**Pruebas de oro que no cambian.** No aparecen en el diff, y lo compruebo con `git diff --stat` y corriéndolas:
- `test_mowa_mes_speech_oro.py`, `oro_mowa_mes_congelados.py` y `oro_mowa_mes_datos.py`, que son las huellas y la matriz GSM-7;
- `test_speech_original.py`, `test_mowa_mes_speech.py`, `test_mowa_mes_speech_v2.py`, `test_mowa_mes_speech_gsm7.py` y `test_mowa_mes_speech_constantes.py`;
- `test_mowa_mes_campana.py`, `test_mowa_mes_division.py` (RF-54 y D-CA-3) y los dos `test_mowa_mes_descripcion*.py`;
- `test_api_mowa_mes_speech_v2.py` y `test_api_mowa_mes_campanas.py`.

**Lo que cambia a propósito:**
- `test_codigos_mowa_mes.py`: el código nuevo entra en el orden;
- el contrato: `ExclusionRespuesta` y la previsualización v2;
- la prueba del contexto `mowa_mes.speech`: sus variables suman los adicionales.

**Pruebas nuevas.** Usan los cuatro adicionales sintéticos de `tests/campos_adicionales_memoria.py`, de modo que no hacen falta datos nuevos:
- **D-CA-0:**
  - una v2 con un adicional de cada tipo, acotado, genera el mensaje con el valor de la fila (el texto con `primeros`, el número con `a_texto | primeros` y la fecha con `formato_fecha`);
  - el ejemplo de la previsualización usa el valor sintético del tipo;
  - el producto de la muestra trae su propio valor;
  - el contexto ofrece los adicionales con su tipo.
- **D-CA-1:**
  - un texto sin tope da `sin_cota_variable` en su nodo, con su nombre, y un número sin tope también;
  - un número con `a_texto | primeros(n)` no da problema;
  - un nodo con el adicional como argumento y sin tope da el problema;
  - una fecha sin `formato_fecha` no da el problema de D-CA-1;
  - el titular sin `primeros` sigue igual que hoy;
  - guardar con el problema da 422, y no se guarda.
- **D-CA-2:**
  - `None`, `""` y `"  "` excluyen, y el detalle trae el campo;
  - con dos vacíos salen los dos, en el orden de los nodos;
  - el orden de evaluación: `falta_vencimiento` gana a este código, y este código gana al WhatsApp y a los 160;
  - un adicional vacío que el segmento no usa no excluye nada;
  - un archivado vacío excluye igual;
  - la API devuelve el nombre técnico y el legible, y renombrar cambia el legible.
- **Persistencia** (`@postgres`, la corre `architec`): `campos` de ida y vuelta, y una exclusión anterior a la migración se lee como `()`.
- **Aviso:** con un archivado en la expresión sale el nombre, y sin archivados sale vacío.
- **Mutación,** en una copia, nunca en el árbol compartido:
  - quitar la exigencia de cota, o aplicarla también a la fecha;
  - cambiar `_vacio` por `is None`;
  - mover el código después del WhatsApp;
  - no pasar los adicionales al constructor de la campaña;
  - perder `campos` al guardar.

### 7.7 Frontend (T-MM-F11), espera el contrato de B12

- **`mowaMes.codigo.falta_campo_adicional`** en es y en. Los textos los propone designer; un borrador: «Falta un campo adicional que el mensaje necesita: {campos}.».
- **El detalle de la exclusión** muestra los nombres legibles en `mowa-mes/campana.astro` y en la sección Exclusiones de `seguimiento.astro`.
- **El aviso de campo archivado** va en la previsualización del editor v2.
- **La lista de variables del editor** sale del contexto. Para que el nombre legible de un adicional se vea hay que esperar T-CA-F1 del motor, que es quien agrega la etiqueta literal. Si F11 llega antes, el editor muestra el nombre técnico hasta que entre F1. Se dice al entregar y no bloquea.
- **Pruebas:** Vitest del formato del detalle, y Playwright de la exclusión con el detalle y del aviso.

### 7.8 Cortes

| Corte | Qué | Depende | Revisión |
|---|---|---|---|
| **T-MM-B12** | 7.2 a 7.6: variables v2, tope, exclusión, aviso, migración y contrato | T-CA-B2 en main | yo; `coordinador_motor_texto_enriquecido` mira el contexto y el uso de la cota; `architec` corre `-ConBase` y la migración de ida y vuelta |
| **T-MM-F11** | 7.7 | el contrato de B12; las etiquetas, T-CA-F1 | yo; designer los textos |
| **T-MM-C8** | El cierre contra D-CA-0 a D-CA-2 y RF-64 a RF-66 en lo que toca a MOWA MES | B12 y F11 | `architec` |

Va en un solo corte de backend: D-CA-0 sin D-CA-2 dejaría salir un SMS con un hueco.

### 7.9 Preguntas para `architec`

- **P-1. ¿Se guardan los campos de la exclusión (la migración de 7.4)?** La alternativa es no migrar y mostrar los nombres solo en la previsualización, que se arma en memoria, de modo que una campaña ya guardada diría solo «falta un campo adicional». **Recomiendo migrar:** la §28 aprobó el nombre técnico y el legible en la pantalla, y es una sola columna nula.
- **P-2. ¿El aviso de archivado también va en la previsualización de la campaña?** **Recomiendo que no** por ahora (7.5).

**Respuestas de `architec` (2026-10-27): plan aprobado.** P-1: sí, la columna `mowa_mes_exclusion.campos text[] NULL`, con la migración encadenada a la de T-CA-B2. La escribe el dev y la aplica `architec`: en `auto_cusco_test` al verificar y, con permiso del usuario, en `auto_cusco`. P-2: no por ahora. La exclusión ya nombra el campo, y se revisa en T-MM-C8 si en uso real hace falta el aviso en la campaña. B12 arranca cuando T-CA-B2 esté en `main`.
