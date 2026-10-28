# Revisión de los campos adicionales en el speech (T-MM-C8)

> **Revisada el 2026-10-27.** Decisiones D-CA-0 a D-CA-3 del usuario (`d999698`, §28 del plan del motor y el registro de cambios de RF-65). Plan: §7 de [plan.md](plan.md), aprobado en `91fc3d0`. Cierra la parte de MOWA MES de RF-64 a RF-66.
> - **T-MM-B12** (backend): `fdc2e5d`.
> - **T-MM-F11** (frontend): `74fe23c` (punto 1, el texto del motivo) y `03babbb` (el resto).

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Requerimientos: [atomics-requirements.md](../../atomics-requirements.md) RF-64 a RF-66; [mowa-mes.md](../../mowa-mes.md) §19.

## 1. Cortes

| Corte | Dónde | Contenido | Agente | Mi revisión |
|---|---|---|---|---|
| **T-MM-B12** | `fdc2e5d`; 24 archivos y 5 nuevos | Los adicionales en el speech v2 (`adicionales_de`, `adicionales=` por palabra clave y vacío por defecto). La cota obligatoria (`SIN_COTA_VARIABLE` en el nodo). `FALTA_CAMPO_ADICIONAL` con `Exclusion.campos` y la migración `e9b3d2a7c561`. `campos_archivados` en la previsualización. Contrato. `mowa-mes.md` §19. Del frontend, solo el texto del código y los datos simulados | dev_backend_modulo_mowa_mes | completa |
| **T-MM-F11, punto 1** | `74fe23c`; 3 archivos | La etiqueta corta `mowaMes.seguimiento.exclusiones.motivo.falta_campo_adicional`, que faltaba en B12 (§5). Una guarda de Vitest para cada código de `CODIGOS_EXCLUSION` | dev_frontend_modulo_mowa_mes | completa |
| **T-MM-F11** | `03babbb`; 11 archivos y 2 nuevos | `detalleDeExclusion` y `listaDeCampos`. El detalle en seguimiento y los nombres bajo el tag en la campaña. El aviso de archivados en el editor v2. `mowa-mes.md` §19.1 | dev_frontend_modulo_mowa_mes, con `designer` | completa |

## 2. Trazabilidad

| Decisión o requerimiento | Implementación | Pruebas |
|---|---|---|
| **D-CA-0:** el speech v2 ofrece los adicionales | `speech.adicionales_de(catalogo)` lee `campos()` una vez, archivados incluidos para que lo guardado resuelva. Las v2 compilan con `{**VARIABLES_V2, **adicionales}`. La configuración, la campaña, `contexto_speech(catalogo)` y la API reciben el catálogo; las llamadas sin adicionales dan lo mismo que antes. Los ejemplos son sintéticos y hay uno por tipo | Una v2 con un adicional de cada tipo, con su cota, genera con el valor de la fila. La previsualización usa el ejemplo del tipo. El contexto del editor los ofrece con su tipo. N5, N8, N11, N13 y N14 (§4) |
| **D-CA-1:** un adicional de texto o de número exige `primeros(n)` | Cada nodo que lee un adicional de texto o de número, como base o como argumento, se compila solo; sin `cota` da `SIN_COTA_VARIABLE` en ese nodo, con su nombre. Se usa la cota del motor, así que vale `ad_numero \| a_texto \| primeros(6)`. No aplica a una fecha. Al guardar, `SpeechInvalido` da 400, como cualquier speech inválido | Texto y número sin tope dan el problema. Número con `a_texto \| primeros` no lo da. El argumento sin tope lo da, probado con `si_vacio`. La fecha no lo da. El titular, igual que antes. Guardar no guarda. En la pantalla, el problema sale en el nodo (spec F11). N1, N2 y N10 |
| **D-CA-2:** un adicional vacío que el segmento usa excluye con `falta_campo_adicional` | Después de `falta_vencimiento` y antes del WhatsApp y de los 160. Usa el mismo `_vacio` del titular. Excluye también si el campo está archivado. `Exclusion.campos` lleva los nombres técnicos en el orden de los nodos y se guarda en `mowa_mes_exclusion.campos text[] NULL`. La API resuelve la etiqueta al leer | `None`, `""` y `"  "` excluyen. Dos vacíos salen los dos, en orden. El orden contra el vencimiento y el WhatsApp. Un vacío que no se usa no excluye. Un archivado vacío excluye. La API da técnico y legible, y renombrar cambia el legible. Ida y vuelta `@postgres` y la fila anterior a la migración. N3, N4, N6, N7, N9 y N15 |
| **D-CA-3:** el .xlsx de MES no gana columnas | Sin cambio en la exportación | Las pruebas de oro de división y exportación no aparecen en el diff de B12 y pasan |
| **RF-65:** renombrar no rompe nada | Se guarda el nombre técnico; la etiqueta se resuelve al leer, en la API y en la pantalla | «renombrar cambia el legible» (API) |
| **RF-65:** el archivado sigue funcionando y se avisa | `previsualizar_speech_v2` devuelve `campos_archivados` (`archivados_entre`) como `[{nombre, etiqueta}]`. Es un aviso: nunca bloquea, y guardar se permite. El editor lo muestra con `avisoDeArchivados`, después del aviso de WhatsApp | API: con y sin archivados, y en una v1. Playwright: con archivado, sin archivado, al cambiar de versión, en v1 y si la previsualización falla. N12 y la M3 de F11 |
| **RF-66 en MOWA:** nombre legible y marca de adicional | En el editor, el selector y las fichas los pinta T-CA-F1 desde el contexto (`etiqueta`, `adicional`, `archivado`), sin código de MOWA. En las exclusiones, el detalle de seguimiento y la celda de la campaña usan la etiqueta, nunca el `ad_…`, entre las comillas del idioma | Vitest del detalle: un campo, varios, otro código, sin campos y comillas por idioma. Playwright: seguimiento, la campaña a 360 y 1440 px, el selector con «Adicional» y sin el archivado. axe en claro y oscuro |

## 3. Decisiones

- **Del usuario (2026-10-27):** D-CA-0 a D-CA-3.
- **De `architec` (§7.9):**
  - **P-1:** se guardan los campos de la exclusión (la migración).
  - **P-2:** el aviso de archivados no va en la previsualización de la campaña por ahora, y se revisa aquí (§6).
- **Del coordinador, apartes del plan aceptados:**
  - **400 y no 422** al guardar un speech con el problema: es el código de todo speech inválido.
  - **El caso del argumento** se prueba con `si_vacio`, porque `primeros(n)` no acepta una variable como `n`.
  - **`previsualizar_speech_v2` devuelve un cuarto valor,** los archivados.
  - **`mensaje_de` recibe `adicionales` solo si el segmento los usa.** Así la llamada de siempre es idéntica y el `ConstructorEspia` de las pruebas de oro no cambia.
  - **`campos_archivados` es `[{nombre, etiqueta}]` y no una lista de nombres,** porque el aviso necesita el nombre legible.
  - **En F11, la clase `mm-exclusion__campos`,** que después tomó el estilo de designer.
  - **En F11, `falta_campo_adicional` en `CODIGOS_CATALOGO` de la API falsa,** y no en `EXCLUSIONES_EN_ORDEN`, para no mover los conteos de otros specs.
- **Pruebas que cambian a propósito:**
  - `test_api_mowa_mes_campanas.py`, una línea autorizada (`"campos": []`). Es la única prueba de oro del diff.
  - `test_codigos_mowa_mes.py`, el orden de evaluación.
  - `test_campos_adicionales_variables.py`, del motor, con visto bueno de `coordinador_motor_texto_enriquecido`: afirmaba que el speech no tenía adicionales, que es justo lo que cambia D-CA-0.
- **De `designer`:**
  - El detalle va en dos claves, una y varias, fuera de `mowaMes.codigo.*`, cuya prueba espejo compara el conjunto con el enum.
  - Las comillas son las del idioma y salen de una plantilla (`mowaMes.exclusiones.campo`), no de `avisoDeArchivados`, que pone «» siempre.
  - En la campaña, sin columna Detalle: los nombres van siempre en su propia línea bajo el tag, en todos los anchos, y sin `nowrap`.
  - El aviso va después del de WhatsApp.

## 4. Verificación

- **B12, la cadena:**
  - ruff limpio y `exportar_openapi --comprobar` coincide.
  - pytest sin base, sin paralelismo: 3203 pasan y 155 omitidas.
  - Frontend: tipos, `astro check` con 0 errores, Vitest 935/935 y Playwright 282/282 en los 7 specs de MOWA con `--workers=1`.
- **B12, mutaciones:** 15/15, de una en una, en una copia que ya está borrada:
  - N1, quitar la cota; N2, la cota también a la fecha;
  - N3, `_vacio` por `is None`; N4, el código después del WhatsApp;
  - N5, la campaña sin adicionales; N6, perder `campos` al guardar;
  - N7, el orden del catálogo en vez del de los nodos; N8, los archivados fuera de `adicionales_de`;
  - N9, la etiqueta sin resolver; N10, guardar sin el catálogo;
  - N11, el contexto del editor sin catálogo; N12, el aviso siempre vacío;
  - N13, `mensaje_de` sin los valores; N14, la previsualización sin adicionales;
  - N15, la exclusión sin `campos`.
- **B12, `architec` sobre `1c4bdc7`:**
  - `-ConBase`: 3225 y 155 `@postgres`, con las 3 nuevas.
  - La migración, de ida y vuelta, en `auto_cusco_test`.
  - `exportar_openapi --comprobar`, contrato, `astro check`, tipos, Vitest 957, build y Playwright completo 623/623.
  - Sin WSL, por decisión del usuario.
- **F11, punto 1, `architec`:** la prueba nueva falla sin el arreglo y pasa con él; Vitest 964 y `astro check` 0. Sin Playwright, porque son solo textos.
- **F11, el dev:**
  - Sin turno: Vitest 973/973, `astro check` 0, tipos y `contrato:comprobar`.
  - Playwright con `--workers=1`. La primera tanda dio 153 que pasan y 2 que fallan, las dos en el spec nuevo (§5). Después: el spec nuevo 21/21 y seguimiento 22/22. Los casos de MOWA de `accesibilidad.spec.ts`, 30/30. Tras el CSS de designer, el spec nuevo 22/22.
  - Mutaciones, 5/5 en una copia ya borrada. M1, etiqueta por nombre. M2, singular y plural cruzados. M3, no ocultar el aviso (solo la ve Playwright). M4, las comillas. M5, el detalle para cualquier código (solo la ve Vitest).
- **F11, `architec` sobre `2104f05`:** contrato, `astro check`, tipos, Vitest 985, build y Playwright completo 681/681.
- **Los worktrees** `auto_cusco_mowa_b12` y `auto_cusco_mowa_f11` se borraron después de comparar cada archivo con su commit. Lo único distinto eran líneas i18n que main ya había cambiado después.

## 5. Lo que encontró la revisión

- **B12, antes del commit:**
  - Una lambda en el registro de producto rompía la igualdad de `contexto_speech()`. Se cambió por una dataclass congelada.
  - Una prueba del motor afirmaba lo contrario de D-CA-0 (§3).
- **B12, después del commit:** el código nuevo no tenía la etiqueta corta. El filtro «Motivo» de seguimiento, que recorre `CODIGOS_EXCLUSION`, mostraba la clave cruda, y lo mismo pasaba con el tag en las dos tablas. Ninguna prueba lo vigilaba. **Se me pasó en la revisión de B12.** Se corrigió aparte en `74fe23c` con una guarda que exige la clave para cada código. Junto con la prueba espejo que ata `CODIGOS_EXCLUSION` al catálogo del backend, un motivo nuevo sin texto ya no llega a la pantalla.
- **F11, Playwright:** la API falsa no tenía el código en su catálogo, y el filtro daba 422. Además, una prueba en inglés esperaba el título en español. Las dos fallas eran de las pruebas, no de la pantalla.
- **F11, designer:** a 360 px un nombre quedaba partido junto al tag («Monto» / «en mora»). Ahora los nombres van en su propia línea, y una prueba lo fija a 1440 px.

## 6. P-2 revisada: el aviso de archivados en la campaña

**Un hecho que el plan no tuvo en cuenta.** Un adicional archivado deja de encontrarse al analizar una sábana nueva: la columna queda «sin coincidencia» (`test_un_adicional_archivado_deja_de_encontrarse_al_volver_a_analizar`, en `test_campos_adicionales_ciclo.py`). Desde esa carga, el campo viene vacío en todas las filas. Si un speech v2 lo usa, **todos los productos de los segmentos que lo leen quedan fuera** con `falta_campo_adicional`.

- La previsualización de la campaña lo muestra como exclusiones «Sin campo adicional «Región»», pero no dice que el campo está archivado. Esa es la causa, y se corrige en el speech o reactivando el campo.
- El aviso de archivado solo sale al abrir el speech en la configuración.

**Recomiendo agregar ahora el aviso a la previsualización de la campaña.** Es un corte chico:
- backend: la previsualización de la campaña devuelve `campos_archivados`, que son los archivados que leen las versiones del speech de sus segmentos;
- frontend: un `.notice--info` con `avisoDeArchivados`.

La alternativa es dejarlo como está y esperar a que pase en uso real: la exclusión ya nombra el campo. Lo decide `architec`. Si se hace, lo abro como T-MM-B13 y T-MM-F12.

**Decisión de `architec` (2026-10-27): sí, ahora.** Archivar un campo que usa un speech saca a todos los productos de esos segmentos y la campaña no dice por qué; el aviso es barato y evita esa sorpresa.

## 7. Pendiente

- **La migración `e9b3d2a7c561` en `auto_cusco`:** aplicada por `architec` con permiso del usuario el 2026-10-27, después del commit de B12 (`c8f1a3d6e254` → `e9b3d2a7c561`).
- **P-2, decidida por `architec` el 2026-10-27: sí.** Se abre T-MM-B13 (backend) y T-MM-F12 (frontend) para el aviso de archivados en la previsualización de la campaña, con el plan en §8 de `plan.md`.
- **Linux:** queda para el CI de GitHub al subir. No hubo WSL en ningún corte, por decisión del usuario.
