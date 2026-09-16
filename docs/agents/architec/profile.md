# Perfil de agente: architec

- **Proveedor:** Anthropic (Claude Code, sesión `architec`)
- **Rol/especialización actual:** arquitectura, requisitos y coordinación general del backend
- **Documentos que consulta habitualmente:** `/AGENTS.md`, `docs/planning.md`, `docs/modules.md`, `docs/atomics-requirements.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/testing.md`, `.claude/skills/verificar/SKILL.md`
- **Documentos que mantiene/actualiza:** `docs/atomics-requirements.md` (RF), `docs/requirements.md`, `docs/modules.md`, `docs/planning.md`, `docs/architecture.md`, documentos técnicos por módulo del backend, `docs/agents/_registry.md`, `docs/agents/tasks.md`
- **Última sesión:** 2026-09-16

## Responsabilidades

- Traducir los pedidos del usuario a requerimientos formales (skill `actualizar-requerimientos-rf`) y a un diseño arquitectónico coherente con puertos/adaptadores y vertical slicing (RF-30).
- Delegar la ejecución de módulos a sus coordinadores y revisar que el resultado respete `docs/planning.md`, `docs/modules.md` y los RF.
- Verificar lo entregado por los agentes delegados antes de commitear, con las capas de verificación que correspondan (`verificar`).
- Commitear el trabajo de los agentes delegados con el trailer `Agente:` de quien lo escribió e informar cada commit al usuario (`docs/agents/README.md`).
- Coordinar con la sesión `designer` los cambios que afecten al frontend compartido.

## Cadena de delegación vigente

| Módulo | Coordinador | Ejecutores |
|---|---|---|
| `mowa_mes` (primer conector SMS) | `coordinador_modulo_mowa_mes` | `dev_backend_modulo_mowa_mes`, `dev_frontend_modulo_mowa_mes` (con `designer` para lo visual) |

## Nota de continuidad para la próxima sesión

- 2026-09-13: requerimientos generales de gestiones digitales (supervisión) y específicos de `mowa_mes` en redacción; decisiones del usuario: RF nuevos como sección aparte sin renumerar, fecha en todos los speech y exclusión de productos sin speech, supervisión configurable por campaña. Delegación a las sesiones ya abiertas `coordinador_modulo_mowa_mes`, `dev_backend_modulo_mowa_mes` y `dev_frontend_modulo_mowa_mes`: el usuario eligió usarlas en vez de lanzar subagentes, para no tener dos agentes con el mismo nombre en el repositorio. Requerimientos commiteados en `1bd7bb7`.
- 2026-09-14 a 2026-09-16: commits del módulo, todos sin push: `7849ef0` (B6a), `a9bbe4b` (respuestas C-1 a C-6), `25eab2f` (F4), `5af69ec` (decisiones del usuario: enviado solo con `estado` = `enviado`, documento que no es DNI ni RUC se carga con advertencia `documento_no_estandar`, S-MM-7 y S-MM-8 confirmados), `082308c` (B6b), `f86308b` (F3 y PUT parcial de configuración) y `265ffca` (F2 parte A). `designer` commiteó `7287f2d` (navegación) y `a9fe573` (`/cartera`, que destraba F2 parte B y F5).
- Cómo se commitea cada corte: worktree temporal desde HEAD con los archivos completos copiados. Los parciales compartidos se arman desde HEAD: `es.json`/`en.json` con solo el bloque nuevo de `mowaMes.*` y `tasks.md` con solo las filas del corte. Luego se corren `verificar.ps1 -ConBase` y `npm run verificar` con Playwright en un puerto propio (4398), se comprueban las huellas SHA-256 contra el árbol y se stagea con `git add` más `hash-object`/`update-index` para los parciales. Un solo commit con varios trailers cuando separar backend y frontend dejaría un commit intermedio en rojo (prueba de códigos contra i18n).
- Decisiones de architec en el módulo: `PUT /mowa-mes/configuracion` es actualización parcial (omitido conserva, `null` en WhatsApp borra, `null` en límites da 422), propia de ese endpoint; `/supervisores` sigue siendo reemplazo completo. `con_correspondencia` por id cuenta cualquier estado y no se rotula como enviados.
- Siguiente: F2 parte B (sobre `a9fe573`), luego F5 sobre ese commit, cierre de B7 y revisión integral T-MM-C2 del coordinador. El módulo se marca cerrado en `planning.md` solo cuando F5 tenga axe en verde para Configuración, Seguimiento y Campaña.
