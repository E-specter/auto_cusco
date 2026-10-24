# Revisión de GSM-7, M3 y fecha de envío en `mowa_mes` (T-MM-C4)

> **Cerrada el 2026-10-24.** RF-MM-27 (mensaje en GSM-7), RF-MM-19 ampliado (el largo se mide sobre el mensaje normalizado), RF-MM-17 ampliado (M3: solo versiones v2) y la parte de MOWA MES de RF-55 (días ajustados a la fecha de envío) están implementados y commiteados. Subido hasta `5ce9834`; `8894874` en adelante, sin push.

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Requerimientos: decisiones del usuario del 2026-10-19 (`b12d384`), la transliteración (`204b3dc`) y los espacios especiales (2026-10-20, en B16). Plan: `plan.md` §6.

## 1. Commits

| Commit | Contenido | Agente | Mi revisión |
|---|---|---|---|
| `535a61b` | B16 del motor: `a_gsm7`, `largo_gsm7`, `caracteres_borrados`, `compilar(..., medida=)` y el oro aditivo | dev_backend_motor | §13, dos pasadas |
| `32bfebf` | B15: crear o editar una v1 da 400 `version_v1_retirada` | dev_backend_motor | §13 |
| `3fe79af` | F8: `/mowa-mes/configuracion` solo v2; las v1 en solo lectura con «Convertir a v2» | dev_frontend_motor | §13 |
| `5ce9834` | B13 del motor: fecha de envío y días ajustados; la previsualización del speech ajusta a hoy en Lima | dev_backend_motor | §13, la parte de MOWA MES |
| `8894874` | **T-MM-B9**, la base: mensaje normalizado a GSM-7 en la campaña y en la previsualización, medido antes de los 150 y 160; `caracteres_quitados` por grafema | dev_backend_modulo_mowa_mes | completa |
| `19adb4c` | F6 del motor: `avisoSegmento` «ajustados a hoy…» | dev_frontend_motor | §13, solo esa clave |
| `0de6f47` | **T-MM-B9, segunda parte**: `ContextoTexto.medida` y `salida`; el editor del speech mide y muestra como la tabla | dev_backend_modulo_mowa_mes | completa (y `coordinador_motor` las líneas del motor) |
| `97ebfe0` | **T-MM-F7**: hint de GSM-7, línea «Al enviar se borran», tarjeta apilada y unidad del largo | dev_frontend_modulo_mowa_mes | completa (y designer la experiencia) |

Documentación de `designer` de la que depende: `837df75` y `90ecc80` (§10.2 de `motor-texto-enriquecido-interfaz.md`).

## 2. Trazabilidad

| RF | Implementación | Pruebas |
|---|---|---|
| RF-MM-27 GSM-7 | `a_gsm7` (motor) en este orden: NFD sin marcas, después la transliteración (`“ ” « »`→`"`, `‘ ’`→`'`, `…`→`...`, `– —`→`-`, `° º`→`o`, `ª`→`a`, espacios Zs y la tabulación → espacio) y por último borra lo que quede fuera de GSM-7. MOWA MES la aplica al texto ya evaluado, nunca a cada variable. La versión se guarda como se escribió. | Tablas de TS 23.038; recorrido de todo Unicode; idempotencia y aplicación por pieza; oro: los 6 mensajes del original == `a_gsm7(congelado)`, sin borrados ni cambios de largo, y `MATRIZ_HUELLA_GSM7` explicada fila por fila; huellas 17, 92 y la original sin cambios; conciliación de una campaña nueva y de una anterior con tildes |
| RF-MM-19 ampliado | `largo_gsm7` (los extendidos cuentan 2) sobre el mensaje normalizado; la cota con `medida=largo_gsm7_normalizado`, exacta para el texto fijo y a 1 por carácter en las variables (supuesto declarado); `muestra[].largo` en unidades GSM-7; el editor v2 mide igual que la tabla (`ContextoTexto.medida` y `salida`) | Bordes 150, 151, 160 y 161 con `€` y `…`; 158 crudos que son 160 reales; «9 a 30» sigue en 156; paridad editor = tabla; cartera sigue con `len` |
| RF-MM-27, el aviso | `caracteres_quitados` por grafema (`grafemas_borrados`, reglas de emoji de UAX #29, sin dependencias), por trozo para no inventar grafemas en las uniones; frontend: hint fijo, línea por segmento con los invisibles por su nombre, siguiendo al segmento en pantalla | Composición de emojis (tono de piel, ZWJ, banderas, keycap, etiquetas); propiedad de que la unión == lo que borra `a_gsm7`; Vitest del armado de la línea; Playwright en v1 y v2, al cambiar de segmento sin clic, a 360 px y axe |
| RF-MM-17 ampliado (M3) | Las v1 no se crean ni se editan (400 antes de cualquier otra validación); se leen, se usan en campañas y se convierten; la pantalla las muestra en solo lectura | Campaña con una v1 heredada que no es la original, sin base y con base; -ConBase de 62 `@postgres` en los tres archivos tocados |
| RF-55 (parte de MOWA MES) | La previsualización del speech con un producto real o con una selección ajusta los días a hoy en Lima, con la misma fórmula que la campaña; la regla de la campaña (RF-MM-15) no cambia | 25 días con 10 de diferencia caen en 31 a 60; paridad con `campana.py` en 15 valores y 4 fechas |

**Resultado:** los cinco tienen implementación y pruebas. Verificación final de `architec` sobre cada commit, con las capas que le correspondían: `-ConBase` con todas las `@postgres` en verde y backend en Linux en los cortes de backend, y Playwright completo en los que tocan el frontend o el contrato (442/442 en `97ebfe0`).

## 3. Decisiones

- **Del usuario:** forzar GSM-7 (2026-10-19); transliterar los signos tipográficos (2026-10-19); los espacios especiales pasan a un espacio (2026-10-20); M3 ahora.
- **De `architec`:** se normaliza antes de medir; el oro de B5 cambia a propósito (RF-54); la cota a 1 por carácter en las variables, como supuesto declarado; el orden de los commits; B9c descartado.
- **Del coordinador, acordadas con `coordinador_motor`:**
  - `a_gsm7` es función del motor, con cota de 3 por carácter (tope verdadero), y MOWA MES la aplica al texto ya evaluado;
  - el oro de B5 afirma `salida == a_gsm7(congelado)` y no reemplaza las constantes;
  - el contexto del speech mide igual que la tabla, con `medida` y `salida` fuera del contrato;
  - el valor por defecto se decide sobre el texto crudo, y la salida va al final.
- **Del coordinador, con `designer`:** lo borrado va por grafema; en la v1 la línea va en la celda Estado y conserva el tono de advertencia; la tarjeta apilada la abre el segmento; el largo sigue diciendo «caracteres», con la unidad explicada en la nota.
- **Textos que no podían entrar antes que el código que los vuelve ciertos:** `avisoSegmento` pasó de F8 a F6, y el hint de GSM-7 de F8 a F7.

## 4. Rendimiento

- **B9:** con 46 000 filas, previsualizar sube 9 % y crear 11 % (unos 10 µs por mensaje, medio segundo por campaña). Aceptado por `architec`.
- **b9b:** `medir_generacion` con 45 000 filas, sin cambio.
- **T-MM-B9c, el atajo para el texto ya simple: probado y descartado.** El ahorro (~1 µs por mensaje, ~0,05 s por campaña) queda dentro del ruido de ±0,3 s. El parche quedó guardado fuera del repositorio.

## 5. Lo que encontró la revisión antes del commit

- B16: la cota de `a_gsm7` rompía el invariante del motor («la cota es siempre un tope verdadero»), y el oro armaba el mensaje por un camino que B9 no iba a usar.
- B9: el contrato del frontend no se había regenerado, y la API falsa quedaba mal tipada; se inventaban grafemas en la unión de dos trozos; la agrupación era cuadrática con muchos indicadores regionales (lo vio `coordinador_motor`); había datos de prueba con aspecto real.
- B9, segunda parte: el valor por defecto se decidía después de la salida; la rama de plantilla del generador no tenía prueba con la medida (lo destapó una mutación después del rebase).
- B15: la cobertura de una campaña con una v1 heredada se había perdido.
- F8 y F6: dos textos que habrían prometido un comportamiento antes de que existiera.
- F7: la línea de v2 no seguía al segmento cuando cambiaba sin un clic.
- **Lo que se me pasó:** una `@postgres` que seguía esperando «venció». Era la gemela con base de una prueba ya actualizada; la encontró `architec` con `-ConBase`. Desde entonces pido que en cada entrega se lean una por una las `@postgres` que afirman un mensaje armado.

## 6. Pendientes

- `git push` de todo lo anterior: lo decide `architec` con el usuario.
- Fuera de esta tanda, sin abrir: el 150 y el 160 en frases por código, y los 32 MB del reporte.
- Opcional y sin prioridad: el perfil con cProfile de crear campaña antes y después de B9, si alguna vez interesa recuperar los ~9 µs.
- No apliqué ninguna migración: esta tanda no tiene. La base de trabajo `auto_cusco` no necesita cambios.
