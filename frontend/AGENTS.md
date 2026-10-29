## Development

When starting the dev server, use background mode:

```
astro dev --background
```

Manage the background server with `astro dev stop`, `astro dev status`, and `astro dev logs`.

## Documentation

Full documentation: https://docs.astro.build

Consult these guides before working on related tasks:

- [Adding pages, dynamic routes, or middleware](https://docs.astro.build/en/guides/routing/)
- [Working with Astro components](https://docs.astro.build/en/basics/astro-components/)
- [Using React, Vue, Svelte, or other framework components](https://docs.astro.build/en/guides/framework-components/)
- [Adding or managing content](https://docs.astro.build/en/guides/content-collections/)
- [Adding styles or using Tailwind](https://docs.astro.build/en/guides/styling/)
- [Supporting multiple languages](https://docs.astro.build/en/guides/internationalization/)

## Helpers compartidos (`src/lib`, `e2e`)

Antes de escribir un helper en una página, busca aquí si ya existe:

- `lib/paginacion.ts`: `paginar` y `PaginaLocal`, paginación en el cliente de filas que la página ya tiene (no llama a la API), y `pintarPaginador(raiz, {desde, hasta, total})`, que pinta el `.pager` de toda tabla paginada (cliente o servidor): el rango, cada botón apagado en su borde, y oculto con una sola página. Marcado: `data-pager` con `data-page-prev`, `data-page-range` (con `aria-live`) y `data-page-next`; el estilo es el `.pager` de `ui.css`.
- `lib/dom.ts`: `$` (con `!`), `ocupado` (botón cargando) y `appendBreakable` (identificador con `<wbr>` tras cada `_`), para los scripts de las páginas. `cargas.astro` conserva su propio `$`, que devuelve `null`.
- `mensajeDeError` en `lib/api.ts`, junto a `ApiError`: la frase para el usuario ante un fallo (red, `detail` del servidor o genérica). `lib/generar-carga-mensajes.ts` tiene otra, con los códigos del motor, a propósito.
- `conJson(método, cuerpo, signal?)` en `lib/api.ts`: el `RequestInit` de una llamada con cuerpo JSON. Todo `api-*.ts` arma sus escrituras con él; no escribas otra copia.
- `traducirPorPrefijo(prefijo, codigo, respaldo)` en `lib/i18n.ts`: el texto de un código de un catálogo `<prefijo>.<codigo>`, o la frase del servidor si falta la clave. `traducirCodigo` (MOWA MES), `textoDeCodigo` (motor) y `mensajeProblema` (editor) son envoltorios de una línea. Un catálogo nuevo se suma con su prefijo, no con otra copia.
- `e2e/apoyo.ts`: `json(route, estado, cuerpo)` y `siguiente(cola)` (la respuesta guionada que repite la última) para toda API falsa y todo spec. `e2e/apoyo-seleccion.ts`: `montarSeleccion` y `seleccionFalsa`, las tres llamadas del selector compacto sobre la API falsa de un módulo. Están aparte para que `apoyo.ts` no importe las API falsas (sin ciclo).
- `lib/tabla-dom.ts`: lo que un script arma a mano para una tabla: `tabla(clase, columnas, {apilable})` (con su contenedor de scroll), `celda` (con la etiqueta de columna para cuando se apila), `celdaDeFila` (`th scope="row"`), `vacio` y `cifra` (con `apagada`). Los textos llegan ya traducidos.
- `.page`, `.page__head`, `.page__title` y `.page__intro` en `ui.css`: el marco de toda pantalla (columna del ancho del shell, centrada, con su gutter) y su cabecera. Una pantalla nueva abre con `<div class="page">`; lo propio va en su clase al lado (`class="page cl"`), nunca otra copia del marco. Las rejillas de cada pantalla (`.cartera__grid`, `.mm-plataforma`) no suben.
