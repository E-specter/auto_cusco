# Plan de la limpieza de duplicados de C9 (T-MM-C10)

> **Estado: cerrado el 2026-10-29.** Los 20 cortes están en `main`, de `616cd80` a `fff021d`. La revisión de cierre, con los hashes, las desviaciones y la verificación, está en [revision-c10.md](revision-c10.md).
>
> **Escrito el 2026-10-29 sobre `101e153`.** Es solo el plan: no hay código hasta que lo apruebe `architec`.
>
> **Decisión del usuario:** lo copiado y lo mal ubicado de C9 ([recapitulacion-c9.md](recapitulacion-c9.md) §C) se corrige antes del pulido de experiencia. Elecciones del 2026-10-29:
> - **E1-A:** supervisores y calendario pasan a dos entradas propias del menú.
> - **E2-A:** el reporte acepta los formatos de la sábana. RF-MM-20 se amplió en `101e153`.
> - **E3-A:** entran el paginador y las tablas unificados, y la estructura de página común.

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Desarrollan:
- los cortes `L-B*`: `dev_backend_modulo_mowa_mes`;
- los cortes `L-F*`: `dev_frontend_modulo_mowa_mes`.

Cada encargo va con `notify_when_idle`.

---

## 1. Reglas de todos los cortes

- **Refactor puro, salvo donde se declara.** No cambia nada visible ni del contrato:
  - `exportar_openapi --comprobar` sin diferencias;
  - las claves i18n intactas, con el `git diff` de `es.json` y `en.json` vacío;
  - las pruebas de oro y las huellas 17 y 92 sin tocar.
  Las pruebas existentes solo cambian imports o rutas, y cada cambio de aserción se justifica en la entrega.
- **Lo que cambia a propósito** se declara en su corte, con la prueba que lo fija: E1, E2, E3 y los casos que hoy no se alcanzan.
- **Un corte es un commit,** y queda en verde por sí solo.
- **Mutación a mano** sobre lo extraído, en una copia desechable y nunca en el árbol compartido.
- **Motor.** Lo que toque `texto_enriquecido`, las selecciones, las definiciones, la segmentación o las API falsas del motor pasa por `coordinador_herramientas_implementadas` antes de llegar a `architec`, igual que su §13 conmigo.
- **Las pantallas generales** que toque cada corte (Cartera, Cargas, Columnas y Generar carga) corren su spec en el turno del corte.
- **Turnos de máquina:**
  - lo liviano va sin turno: ruff, pytest por archivos, Vitest, `astro check`, `npm run tipos` y `contrato:comprobar`;
  - lo pesado, con turno pedido a `architec` y 2 GB libres: pytest completo, Playwright y las mutaciones;
  - los devs no corren `@postgres`: es `-ConBase` de `architec`.

## 2. Lo que encontré al contrastar el alcance con el código

Cambia el alcance base en cuatro puntos:

1. **`fecha_en_lima` no es `hoy_en_lima`.** `fecha_en_lima(momento)` (`campana.py:194`) recibe el momento del reloj inyectable, y toma como hora de Lima un momento sin zona. `hoy_en_lima()` (`fecha_envio.py:42`) no recibe nada. Reemplazar una por otra rompería el reloj falso de las pruebas.
   - **Corrección:** `fecha_en_lima` pasa a `fecha_envio.py`, junto a `hoy_en_lima`, que se define con ella. Es puro: `ahora_en_lima()` ya trae zona.
2. **El saneador del nombre de archivo no es una copia.**
   - El de MES (`nombre_archivo.py:44`, `_PROHIBIDOS`) solo quita lo que prohíbe Windows y los caracteres de control. Conserva tildes, «ñ» y espacios.
   - El de `exportadores/comunes.py:20-35` pasa a ASCII, cambia los espacios por `_`, corta en 80 caracteres y vive en `adapters`, que el núcleo no puede importar.
   - Usarlo **cambiaría los nombres de los archivos de MES**, así que no es un refactor puro. **Lo saco de la base:** son dos políticas distintas, y lo desarrollo como E4 en §7.
3. **El paso de GSM-7 es privado.** El NFD sin marcas está dentro de `_caracter` (`gsm7.py:102-106`). Para que la conciliación lo importe, el motor tiene que exponerlo como una función pública. Corte del motor.
4. **El lector va en dos cortes.** Primero, lo puro: el lector general, con solo `.xlsx` y los mismos errores. Después, E2: los demás formatos. Así, si E2 hubiera que revisarlo, lo puro ya entró.

Verificado, sin cambio de alcance:
- las 4 copias de `vacia` y `_vacio` son equivalentes (`== ""` después de `strip()` es lo mismo que `not strip()`);
- `mensajeDeError` está 5 veces y `ocupado` 4, idénticos;
- `conJson` es idéntico, salvo el de `api-archivos-carga.ts:22`, que tiene el método fijo en POST;
- `textoDeCodigoDelMotor` es copia literal de `textoDeCodigo`;
- el WhatsApp se valida al guardar la configuración (`configuracion.py:105, 246, 267`) y en la petición de campaña (`campana.py:506`, `whatsapp_valido`). Un número inválido nunca llega a armar el enlace.

## 3. Cortes del backend (`dev_backend_modulo_mowa_mes`)

| Corte | Qué | Archivos | Capas | Mutación | Revisión | Costo |
|---|---|---|---|---|---|---|
| **L-B1** | `vacia` y `normalizar_nombre`, cada uno con su hogar en el núcleo | Nuevos: `core/entities/valores.py` (`vacia`) y `core/entities/nombres.py` (`normalizar_nombre`). Se borran las copias de `campana.py:199`, `segmentacion.py:52`, `lector_reporte_mowa_mes.py:29`, `adapters/input/celdas.py:7` (que la importa del núcleo), `entities/definiciones_columnas.py:24`, `repositorio_selecciones_postgres.py:26` y `repositorio_mowa_mes_postgres.py:32`. Cambian los imports de `repositorio_definiciones_postgres.py` y `definiciones_columnas/servicio.py` | Nú, Ad, ruff. PG: los nombres únicos de selecciones, definiciones y versiones de speech, con `-ConBase` | `vacia` sin `strip()`; `normalizar_nombre` sin `casefold()` | Motor: selecciones, definiciones y segmentación son suyas | 0,5 |
| **L-B2** | `fecha_en_lima` junto a `hoy_en_lima` | `campana.py:194`, que se borra, y sus 3 usos (`:320`, `:458`, `:478`); `services/fecha_envio.py` | Nú: campaña con reloj falso, sin zona y con zona | Ignorar `tzinfo` | — | 0,25 |
| **L-B3** | El lector del reporte usa `normalizar_cabecera` del mapeador | `lector_reporte_mowa_mes.py:24-26`, que se borra, y se importa `mapeador/similitud.py:29` | Ad: las 8 de `test_lector_reporte_mowa_mes.py` sin cambios, más una nueva, en la que cada columna de `COLUMNAS_REPORTE` con mayúsculas, tildes y espacios dobles se sigue encontrando | No normalizar | — | 0,25 |
| **L-B4** | `numero_valido` a un módulo común, y el enlace de WhatsApp del motor | Nuevo: `core/entities/telefono.py` (`numero_valido`, RF-02). Se borra de `gestiones_digitales/supervision.py:25`, y cambian los imports de `supervision.py:65`, `campana.py:231`, `speech.py:65` y `:636` y `funciones/enlaces.py:4`. El motor expone `enlace_whatsapp(telefono, prefijo=PREFIJO_WHATSAPP)`, hoy privado en `enlaces.py:11`. Se borra `speech.py:139-140`, y `speech.py:545` usa la del motor. Una prueba de arquitectura dice que el motor no importa `gestiones_digitales` | Nú: speech, **oro** (sin cambios: las huellas 17 y 92 y los mensajes v1 son iguales), motor y supervisión. API: speech | El enlace sin prefijo; `numero_valido` con 8 dígitos | **Motor** (`enlaces.py`) | 0,75 |
| **L-B5** | `normalizar_mensaje` de la conciliación usa el paso de GSM-7 | `gsm7.py` expone `sin_marcas(texto)` (NFD sin combinantes), que usan `_caracter` y `conciliacion.py:36-39`. Esta conserva su `.strip()` | Nú: conciliación (17) y las de GSM-7 del motor sin cambios | `sin_marcas` no quita los combinantes | **Motor** (`gsm7.py`) | 0,25 |
| **L-B6** | El ayudante de la prueba espejo de i18n | Nuevo: `tests/ayudas/espejo_i18n.py` (`claves_de(prefijo)` y `assert_cubre(enum, prefijo)`, que leen `frontend/src/i18n/*.json`). Se migra `test_codigos_mowa_mes.py`, que no es de oro, y se ofrece al motor para las suyas | Nú: las pruebas | Borrar una clave en `es.json`: la prueba falla y nombra la clave | — | 0,5 |
| **L-B7** | El lector del reporte sobre `LectorTablaPort`, la parte pura | `LectorReporteMowaMes` recibe un `LectorTablaPort` y aplica encima las 8 columnas, `_dni`, `_fecha` y `_mes_id`. `LectorReportePort.leer(contenido, nombre_archivo)`, y `reportes.py:54` pasa el nombre, que la API ya tiene (`mowa_mes_campanas.py:1036`). **Sigue solo `.xlsx`:** otra extensión da el mismo `ReporteInvalido` de hoy. Los errores del lector general se traducen a `ReporteInvalido` con los textos de hoy | Ad: las 8 sin cambios, más «otra extensión se rechaza igual». API del reporte. PG: la conciliación, con `-ConBase`. Sin diferencias en OpenAPI | No traducir el error; aceptar otra extensión | — | 1 |
| **L-B8** | **E2-A:** los formatos de la sábana | Se quita la exigencia de `.xlsx`. El lector general reconoce el formato por su contenido, con las opciones por defecto. **Primera hoja, como dice RF-MM-20:** por defecto el lector general elige `VENCIDA` si existe, así que el de MES vuelve a leer con la primera hoja si la elegida es otra. `_dni`, `_fecha` y `_mes_id` aceptan también texto, porque el CSV trae todo como texto. Cambia la descripción del `File` en la API y se regenera el contrato, **declarado** | Ad: el mismo reporte sintético en `.xlsx` y en `.csv` (con `;` y con `,`, y en UTF-8 y Latin-1) da las mismas `FilaReporte`. `.xlsb`, `.xls` y `.ods` los cubren las pruebas del lector general. API. Co | Tomar la hoja por defecto; perder los ceros del DNI en CSV | — | 1 |
| **L-B9** | `division.py` a común | Nuevo: `core/services/division_archivos.py`, con `dividir(filas, escribir, max_filas, max_bytes)`, `previstos_por_filas` y `tramos_por_filas`, genéricos sobre un `Protocol`. `plataformas/mowa_mes/division.py` queda como un envoltorio con los números de MES (`entities/mowa_mes.py:132-134`) y la supervisión en el primer archivo | Nú: división (7) y campaña. PG: la creación con división real, en `test_mowa_mes_campanas_postgres.py`, con `-ConBase` | Las de la división: el corte por bytes, el corte recursivo y el tope de filas | — | 1 |

**Total del backend: unos 5,5 días de agente.**

## 4. Cortes del frontend (`dev_frontend_modulo_mowa_mes`)

### 4.1 Base

| Corte | Qué | Archivos | Pantallas generales | Capas | Mutación | Revisión | Costo |
|---|---|---|---|---|---|---|---|
| **L-F1** | `$`, `ocupado`, `appendBreakable` y `mensajeDeError` a `lib/` | Nuevo: `lib/dom.ts` (`$`, `ocupado`, `appendBreakable`) y `mensajeDeError` en `lib/api.ts`, junto a `ApiError`. Cambian `campana.astro`, `configuracion.astro`, `seguimiento.astro`, `columnas.astro`, `cartera.astro` (`$`), `cargas.astro` (`appendBreakable`; su `$` sin `!` **se queda**, porque no es la misma) y `scripts/selector-seleccion.ts` | Columnas, Cartera, Cargas; y Generar carga, por el selector | Ti, Vitest (`mensajeDeError`: red, `detail` y genérico), E2E de las 3 de MOWA y las 4 generales, A11y sin cambios | `mensajeDeError` ignora `detail` | Motor (`selector-seleccion.ts`) | 1 |
| **L-F2** | `conJson` exportado de `api.ts` | Se borra de `api-mowa-mes.ts:70`, `api-definiciones.ts:23`, `api-mapeador.ts:21` y `:35`, `api-archivos-carga.ts:22` (pasa a `conJson('POST', …)`) y `api-texto-enriquecido.ts:48`; `api.ts:249` lo usa | Columnas, Cargas (el mapeador), Generar carga y el editor | Ti, Vitest de API, E2E de esas pantallas | Sin `content-type` | **Motor** (sus `api-*`) | 0,5 |
| **L-F3** | `paginar` a `lib/paginacion.ts` | `mowa-mes.ts:284-322`, que solo usa `campana.astro` | — | Vitest (cambia el import en `mowa-mes.test.ts`), E2E de la campaña | Un desborde de la última página | — | 0,25 |
| **L-F4** | `traducirPorPrefijo(prefijo, codigo, respaldo)` | En `lib/i18n.ts`. `traducirCodigo` (`mowa-mes.ts:115`), `textoDeCodigo` (`generar-carga-mensajes.ts:28`) y el de `scripts/editor-texto.ts:172` quedan como envoltorios de una línea, así sus llamadas no cambian. Se borra `textoDeCodigoDelMotor` (`mowa-mes-speech-v2.ts:99`), que pasa a `textoDeCodigo` | Generar carga y el editor | Ti, Vitest (las pruebas espejo de i18n sin cambios), E2E de speech-v2, Generar carga y el editor | Ignorar el prefijo | **Motor** | 0,5 |
| **L-F5** | `e2e/apoyo.ts` | `json`, con 13 copias; `siguiente`, con 4 (`api-falsa-mowa-mes.ts:743`, `api-falsa.ts:210`, `api-falsa-definiciones.ts:272` y `api-falsa-archivos-carga.ts:170`); y `montarSeleccion`, con 4 (`accesibilidad.spec.ts:55` y 3 specs de MOWA) | Todas, solo en las pruebas | Ti (`tsc` cubre e2e), Playwright completo en la verificación de `architec` | `json` sin `content-type`: los specs fallan | **Motor** (sus API falsas) | 0,75 |
| **L-F6** | La fuga de `.stat__value.muted` | Pasa de `mowa-mes.css:565` a `ui.css`, junto a `.stat__value` (`:486`). Es de `designer` | Las que usan `.stat` | E2E con axe de la campaña y del seguimiento. Sin cambio visible | — | `designer` | 0,25 |

### 4.2 E1-A: supervisores y calendario, fuera de MOWA MES

| Corte | Qué | Costo |
|---|---|---|
| **L-F7** | **Rutas propuestas:** `/supervisores` y `/calendario`. Son las mismas raíces que su API (`/supervisores`, `/calendario/*`), y siguen la forma de `/columnas` | 3,5 |

Lo que hace L-F7:
- **Menú:** dos entradas nuevas en la sección `configuracion` de `lib/navegacion.ts:97-100`, después de «Columnas de carga»: «Supervisores» y «Calendario laboral», con claves `nav.supervisores` y `nav.calendario`. Los textos los fija `designer`.
- **Páginas nuevas:** `pages/supervisores.astro` y `pages/calendario.astro`, con lo que hoy está en `configuracion.astro`:
  - supervisores: unas 330 líneas (`:175` y `:837-1166`);
  - calendario: unas 230 (`:344` y `:1825-2053`).
- **Lógica:** sale de `mowa-mes.ts:164-282` (`BorradorSupervision`, `renombrarProcedencia`, `accionDia`…) a `lib/supervision.ts` y `lib/calendario.ts`.
- **API:** sale de `api-mowa-mes.ts:105-112` y `:142-151` a `lib/api-supervision.ts` y `lib/api-calendario.ts`. La campaña, que pide los supervisores por defecto, cambia solo el import.
- **CSS:** `.mm-lista`, `.mm-fila`, `.mm-mover`, `.mm-supervisores__*` y `.mm-calendario__*` salen de `mowa-mes.css` a `styles/supervisores.css` y `styles/calendario.css`, sin el prefijo `mm-`. El aspecto no cambia.
- **i18n:** `mowaMes.supervisores.*` pasa a `supervisores.*` y `mowaMes.calendario.*` a `calendario.*`. Es un renombre mecánico, el mismo en es y en. Lo vigilan dos pruebas: la de paridad es/en, y una nueva que exige que no quede ninguna clave `mowaMes.supervisores` ni `mowaMes.calendario`.
- **MOWA MES › Configuración** se queda con el límite, el WhatsApp, la tarifa, los límites por archivo, la plantilla y el speech. Suma un `.notice--info` con los enlaces a las dos pantallas; el texto lo pone `designer`.
- **Pruebas:**
  - lo de supervisores y calendario de `mowa-mes-configuracion.spec.ts` pasa a `supervisores.spec.ts` y `calendario.spec.ts`. Las aserciones son las mismas y cambian la ruta y el selector raíz;
  - sus rutas falsas salen de `api-falsa-mowa-mes.ts` a `api-falsa.ts`;
  - `accesibilidad.spec.ts` gana los estados de las dos pantallas y conserva los de la configuración de MOWA;
  - una prueba de navegación muestra las dos entradas nuevas y marca la activa.
- **Cambio visible, declarado:** dos entradas en el menú, dos pantallas y el aviso con enlaces. Lo aprueba `designer` con capturas antes del commit.
- **Capas:** Ti, Vitest de las lógicas movidas (cambian los imports), E2E de las pantallas nuevas y de la configuración de MOWA, y A11y en claro, oscuro y 360 px.
- **Mutación:** la entrada del menú sin marca de activa; una acción de calendario que no se guarda.
- **Riesgo:** medio. Mueve rutas, navegación, specs y docs: `mowa-mes.md` §2 y §3, y `modules.md`.

### 4.3 E2-A en la pantalla

| Corte | Qué | Costo |
|---|---|---|
| **L-F8** | El `<input type="file">` del seguimiento deja de limitarse a `.xlsx`: su `accept` pasa a los formatos de RF-57. Su hint cambia de texto, a cargo de `designer`. La API falsa acepta un `.csv`. Va después de L-B8. **Cambio visible, declarado.** Capas: E2E del seguimiento, con importar un `.csv` sintético, y A11y | 0,5 |

### 4.4 E3-A, con `designer`: el paginador, las tablas y la estructura de página

| Corte | Qué | Costo |
|---|---|---|
| **L-F9** | **El paginador unificado** en `lib/paginador.ts`, para `cartera.astro:671`, `cargas.astro:919`, `campana.astro:956` y `seguimiento.astro:439`. Unifica los atributos (`data-rango` frente a `data-page-range`) y el texto «desde–hasta de total» (`console.incidencias.range`) | 2 |
| **L-F10** | **Las tablas** en `lib/tabla-dom.ts`: `tabla(clase, columnas, {apilable})`, `celda`, `vacio` y `cifra`. Las usan la campaña, el seguimiento, Cartera (`celda` y `vacio`) y `campos-adicionales-gestion.ts:71`. Las variantes de hoy pasan a parámetros, como `celda` con la etiqueta de columna para apilar, o `cifra` con `apagada` | 1,5 |
| **L-F11** | **La estructura de página común** en `ui.css`. El nombre de las clases lo decide `designer`, por ejemplo `.pagina`, `__head`, `__title`, `__intro` y `__grid`. Reemplaza las 5 copias: `mowa-mes.css:9-60`, `console.css:9`, `cartera.css:8-47`, `generar-carga.css:8` y `columnas.css:20` | 2 |

Detalle de E3:
- **El aspecto final lo decide `designer`:** el del paginador unificado y el de la clase de página. Lo aprueba con capturas antes y después del commit.
- **El proyecto no tiene regresión visual automatizada.** Las capturas de `designer` son la comprobación, y se dice al reportar.
- **Pantallas generales:** Cartera, Cargas, Columnas, Generar carga, la campaña, el seguimiento y la configuración de MOWA.
- **Capas:** Ti, Vitest de las piezas nuevas (el rango del paginador y las variantes de `celda`), E2E de las 7 pantallas y A11y.
- **Las aserciones de los specs** cambian solo en los selectores del paginador, si se unifican los atributos, y cada cambio se justifica.
- **Mutación:** el rango del paginador desplazado en uno; `celda` sin la etiqueta de columna.
- **Riesgo:** medio. Es lo más visible del plan.

**Total del frontend: unos 12 días de agente**, entre la base (3,25), E1 (3,5), E2 (0,5) y E3 (5,5).

## 5. Orden

Tomo el orden de `architec` con dos ajustes:
- el backend y el frontend avanzan **en paralelo**, porque son devs distintos y la máquina igual ordena las corridas pesadas;
- E2 en la pantalla (L-F8) espera a L-B8.

| Paso | Backend | Frontend | Por qué en este orden |
|---|---|---|---|
| 1 | L-B2, L-B3, L-B1, L-B5, L-B4, L-B6 (la base) | L-F3, L-F1, L-F2, L-F4, L-F5, L-F6 (la base) | Lo de menor riesgo primero. L-B1 va antes del lector porque toca su `_vacia`. L-F3 va antes de L-F1, porque los dos tocan la campaña |
| 2 | L-B7 y después L-B8 (el lector y E2) | L-F7 (E1) | E1 va después de L-F1, porque mueve código de la configuración que L-F1 ya limpió |
| 3 | L-B9 (la división) | L-F8 (E2 en la pantalla), cuando entre L-B8 | |
| 4 | — | L-F9, L-F10 y L-F11 (E3, con `designer`) | Al final, porque cambia lo visible en 7 pantallas y conviene sobre todo lo anterior ya en `main` |

**Entregas a `architec`.** Para gastar menos turnos de verificación, junto cortes en una sola entrega, cada uno con su commit:
- backend: (1) la base, (2) L-B7 y L-B8, (3) L-B9;
- frontend: (1) la base, (2) L-F7, (3) L-F8, (4) E3.

**Camino crítico: el frontend, con unos 12 días.** El backend termina hacia el día 5 o 6.

## 6. Costo total

**Unos 17,5 días de agente:** 5,5 del backend y 12 del frontend. Con los dos devs en paralelo, el plazo lo marca el frontend, unos 12 días, más los turnos de máquina y las revisiones de `designer` y del motor.

Coincide con lo que estimó C9 (§C.3): limpieza barata, lector y división, unos 8-10 días; supervisores y calendario, 4-5; el paginador, las tablas y el CSS, 3-4.

## 7. E4, una decisión nueva para el usuario: el saneador del nombre de archivo

**Decidido: A (usuario, 2026-10-29).**

**Contexto.** C9 lo dio por duplicado, y no lo es: son dos políticas.
- Los archivos de MES se nombran con la plantilla del usuario (RF-MM-25). El saneador de MES solo quita lo que Windows prohíbe y los caracteres de control, así que un nombre como «Campaña_Preventiva 1.xlsx», sintético, queda tal cual.
- El saneador común es para los archivos de las definiciones y para las cabeceras HTTP. Pasa a ASCII, cambia los espacios por `_` y corta en 80 caracteres.

| Opción | Qué cambia | Ventajas | Desventajas | Costo | Riesgo |
|---|---|---|---|---|---|
| **A. Dejar los dos** ✅ | Nada | Cada saneador hace lo suyo, y los nombres de MES siguen como el usuario los escribió | Quedan dos funciones parecidas, con un comentario que explique por qué | 0 | Ninguno |
| B. Usar el común en MES | Los nombres de los archivos de MES pierden las tildes y la «ñ», cambian los espacios por `_` y se cortan en 80, no en 120. Hay que cambiar RF-MM-25 y unas 46 pruebas del nombre | Una sola política de nombres | Es un cambio visible para quien busca el archivo en MES. Y el saneador común tendría que moverse al núcleo | 1 | Medio |
| C. Extraer solo la clase de caracteres prohibidos | Nada visible: una expresión regular común | Una línea menos repetida | Casi no aporta | 0,25 | Bajo |

**Recomiendo A.** No hay duplicación de comportamiento, y B cambia algo que el usuario ve en MES sin que nadie lo haya pedido.

## 8. Fuera de este plan

- Hasta que haya un segundo canal: la plantilla del nombre, las tablas de campañas y las versiones de speech.
- El pulido de experiencia de C9 (P-1 a P-5): va después de esta limpieza.
- Para esa pasada de pulido: en `/supervisores`, los botones ↑ y ↓ siempre presentes, con el del borde `disabled`, el mismo criterio de «Subir/Bajar» de F3. Hoy cambian de lugar entre filas porque el que no puede moverse se oculta (`visibility: hidden`). Venía así desde la configuración, así que no es un defecto de L-F7.
- La corrección de C9 sobre D-1 va en `recapitulacion-c9.md`, en este mismo commit.
