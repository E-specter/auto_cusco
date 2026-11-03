# Revisión de la limpieza de duplicados de C9 (T-MM-C10)

> **Cerrada el 2026-10-29.** Plan: [plan-c10.md](plan-c10.md), aprobado en `2833b04`. Partió de la decisión del usuario de corregir lo copiado y lo mal ubicado de [recapitulacion-c9.md](recapitulacion-c9.md) §C antes del pulido de experiencia, con las elecciones E1 a E4. Los 20 cortes están en `main`, de `616cd80` a `fff021d`, sin subir con `git push`.

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Revisores:
- `coordinador_herramientas_implementadas` revisó todo corte que tocaba su código o sus pantallas, como en la §13 de MOWA MES pero al revés;
- `designer` aprobó con capturas todo cambio visible.

## 1. Cortes

| Corte | Commit | Qué | Agente |
|---|---|---|---|
| L-B2 | `616cd80` | `fecha_en_lima` a `fecha_envio.py`, y `hoy_en_lima` se define con ella. Incluye el comentario de E4-A en `nombre_archivo.py` | dev_backend_modulo_mowa_mes |
| L-B3 | `ab68a25` | El lector del reporte usa `normalizar_cabecera` del mapeador | dev_backend_modulo_mowa_mes |
| L-B1 | `b9e4206` | `core/entities/valores.py` (`vacia`) y `nombres.py` (`normalizar_nombre`). Se borran 7 copias | dev_backend_modulo_mowa_mes |
| L-B5 | `168a29a` | `gsm7.sin_marcas` pública; la usa la conciliación | dev_backend_modulo_mowa_mes |
| L-B4 | `f73bc82` | `core/entities/telefono.py` (`numero_valido`, RF-02). `enlace_whatsapp` público del motor. El motor ya no importa `gestiones_digitales` | dev_backend_modulo_mowa_mes |
| L-B6 | `e466b08` | `tests/ayudas/espejo_i18n.py`. Se migra `test_codigos_mowa_mes.py` | dev_backend_modulo_mowa_mes |
| L-F3 | `f68445c` | `paginar` a `lib/paginacion.ts` | dev_frontend_modulo_mowa_mes |
| L-F1 | `2293745` | `lib/dom.ts` (`$`, `ocupado`, `appendBreakable`) y `mensajeDeError` en `api.ts` | dev_frontend_modulo_mowa_mes |
| L-F2 | `3f6e421` | `conJson` exportado de `api.ts`. Se borran 6 copias | dev_frontend_modulo_mowa_mes |
| L-F4 | `a0e17cf` | `traducirPorPrefijo` en `i18n.ts`. Se borra `textoDeCodigoDelMotor` | dev_frontend_modulo_mowa_mes |
| L-F5 | `52742b7` | `e2e/apoyo.ts` y `e2e/apoyo-seleccion.ts` | dev_frontend_modulo_mowa_mes |
| L-F6 | `5de6bfa` | `.stat__value.muted` pasa de `mowa-mes.css` a `ui.css` | dev_frontend_modulo_mowa_mes |
| L-B7 | `53fa0fa` | El lector del reporte sobre `LectorTablaPort`, la parte pura | dev_backend_modulo_mowa_mes |
| L-B8 | `73e72b1` | **E2-A:** el reporte acepta los formatos de la sábana (RF-57). Siempre se lee la primera hoja | dev_backend_modulo_mowa_mes |
| L-B9 | `c832f26` | `core/services/division_archivos.py` y su entidad. MOWA queda como envoltorio | dev_backend_modulo_mowa_mes |
| L-F7 | `46af2e7` | **E1-A:** `/supervisores` y `/calendario`, en la sección «Configuración» del menú | dev_frontend_modulo_mowa_mes |
| L-F8 | `18b8c50` | **E2-A en la pantalla:** el `accept` y el hint del seguimiento | dev_frontend_modulo_mowa_mes |
| L-F10 | `b9cf1e9` | **E3-A:** `lib/tabla-dom.ts` (`tabla`, `celda`, `celdaDeFila`, `vacio` y `cifra`) | dev_frontend_modulo_mowa_mes |
| L-F9 | `2f6b6cd` | **E3-A:** un solo `.pager` en `ui.css` y `pintarPaginador` en `lib/paginacion.ts` | dev_frontend_modulo_mowa_mes |
| L-F11 | `fff021d` | **E3-A:** `.page`, `.page__head`, `.page__title` y `.page__intro` en `ui.css` | dev_frontend_modulo_mowa_mes |

**E3 se verificó una sola vez.** Los tres cortes (L-F10, L-F9 y L-F11) se apilaron en ramas y se verificaron juntos, para que el usuario no tuviera que liberar memoria tres veces.

## 2. Qué se borró

- **Backend:**
  - 4 copias de `vacia`/`_vacio`/`_vacia`, que van a `valores.py`;
  - 3 de `normalizar_nombre`, que van a `nombres.py`;
  - la tercera variante de `normalizar_cabecera`;
  - el `enlace_whatsapp` de `speech.py`;
  - el paso NFD de la conciliación, que pasa a `sin_marcas`;
  - `fecha_en_lima` de `campana.py`;
  - la apertura de Calamine del lector del reporte, unas 20 líneas;
  - la lógica de división de `plataformas/mowa_mes/division.py`, que queda como envoltorio;
  - el recorrido propio del JSON de i18n en la prueba espejo de MOWA.
- **Frontend:**
  - `mensajeDeError` en 5 sitios y `ocupado` en 4;
  - `$` en 5 sitios; el de `cargas.astro`, sin `!`, se queda;
  - `conJson`, 6 copias;
  - `appendBreakable`;
  - `textoDeCodigoDelMotor`;
  - `json` (13 copias), `siguiente` (4) y `montarSeleccion` (4) de las pruebas e2e;
  - las funciones de tabla: 4 de la campaña, 4 del seguimiento, 2 de Cartera, y `vacio` de supervisores y de calendario;
  - 4 implementaciones del paginador y `.incidencias__pager`;
  - las 7 cáscaras de página: `.mm`, `.console`, `.cartera`, `.gc`, `.cl`, `.supervisores` y `.calendario`.
- **Configuración de MOWA MES:** las secciones de supervisores y de calendario salen a sus pantallas propias. `configuracion.astro` baja de unas 2105 líneas a unas 1372.

## 3. Cambios visibles, declarados y aprobados

- **E1, L-F7:**
  - dos entradas nuevas en el menú: «Supervisores» y «Calendario laboral»;
  - dos pantallas: `/supervisores` y `/calendario`;
  - un aviso de transición en MOWA MES › Configuración, con enlaces a las dos;
  - la tarjeta Plataforma a todo el ancho, en una rejilla `auto-fit`;
  - el panel del calendario titulado «Feriados y días no laborables»;
  - las claves `mowaMes.supervisores.*` y `mowaMes.calendario.*` pasan a `supervisores.*` y `calendario.*`.
- **E2, L-B8 y L-F8:**
  - el reporte acepta .xlsx, .xlsb, .xls, .ods, .csv, .tsv, .txt y .json, con la descripción del `File` cambiada en OpenAPI;
  - un archivo cuya extensión no coincide con su contenido, o un CSV o JSON ilegible, da el motivo del lector general;
  - el `accept` y el hint del seguimiento.
- **El paginador, L-F9:** a 1280 px queda igual. A 360 px, el rango va arriba y centrado y los botones debajo, uno en cada extremo; antes, «Siguientes» bajaba solo a otra línea. El rango lleva `aria-live="polite"`.
- **Columnas, L-F11:** toma la estructura común. Pasa de 80rem a `--shell-max`, el gap de `space-5` a `space-4` y el padding de `space-5 space-4 space-7` a `space-4 gutter space-6`. Con el editor abierto, la altura baja 60 px a 1280 y 52 px a 1920.
- **`.page__head` lleva siempre `align-items: flex-start`:** las cabeceras de Cartera y de Generar carga quedan idénticas byte a byte, comprobado con capturas antes y después.

## 4. Decisiones

- **Del usuario (2026-10-29):**
  - E1-A: supervisores y calendario en dos entradas propias;
  - E2-A: los formatos de la sábana, sin opciones en pantalla. RF-MM-20 se amplió en `101e153`;
  - E3-A: el paginador, las tablas y la estructura de página entran ahora;
  - E4-A: se quedan los dos saneadores de nombre de archivo.
- **De `designer`:**
  - los textos de E1 y del hint de E2;
  - los enlaces del aviso con `color: inherit` y subrayado;
  - Plataforma a todo el ancho;
  - el título del panel del calendario;
  - el marcado, el CSS y los atributos `data-page-*` del paginador;
  - los nombres `.page*`;
  - `align-items: flex-start` siempre;
  - Columnas con `.page` completo (opción A), porque los 80rem no tenían un porqué escrito;
  - la coma de miles de `formatNumber` se queda.
- **De `architec`:**
  - verificar E3 en una sola corrida;
  - la documentación va en el mismo corte que la cambia;
  - los turnos de máquina los lleva la cola del motor;
  - 4 GB libres para la cadena del frontend.

## 5. Desviaciones del plan

- **`fecha_en_lima` no se reemplazó por `hoy_en_lima`:** recibe el reloj inyectable. Se movió junto a `hoy_en_lima` (plan §2.1).
- **El saneador del nombre de archivo no era una copia:** el de MES conserva las tildes, la ñ y los espacios, como pide RF-MM-25. Salió de la base y pasó a ser E4. El usuario eligió A, dejar los dos, y queda un comentario en `nombre_archivo.py`.
- **La mutación del plan para L-F5, «`json` sin content-type», es equivalente:** el frontend no lee el content-type de ninguna respuesta. Se reemplazó por «`json` ignora el estado» y «`siguiente` no avanza», que sí se detectan.
- **`TELEFONO_VALIDO` vive en `core/entities/telefono.py`,** y `ingesta_sabana/reglas.py` lo importa, porque una entidad no puede importar un servicio.
- **El plan decía que hoy el lector del reporte aceptaba «solo .xlsx», y no era exacto:** ya abría cualquier hoja de cálculo que Calamine lee. L-B7 lo conserva.
- **E2 son 8 formatos y no 5,** porque RF-57 incluye CSV con tabulación y JSON.
- **`apoyo-seleccion.ts` va separado de `apoyo.ts`,** para evitar un ciclo de imports con `api-falsa.ts`.
- **`conJson('POST', …)` en `api-archivos-carga.ts` y en `api-texto-enriquecido.ts`,** que tenían el método fijo.
- **`mensajeDeProblema` del speech v2 también usa `traducirPorPrefijo`.**
- **En L-F7, las clases `mm-*` que usaba la campaña para sus supervisores pasan a `supervisores-*`,** y `campana.astro` importa `supervisores.css`. `moverElemento` vive en `lib/supervision.ts`.
- **`pintarPaginador` acepta `null`,** para una página vacía del seguimiento. La campaña y el seguimiento conservan, junto a `data-pager`, el atributo que distingue a cada uno de sus dos paginadores.
- **Columnas es `<div class="page cl">` y no `<main class="page columnas">`:** el Shell ya trae un `<main>`, y `.columnas` es una clase de Cartera. Mi inventario para `designer` le había atribuido mal esa regla.
- **La consola toma solo `.page` y no `.page__head`,** porque no tiene una cabecera propia: su h1 es el de la regla de fechas.

## 6. Verificación

- **Por los devs, en cada corte y en turno de máquina:**
  - backend: ruff, `exportar_openapi --comprobar` y pytest completo; la base dio entre 3474 y 3517, y L-B7 a L-B9 entre 3606 y 3618;
  - frontend: contrato, tipos, `astro check`, Vitest (de 1093 a 1149) y Playwright, con 1 worker, de los specs que tocaba cada corte;
  - mutaciones: 9 en la base del backend, 8 en L-B7 a L-B9, 9 en la base del frontend, 4 en L-F7, 2 en L-F8, 1 en L-F10, 4 en L-F9 y 2 en L-F11. Todas detectadas.
- **Por `architec`, sobre cada entrega:**
  - backend: `verificar.ps1 -ConBase`, con 166 `@postgres` (entre ellas las de selecciones, definiciones, configuración y campañas que pedía L-B1) y `alembic check`;
  - frontend: contrato, tipos, `astro check`, Vitest, build de producción y Playwright completo. Dio 764/764 sobre `c832f26`, 805/805 sobre `18b8c50` y 860/860 sobre `fff021d`;
  - el texto final del hint de L-F8 lo cubrió su Playwright completo, porque la corrida del dev la cortó la memoria.
- **Pruebas de oro y huellas 17 y 92:** intactas en todos los cortes.
- **No se corrió:** WSL y el CI de Linux, que quedan para el CI de GitHub al subir. El proyecto no tiene regresión visual automatizada: las capturas de `designer` hicieron de comprobación.

## 7. Lo que encontró la revisión

- **Un espacio perdido en el aviso de L-F7:** Astro comprimía el espacio entre `<span>` y `<a>`. Se corrigió con `{' '}`, y ahora `toHaveText` fija el aviso completo en es y en.
- **`LectorFalso` de `test_mowa_mes_campana.py`** no aceptaba el parámetro nuevo del puerto. Lo atrapó el pytest completo de L-B7; en la corrida liviana se había saltado ese archivo.
- **Teléfonos fuera del rango sintético en `test_telefono.py`:** los atrapó `test_datos_sinteticos`, y ahora son 900000xxx.
- **El inventario de la estructura de página que le pasé a `designer`** atribuía mal `.columnas`. Lo encontró el dev, y `designer` decidió de nuevo con la información correcta.
- **El coordinador del motor precisó en L-F11** que las reglas no eran exactas en todo, por `align-items` y por el gap y el padding de Columnas. Se declaró con capturas y medidas.
- **Memoria:** una corrida de L-F8 se cruzó con otro Playwright del árbol principal, que no era de MOWA, y otra la cortó el sistema. No se relanzó sin avisar. Para el Playwright completo de `architec`, el usuario cerró Chrome y Excel.

## 8. Fuera a propósito

- **Hasta que exista un segundo canal:** la plantilla del nombre de archivo, las tablas de campañas y las versiones de speech, como dice C9 §C.2.
- **El GSM-7 del frontend, los costos y la conciliación** siguen en MOWA. Se extraen cuando haya otro SMS.

## 9. Pendiente

- **Pasada de pulido,** C9 P-1 a P-5, más:
  - los botones ↑↓ de `/supervisores` siempre presentes, el del borde `disabled` (plan-c10 §8);
  - quitar el aviso de transición de la configuración de MOWA: lo decide `designer`.
- **Observación de `architec` sobre el lector del reporte:** `_motivo` reconoce los errores del lector general por el texto del mensaje. No rompe, porque cae en el motivo general, pero es frágil. Si el lector general llega a distinguir las causas con un código, conviene usarlo.
- **El segundo conector:** cambia `supervisores.intro`, que hoy nombra MOWA MES (anotado en `modules.md`).
- **C9 D-1:** importar el reporte de una campaña nuestra, cuando haya un envío real.
- **C9 D-2:** el tope de 32 MB del reporte sigue igual; se revisa cuando se sepa cuánto pesa un reporte mensual real.
- **`git push`** de los 20 commits.
