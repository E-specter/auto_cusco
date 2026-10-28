# Revisión de cierre del filtro de valores y del orden de los filtros (T-FV-C2)

> **2026-10-28, `architec`.** Cierra RF-67 y RF-68 ([atomics-requirements.md](../../atomics-requirements.md)), pedidos por el usuario el 2026-10-28 después de probar los campos adicionales. Plan: §29 del plan de `coordinador_motor_texto_enriquecido` (aprobado en `d4caeb3`). Reglas de interfaz: [filtro-valores-interfaz.md](../../filtro-valores-interfaz.md).

## 1. Cortes

| Corte | Commit | Qué |
|---|---|---|
| Requerimientos | `51f808b` | RF-67 y RF-68 |
| T-FV-C1 | `d4caeb3` | Plan; decisiones D-FV-1 y D-FV-2 en RF-67 |
| T-FV-F0 | `557588f` | Reglas de interfaz, aprobadas por el usuario |
| T-FV-B1 | `09581df` | `no_en`, el vacío en `en`/`no_en`, escape de `\|` y `\\`, `resumen_filtro` por operador |
| T-FV-F1 | `400d6ec` | `no_en`, vacío y escape en la selección; texto `op.no_en` |
| T-FV-B2 | `271703c` | `GET /cartera/valores`, umbral en `Settings`, prueba espejo de operadores |
| T-FV-B3 | `99a7fbf` | Memoria de la decisión del umbral y de las listas |
| T-FV-F2 | `cf9df89` | La lista de valores en el filtro |
| (aparte) | `f19d64b` | Prueba de accesibilidad intermitente (`finished` de una transición cancelada) |
| T-FV-F3 | `b7abca4` | Reordenar los filtros |

## 2. Trazabilidad

| Requerimiento | Dónde | Evidencia |
|---|---|---|
| **RF-67:** lista automática en texto (base o adicional) con hasta el umbral de valores; si lo supera, se escribe como hoy | `271703c` (`ofrece_lista`, umbral 100 en `Settings`), `cf9df89` | Prueba con 150 teléfonos sintéticos: no se devuelve ningún valor; Playwright de `filtro-valores` |
| **RF-67:** cantidad por valor, «(vacío)» como opción, orden por cantidad con desempate alfabético y «(vacío)» al final, comparación tal cual (D-FV-1, D-FV-2) | `271703c`, `09581df` | Pruebas del caso de uso; pasada real: Región con 5 valores y su cantidad |
| **RF-67:** incluir o excluir | `09581df` (`no_en`), `400d6ec`, `cf9df89` | Prueba de partición `en`/`no_en` en PostgreSQL; pasada real: 1 005 + 3 994 = 4 999, el total de la fecha |
| **RF-67:** lista contextual con los filtros de arriba; el valor marcado sin productos queda aparte | `cf9df89` | Playwright de `filtro-valores` |
| **RF-68:** reordenar arrastrando o con teclado; el orden define la cascada y no el resultado; se guarda | `b7abca4` | Playwright de `orden-filtros`, `mowa-mes-campana-orden`; el JSONB ya conservaba el orden (pruebas de ida y vuelta) |
| **MOWA MES** (§13 en cada corte) | `09581df`, `cf9df89`, `b7abca4` | La campaña toma el orden de la selección guardada; mover emite `seleccioncambiada`; las pruebas de oro de MOWA sin cambios |

## 3. Rendimiento

46 000 filas sintéticas, `auto_cusco_test`, dos corridas cada vez. Antes de T-FV-B3 la lista daba p95 de 168 a 272 ms, sobre el presupuesto de 150 ms. Con la memoria de T-FV-B3, las llamadas siguientes salen en 0,4–2,4 ms (p95); la primera de cada lista, p50 de 38 a 136 ms y p95 de 48 a 225 ms, con el exceso en casos distintos de una corrida a otra por ruido de la máquina. Se aceptó: la primera llamada se paga una vez por campo y versión vigente.

## 4. Lo que encontró la verificación de `architec`

- **Conteos de solo lectura en `auto_cusco`** antes de B1: ninguna selección ni campaña guardada tenía «\\» ni `:en:` con un elemento vacío; no hizo falta migración.
- **T-FV-B1 dejó la clave cruda `op.no_en`** en el menú de operadores hasta `400d6ec`. Para que no se repita, T-FV-B2 trae una prueba espejo: cada operador del backend tiene su texto en es y en.
- **T-FV-B2:** el script de medición no arrancaba (le pasaba `LectorCalamine` a la ingesta); se corrigió en el corte. La medición quedó fuera de presupuesto y se abrió T-FV-B3.
- **Prueba intermitente** de accesibilidad: se arregló aparte en `f19d64b`.
- **Memoria:** dos corridas de verificación se cortaron por falta de memoria; se reanudaron cuando el usuario la liberó. Las de F2 y F3 corrieron con un worker.

## 5. Pendiente

- **Linux:** por decisión del usuario no corre WSL; la capa queda para el CI de GitHub, que corre al subir.
- **Formato de números:** las cantidades salen con coma de miles («1,010»), como en el resto de la aplicación. Cambiarlo es una decisión aparte y para toda la aplicación.

**Veredicto:** RF-67 y RF-68 cumplidos.
