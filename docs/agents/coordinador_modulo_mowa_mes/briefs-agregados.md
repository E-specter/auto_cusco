# Briefs de los agregados del 2026-09-28 (RF-MM-23 a RF-MM-26)

Encargos listos para enviar apenas estén abiertas las sesiones `dev_frontend_modulo_mowa_mes` y `dev_backend_modulo_mowa_mes`. El contexto está en `plan.md` §5. Los requerimientos son `requerimientos-mowa-mes.md`, RF-MM-23 a 26 (`93b7ca6`), con las notas de `architec` sobre D-1 a D-3.

## Reglas comunes a los dos

- **No commitean.** Entregan al coordinador: lista de archivos completos y parciales, capas corridas con su base, y las que quedaron fuera con el motivo.
- **Mutaciones:** solo en un worktree o una copia, nunca en el árbol compartido.
- **Base de datos:** las pruebas postgres van contra `auto_cusco_test` (`verificar.ps1 -ConBase`). Nadie escribe en `auto_cusco`, y un valor desconocido se reporta, no se restituye.
- **Playwright:** con `$env:PLAYWRIGHT_PUERTO` en un puerto libre y en un worktree desde HEAD.
- **Informes:** dicen la base usada y el desglose de `--list` por archivo.
- **Datos:** sin teléfonos ni documentos en código, pruebas, documentación ni mensajes, salvo el rango sintético `900000xxx`.
- **Archivos compartidos:** `ui.css`, `api.ts`, `navegacion.ts`, `Navegacion.astro`, los componentes compartidos y `playwright.config.ts` son de `designer`. Lo que haga falta ahí se le pide a él.
- **i18n:** claves nuevas en un bloque `mowaMes.*` contiguo al final de `es.json` y `en.json`.

## F6-A: paginación de la previsualización (dev_frontend)

- **Base:** `93b7ca6` (o HEAD al empezar).
- **Qué hace:**
  - La muestra (20 filas) y las exclusiones (100) de la previsualización de `/mowa-mes/campana` se paginan de a 10 filas, con `.pager` de `ui.css`.
  - Solo se pagina lo que ya llegó: no se vuelve a pedir la previsualización.
  - La tabla de exclusiones muestra siempre el total de excluidos. Si pasan de 100, un aviso dice que solo se ven las 100 primeras y que la lista completa está en Seguimiento, después de crear la campaña.
  - Al recalcularse la previsualización, las dos tablas vuelven a la página 1.
- **Pruebas:**
  - Vitest para la lógica de paginación, que va en `src/lib`: bordes con 0, 10, 11, 20 y 100 filas.
  - Playwright para navegar páginas, el total, el aviso de más de 100 y la vuelta a la página 1 al recalcular.
  - Casos axe de la tabla paginada, en claro y oscuro.
  - Mutación en el worktree.
- **Visual:** con `designer`. El paginador ya existe; si hace falta algo más, se le pide a él.
- **Entrega:** `npm run verificar` completo en un worktree desde la base, con puerto propio.

## B8: tarifa, costos y nombre de archivos (dev_backend)

- **Base:** HEAD al empezar. Se commitea después de F6-A; si F6-A ya entró, se verifica sobre ese commit.

### Tarifa y costos (RF-MM-23 y RF-MM-24)

- **Tarifa:** `tarifa_sms` en la configuración del conector. Es `Decimal` mayor o igual a 0 con hasta 4 decimales, y vale `0.02` por defecto. Va en el `PUT` parcial: omitida conserva el valor, y `null` responde 422 porque no admite nulo.
- **Congelada en la campaña:** la campaña guarda la tarifa al crearse. Las campañas anteriores quedan con tarifa `NULL` y su costo no está disponible; no se les asigna la tarifa actual.
- **Costo estimado:** cargados × tarifa, con la supervisión incluida. Aparece en la previsualización y en el detalle y el listado de la campaña.
- **Costo real:** enviados según E-1 × la tarifa de la campaña. No se guarda: sale de la conciliación vigente y se recalcula con cada reemplazo del reporte. Sin reporte importado, viene como pendiente, con un campo que lo distinga de cero.
- **Costo del mes:** suma de los costos estimados de las campañas imputadas al mes, con la regla del límite (mes de la fecha de envío). Las campañas sin tarifa se omiten, y el resultado dice cuántas quedaron fuera. Va junto al consumo del límite.
- **Montos:** `Decimal` en todo el backend, nunca `float`. En el contrato viajan como texto decimal, igual que `/cartera`: los costos con precisión completa y la tarifa con sus decimales. Se guarda el valor exacto; el redondeo a 2 decimales, a la mitad hacia arriba, es solo de presentación.

### Nombre de los archivos (RF-MM-25)

- **Plantilla:** `plantilla_nombre_archivo` en la configuración, que vale por defecto `mowa_mes_campana_{campana}_{archivo}_de_{total}`, y opcional por campaña al crearla.
- **Variables:** `{campana}`, `{descripcion}`, `{fecha_envio}`, `{fecha_corte}` (en formato AAAA-MM-DD), `{archivo}`, `{total}` y `{cantidad}`. Una variable desconocida se rechaza con 400 y un detalle que dice cuál, tanto en la configuración como en la campaña. Una llave sin cerrar también se rechaza.
- **Resolución, en el núcleo:**
  1. Sustituir las variables.
  2. Reemplazar `\ / : * ? " < > |` por `_`.
  3. Recortar los espacios y puntos de los extremos.
  4. Limitar a 120 caracteres sin la extensión. El recorte se aplica a la parte de la plantilla, nunca al sufijo.
  5. Con más de un archivo y sin `{archivo}` en la plantilla, agregar `_{archivo}de{total}`.
  6. Si el resultado queda vacío, usar la plantilla por defecto.
  7. Agregar `.xlsx`.
- **Guardado:** cada archivo guarda su nombre resuelto en una columna nueva. Las campañas existentes se completan en la migración con el nombre actual, así que sus descargas no cambian.
- **Descarga:** `Content-Disposition` lleva `filename` en ASCII, con el criterio de `exportadores/comunes.py`, y `filename*` en UTF-8 (RFC 5987).
- **Previsualización:** trae el nombre del primer archivo. `{campana}` sale como un marcador visible y el nombre viene marcado como estimado si usa `{total}` o `{archivo}`. La respuesta de creación y el detalle traen los nombres reales.
- **Pruebas:** propiedades a mano sobre el saneamiento. Ningún resultado contiene caracteres prohibidos, ninguno pasa de 120 y dos archivos de la misma campaña nunca repiten nombre. Se cubren también las variables, los bordes (vacío, solo caracteres prohibidos, solo espacios y puntos, largo exacto de 120) y la variable desconocida.

### Condiciones

- **Migración:** una sola, con ida y vuelta (`upgrade`, `downgrade -1`, `upgrade`) y `alembic check` limpio.
- **Contrato:** `openapi.json` y `contrato-api.d.ts` regenerados en el mismo corte. Los 4xx cumplen la regla de `detail` obligatorio.
- **Documentación:** las cuatro decisiones técnicas quedan en `docs/mowa-mes.md`.
- **Mutaciones en el worktree:**
  - tarifa actual en lugar de la congelada;
  - `float` en lugar de `Decimal`;
  - costo real con cualquier estado;
  - sufijo recortado por el límite de 120;
  - variable desconocida aceptada.
- **Entrega:** `verificar.ps1 -ConBase` contra `auto_cusco_test`, más `contrato:comprobar`.

## Reglas de interfaz de `designer` (2026-09-28), vinculantes para F6-A y F6-B

- **Paginación (F6-A):**
  - `.pager` como en `/cartera`: anterior, `«1–10 de 20»` en `mono muted` y siguiente. Solo aparece si hay más de 10 filas.
  - El encabezado de exclusiones siempre muestra el total real con `formatNumber`.
  - Si pasan de 100, un `.notice--info` encima de la tabla: «Se muestran las primeras 100 de N. La lista completa estará en el seguimiento de la campaña después de crearla.»
  - Al recalcular, las dos tablas vuelven a la página 1. El foco solo se mueve si estaba en el paginador.
  - La lógica, pura, va en `src/lib/mowa-mes.ts`.
- **Montos (F6-B):**
  - `formatSoles` (siempre 2 decimales) y `formatTarifa` (entre 2 y 4 decimales) de `format.ts`. Son de `designer` y ya están commiteadas en `be80ac5`: F6-B arranca sobre ese commit o uno posterior.
  - Reciben texto y nunca pasan por `Number()`. El frontend no multiplica: los costos llegan calculados.
  - «No disponible» y «Pendiente del reporte» van en `muted`, como texto y no en la columna numérica.
- **Dónde va cada monto (F6-B):**
  - Previsualización: «Costo estimado» en `.mm-cifras`, con el hint «N SMS × S/ tarifa».
  - Tabla de Seguimiento: dos columnas `.num`, estimado y real.
  - Resumen del mes: en la misma línea que el límite, separado por «·».
  - Tarifa en Configuración: `input text` con `inputmode="decimal"`, hint, y error en `.field__error` anclado con `aria-describedby`. Sin `type=number`.
- **Plantilla (F6-B):**
  - Un campo mono y, debajo, las variables como botones `.btn--sm .btn--quiet` que se insertan en la posición del cursor.
  - «Nombre del primer archivo:» en mono.
  - El frontend **no recalcula** el nombre: lo trae el backend.
  - Las llaves desconocidas se pueden marcar en vivo contra la lista que manda el backend, pero el error final sale del 400 del backend: «{x} no es una variable…».

## Agregados a B8 que pide `designer`

- **Lista de variables:** la respuesta de configuración incluye las variables válidas de la plantilla, para que el frontend no las tenga escritas a mano.
- **Ejemplo en Configuración:** un `POST` de revisión de la plantilla, o la respuesta de guardarla, devuelve el nombre resuelto con datos de muestra. Configuración no tiene previsualización. Tiene que usar la misma función del núcleo, sin una segunda implementación.
- **Montos:** tarifa, costo estimado, costo real y costo del mes viajan como texto. El backend los calcula y el frontend no multiplica.

## Agregados aprobados por `architec` (2026-09-28)

- **`costo_estimado_estado`** (`calculado` o `no_disponible`), junto a `costo_real_estado` (`calculado`, `pendiente` o `no_disponible`). El frontend decide por el estado, nunca porque el monto venga `null`.
- **`campanas_sin_tarifa`: int** en el costo del mes.
- **`enviados_conciliados`:** conteo derivado de la campaña para calcular el costo real en el listado (ver `plan.md` §5.4).
- **Regla de interfaz de `designer` para F6-B:**
  - `calculado`: `formatSoles(costo)` en la columna `.num`.
  - `pendiente`: «Pendiente del reporte», en `muted`.
  - `no_disponible`: «No disponible», en `muted`, con `title` y `aria-description` «Campaña creada antes de guardar la tarifa».
  - Costo del mes: si `campanas_sin_tarifa` es mayor que 0, junto a la cifra va «no incluye {n} campañas sin tarifa».
  - Todos estos textos van en i18n es y en, dentro del bloque `mowaMes.*`.
