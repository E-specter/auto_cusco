# Revisión de la descripción de campaña de una sola línea (T-MM-C7)

> **Revisada el 2026-10-27.** RF-MM-04, una sola línea (`1945381`): el usuario confirmó que el campo «Descripción de Campaña» de MES no admite saltos de línea. Responde la pregunta que dejó abierta C6 (§6).
> - **T-MM-B11** (backend): en `422804e`, sin push.
> - **T-MM-F10** (frontend): revisado, sin commit, sobre `171025e`.

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Requerimiento: `requerimientos-mowa-mes.md` RF-MM-04.

## 1. Cortes

| Corte | Dónde | Contenido | Agente | Mi revisión |
|---|---|---|---|---|
| **T-MM-B11** | `422804e`; 7 archivos | `una_linea` en la entidad. El validador de `PeticionCampanaEntrada` la aplica antes de medir los 100 y devuelve el valor cambiado. `descripcion_sugerida` la aplica a cada resumen de filtro. Contrato (solo la descripción del campo). `mowa-mes.md` §18 | dev_backend_modulo_mowa_mes | completa |
| **T-MM-F10** | `auto_cusco_mowa_f10`, rama `mowa-f10-una-linea`; 6 archivos | El campo pasa de `textarea` a `<input type="text">`. Pegado y soltado a mano con los saltos como espacios, insertados con `execCommand('insertText')`. U+2028 y U+2029 tecleados pasan a espacio. `flex-wrap` del campo y «Copiar». API falsa como B11 | dev_frontend_modulo_mowa_mes, con `designer` | completa |

## 2. Trazabilidad

| RF-MM-04, lo nuevo | Implementación | Pruebas |
|---|---|---|
| La API registra una sola línea | `una_linea`: `\r\n` es UN espacio; después `\r`, `\n`, U+2028 y U+2029 sueltos. Los espacios seguidos no se juntan. `\v`, `\f` y U+0085 no se tocan: nadie los decidió. Se aplica **antes** del `strip()` y de medir, y el validador devuelve el valor cambiado, que es lo que se guarda | Los cinco saltos uno por uno; CRLF como uno y `\n\r` como dos; 100 crudos con un CRLF adentro (101 unidades que valen 100) se aceptan; VT, FF y U+0085 intactos; lo guardado sin saltos en la previsualización, la creación y el GET |
| La sugerida también es de una línea | Un valor de filtro de texto puede traer un salto (`titular:contiene:a\nb`: `convertir` solo recorta los extremos). `descripcion_sugerida` pasa cada resumen por `una_linea` antes de unir y medir | Un filtro con salto da una sugerida de una línea; el corte de 100 se mide después del cambio |
| El campo de la pantalla es de una línea | `<input type="text" maxlength="100" autocomplete="off">`. Un `input` borra `\r` y `\n` al pegar, lo que junta las palabras, y deja U+2028 y U+2029. Por eso el pegado es a mano: `textoDePegado` normaliza los saltos (`normalizarSaltos`, la misma regla que el backend) y corta a lo que cabe sin partir un par sustituto (`recortarSinPartirPares`), descontando la selección que reemplaza | Vitest de los cinco saltos, del corte con emoji y de la selección; Playwright de pegar «uno CRLF dos LF tres», U+2028 en el pegado, pegado largo y pegado que cabe |
| Pegar se deshace con Ctrl+Z | `insertarEnElCampo` inserta con `execCommand('insertText')`, que deja una entrada en el historial de deshacer y dispara `input`. Si el navegador lo rechaza (`false` o excepción), cae a `setRangeText` más un `input` sintético | Playwright de Ctrl+Z y Ctrl+Shift+Z tras un pegado con saltos y tras uno que no cabe; respaldo con `insertText` en `false` y con excepción |
| El aviso de pegado cortado sigue | Se mide sobre el texto ya normalizado (un CRLF cuenta 1) y se anuncia una vez, aunque no entre nada | Vitest «el aviso se mide ya normalizado»; Playwright en es y en |
| Ancho angosto | `.mm-descripcion` con `flex-wrap` y el campo en `flex: 1 1 16rem`: bajo ~480 px, «Copiar» baja debajo del campo en vez de quitarle ancho (decisión de `designer`) | El spec de la descripción en 360 px; axe en claro y oscuro |

## 3. Decisiones

- **Del usuario (2026-10-27):** el campo de MES es de una sola línea, y los saltos se cambian por un espacio.
- **Del coordinador, con visto bueno de `architec`:**
  - la sugerida también pasa por `una_linea`, en cada resumen. Lo encontró el dev de backend: un valor de filtro de texto puede traer un salto adentro y llegaba a la sugerida, que es lo que se guarda cuando la descripción va vacía;
  - `\v`, `\f` y U+0085 se dejan como están, en la API y en la pantalla, porque no se decidieron.
- **Del coordinador:** el pegado se inserta con `execCommand('insertText')` y no con `setRangeText`. La primera versión usaba `setRangeText`, que no deja entrada de deshacer: un pegado equivocado no se podía deshacer con Ctrl+Z. Lo rechacé y M7 lo vigila.
- **Atajos aceptados, cada uno con su comentario `shortcut:` en `campana.astro`:**
  - **Soltar (drop):** solo un texto soltado que trae un salto se inserta a mano, y va donde está la selección, no bajo el puntero (un `input` no da la posición del puntero). Cualquier otro drop lo hace el navegador.
  - **Respaldo sin deshacer:** si `insertText` falla, `setRangeText` no deja entrada de deshacer.
  - **U+2028 o U+2029 tecleados:** se cambian asignando `value`, lo que en Chrome borra el historial de deshacer del campo. Solo pasa con esos caracteres, que no salen de un teclado común. La mejora, si alguien lo reporta: seleccionar el rango y usar `execCommand('insertText', false, ' ')`.
- **De `designer`:** el `flex-wrap` y el ancho base del campo.

## 4. Verificación

- **B11.**
  - Del dev: ruff limpio; `exportar_openapi --comprobar`, contrato y tipos; pytest sin base 2 820 y 145 omitidas.
  - Mutaciones: 14/14, de una en una en una copia: los cinco saltos (CRLF como dos, y olvidar U+2028, U+2029, CR y LF), medir antes del cambio, no devolver el valor cambiado, tocar `\v`, U+0085 o `\f`, la API sin el cambio, la sugerida sin `una_linea` y medida antes del cambio, y `\n\r` como uno.
  - Las `@postgres`, leídas una por una: ninguna cambia. La única que toca la descripción (`test_mowa_mes_campanas_postgres.py:615`) inserta sin saltos.
  - Yo, en el worktree: los dos archivos de pruebas de la descripción, 62 pasan.
  - De `architec` sobre el commit, contra `3448572`: `-ConBase` 2 820 en la pasada general y 145 `@postgres` contra `auto_cusco_test`, `exportar_openapi --comprobar`, contrato y tipos. Sin WSL, por memoria.
- **F10** (dev, sobre `422804e`):
  - `contrato:comprobar` y `tipos` pasan; `astro check` 0 errores; Vitest 38 archivos y 897 pruebas.
  - Playwright `mowa-mes-campana-descripcion.spec.ts` 43/43 con `--workers=1`, con axe en claro y oscuro.
  - Playwright `mowa-mes-campana.spec.ts` 45/45 con `--workers=1`, ya sobre `171025e`. Antes, Claude Code lo cortó dos veces por memoria y después se apagó el equipo; corrió en su turno de la regla de una tarea pesada a la vez.
  - Entre los dos specs, 88/88. El rebase sobre `171025e` (el mapeador) no tocó ninguno de los 6 archivos; lo demás de la cadena corrió sobre `422804e`.
- **Mutaciones de F10:** 10/10, de una en una con `--workers=1`, en la copia `auto_cusco_mowa_f10_mut`, con el control sin mutar en verde:
  - sin `preventDefault` en el pegado (Playwright);
  - CRLF como dos espacios (los dos);
  - olvidar U+2028 (los dos);
  - el pegado sin recortar a lo que cabe (los dos);
  - el aviso medido antes de normalizar (solo Vitest);
  - partir un par sustituto al recortar (los dos);
  - solo `setRangeText`, sin historial de deshacer (Playwright);
  - U+2028 tecleado se queda (Playwright);
  - el drop con salto lo hace el navegador (Playwright);
  - la selección no libera espacio al pegar (solo Vitest).

  Ocho las ve Playwright y seis Vitest; cuatro, las dos capas. El dev las había contado como 11: la M8 del script era idéntica a M4 y la quitó, sin renumerar.
- **Queda para `architec` sobre el commit de F10:** contrato, `astro check`, tipos, Vitest, `build:produccion` y Playwright completo.

## 5. Lo que encontró la revisión antes del commit

- **F10, deshacer:** con `setRangeText` un pegado no se deshacía con Ctrl+Z. Se cambió a `execCommand('insertText')` (§3).
- **B11, la sugerida:** un salto dentro de un valor de filtro llegaba a la descripción guardada (§3).
- **F10, comentarios:** el CSS todavía hablaba de un textarea, y el `shortcut:` de U+2028 proponía mejorar con `setRangeText`, que tampoco conserva el deshacer. Corregidos.
- **C4 y B19, en la pasada anterior:** ya registrados en C5.

## 6. Pendiente, fuera de RF-MM-04

- **T-API-B1** (equipo motor): una mitad de par sustituto suelta en el JSON da 500. Va por el mismo camino de entrada que B11; quien entre segundo en main rebasa.
- **`\v`, `\f` y U+0085:** pasan tal cual a la descripción. Si MES los rechaza, hay que preguntarle al usuario qué hacer con ellos.
