# Revisión de la descripción de campaña de hasta 100 caracteres y el botón «Copiar» (T-MM-C6)

> **Revisada el 2026-10-27.** RF-MM-04 ampliado el 2026-10-27: el campo «Descripción de Campaña» de MES admite 100 caracteres, lo que cierra el supuesto S-MM-3, y el usuario pidió un botón «Copiar» al costado del campo.
> - **T-MM-B10** (backend): en `21ccaf6`, sin push.
> - **T-MM-F9** (frontend): revisado, sin commit, rebasado sobre `21ccaf6`.

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Requerimiento: `requerimientos-mowa-mes.md` RF-MM-04 (`9fc0647`).

## 1. Cortes

| Corte | Dónde | Contenido | Agente | Mi revisión |
|---|---|---|---|---|
| **T-MM-B10** | `21ccaf6`; 7 archivos | Un validador rechaza con 422 si `largo_utf16(descripcion.strip()) > 100`. `descripcion_sugerida` se acorta por filtros enteros, o queda en 97 + `...`. Contrato con el tope y la unidad. `mowa-mes.md` §18 | dev_backend_modulo_mowa_mes | completa |
| **T-MM-F9** | `auto_cusco_mowa_f9`, rama `mowa-f9-copiar`, sobre `21ccaf6`; 7 archivos modificados y 2 nuevos | `maxlength="100"`, contador «N/100», botón «Copiar» con respaldo `execCommand`, aviso en `role="status"`, aviso de pegado cortado y la API falsa acortando como B10 | dev_frontend_modulo_mowa_mes, con `designer` | completa, dos pasadas |

## 2. Trazabilidad

| RF-MM-04, lo nuevo | Implementación | Pruebas |
|---|---|---|
| La API rechaza más de 100 | `PeticionCampanaEntrada._descripcion_cabe_en_mes`. Es el único camino de entrada: lo heredan la previsualización y `CreacionCampanaEntrada`, y no hay edición posterior. Se mide **lo que se registra** (`strip()`) en **unidades UTF-16** (`largo_utf16`) | Bordes 100 y 101 con espacios en los extremos; tildes (igual que `len`); emoji (50 sí y 51 no; 98 «a» + emoji sí y 99 + emoji no); 422 en la previsualización y en la creación; el contrato dice el tope y la unidad |
| La sugerida se acorta | Prefijo y filtros enteros desde el principio hasta el primero que no cabe, cerrada con `...` sin coma. Si ni el primero cabe, 97 unidades + `...`, recortando de a un carácter (sin partir pares sustitutos) | 100 exactos (sin `...`), 101, sin filtros, el corte justo después del segundo filtro y justo antes, no salta a un filtro posterior más corto, primer filtro de más de 97, emoji en el corte, y una propiedad con semilla fija de 3 000 casos |
| La pantalla no deja pasar de 100 y muestra cuántos van | `maxlength="100"`. El contador «N/100» con `value.length`, asociado por `aria-describedby` y sin anunciarse a cada tecla. Sigue a la sugerida, que llena el campo sin `input`. Tono de advertencia en 100/100. Aviso cuando un pegado no cabe | Vitest del contador (con emoji) y del pegado; Playwright: tope, emoji, sugerida larga, pegado en es y en, 360 px y axe en claro y oscuro |
| «Copiar» copia lo que se registra | `descripcionARegistrar`: `trim()` o, si queda vacío, la sugerida de la última previsualización (lo mismo que hace el backend). Con `aria-disabled` cuando no hay nada que copiar | Vitest de qué se copia; Playwright leyendo el portapapeles con `readText` |
| Aviso, y si el navegador no deja copiar | `copiarConRespaldo`: primero `navigator.clipboard.writeText`; si no existe o rechaza, `execCommand('copy')` sobre la parte sin espacios del campo, o sobre un textarea temporal si el campo está vacío; recién después, el error, con el texto seleccionado. `avisar()` vacía la región y escribe a los 100 ms, para que un aviso igual se repita | Vitest de los 5 casos del orden de intentos; Playwright sin `navigator.clipboard`, con `writeText` que rechaza, con `execCommand` en `false` y con `execCommand` que lanza; el `MutationObserver` ve la región vaciarse entre dos copias |

## 3. Decisiones

- **Del usuario (2026-10-27):** el tope de 100, el acortado de la sugerida y el botón «Copiar».
- **Del coordinador, con visto bueno de `architec`:**
  - el tope va sobre `strip()`;
  - se mide en unidades UTF-16, lo mismo que cuenta el `maxlength` del navegador y del formulario de MES: la pantalla y la API no discrepan y es la medida más estricta;
  - sigue siendo un 422 de validación;
  - la sugerida acortada es `CajaCusco f1, f2...`.
- **De `architec`:** antes de declarar el error, intentar `execCommand('copy')`. Sin `navigator.clipboard` (http fuera de localhost), el botón no fallaría siempre.
- **De `designer`:**
  - los textos;
  - `aria-disabled` (no `disabled`), para que el botón siga en el orden de tabulación;
  - el tono solo en el tope;
  - el aviso a los 100 ms, porque algunos lectores juntan cambios cercanos;
  - el botón queda local a la página, sin componente compartido.

## 4. Verificación

- **B10.**
  - Del dev: ruff limpio, `exportar_openapi --comprobar`, contrato y tipos; pytest sin base 2 787 y 145 omitidas; 16/16 mutaciones (la rebanada inicial del corte es equivalente: la hace el `while`).
  - Las `@postgres`, leídas una por una: ninguna cambia.
  - De `architec` sobre el commit: `-ConBase` con 2 787 y 145 `@postgres`, contrato y tipos. Linux queda para el CI al subir, porque había 1,6 GB libres.
- **F9** (dev, `--workers=2` por la memoria): contrato OK, `astro check` 0 errores, Vitest 892, y Playwright 72/72 entre `mowa-mes-campana-descripcion` (27) y `mowa-mes-campana` (45). Después del arreglo de accesibilidad, `astro check` 0 errores y el spec de la descripción 28/28, con axe en claro y oscuro.
- **Mutaciones de F9:** 13/13, de una en una con `--workers=1`:
  - sin `maxlength`;
  - copiar sin `trim`;
  - vacío sin la sugerida;
  - el fallo sin seleccionar;
  - el aviso fuera de la región;
  - el contador sin seguir a la sugerida;
  - saltarse `execCommand`;
  - llamarlo aunque el portapapeles funcionó;
  - pegado sin aviso;
  - el contador por puntos de código;
  - sin tono en el tope;
  - el aviso sin vaciar;
  - la región de estado con `display:none` estando vacía.
- **Queda para `architec` sobre el commit de F9:** contrato, `astro check`, tipos, Vitest, `build:produccion` y Playwright completo. El dev no corrió el completo sobre esta versión: la vez que lo intentó, Claude Code lo cortó por memoria.

## 5. Lo que encontró la revisión antes del commit

- **F9, accesibilidad:** la región `role="status"` se ocultaba con `display:none` cuando estaba vacía. Como `avisar()` la vacía para repetir un aviso, salía del árbol de accesibilidad justo antes de recibir el texto, y NVDA o JAWS podían no anunciarlo. Los `MutationObserver` de las pruebas no lo veían. Se corrigió dejando la región siempre presente: sin `display:none`, con un margen negativo que anula el hueco vacío. Una prueba nueva la busca por su rol con la región vacía, después de copiar y después de editar, y la mutación que vuelve a ocultarla la hace fallar.
- **F9:** el aviso «copiada» no se repetía al copiar dos veces (mismo texto en la región). Ahora se vacía antes de escribir.

## 6. Pendiente, fuera de RF-MM-04

- **Una mitad de par sustituto suelta en el JSON** (`"\ud800"`) pasa la validación de pydantic y la respuesta revienta con 500 (`surrogates not allowed`). Ya pasaba con el tope de 1000. `architec` la trata como tarea aparte cuando decida el usuario.
- **Saltos de línea:** el campo de la app es un textarea y admite saltos de línea. Si el campo de MES es de una sola línea, pegar una descripción con un salto la junta o la corta. Está preguntado al usuario; mientras no responda, no cambia nada.
