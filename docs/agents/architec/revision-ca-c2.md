# Revisión de cierre de los campos adicionales (T-CA-C2)

> **2026-10-28, `architec`.** Cierra RF-59 ampliado y RF-64 a RF-66 ([atomics-requirements.md](../../atomics-requirements.md)), pedidos por el usuario el 2026-10-27 al revisar `/cargas` en dos pasos. Plan: §28 del plan de `coordinador_motor_texto_enriquecido` (aprobado en `d999698`); MOWA MES: §7 y §8 del plan de `coordinador_modulo_mowa_mes` y su cierre [revision-c8.md](../coordinador_modulo_mowa_mes/revision-c8.md).

## 1. Cortes

| Corte | Commit | Qué |
|---|---|---|
| Requerimientos y tablero | `d4dafb6` | RF-59 ampliado, RF-64 a RF-66 |
| T-CA-C1, T-MAP-C2 | `d999698` | Plan y cierre del mapeador; decisiones P-6 y D-CA-0 a D-CA-3 en RF-65 |
| T-MAP-B4 | `fb0dce1` | Alias legibles en el catálogo del mapeador |
| T-MAP-F3 | `7efcdac` | Búsqueda en la lista de campos |
| T-CA-B1 | `fb1d72b` | `CatalogoCartera` como única fuente para todos los consumidores |
| T-CA-F0 | `f562032` | Reglas de interfaz (`campos-adicionales-interfaz.md`) |
| T-CA-B2 | `156a9df` | Migración `c8f1a3d6e254`, ingesta, API y contrato |
| T-MAP-B5 | `65608ac` | Parecido por contenido y menos ruido de incidencias |
| T-CA-F1 | `1c4bdc7` | Crear desde el mapeo y las marcas en las listas |
| T-MM-B12, F11 | `fdc2e5d`, `74fe23c`, `03babbb` | Los adicionales en el speech de MOWA MES; migración `e9b3d2a7c561` |
| T-MAP-F4, T-CA-F2 | `2f9be42`, `2104f05` | Aviso «todo listo»; gestión en `/cargas` |
| T-CA-F3 | `fc2e36d` | El mapeador destruido no deja listeners vivos |
| T-MM-C8, B13, F12 | `1a40025`, `7a60f07`, `9532800` | Cierre de MOWA y aviso de archivados en la campaña |
| T-MAP-F5 | `5d76bcd` | Texto corregido del aviso de campo archivado |

## 2. Trazabilidad

| Requerimiento | Dónde | Evidencia |
|---|---|---|
| **RF-59 ampliado:** buscar en la lista; el campo en uso visible y no elegible | `7efcdac`, `fb0dce1` | Playwright con axe a 1440, 930 y 360; capturas aprobadas por el usuario («movil» encuentra Teléfono por su alias) |
| **RF-64:** crear desde el mapeo, nombre legible único, tipo, técnico estable, siempre opcional | `156a9df` (API, 409 `nombre_repetido` con el campo), `1c4bdc7` (pantalla), `fb1d72b` (`ad_<slug>` y reservados) | Pasada real: crear «Monto en mora» (número) y confirmar la carga; el 409 contra un archivado sin «Usar» |
| **RF-64:** valor no convertible → vacío y advertencia | `156a9df` (`valor_no_convertible`) | Pasada real: «sin dato» quedó vacío, con la incidencia en su fila y el valor original |
| **RF-65:** queda en el catálogo y se recuerda | `156a9df`, `1c4bdc7` | Pasada real de F3: en la segunda carga, «Canal preferido» se reconoció solo |
| **RF-65:** sin la columna, vacío; versiones anteriores, vacío | `156a9df` (`adicionales` NULL) | `test_una_carga_sin_adicionales_deja_la_columna_en_null` (@postgres, corregida por `architec`) |
| **RF-65:** renombrar sin romper; tipo fijo; archivar y reactivar (P-6) | `156a9df` (PATCH), `2104f05` (gestión) | Pasada real: renombrar, archivar y reactivar en Cargas |
| **RF-65:** aviso de archivado con la consecuencia real | `5d76bcd`, `7a60f07`, `9532800` | Texto aprobado por el usuario el 2026-10-28; los avisos de MOWA dicen que el producto queda fuera |
| **RF-66:** filtros y segmentación | `fb1d72b`, `1c4bdc7` | Pasada real: «Monto en mora mayor que 200» deja 6 de 8 en Cartera |
| **RF-66:** indicadores (suma, promedio, mínimo y máximo solo si es número) | `fb1d72b` | Pruebas del núcleo |
| **RF-66:** variables de texto y columnas de carga | `156a9df` (`VariableRespuesta` con etiqueta), `1c4bdc7` | El catálogo del editor lo ofrece con su etiqueta; medición: generar 23 000 filas con una columna del adicional, 1,2 s |
| **RF-66:** una sola fuente; una capacidad nueva lo recibe sin código | `fb1d72b` | Prueba de arquitectura y prueba de «capacidad nueva» |
| **RF-66 en MOWA MES:** D-CA-0 a D-CA-3 | `fdc2e5d`, `03babbb` | [revision-c8.md](../coordinador_modulo_mowa_mes/revision-c8.md) §2 |

## 3. Rendimiento

Sábana sintética de 46 000 filas, mejor de 3, antes y después de T-CA-B2: generar 2,36 → 2,40–2,47 s y métricas con filtro 42 → 47–64 ms, dentro del ruido. Con un adicional numérico: filtro 84 ms, página 44 ms, generar 23 000 filas 1,2 s.

## 4. Lo que encontró la verificación de `architec`

- **T-CA-B2:** una prueba @postgres confirmaba solo el pagaré; el mapeo exige decidir cada columna. Se corrigió la prueba.
- **T-CA-F1:** la tabla de incidencias mostraba el nombre técnico; se resolvió en T-CA-F2.
- **F1, pasada real sobre F4+F2:** en una segunda carga sin recargar, el mapeador anterior también enviaba «Crear campo» a su borrador viejo. Se arregló en T-CA-F3, con la regresión e2e.
- **T-CA-F3:** una prueba vieja esperaba que el mapeador destruido abriera su lista; se corrigió la prueba.
- **T-MM-B12:** el código nuevo no tenía su texto corto (lo encontró `coordinador_modulo_mowa_mes`); `74fe23c`, con una guarda para cada código.

## 5. Pendiente

- **T-MAP-F6** (`designer`): espacio duro antes de «›» en los avisos, y quitar la constante `RUTA` sin usar en `mowa-mes-adicionales.spec.ts`.
- **Linux:** por decisión del usuario no corre WSL; la capa queda para el CI de GitHub. El usuario subió hasta `91fc3d0` y el CI pasó en backend y frontend; de `f562032` en adelante (T-CA-B2, B12, B13 y los cortes de frontend) espera el próximo push.
- **T-SAB-1:** el `.xlsb` real del 26.10.2026 que dio 400; espera el archivo del usuario.
- Las migraciones `c8f1a3d6e254` y `e9b3d2a7c561` están aplicadas en `auto_cusco` con permiso del usuario.

**Veredicto:** RF-59 ampliado y RF-64 a RF-66 cumplidos.
