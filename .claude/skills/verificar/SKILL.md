---
name: verificar
description: Usar antes de dar por terminado cualquier cambio en auto_cusco, y cuando el usuario pregunte si algo está probado o pida pruebas. Decide qué capas de verificación le corresponden al cambio —las clásicas (núcleo, adaptadores, API, integración, extremo a extremo) y las avanzadas (tipos, contratos, propiedades, mutación, accesibilidad, regresión visual, seguridad, rendimiento, migraciones)—, cómo correrlas y qué se puede afirmar al reportarlo. Cubre backend (pytest, PostgreSQL) y frontend (Vitest, Playwright).
---

# Verificar un cambio en auto_cusco

El protocolo completo está en `docs/testing.md`. Esta guía es lo que hay que tener presente **mientras** se trabaja, no después. El detalle de cada capa avanzada —cuándo aplica, qué herramienta encaja con este stack y qué atrapa— está en [capas.md](capas.md).

## La regla

**Un cambio no está verificado hasta pasar todas las capas que le apliquen.** Pasar una capa no dice nada de otra: un caso de uso probado con dobles no demuestra que la consulta real funcione, una API probada con `TestClient` no demuestra que la pantalla haga lo correcto, y una suite en verde no demuestra que atrape un error.

Si una capa aplica y no se corrió, **se dice al reportar**, con el motivo. Nunca se reporta "probado" a secas.

**Aplicar no es acumular.** Cada capa cuesta tiempo y mantenimiento; se elige por lo que el cambio arriesga, no por completar una lista. Un cambio de copia no necesita pruebas de mutación; una regla de normalización sí merece pruebas basadas en propiedades.

## Capas clásicas

Son el mínimo. Existen y están configuradas.

| Si tocaste... | Corre como mínimo |
|---|---|
| Reglas de negocio o un caso de uso (`app/core/`) | Núcleo, con dobles de prueba |
| Un adaptador de entrada/salida (lectura de archivos, exportadores) | Adaptadores, con archivos generados en memoria |
| Un router (`app/api/`) | API con `TestClient`, sustituyendo la dependencia del caso de uso |
| Persistencia, SQL, modelos o migraciones | **Integración contra PostgreSQL real** (marcador `postgres`) |
| Algo que atraviesa varias capas | Además, una prueba de la cadena completa contra PostgreSQL |
| Lógica de interfaz (`frontend/src/lib/`) | Núcleo del frontend (`node`) o DOM (`jsdom`) según toque el documento |
| Una pantalla | Lo anterior, más extremo a extremo con Playwright |
| Cualquier cosa | Formato, lint y tipos (`ruff`; `astro check` en el frontend) |

El hueco que más se cuela: **un caso de uso nuevo que consulta la base queda con todas sus pruebas en verde usando un repositorio en memoria.** Eso deja sin verificar la paginación real, el orden real y los tipos que devuelve PostgreSQL. Si tu caso de uso consulta o escribe, le toca una prueba `postgres`.

## Capas avanzadas

Atrapan lo que las clásicas dejan pasar. **Ninguna está configurada todavía salvo donde se indica**; ver el estado y el porqué de cada una en [capas.md](capas.md).

| Capa | Qué pregunta responde | Aplica sobre todo a | Estado |
|---|---|---|---|
| Tipos estáticos | ¿El código es coherente antes de ejecutarlo? | Todo el backend | Frontend sí (`astro check`); backend no |
| Contratos | ¿Dos piezas que deben coincidir siguen coincidiendo? | Frontera frontend-backend, catálogos compartidos | Parcial: códigos de incidencia y columnas; falta el esquema de la API |
| Basadas en propiedades | ¿La regla se cumple para *cualquier* entrada, no solo las que imaginé? | Normalización (N-1 a N-8), mapeo de campos, fecha desde el nombre | No |
| Mutación | ¿Mis pruebas fallarían si el código estuviera mal? | Núcleo de ingesta, versionado, mapeo | Solo a mano ("romper a propósito") |
| Cobertura | ¿Qué código no ejecuta ninguna prueba? | Todo, como señal y no como meta | No |
| Accesibilidad automatizada | ¿La pantalla cumple WCAG AA sin revisarla a ojo? | Cada pantalla | No (se verificó a mano en Fase 1) |
| Regresión visual | ¿Cambió cómo se ve algo que nadie quería cambiar? | Pantallas, reglas del brand guide | No |
| Seguridad | ¿Hay dependencias vulnerables, secretos o patrones inseguros? | Todo, con más peso por los datos de cobranza | No |
| Rendimiento y volumen | ¿Aguanta el volumen real en el tiempo esperado? | Ingesta, consultas de cartera, generación de cargas | Solo a mano con volumen sintético |
| Migraciones reversibles | ¿La migración baja y vuelve a subir sin romper? | Cada migración nueva | Solo `alembic check` (deriva), no el ida y vuelta |

**Un nivel avanzado no configurado no se instala de paso** dentro de una tarea pequeña: agregar una herramienta al proyecto es una decisión que se consulta con el usuario. Lo que sí se hace siempre es **nombrarlo al reportar** si el cambio lo pedía.

## Qué capas le tocan a tu cambio

Además de las clásicas de arriba:

| Si tu cambio... | Suma |
|---|---|
| Agrega o cambia una regla de normalización, validación o parseo | Propiedades; mutación si es núcleo |
| Cambia un endpoint, su forma de respuesta o sus códigos de estado | Contrato con el frontend |
| Agrega un código, campo o valor que otro lado debe conocer | Contrato (catálogo compartido) |
| Crea o modifica una pantalla | Accesibilidad automatizada; regresión visual si toca el sistema visual |
| Toca tokens, `ui.css` o componentes compartidos | Regresión visual en todas las pantallas, no solo la que motivó el cambio |
| Agrega o actualiza dependencias | Auditoría de dependencias |
| Maneja archivos subidos, datos personales, SQL o cabeceras HTTP | Seguridad: análisis estático y revisión de lo que se registra en logs |
| Toca ingesta, consultas sobre cartera completa o generación de archivos | Rendimiento con volumen real sintético (~46 000 filas) |
| Agrega una migración | Ida y vuelta: `upgrade`, `downgrade -1`, `upgrade` |
| Corrige un error | La prueba que falla primero, en la capa más baja donde se reproduzca |

## Comandos

Desde `backend/`:

```powershell
.\scripts\verificar.ps1            # formato, lint y pruebas
.\scripts\verificar.ps1 -ConBase   # agrega migraciones e integración con PostgreSQL
```

Desde `frontend/`, cuando la tarea tocó la interfaz:

```powershell
npm run verificar                  # tipos, build, núcleo/DOM y extremo a extremo
```

Las pruebas `postgres` se saltan solas sin `AUTO_CUSCO_DB_TESTS=1`; que el resumen diga "9 skipped" **no** es que estén en verde.

Los comandos de las capas avanzadas, para cuando se configuren, están en [capas.md](capas.md).

## Cómo se escribe una prueba aquí

- **Datos sintéticos siempre.** Nunca nombres, documentos ni teléfonos reales, ni en pruebas ni en documentación ni en la conversación (ver `/AGENTS.md`). Para una sábana completa, `backend/scripts/generar_sabana_sintetica.py`. Los generadores de pruebas basadas en propiedades también: se construyen, nunca se alimentan de archivos reales.
- **Las pruebas contra la base limpian lo que crean** y usan fechas fuera de rango operativo para no pisar datos de trabajo.
- **Preparar, ejecutar y comprobar,** separados por una línea en blanco. Una idea por prueba, nombre en español que describa el comportamiento.
- **Cobertura mínima de algo nuevo:** caso normal, bordes, entradas inválidas y, cuando dos piezas deben coincidir, una prueba de contrato entre ellas.
- **Un error se reproduce con una prueba que falla antes de corregirlo,** en la capa más baja donde se reproduzca, y esa prueba se queda como regresión.
- **Una prueba que no puede fallar no protege nada.** Para una prueba nueva que importa, rompe a propósito el comportamiento que cubre y comprueba que falla por el motivo correcto. Es la versión manual de las pruebas de mutación, y hoy la única que tiene el proyecto.
- **Un contrato lee la fuente de verdad del otro lado,** nunca una copia guardada en la prueba; si la fuente deja de encontrarse, la prueba revienta con un mensaje, no pasa en verde vacía.

## Cómo se reporta

Nombra cada capa y lo que quedó fuera, distinguiendo **no la corrí** de **el proyecto no la tiene**. Comparar:

- ❌ "Implementado y probado, 47 pruebas en verde."
- ❌ "Núcleo, API e integración en verde." (calla que la regla nueva pedía propiedades)
- ✅ "Núcleo, adaptadores y API en verde (47 pruebas); integración contra PostgreSQL en verde (9). No aplican extremo a extremo ni regresión visual: no hay pantalla. Aplicaba basadas en propiedades por ser una regla de normalización, pero el proyecto no tiene Hypothesis configurado; lo cubrí con 12 casos de borde a mano y queda pendiente."

Lo segundo es lo que permite decidir si se puede seguir. Lo primero suena mejor y vale menos.

## Antes de cerrar

- `docs/planning.md` si se completó un punto o cambió el alcance; `docs/modules.md` si cambió el estado de un módulo.
- Si cambió una regla de negocio, actualízala en su documento (`docs/sabana-schema.md`, `docs/versionado-sabanas.md`, `docs/mapeo-campos.md`, `docs/generacion-cargas.md`, `docs/consulta-cartera.md`).
- Si configuraste una capa avanzada, actualiza su estado aquí y en [capas.md](capas.md), y en la tabla de niveles de `docs/testing.md`.
- Commit con prefijo `feat`, `fix`, `docs`, `test`, `refactor` o `chore` y el módulo entre paréntesis, firmado con el trailer `Agente: <nombre de la sesión>` (ver `docs/agents/README.md`).
- **Informa el commit al usuario en cuanto lo creas:** hash corto, mensaje, qué incluye, qué capas corrieron y cuáles no, y si falta `git push`.
