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

Consultas originales:

| ID | Pregunta | Propuesta del coordinador | Bloquea |
|---|---|---|---|
| C-1 | ¿El consumo del límite mensual se imputa al mes de generación de la carga o al mes de envío programado? | Mes de la fecha de envío que usa RF-MM-15 | B4 (límite) |
| C-2 | ¿Se puede sacar `_SeleccionPaginada` de `generacion_cargas/servicio.py` a una pieza pública de `seleccion_cartera/` para reutilizarla, sin cambiar su comportamiento? | Sí, con las pruebas actuales en verde | B4 |
| C-3 | ¿La normalización de la conciliación convierte `ñ` en `n`? La evidencia solo muestra tildes | Normalizar también `ñ`/`Ñ` → `n`/`N`: no afecta la correspondencia legítima y cubre el caso si MES la quita | B5 |
| C-4 | Un producto sin documento, ¿se excluye o se carga con `dni` vacío? RF-MM-13 no lo lista | Excluir con el código `falta_documento` | B4 |
| C-5 | Un reporte con más de un `id` de MES en el mismo archivo, ¿se rechaza o se asocia cada `id` por separado? | Asociar cada `id` a la campaña elegida | B5 |
| C-6 | Los archivos generados, ¿se guardan en PostgreSQL o en `data/output/gestiones/`? | PostgreSQL: descarga reproducible y sin archivos sensibles sueltos en disco | B4 |
