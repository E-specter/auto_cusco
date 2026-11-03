# Revisión de cierre del mapeador de encabezados (T-MAP-C2)

Cerrada el 2026-10-27, sobre `main` en `ed9a847`. **RF-57 a RF-63: cumplidos.** Quedan tres hallazgos de la pasada contra el backend real de `architec`. Ninguno bloquea, y se corrigen en un corte chico, T-MAP-B5 (§3). T-MAP-B4 es otro corte: los alias literales en el catálogo, para la búsqueda de T-MAP-F3.

## 1. Trazabilidad

| RF | Qué pide | Dónde quedó | Pruebas principales | Estado |
|---|---|---|---|---|
| RF-57 | Excel (con hoja), ODS, CSV (separador y codificación detectados y ajustables) y JSON | B2 (`d66d518`): `LectorTablaPort` y los lectores CSV, JSON y hojas. Separador por consistencia (gana `;`) y codificaciones UTF-8 con BOM → UTF-8 → Windows-1252 → Latin-1 (`c49b8d4`). F2 (`ed9a847`): hoja, separador y codificación en pantalla, con «(detectado)» | `test_lector_tabla` (propiedades con 1 000 CSV), `test_api_mapeador`, `carga-mapeada.spec` | Cumplido |
| RF-58 | Análisis antes de cargar: recordado, coincide, parecido o sin coincidencia, con ejemplos | B1 (`96a1907`): `analizar` en tres pasadas, parecidos «mejor primero», una sola `coincide` (también en el camino viejo, M-6). B3 (`b0244b7`, `b167161`): borrador con el análisis guardado. F1 (`171025e`) | `test_mapeador_analisis` (permutación de columnas), paridad del camino viejo | Cumplido. Ver H-1 |
| RF-59 | Elegir el campo de una lista con «No cargar» | F1: el select agrupado, con el campo en uso deshabilitado (decisión del 2026-10-27) | `mapeador.spec`, `tests/nucleo/mapeador.test.ts` | Cumplido. La búsqueda (RF-59 ampliado) es T-MAP-F3, de designer |
| RF-60 | No confirmar con problemas: parecido sin revisar, obligatorio sin columna, campo repetido | B1 `validar` (siete códigos) contra el análisis guardado (M-4). B3b: 422 `mapeo_con_problemas`. F2: el botón inactivo con su motivo y el 422 vuelve con `fijarProblemas` | `test_mapeador_validacion`, `carga-mapeada.spec` | Cumplido |
| RF-61 | Recordar lo confirmado | B3a: `mapeo_recordado` por (catálogo, normalizado, ocurrencia) (M-1), *upsert* en la misma transacción | `test_mapeador_ciclo` (los dos «Pagare»), `@postgres` | Cumplido |
| RF-62 | Guardar con la versión el mapeo y el origen de cada asignación | B3a: `carga.asignaciones` (con el encabezado normalizado, comprobado al procesar) y `formato.mapeo` aditivo (`origenes`, `ignoradas`) | `test_ingesta_mapeo_explicito` | Cumplido. Ver H-2 |
| RF-63 | Reutilizable por catálogo | Núcleo sin dependencias de la sábana (prueba de arquitectura), API `/mapeador/{catalogo_id}`, componente `MapeadorEncabezados` que no conoce la sábana | `test_mapeador_*` (arquitectura), `test_contrato_mapeador` | Cumplido |

## 2. Hallazgos de la pasada real (architec)

- **H-1. «Numero de pagare» sale «sin coincidencia» y no «parecido a Pagaré».** La similitud de §3.2 es el máximo de `SequenceMatcher` (0,55) y Jaccard de palabras (1/3), y las dos quedan bajo el umbral de 0,75. Las dos castigan un encabezado que *contiene* el nombre del campo y le suma palabras. **Propuesta:** sumar a ese máximo el **coeficiente de solapamiento** de palabras, |A ∩ B| / min(|A|, |B|), sin las palabras vacías (`de`, `del`, `la`, `las`, `el`, `los` e `y`). «numero de pagare» contra `pagare` da 1, y contra `pagare_duplicado`, 0,5. Gana `pagare` y queda como **parecido**: el usuario lo confirma, como pidió (RF-58). El umbral no cambia. El empate (< 0,02) sigue evitando las sugerencias dudosas: por ejemplo, «segmento financiero» contra `segmento_actual` y `segmento_atraso`. Pruebas: el caso de architec, una tabla de encabezados sintéticos con su sugerencia esperada (incluidos los que deben quedar sin sugerencia por empate) y la paridad del camino viejo (`coincide` no cambia).
- **H-2. Ruido de incidencias en una carga confirmada.**
  - Unas 40 `columna_faltante` (advertencia) salen por los campos opcionales que el archivo no trae.
  - `cabecera_desconocida` marca una columna que el usuario dejó en «No cargar» a propósito.

  **Propuesta,** solo para el camino con mapeo confirmado (`mapeo_explicito`). El camino viejo no cambia:
  - una columna en «No cargar» confirmada no genera `cabecera_desconocida` ni `cabecera_duplicada`. La decisión ya queda en `formato.mapeo.ignoradas`;
  - los campos opcionales sin columna generan UNA advertencia de resumen, `columnas_opcionales_ausentes`, con la cantidad y la lista de campos en el detalle, en lugar de una por campo. Así se sigue cumpliendo N-1 («una cabecera faltante debe reportarse»), sin el ruido;
  - `columna_faltante` (error) para un obligatorio no cambia, aunque en una carga confirmada no puede pasar (RF-60).

  La paridad de B3a se reformula: las mismas filas, el mismo resumen de filas y el mismo `formato.mapeo`. Las incidencias de cabecera cambian de forma a propósito. El código nuevo va a `CODIGOS_INCIDENCIA` y a i18n, con un texto que revisa designer.
- **H-3. El comentario de `descartarBorrador`** (`frontend/src/lib/api-mapeador.ts`) dice «204 also for a draft that expired». Es cierto para uno vencido que todavía está en la base, pero un id inexistente da 404. La pantalla trata los dos igual. Se corrige el comentario.

## 3. Corte de cierre propuesto: T-MAP-B5

H-1 y H-2 en el backend, más H-3 (una línea) en el mismo corte, con la paridad reformulada. dev_backend lo hace después de que se apruebe el plan de los campos adicionales, porque los dos tocan `similitud.py` y `mapeo_explicito.py` (el campo adicional pasa por los dos). Así se ordenan sin rebases cruzados.

## 4. Lecciones

- Una prueba con la base real y datos parecidos a los reales (H-1, H-2) encuentra lo que las propiedades sintéticas no ven. Vale la pena una pasada así al cierre de cada capacidad que toca la ingesta.
- El recálculo del origen en el backend y el «Aceptar» explícito en la pantalla se escribieron juntos (§3.4 del diseño y §3.5 de la interfaz), y eso evitó una revisión silenciosa.
- La memoria de la máquina obligó a turnos de una tarea pesada a la vez, y a mutar sobre copias y no en el worktree, después de dos mutantes que quedaron aplicados al cortarse una corrida.
