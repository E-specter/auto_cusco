# Registro de documentación del proyecto (`/docs`)

> Índice vivo de todo lo que existe bajo `/docs`. Cualquier agente que agregue
> o descubra una ruta nueva debe añadir/actualizar una fila aquí en la misma
> sesión en que lo detecta (protocolo de autoactualización, skill
> `coordinador-multiagente`, sección 5). No borrar filas salvo que la ruta
> haya sido eliminada del proyecto y el usuario lo confirme.

| Ruta | Tipo | Propósito | Agente/rol que la creó o mantiene | Última actualización |
|---|---|---|---|---|
| /docs/README.md | Doc | Índice de la documentación y estado del proyecto | architec (docs) | 2026-09-13 |
| /docs/planning.md | Doc | Plan general, fases y avance | architec (arquitectura) | 2026-10-19 |
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
| /docs/mapeador-encabezados.md | Doc | Diseño técnico del mapeador de encabezados reutilizable (RF-57 a RF-63): formatos, estados, similitud, validación, mapeos recordados, API, componente y cortes | architec (arquitectura) | 2026-10-24 |
| /docs/mapeador-encabezados-interfaz.md | Doc | Reglas de interfaz vinculantes del mapeador de encabezados (T-MAP-F1): montaje del componente `MapeadorEncabezados`, resumen y filtro, estados, campo de carga, problemas, opciones de lectura, pantalla de cargas, accesibilidad, textos y pruebas mínimas | designer (ui) | 2026-10-27 |
| /docs/campos-adicionales-interfaz.md | Doc | Reglas de interfaz vinculantes de los campos adicionales (T-CA-F0, RF-64 a RF-66): crear un campo desde el mapeo (referencia, formulario, errores), cómo se distingue un adicional en las listas de Cartera, el editor, el constructor y el mapeador, y renombrar, archivar y reactivar | designer (ui) | 2026-10-27 |
| /docs/filtro-valores-interfaz.md | Doc | Reglas de interfaz vinculantes del filtro de valores tipo etiqueta y del orden de los filtros (T-FV-F0, RF-67 y RF-68): la lista con cantidades, «(vacío)», incluir o excluir, búsqueda, el valor marcado sin productos, la cascada y su recálculo, y reordenar con arrastre, «Subir»/«Bajar» y anuncio; marca lo que cambia en la campaña de MOWA MES | designer (ui) | 2026-10-28 |
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
| /docs/agents/coordinador_modulo_mowa_mes/plan.md | Doc | Plan de ejecución del módulo `mowa_mes` (T-MM-C1): diseño confirmado, secuencia, criterio de listo y consultas escaladas | coordinador_modulo_mowa_mes | 2026-09-13 |
| /docs/agents/coordinador_modulo_mowa_mes/briefs-agregados.md | Doc | Encargos listos para enviar de los agregados RF-MM-23 a 26 (F6-A, B8 y F6-B), con las reglas de interfaz de `designer` | coordinador_modulo_mowa_mes | 2026-09-28 |
| /docs/agents/coordinador_modulo_mowa_mes/revision-c3.md | Doc | Revisión de los agregados RF-MM-23 a 26 (T-MM-C3): commits, trazabilidad, decisiones, rendimiento y pasada manual | coordinador_modulo_mowa_mes | 2026-09-28 |
| /docs/agents/coordinador_modulo_mowa_mes/revision-c4.md | Doc | Revisión de GSM-7 (RF-MM-27, RF-MM-19 ampliado), M3 (RF-MM-17) y la parte de MOWA MES de RF-55 (T-MM-C4): commits, trazabilidad, decisiones, rendimiento y lo que encontró la revisión | coordinador_modulo_mowa_mes | 2026-10-24 |
| /docs/agents/coordinador_modulo_mowa_mes/revision-c5.md | Doc | Revisión de los extendidos de GSM-7 transliterados (RF-MM-27 ampliado, cierra S-MM-9; T-MM-C5): cortes, trazabilidad, constantes que cambian, decisiones, verificación y lo que encontró la revisión | coordinador_modulo_mowa_mes | 2026-10-27 |
| /docs/agents/coordinador_modulo_mowa_mes/revision-c6.md | Doc | Revisión de la descripción de campaña de hasta 100 caracteres y el botón «Copiar» (RF-MM-04 ampliado, cierra S-MM-3; T-MM-C6): cortes, trazabilidad, decisiones, verificación y lo que encontró la revisión | coordinador_modulo_mowa_mes | 2026-10-27 |
| /docs/agents/coordinador_modulo_mowa_mes/revision-c7.md | Doc | Revisión de la descripción de campaña de una sola línea (RF-MM-04, T-MM-C7): cortes, trazabilidad, decisiones, atajos aceptados, verificación y lo que encontró la revisión | coordinador_modulo_mowa_mes | 2026-10-27 |
| /docs/agents/coordinador_modulo_mowa_mes/revision-c2.md | Doc | Revisión integral del módulo `mowa_mes` (T-MM-C2): commits, trazabilidad de RF con pruebas, decisiones y pendientes | coordinador_modulo_mowa_mes | 2026-09-19 |
| /docs/motor-texto-enriquecido.md | Doc | Diseño técnico del motor de texto enriquecido y del constructor de columnas dinámicas (RF-42 a RF-54): estado actual, migración de MOWA MES, contratos, catálogo de funciones, riesgos | architec (arquitectura) | 2026-09-29 |
| /docs/motor-texto-enriquecido-interfaz.md | Doc | Reglas de interfaz vinculantes del motor de texto enriquecido y del constructor de columnas (T-MTE-F1): editor de piezas en línea, previsualización, errores en su lugar, variantes por segmento y reparto de componentes compartidos | designer (ui) | 2026-09-29 |
| /docs/agents/coordinador_motor_texto_enriquecido/profile.md | Doc | Perfil del coordinador del motor de texto enriquecido | architec; coordinador_motor_texto_enriquecido | 2026-09-29 |
| /docs/agents/coordinador_motor_texto_enriquecido/plan.md | Doc | Plan de ejecución del motor de texto enriquecido (T-MTE-C1): contraste del diseño con el código, ajustes D1 a D12, cortes y orden | coordinador_motor_texto_enriquecido | 2026-09-29 |
| /docs/agents/dev_backend_motor_texto_enriquecido/profile.md | Doc | Perfil del desarrollador backend del motor de texto enriquecido | architec; dev_backend_motor_texto_enriquecido | 2026-09-29 |
| /docs/agents/dev_frontend_motor_texto_enriquecido/profile.md | Doc | Perfil del desarrollador frontend del motor de texto enriquecido (bajo las reglas de designer) | architec; dev_frontend_motor_texto_enriquecido | 2026-09-29 |
| /docs/agents/dev_frontend_motor_texto_enriquecido/plan-f3-f4.md | Doc | Plan de F3 (constructor de columnas) y F4 (speech v2 en MOWA MES): pantallas, estados, escenarios de Playwright, pruebas y preguntas de contrato | dev_frontend_motor_texto_enriquecido | 2026-10-01 |
| /docs/agents/dev_frontend_motor_texto_enriquecido/dudas-designer.md | Doc | Dudas de F3 y F4 para `designer` (frontera de variantes, montaje de componentes, navegación, claves i18n) | dev_frontend_motor_texto_enriquecido | 2026-10-01 |
| /docs/agents/dev_frontend_motor_texto_enriquecido/plan-f5.md | Doc | Plan de F5, la pantalla «Generar carga» (`/generar-carga`): flujo, estados, contrato y pruebas, aprobado por `designer` | dev_frontend_motor_texto_enriquecido | 2026-10-16 |
| /docs/agents/coordinador_motor_texto_enriquecido/revision-c2.md | Doc | Revisión integral del motor de texto enriquecido (T-MTE-C2): trazabilidad de RF-42 a RF-54, hallazgos, límites, lecciones y commits | coordinador_motor_texto_enriquecido | 2026-10-19 |
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
