# Plan de RF-MM-28 a RF-MM-36 (T-MM-C11)

> **Escrito el 2026-10-30 sobre `1b0d9fe`.** Es solo el plan: no hay código hasta que lo apruebe `architec`.
>
> Requerimientos en [requerimientos-mowa-mes.md](../../requerimientos-mowa-mes.md), en `1b0d9fe`:
> - RF-MM-28 a RF-MM-36, nuevos;
> - RF-MM-17, modificado: solo v2;
> - RF-MM-01 y RF-MM-09, ampliados;
> - S-MM-10, supuesto nuevo.

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Desarrollan:
- los cortes `M-B*`: `dev_backend_modulo_mowa_mes`;
- los cortes `M-F*`: `dev_frontend_modulo_mowa_mes`.

Cada encargo va con `notify_when_idle`.

---

## 1. Reglas de todos los cortes

- **Un corte es un commit,** y queda en verde por sí solo.
- **Contratos y catálogos van con sus pruebas espejo.** Los cambios de contrato (`openapi.json` y `contrato-api.d.ts`), de códigos (`CodigoMowaMes`, `CodigoErrorCampana`) y de claves i18n.
- **Las pruebas de oro no cambian,** salvo en M-B3, con la autorización de `architec`: solo para fijar que el v2 convertido da el mismo mensaje, byte a byte, que el v1 congelado. La regla de las huellas 17 y 92 fijas la levantó el usuario con RF-MM-17.
- **§13 con `coordinador_motor_texto_enriquecido`** en lo que toque el motor, el editor, `/cartera` o las selecciones.
- **`designer` aprueba con capturas** todo cambio visible: textos, lugar y variante.
- **Turnos de máquina por la cola del motor:**
  - 5 GB para la cadena del frontend y 2 GB para pytest, con Playwright en 1 worker;
  - si la memoria corta una corrida, no se relanza sin avisar a `architec`.
- **Solo `architec`:** `-ConBase`, las `@postgres` y las migraciones contra `auto_cusco_test`. Las de `auto_cusco` las corre con permiso del usuario. Cada entrega dice qué `@postgres` le tocan.
- **La documentación va en el mismo corte:** `mowa-mes.md`, `modules.md` y `architecture.md`.
- **Worktrees con ruta absoluta** en `git worktree add`.

## 2. Lo que dice el código hoy y define el plan

- **Qué campaña cuenta.** Los tres agregados están en `repositorio_campanas_mowa_mes_postgres.py`: `cargados_en_mes` (`:195`), `costo_del_mes` (`:202`) y `listar` (`:286`). Los dos primeros filtran por `mes_imputacion`, que ya es el mes de la fecha de envío (S-MM-7). Ese es el único lugar donde se decide qué cuenta.
- **Borrar en cascada ya está.** `mowa_mes_archivo`, `mowa_mes_fila_cargada`, `mowa_mes_exclusion` y `mowa_mes_reporte` tienen `ondelete=CASCADE` hacia la campaña, y `mowa_mes_reporte_fila` hacia el reporte. La versión de speech no se toca: la FK va de la campaña al speech.
- **«Pendiente de reporte» ya existe.** Es `enviados_conciliados IS NULL` en la campaña, y no se crea otra definición.
- **El Speech original se siembra con un literal congelado** en la migración `a4c8e2f6b913` (`SPEECH_ORIGINAL`, como v1), independiente del código de la app. El CHECK `contenido_segun_formato` (`f2c8a4d7b915`) ata `formato` a `expresiones`.
- **Qué guarda cada formato.** Una v2 nativa guarda `partes = []` (`repositorio_mowa_mes_postgres.py:51`), y una v1 guarda sus partes. Así, una versión convertida conserva su texto v1 en `partes`, y una migración puede saber cuáles convirtió.
- **La conversión de hoy es `speech.convertir_a_v2`** (`speech.py:285`): es `expresion_de` por segmento, con titular y fecha `obligatoria`. Se serializa con `texto_enriquecido.serializacion.expresion_a_dict`.
- **Ni la campaña ni `/cartera` guardan un borrador, ni leen parámetros de la URL.** «Editar en Cartera» los necesita (§3.6).

## 3. Diseño por requerimiento

### 3.1 Campañas descartadas (RF-MM-31, RF-MM-32 y RF-MM-01 ampliado)

- **Columna.** `mowa_mes_campana.descartada_en timestamptz NULL`. NULL significa activa. No hay «quién», porque no hay usuarios.
- **Un solo predicado.** En el repositorio, `_ACTIVA = _CAMPANA.c.descartada_en.is_(None)`, que usan `cargados_en_mes`, `costo_del_mes`, `listar` y todo agregado que venga. El repositorio en memoria de las pruebas aplica la misma regla.
- **Por qué alcanza con eso:**
  - el límite y la advertencia de la campaña nueva leen `cargados_en_mes`;
  - las cifras del mes leen `costo_del_mes`;
  - el listado activo lee `listar`.
  Una prueba `@postgres` por agregado fija que una descartada no suma.
- **Ver una campaña descartada se permite.** El detalle, los archivos y su conciliación se pueden ver, porque RF-MM-32 pide «ver». La campaña lleva `descartada_en` en `CampanaRespuesta`.
- **Métodos nuevos:**
  - `descartar(id)`;
  - `restaurar(id)`;
  - `eliminar(id)`, que solo funciona si está descartada; si no, da `CampanaNoDescartada`. El DELETE va en cascada;
  - `listar_descartadas(mes)`, por `mes_imputacion`.
- **API:**
  - `POST /mowa-mes/campanas/{id}/descartar`;
  - `POST /mowa-mes/campanas/{id}/restaurar`;
  - `DELETE /mowa-mes/campanas/{id}`;
  - `GET /mowa-mes/campanas/descartadas?mes=AAAA-MM`. Para el `.segmented` «Activas (N) · Descartadas (M)» y el filtro «Mes de gestión» de `mowa-mes-interfaz.md` §4.2, la respuesta trae también:
    - `meses`: solo los meses que tienen descartadas;
    - `total_descartadas`.
    El listado activo ya trae su total.
- **Códigos nuevos** en `CodigoErrorCampana`, con su i18n y su espejo: `campana_descartada` y `campana_no_descartada`.
- **Importar un reporte a una campaña descartada:** propongo rechazarlo con 409 `campana_descartada` y el texto «restaurala primero». Es la U-1 de §6, para el usuario.
- **La advertencia al descartar** («si se envió, su consumo deja de contar») la decide la pantalla con `enviados_conciliados` o con `reportes` de la campaña. No hace falta un dato nuevo.

### 3.2 Administración de speeches (RF-MM-28, RF-MM-29 y RF-MM-30)

- **Columna.** `mowa_mes_speech_version.deshabilitada_en timestamptz NULL`.
- **Renombrar (RF-MM-28).** Se puede renombrar cualquier versión, incluidas las usadas y el original. Se reusa la unicidad de `nombre_normalizado` y su 409 de nombre repetido. El contenido no cambia, y la huella tampoco, porque no depende del nombre.
- **Deshabilitar y habilitar (RF-MM-29):**
  - `listar_speech` trae la marca;
  - el selector de la campaña muestra solo las habilitadas;
  - `armar`, que usan tanto la previsualización como la creación, rechaza una deshabilitada con un código nuevo, `speech_deshabilitado`;
  - si la versión preseleccionada queda deshabilitada, la campaña preselecciona la primera habilitada, y sin ninguna habilitada lo dice.
- **Eliminar (RF-MM-30).** `DELETE /mowa-mes/speech/{id}`. Solo se permite si:
  - la versión está deshabilitada;
  - `usada_en IS NULL`;
  - no es `original`.
  Si no, da 409 con el motivo: `speech_no_deshabilitado`, `speech_usado` o `speech_original`.
  - Una campaña descartada y después eliminada deja la versión con `usada_en`: RF-MM-32 dice que la versión no cambia, así que sigue sin poder borrarse.
- **API.** `PATCH /mowa-mes/speech/{id}`, con `{nombre?, habilitada?}`, y el `DELETE`. El contrato se regenera.
- **Cada versión trae `eliminable` y `motivo_no_eliminable`** (`usada`, `original` o `null`), pedido de `designer` en `mowa-mes-interfaz.md` §4.5. Así, la pantalla muestra el motivo en vez del botón, sin descubrirlo con un 409. El 409 del `DELETE` se queda como red de seguridad.

### 3.3 Solo v2 (RF-MM-17 modificado)

- **Migración de datos.** Es una sola, en su lugar y sin depender del código de la app.
  - **Convertidor congelado.** Una función `_convertir(partes) -> list[dict]` copiada dentro de la migración. Arma el JSON de los nodos igual que `expresion_de` más `expresion_a_dict` hoy: titular `primeros(8)` obligatorio, parte 1 con cada `[whatsapp]` como `whatsapp_contacto | enlace_whatsapp`, la fecha `formato_fecha` obligatoria y la parte 2.
  - **El original con un literal congelado.** `EXPRESIONES_ORIGINAL` va escrito en la migración. Una prueba fija que `EXPRESIONES_ORIGINAL == _convertir(SPEECH_ORIGINAL)`. Así, una base reconstruida desde cero, que siembra el original como v1, lo convierte siempre igual.
  - **Upgrade.** Cada fila con `formato = 'v1'` pasa a `expresiones = _convertir(partes)` y `formato = 'v2'`. `partes` queda como está: el texto v1, para trazabilidad. Se conservan `id`, `nombre`, `nombre_normalizado`, `usada_en`, `basada_en_id`, `original` y `creado_en`. El CHECK pasa a exigir `formato = 'v2' AND expresiones IS NOT NULL`.
  - **Downgrade exacto.** Las filas con `partes` no vacío eran v1: vuelven a `formato = 'v1'` y `expresiones = NULL`. Las v2 nativas no se tocan. No se pierde nada.
- **Pruebas:**
  - el convertidor de la migración da lo mismo que `convertir_a_v2` serializado, para el original y para 200 juegos de partes sintéticos generados;
  - **el oro, con la autorización de `architec`:** el mensaje del v2 convertido es igual byte a byte al del v1 congelado, en la matriz de `oro_mowa_mes_congelados.py`;
  - `@postgres`, de `architec`: ida y vuelta de la migración con una v1 usada por una campaña. Después del upgrade quedan iguales el id, el nombre, `usada_en` y el texto v1. Después del downgrade, la fila es idéntica a la de antes.
- **Retirar la v1, después de la migración y en dos cortes:**
  - frontend primero (M-F1): fuera la vista v1, «Convertir a v2» y el cliente de `como-v2`;
  - backend después (M-B4): fuera `PartesSegmento` en la entrada, la previsualización con `partes`, el endpoint `/speech/{id}/como-v2`, las ramas `FormatoSpeech.V1` y `VERSION_V1_RETIRADA`, con su espejo.
  - en M-B4, la columna `partes` pasa a llamarse `texto_v1`, nula en las v2 nativas, y `formato` se quita. El downgrade vuelve atrás.
  - el contrato se regenera.

### 3.4 Pendientes de reporte (RF-MM-33)

- **Sin backend nuevo.** En el listado del seguimiento, una campaña activa con `enviados_conciliados == null` lleva un tag «Pendiente de reporte» y el paso siguiente: «Importa el reporte de enviados de MES».
- **Arriba de la lista,** un aviso con cuántas pendientes hay.
- **La campaña recién creada** enlaza a `/mowa-mes/seguimiento?campana=<id>`. El seguimiento abre esa campaña si viene el parámetro.

### 3.5 Datos para cargar la campaña en MES (RF-MM-35)

- **Sin backend nuevo:** todo está en `CampanaRegistrada`.
- **Al crear, un panel** con:
  - los archivos para descargar;
  - cada dato del formulario de MES con su valor y un botón «Copiar»: tipo de carga, descripción, salida, herramientas y programación (RF-MM-03 a 07).
- **`copiarConRespaldo` sale de `mowa-mes-campana.ts` a `lib/portapapeles.ts`.** Es su segundo uso, el que C9 esperaba.

### 3.6 «Editar en Cartera» (RF-MM-09 ampliado)

**Acordado con `coordinador_motor_texto_enriquecido` el 2026-10-30.** El selector sigue siendo genérico: es el mismo componente de Cartera, Columnas, Generar carga y la campaña, y no sabe nada de `volver`.
- **El selector gana solo tres cosas:**
  - `ControladorSelector.cargarGuardada(id): boolean`: el `cargarGuardada` interno de `selector-seleccion.ts:379`, ahora expuesto. Devuelve `false` si el id no está en la lista;
  - un evento `seleccionguardada` con `{id}`, que se emite en `trasGuardar` (`:812`) al guardar la misma selección y al guardar como nueva;
  - `ControladorSelector.confirmarDescartar(): Promise<boolean>`: el diálogo interno del selector, «Hay cambios sin guardar» (`SelectorSeleccion.astro:233`, `selector.descartar.*`). Sin cambios, resuelve `true` sin abrir nada. Con cambios, abre ese mismo diálogo y resuelve según el botón. El enlace «Volver a la campaña sin guardar» navega solo con `true`. Nada de `confirm()` nativo ni de un diálogo nuevo. Prueba: con cambios abre el diálogo; «Seguir editando» no navega; descartar sí navega; y sin cambios navega directo.
- **Ida.** La campaña guarda su borrador en `sessionStorage`, con una clave versionada: todos los campos, la fecha y la selección. Abre `/cartera?seleccion=<id>&volver=/mowa-mes/campana`.
- **En Cartera, la página `cartera.astro`** (no el selector):
  - lee `seleccion` y `volver`, y llama a `cargarGuardada`;
  - con `volver`, muestra la línea «Al guardar, vuelves a la campaña» y el enlace «Volver sin guardar», que va a `volver` sin `seleccion`. Los textos los pone `designer`;
  - al recibir `seleccionguardada`, navega a `volver?seleccion=<id>`.
- **Vuelta.** La campaña restaura el borrador, lo borra de `sessionStorage` y llama al mismo `cargarGuardada`. Es un solo mecanismo para los dos lados.
- **Condiciones de la §13 del motor:**
  1. `volver` se valida con `new URL(volver, location.origin)`: mismo origin, pathname que empieza con `/mowa-mes/` y sin `//` al principio. Si no cumple, se ignora. Prueba con `//evil.com`, `https://evil.com/mowa-mes/`, `/mowa-mes/../cartera` y `javascript:`.
  2. Un `seleccion` que no existe deja Cartera vacía, como hoy, con un aviso. Nunca un error.
  3. Sin parámetros, Cartera, Columnas y Generar carga hacen lo mismo que hoy, y sus specs pasan sin cambiar lo esperado.
  4. Si el borrador no se puede leer o restaurar, la campaña arranca vacía sin romperse.
  5. E2E: ida y vuelta con «Guardar» y con «Guardar como nueva», «Volver sin guardar» y el `volver` inválido.
- **Lo hace `dev_frontend_modulo_mowa_mes`,** con la §13 del motor sobre `selector-seleccion.ts` y `cartera.astro`.
- **La campaña no tiene editor de filtros propio,** como decidió el usuario.

### 3.7 Iconografía (RF-MM-36)

El criterio ya está escrito por `designer` (T-MM-D11, `docs/mowa-mes-interfaz.md`, todavía en su worktree):
- §3: el catálogo de conceptos e iconos lucide, y los tamaños por contexto. En tiempo de ejecución, los iconos salen de `<template data-icono-*>`, y los tags lo llevan a 1,2em por CSS;
- §4.1: el límite mensual, con `gauge` en el título del panel y una barra de uso `aria-hidden`, accent hasta 90 %, signal de 90 % a 100 % y danger arriba.

Las reglas de interfaz de cada función nueva entran en su corte, cada una en el suyo:
- §4.2, las descartadas: M-F3;
- §4.3, los pendientes: M-F4;
- §4.4, «Para subir a MES»: M-F5;
- §4.5, las deshabilitadas: M-F2;
- §4.6, las confirmaciones: M-F2 y M-F3;
- §5, los textos: el corte que los use.

Los iconos de lo que ya existe van en cortes propios, uno por pantalla:
- M-F7a, el seguimiento, con el límite mensual primero;
- M-F7b, la campaña;
- M-F7c, la configuración.

### 3.8 Dónde está el id de MES (RF-MM-34)

**Bloqueado por S-MM-10:** falta saber cómo aparece el id en la web de MES. Va como último corte: un hint junto al campo, con el texto de `designer`.

## 4. Cortes

| Corte | Qué | Depende | Revisión | Costo |
|---|---|---|---|---|
| **M-B1** | §3.1 en el backend: migración `descartada_en`, el predicado `_ACTIVA`, los métodos, la API, los códigos e i18n, el contrato y `mowa-mes.md`. **Pruebas:** núcleo; API; `@postgres` por agregado (cargados, costo y listado), de la cascada al eliminar (incluido `reporte_fila`, y `usada_en` del speech sin cambio) y de la migración de ida y vuelta. **Mutación:** sin el predicado en un agregado, y eliminar una activa | — | yo; `architec` (`-ConBase`) | 2 |
| **M-B2** | §3.2 en el backend: migración `deshabilitada_en`; renombrar, deshabilitar, habilitar y eliminar; `speech_deshabilitado` en `armar`; los códigos y el contrato. **Pruebas:** núcleo, API y `@postgres` (unicidad al renombrar, y los tres motivos para no eliminar). **Mutación:** permitir eliminar una usada, y previsualizar con una deshabilitada | M-B1, por la cadena de migraciones | yo | 2 |
| **M-B3** | §3.3, la migración de datos a v2: convertidor y literal congelados, CHECK nuevo y downgrade exacto. **Pruebas:** convertidor contra app (200 sintéticos), oro byte a byte (con la autorización de `architec`) y `@postgres` de ida y vuelta. **Mutación:** sin `obligatoria` en el titular, y downgrade sin restaurar `expresiones = NULL` | M-B2 | yo; `architec` (y `auto_cusco` con permiso del usuario) | 2,5 |
| **M-F5** | §3.5, los datos para MES al crear, y `lib/portapapeles.ts` | — | yo; `designer` | 1,5 |
| **M-F4** | §3.4, pendientes de reporte y el enlace desde la campaña creada | — | yo; `designer` | 1 |
| **M-F3** | §3.1 en la pantalla: descartar, con la advertencia si tiene reporte; la sección de descartadas por mes («Octubre de 2026»); ver, restaurar y eliminar, con sus confirmaciones | M-B1 | yo; `designer` | 2,5 |
| **M-F2** | §3.2 en la pantalla: renombrar; deshabilitar y habilitar; la sección de deshabilitadas con vista de solo lectura del motor, habilitar y eliminar; el selector de la campaña sin las deshabilitadas | M-B2 | yo; `designer`; el motor (§13, por el editor en solo lectura) | 2,5 |
| **M-F1** | §3.3 en la pantalla: fuera la vista v1, «Convertir a v2», `obtenerComoV2`, el camino v1 de GSM-7 y las API falsas v1 | M-B3 en `main`, porque sin la migración las v1 quedarían sin vista | yo; `designer` | 1,5 |
| **M-B4** | §3.3: fuera la v1 del backend, `partes` pasa a `texto_v1`, sale `formato`, y el contrato se regenera | M-F1 | yo; el motor (§13, porque el speech usa el motor) | 1,5 |
| **M-F6** | §3.6, «Editar en Cartera»: `cargarGuardada` y `seleccionguardada` en el selector, los parámetros en `cartera.astro`, y el borrador y la vuelta en la campaña | el diseño acordado con el motor | yo; el motor (§13); `designer` | 2 |
| **M-F7a/b/c** | §3.7, iconos en el seguimiento (con el medidor del límite), la campaña y la configuración | `mowa-mes-interfaz.md` en `main` | `designer` | 1,5, 1 y 1 |
| **M-F8** | §3.8, el hint del id de MES | S-MM-10, el dato del usuario | `designer` | 0,25 |

## 5. Orden y costo

- **Backend, en cadena por las migraciones:** M-B1 → M-B2 → M-B3. Después, M-B4, cuando M-F1 ya esté en `main`.
- **Frontend, en paralelo:**
  - primero lo que no depende del backend: M-F5 y M-F4;
  - después M-F3 (sobre M-B1), M-F2 (sobre M-B2), M-F1 (sobre M-B3) y M-F6 (cuando esté el diseño con el motor);
  - los iconos (M-F7a, b y c), cuando `mowa-mes-interfaz.md` esté en `main`. Van después de los cortes de su pantalla, para no tocarla dos veces a la vez;
  - M-F8 al final, cuando el usuario dé el dato de S-MM-10.

**Costo: unos 23 días de agente, en 14 cortes.** Son 8 del backend y unos 15 del frontend. El plazo lo marca el frontend, unos 15 días con los dos devs en paralelo, más los turnos de máquina y las revisiones.

## 6. Decisiones para el usuario

### U-1. Importar un reporte de enviados a una campaña descartada

**Contexto.** Una campaña descartada queda fuera de todos los cálculos (RF-MM-31). Si llega su reporte de MES, ¿qué se hace? RF-MM-31 y RF-MM-32 no lo dicen.

| Opción | Qué cambia | Ventajas | Desventajas | Costo | Riesgo |
|---|---|---|---|---|---|
| **A. Rechazar, con «restáurala primero»** ✅ | La importación da 409 `campana_descartada` con ese texto | Es coherente con «fuera de todo». No hay datos guardados que no se ven en ningún lado. Si se envió de verdad, restaurarla es un clic y vuelve a contar | Un paso más si se descartó por error | Incluido en M-B1 | Bajo |
| B. Aceptar y seguir fuera de los cálculos | Se guarda el reporte, pero no suma | No bloquea nada | Datos invisibles en los totales, y una campaña enviada que no cuenta en el límite, en silencio | Igual | Medio: el límite subestimado sin aviso |
| C. Restaurarla sola al importar | Importar la devuelve a las activas | Cero pasos | Un efecto que nadie pidió, y deshace un descarte deliberado | Igual | Medio |

**Recomiendo A.** **Decidido: A (usuario, 2026-10-30).** RF-MM-31 ampliado en `docs/requerimientos-mowa-mes.md`.

### Otras decisiones, menores, que `designer` toma en sus cortes

- el texto de las confirmaciones (descartar, eliminar una campaña y eliminar una versión);
- el lugar de la sección de descartadas y de la de deshabilitadas;
- cómo se ve el panel de datos para MES.

## 7. Fuera de este plan

- RF-MM-36 en detalle: espera el criterio de `designer`.
- S-MM-10: el dato del usuario.
- Los pendientes de C9 y C10 que no son estos RF:
  - `resumen_filtro` a común;
  - el tope de 32 MB (D-2);
  - la fragilidad de `_motivo`;
  - los botones ↑↓ de `/supervisores`;
  - el aviso de transición.
