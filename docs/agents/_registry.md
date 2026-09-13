# Registro de documentación del proyecto (`/docs`)

> Índice vivo de todo lo que existe bajo `/docs`. Cualquier agente que agregue
> o descubra una ruta nueva debe añadir/actualizar una fila aquí en la misma
> sesión en que lo detecta (protocolo de autoactualización, skill
> `coordinador-multiagente`, sección 5). No borrar filas salvo que la ruta
> haya sido eliminada del proyecto y el usuario lo confirme.

| Ruta | Tipo | Propósito | Agente/rol que la creó o mantiene | Última actualización |
|---|---|---|---|---|
| /docs/README.md | Doc | Índice de la documentación y estado del proyecto | architec (docs) | 2026-09-13 |
| /docs/planning.md | Doc | Plan general, fases y avance | architec (arquitectura) | 2026-09-12 |
| /docs/modules.md | Doc | Mapa de módulos, responsabilidades, RF y dependencias | architec (arquitectura), designer (ui, módulo 10) | 2026-09-12 |
| /docs/requirements.md | Doc | Resumen de contexto de requerimientos y requerimientos no funcionales (RNF); enlaza a los RF | architec (requisitos) | 2026-09-13 |
| /docs/atomics-requirements.md | Doc | Requerimientos funcionales numerados (RF), fuente de verdad funcional | usuario; architec (requisitos) | 2026-09-13 |
| /docs/setup.md | Doc | Instalación, entorno, dependencias y base de datos | architec (docs) | 2026-09-11 |
| /docs/architecture.md | Doc | Mapa técnico, puertos/adaptadores con vertical slicing, stack y decisiones | architec (arquitectura) | 2026-09-11 |
| /docs/testing.md | Doc | Protocolo de pruebas y corrección de errores por nivel | architec (qa), designer (qa frontend) | 2026-09-12 |
| /docs/sabana-schema.md | Doc | Esquema formal de la sábana diaria y reglas de normalización | architec (requisitos) | 2026-09-11 |
| /docs/versionado-sabanas.md | Doc | Versionado de sábanas por fecha de corte | architec (arquitectura) | 2026-09-11 |
| /docs/consulta-cartera.md | Doc | Contrato de selección, filtros, métricas y resumen del top n | architec (arquitectura) | 2026-09-12 |
| /docs/mapeo-campos.md | Doc | Motor de reglas de mapeo y expresión de campos (RF-12) | architec (arquitectura) | 2026-09-12 |
| /docs/generacion-cargas.md | Doc | Generación y exportación de archivos de carga (RF-09, RF-13, RF-15) | architec (arquitectura) | 2026-09-12 |
| /docs/contrato-api.md | Doc | Contrato OpenAPI entre la API y el frontend | architec (arquitectura), designer (ui) | 2026-09-13 |
| /docs/selecciones-guardadas.md | Doc | Selecciones de cartera guardadas y compartidas | architec (arquitectura) | 2026-09-12 |
| /docs/design_ui/ | Carpeta | Guía de diseño de interfaz y marca | usuario; designer (ui) | 2026-09-07 |
| /docs/design_ui/brand_guide.json | Doc | Tokens y reglas de marca, fuente de verdad visual | usuario | 2026-09-07 |
| /docs/design_ui/home_flecto.webp | Imagen | Referencia visual para la interfaz | usuario | 2026-09-07 |
| /docs/design_ui/home_orderful.webp | Imagen | Referencia visual para la interfaz | usuario | 2026-09-07 |
| /docs/skills/ | Carpeta | Catálogo de skills reutilizables del proyecto | usuario | 2026-09-13 |
| /docs/skills/coordinador-multiagente.skill | Skill (paquete comprimido) | Coordinación multiagente y estructura de `/docs` | usuario | 2026-09-13 |
| /docs/skills/actualizar-requerimientos-rf.skill | Skill (paquete comprimido) | Integrar requerimientos informales al documento de RF | usuario | 2026-09-13 |
| /docs/agents/ | Carpeta | Coordinación y espacio de trabajo por agente | architec (docs) | 2026-09-13 |
| /docs/agents/README.md | Doc | Convención multiagente: AGENTS.md, firma e informe de commits | architec (docs), designer | 2026-09-12 |
| /docs/agents/_registry.md | Doc | Este registro | architec (docs) | 2026-09-13 |
| /docs/agents/tasks.md | Doc | Tablero compartido de subtareas multiagente | architec (docs); cada agente actualiza sus filas | 2026-09-13 |
| /docs/agents/architec/profile.md | Doc | Perfil del agente `architec` (arquitectura, requisitos, coordinación general) | architec | 2026-09-13 |
| /docs/agents/coordinador_modulo_mowa_mes/profile.md | Doc | Perfil del coordinador del módulo `mowa_mes` | architec; coordinador_modulo_mowa_mes | 2026-09-13 |
| /docs/agents/dev_backend_modulo_mowa_mes/profile.md | Doc | Perfil del desarrollador backend del módulo `mowa_mes` (E2E y calidad de código) | architec; dev_backend_modulo_mowa_mes | 2026-09-13 |
| /docs/agents/dev_frontend_modulo_mowa_mes/profile.md | Doc | Perfil del desarrollador frontend del módulo `mowa_mes` (pruebas unitarias, coordinación con designer) | architec; dev_frontend_modulo_mowa_mes | 2026-09-13 |
| /docs/requerimientos-mowa-mes.md | Doc | Requerimientos del conector SMS MOWA MES (RF-MM-01 a RF-MM-22), decisiones y evidencia de los ejemplos | architec (requisitos) | 2026-09-13 |

## Pendientes de incorporar formalmente a la skill

Rutas o convenciones que aún no encajan en la sección 1 de
`coordinador-multiagente/SKILL.md`. Se listan aquí hasta que el usuario pida
una actualización formal de la skill.

| Ruta | Propósito (inferido) | Detectada por | Fecha |
|---|---|---|---|
| /docs/atomics-requirements.md | La skill da `requirements.md` como documento RF canónico, pero en este proyecto los RF numerados viven aquí y `requirements.md` es su resumen con los RNF | architec | 2026-09-13 |
| /docs/*.md de contrato por módulo (`consulta-cartera.md`, `mapeo-campos.md`, `generacion-cargas.md`, `contrato-api.md`, `selecciones-guardadas.md`, `sabana-schema.md`, `versionado-sabanas.md`, `testing.md`, `architecture.md`) | Documentos técnicos por módulo o transversales, fuera de las siete rutas base de la skill | architec | 2026-09-13 |
| /docs/skills/*.skill | Las skills se distribuyen como paquetes comprimidos (`.skill`), no como carpetas con `SKILL.md` legibles directamente | architec | 2026-09-13 |
