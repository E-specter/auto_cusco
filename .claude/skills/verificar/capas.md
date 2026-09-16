# Capas avanzadas de verificación

Detalle de las capas que complementan a las clásicas de [SKILL.md](SKILL.md). Para cada una: qué atrapa que las demás no, dónde rinde en este proyecto, qué herramienta encaja con el stack y en qué estado está.

**Estado a la fecha de escritura:** ninguna de estas capas está instalada salvo donde se dice. Los comandos son los que se usarían al configurarlas. Agregar una herramienta al proyecto se consulta con el usuario; no se instala dentro de otra tarea.

---

## 1. Tipos estáticos

**Atrapa:** un campo que ya no existe, un `None` que llega donde se esperaba texto, un argumento en el orden equivocado. Errores que las pruebas solo ven si alguna ejecuta justo ese camino.

**Dónde rinde aquí:** en el backend entero, y sobre todo en la frontera entre casos de uso y puertos, donde los dobles de prueba pueden aceptar lo que el adaptador real rechazaría.

| Lado | Herramienta | Estado |
|---|---|---|
| Frontend | `npx astro check` (TypeScript estricto sobre `.astro` y `.ts`) | **Configurado**, en CI |
| Backend | `mypy` o `pyright` en modo estricto sobre `app/` | No configurado |

**Cuidado:** en un backend que ya existe, activar el modo estricto de golpe produce cientos de avisos y la tentación de silenciarlos. Se activa por paquete, empezando por `app/core/`.

---

## 2. Contratos

**Atrapa:** dos piezas que deben coincidir y dejan de hacerlo sin que ninguna falle por sí sola. Es el error típico de un sistema con backend y frontend separados y varios agentes trabajando en paralelo.

**Regla de este proyecto:** un contrato lee la fuente de verdad del otro lado, nunca una copia; y si deja de encontrarla, falla con un mensaje en vez de pasar en verde vacío.

| Contrato | Dónde | Estado |
|---|---|---|
| Códigos de incidencia ↔ traducciones del frontend | `backend/tests/test_codigos_incidencia.py` + `frontend/tests/nucleo/i18n-incidencias.test.ts`, sobre `CODIGOS_INCIDENCIA` | **Configurado**, cerrado por los dos extremos |
| Columnas de la tabla ↔ salida de la normalización | Pruebas del backend | **Configurado** |
| Esquema de la API ↔ tipos del cliente del frontend | Backend: `contratos/openapi.json` + `backend/tests/test_contrato_openapi.py`. Frontend: `src/lib/contrato-api.d.ts` generado + `npm run contrato:comprobar` | **Configurado**, cerrado por los dos extremos y en CI |
| Respuestas falsas de Playwright ↔ API real | `frontend/e2e/api-falsa.ts` tipa sus respuestas con los tipos generados | **Configurado** en compilación: una respuesta falsa que el backend no podría enviar no compila. No comprueba valores, solo formas |

**Cómo funciona:** el backend exporta el esquema y su prueba falla si no coincide con la API; el frontend genera sus tipos desde ese archivo y su comprobación falla si los tipos commiteados quedaron atrás. El detalle está en `docs/contrato-api.md`.

---

## 3. Pruebas basadas en propiedades

**Atrapa:** los casos que nadie imaginó. En vez de "con esta entrada sale esto", se afirma una propiedad ("normalizar dos veces da lo mismo que una", "un DNI válido siempre sale con 8 dígitos") y la herramienta genera cientos de entradas, y cuando una falla la reduce al ejemplo mínimo.

**Dónde rinde aquí,** más que en casi cualquier otro sitio del proyecto:

- **Normalización (N-1 a N-8):** idempotencia, que ningún documento válido se pierda, que un teléfono inválido nunca salga como válido, que cabeceras con espacios, tildes y mayúsculas mapeen igual.
- **Motor de mapeo de campos (RF-12):** que una plantilla de una sola referencia conserve el valor original, que el formato financiero ida y vuelta no pierda decimales.
- **Fecha desde el nombre del archivo:** que nunca sugiera una fecha inexistente (el caso del 31.02).
- **Filtros de cartera:** que filtrar y luego paginar dé los mismos productos que paginar el resultado completo.

| Lado | Herramienta | Estado |
|---|---|---|
| Backend | `hypothesis` | No configurado |
| Frontend | `fast-check` con Vitest | No configurado |

**Cuidado:** los generadores producen datos sintéticos por construcción, lo cual encaja con las reglas de datos. Nunca se siembran con valores de una sábana real.

---

## 4. Pruebas de mutación

**Atrapa:** pruebas que no protegen. La herramienta introduce errores pequeños en el código (cambia `<` por `<=`, borra una línea, invierte una condición) y comprueba si alguna prueba falla. Una mutación que sobrevive es un error que la suite dejaría pasar.

**Dónde rinde aquí:** en el núcleo de ingesta, el versionado (V-1 a V-10) y el mapeo de campos. No en todo: es lenta y su valor está donde un error silencioso cuesta caro.

| Lado | Herramienta | Estado |
|---|---|---|
| Backend | `mutmut` sobre `app/core/` | No configurado |
| Frontend | Stryker con Vitest sobre `src/lib/` | No configurado |
| Manual | Romper a propósito el comportamiento y comprobar que la prueba falla | **Práctica en uso**: así se validaron el contrato de códigos, la cola de diálogos y la fecha desde el nombre |

**Cuándo correrla:** no en cada cambio ni en CI por cada subida. Periódicamente sobre el núcleo, o al cerrar un módulo crítico.

---

## 5. Cobertura

**Atrapa:** código que ninguna prueba ejecuta. **No** mide si las pruebas comprueban algo: una línea ejecutada sin aserción cuenta como cubierta. Por eso es una señal para encontrar huecos, no una meta.

| Lado | Herramienta | Estado |
|---|---|---|
| Backend | `pytest-cov` | No configurado |
| Frontend | `@vitest/coverage-v8` | No configurado |

**Regla:** no se fija un porcentaje mínimo que invite a escribir pruebas vacías. Se mira qué ramas del núcleo quedan sin ejecutar, y se combina con mutación para saber si lo cubierto está realmente comprobado.

---

## 6. Accesibilidad automatizada

**Atrapa:** contraste insuficiente, controles sin nombre accesible, jerarquía de encabezados rota, formularios sin etiquetas, roles ARIA mal usados. El brand guide y `PRODUCT.md` exigen WCAG AA.

**Dónde rinde aquí:** en cada pantalla y en cada estado de ella (diálogos abiertos, errores de formulario, estado sin API), no solo en la carga inicial.

| Herramienta | Estado |
|---|---|
| `@axe-core/playwright` dentro de las pruebas de extremo a extremo | **Configurado** en `frontend/e2e/accesibilidad.spec.ts`: bienvenida, consola y cartera en tema claro y oscuro, más la cartera con el diálogo de guardar en error y con una selección que no aplica. Corre en CI con el resto de Playwright |

**Al agregar una pantalla o un estado con riesgo** (diálogo, error de formulario, tabla generada por script), se suma su caso a ese archivo. En Fase 1 el contraste y el foco se verificaron con un script propio y a mano; eso no se repetía solo en el siguiente cambio, axe sí.

**Cuidado:** axe detecta alrededor de un tercio de los problemas de accesibilidad. No sustituye la revisión con teclado ni con lector de pantalla; sustituye la parte que se olvida.

---

## 7. Regresión visual

**Atrapa:** cambios de aspecto que nadie pidió. Un ajuste en `tokens.css` o `ui.css` que rompe una pantalla que no se estaba mirando.

**Dónde rinde aquí:** mucho, porque el sistema visual es compartido y está gobernado por reglas estrictas (radio 0, dos tonos, no-scroll en la bienvenida). Un cambio de token afecta a todo.

| Herramienta | Estado |
|---|---|
| `expect(page).toHaveScreenshot()` de Playwright, con datos fijos de `api-falsa.ts` | No configurado |

**Cuidado:**

- Las capturas dependen del sistema operativo y del renderizado de fuentes. Las de referencia se generan y comparan **en el mismo entorno que CI** (Linux), no en Windows local.
- Se desactiva la animación de entrada y se fijan fecha, idioma y tema, o cada ejecución difiere.
- Actualizar una captura de referencia es una decisión de diseño, no un trámite para poner CI en verde.

---

## 8. Seguridad

**Atrapa:** dependencias con vulnerabilidades conocidas, secretos commiteados, patrones inseguros (SQL armado con texto, rutas de archivo sin sanear, datos personales en logs).

**Dónde rinde aquí:** el proyecto maneja datos de cobranza con nombres, documentos y teléfonos, recibe archivos subidos de hasta 64 MB y arma consultas con filtros que vienen del usuario.

| Chequeo | Herramienta | Estado |
|---|---|---|
| Dependencias del backend | `pip-audit` (o `uv pip audit` cuando esté disponible) | No configurado |
| Dependencias del frontend | `npm audit --omit=dev` | No configurado |
| Análisis estático del backend | Reglas `S` (bandit) de `ruff` | No configurado |
| Secretos en el repositorio | `gitleaks` en CI | No configurado |
| Datos personales en logs | Revisión en cada cambio que registre errores | **Práctica en uso**: el backend registra solo el tipo de excepción, no su mensaje |

**Siempre, aunque no haya herramienta:** un cambio que toca subida de archivos, filtros de consulta o registro de errores se revisa con la pregunta "¿esto puede sacar un dato de la sábana fuera de la base?".

---

## 9. Rendimiento y volumen

**Atrapa:** lo que funciona con 50 filas y se cae con 46 000. Consultas sin índice, paginación que lee la tabla entera, una interfaz que se congela con miles de incidencias.

**Referencias medidas** (`docs/versionado-sabanas.md`): normalizar y guardar un corte real ~3.9 s; cambiar la vigente 0.4 ms; entradas y salidas entre dos días ~0.3 s. Un cambio que empeore uno de estos órdenes de magnitud es un error, aunque las pruebas pasen.

| Chequeo | Herramienta | Estado |
|---|---|---|
| Volumen de ingesta | `backend/scripts/generar_sabana_sintetica.py --filas 46000` y medir | **A mano**, sin umbral automático |
| Micro-rendimiento de funciones del núcleo | `pytest-benchmark` | No configurado |
| Carga concurrente sobre la API | `locust` | No configurado; previsto en Fase 7 |
| Rendimiento de las pantallas | Lighthouse CI sobre el sitio construido | No configurado |

**Regla:** las mediciones de volumen se hacen con datos sintéticos del tamaño real, nunca con una sábana real.

---

## 10. Migraciones reversibles

**Atrapa:** una migración que sube pero no baja, o que al bajar pierde datos o deja la base en un estado que la siguiente subida no acepta.

| Chequeo | Comando | Estado |
|---|---|---|
| Modelos sin migrar | `uv run alembic check` | **Configurado**, en CI |
| Ida y vuelta | `uv run alembic upgrade head`, `uv run alembic downgrade -1`, `uv run alembic upgrade head` | No automatizado |

---

## Capas que se evaluaron y no aplican hoy

- **Pruebas de caos o de fallos de infraestructura:** el backend corre como un solo proceso sin colas ni réplicas (ver `docs/versionado-sabanas.md`). La recuperación de versiones interrumpidas ya tiene su prueba. Se reconsidera si aparece un sistema de colas.
- **Snapshots de salida textual** (`toMatchSnapshot`): tienden a aprobarse sin leerlas. Para archivos generados se prefiere comprobar cabeceras y valores concretos.
- **Pruebas en varios navegadores:** la interfaz corre en los equipos del BPO; mientras no se confirme qué navegador usan, basta Chromium. Se amplía si el usuario lo confirma.
- **Fuzzing del lector de `.xlsb`:** la lectura la hace `python-calamine`, una biblioteca externa. Lo que es propio se cubre mejor con pruebas basadas en propiedades sobre la normalización.
