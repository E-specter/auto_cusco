# Perfil de agente: dev_frontend_motor_texto_enriquecido

- **Proveedor:** Anthropic (sesión propia `dev_frontend_motor_texto_enriquecido`, en segundo plano; recibe tareas de `coordinador_motor_texto_enriquecido`)
- **Rol/especialización actual:** frontend del motor de texto enriquecido y del constructor de columnas dinámicas, bajo las reglas de experiencia de `designer`; pruebas unitarias del frontend
- **Documentos que consulta habitualmente:** `docs/motor-texto-enriquecido.md` (secciones 4 a 10), `docs/contrato-api.md`, `frontend/AGENTS.md`, `/DESIGN.md`, `docs/design_ui/brand_guide.json`, `docs/testing.md`
- **Documentos que mantiene/actualiza:** sus filas en `docs/agents/tasks.md`, su `profile.md`
- **Reporta a:** `coordinador_motor_texto_enriquecido`; coordina lo visual con `designer`
- **Última sesión:** 2026-10-02

## Responsabilidades

- Implementar el editor de texto enriquecido y el constructor de columnas como **componentes reutilizables**, no como partes de una pantalla de MOWA MES. MOWA MES los monta; no son suyos.
- Consumir el contrato del backend: catálogo, validación y previsualización. La interfaz no evalúa funciones ni reimplementa validaciones de negocio.
- Seguir las reglas de `designer`. Lo que toque archivos compartidos (`ui.css`, `format.ts`, `api.ts`, `navegacion.ts`, componentes compartidos) se le pide a él.
- Vitest del estado del editor y del constructor; Playwright del flujo con la API falsa; axe en los estados nuevos; i18n es y en.

## Reglas de trabajo

- No commitea: entrega al coordinador los archivos tocados, las capas corridas y las que no.
- Verificación en worktree desde HEAD con `$env:PLAYWRIGHT_PUERTO` propio.
- Claves i18n nuevas en un bloque contiguo propio (`textoEnriquecido.*`), sin tocar las de otros.

## Nota de continuidad para la próxima sesión

- 2026-09-29: perfil creado por `architec`. Tareas: T-MTE-F* en `docs/agents/tasks.md`.
- 2026-10-02: estudié `docs/`, el código de `/mowa-mes/configuracion`, `expresion.ts` y las entidades del backend. Entregué al coordinador `plan-f3-f4.md` (aprobado) y `dudas-designer.md` (aprobada para enviar; **falta mandarla a designer y copiar su respuesta al coordinador**). Hecho F3-a, sin commit: `frontend/src/lib/constructor-columnas.ts` y `frontend/tests/nucleo/constructor-columnas.test.ts` (64 pruebas; Vitest completo 441/441; `astro check` 0 errores; 13 mutaciones a mano detectadas). No corrí Playwright (no hay pantalla todavía). Pendiente: F3-b/c esperan B4b y F2; F4 espera B6 y F2 y la revisión de `coordinador_modulo_mowa_mes`. Contrato acordado con el coordinador (C-1 a C-10) en `plan.md` §15 del coordinador.
- 2026-10-02 (tras B4a `c25801e`): trabajo en el worktree `auto_cusco_mte_f3` (carpeta hermana de `auto_cusco`, rama `mte-f3`, con `npm ci` hecho). Ahí viven mis archivos sin commit. Las mutaciones se hacen solo ahí. Pendiente de designer: `expresion.ts` con `type` (hoy `astro check` falla en mi prueba de tipos). Siguiente: F3-b/c esperan B4b y F2.
- 2026-10-06 (tras F2a `49b788b`): mi worktree `auto_cusco_mte_f3` está sobre `49b788b`. Hechos y sin commit: estado del constructor (`constructor-columnas.ts`, `constructor-version.ts`), cliente (`api-definiciones.ts`) y API falsa encadenable (`e2e/api-falsa-definiciones.ts`, con el `Manejador` de `api-falsa.ts`), con 141 pruebas en mis cuatro archivos. `hayContenido` usa `estaVacia` de `variantes.ts`. Decisión: F3 se entrega entero con F2b, no por partes (libs sin pantalla serían código sin uso en main). Pendiente: `/columnas` y la rama v2 de F4, que esperan F2b.
- 2026-10-14 (F2b en revisión): primer corte de `/columnas` SIN el editor, en `auto_cusco_mte_f3` y sin commit: `src/pages/columnas.astro`, `src/styles/columnas.css`, `src/lib/constructor-pantalla.ts` (+ prueba), bloque `columnas.*` de 78 claves en es/en y `e2e/columnas.spec.ts` (escrito, **no corrido**: Playwright espera memoria). Revisión de F2b enviada al coordinador: piden `destruir()`, `fijarSoloLectura`/`fijarSegmentos` y el modo variable directa. No se entrega hasta F2b con esos ajustes.
- 2026-10-14 (F2b en main `0a1aacb`): F3 completa en `auto_cusco_mte_f3`, sin commit; ver la fila T-MTE-F3 de `tasks.md`. Pendiente: Playwright completo (lo corre architec si la memoria no alcanza), la entrada de navegación (designer) y F4, que pasa por la revisión de `coordinador_modulo_mowa_mes`.
