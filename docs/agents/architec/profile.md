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
- 2026-09-21: **módulo `mowa_mes` cerrado.** Nueve commits propios (`7849ef0`, `25eab2f`, `082308c`, `f86308b`, `265ffca`, `ed08875`, `e15b075`, `df53a6d`, `0a6ba5d`) más los transversales de `designer` (`774f39d`, `7287f2d`, `a9fe573`, `de45322`, `d2d3f9d`, `13fadf1`) y la base de pruebas separada (`d7e3d71`). Revisión final del coordinador en `docs/agents/coordinador_modulo_mowa_mes/revision-c2.md`; `planning.md` Fase 3 y `modules.md` §5.1 actualizados. **Nada subido: falta `git push`.**
- Decisiones de architec que trascienden el módulo: `PUT /mowa-mes/configuracion` es actualización parcial (propia de ese endpoint); todo error `4xx` salvo el `422` declara `detail` string obligatorio y un endpoint puede extenderlo con campos propios, comprobado estructuralmente y sin lista de permitidos (`docs/contrato-api.md` §3); las pruebas `postgres` y los scripts de medición corren solo contra una base con sufijo `_test`.
- Pendiente con el usuario: confirmar S-MM-1 a S-MM-6 de `docs/requerimientos-mowa-mes.md` §8. Si decide distinto, S-MM-2 a S-MM-6 son cambios chicos con su prueba; S-MM-1 (integración por API con MES) sería un adaptador de salida nuevo, sin tocar el núcleo.
- Siguiente conector digital: WhatsApp, bloqueado hasta tener la estructura del proveedor. Reutiliza calendario, supervisión digital (RF-37 a RF-41) y el motor de mapeo; lo propio entra como adaptador.
