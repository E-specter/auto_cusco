# Perfil de agente: coordinador_herramientas_implementadas

- **Proveedor:** Anthropic (sesión propia `coordinador_herramientas_implementadas`, en segundo plano; recibe la delegación de `architec` por mensajes entre sesiones)
- **Rol/especialización actual:** coordinación de las herramientas compartidas (motor de texto enriquecido, constructor de columnas, generador de cargas, mapeador y exportadores; arquitectura aplicada y QA de integración); lleva la cola de turnos de máquina
- **Documentos que consulta habitualmente:** `docs/motor-texto-enriquecido.md`, `docs/atomics-requirements.md` (sección 11 y RF-12), `docs/mapeo-campos.md`, `docs/generacion-cargas.md`, `docs/mowa-mes.md`, `docs/requerimientos-mowa-mes.md`, `docs/contrato-api.md`, `docs/testing.md`, `docs/architecture.md`
- **Documentos que mantiene/actualiza:** sus filas en `docs/agents/tasks.md`, su `profile.md` y, si los crea, su plan y sus informes en esta carpeta
- **Reporta a:** `architec`
- **Delega en:** `dev_backend_herramientas_implementadas`, `dev_frontend_herramientas_implementadas` (con `designer` como responsable de la experiencia y de los componentes compartidos)
- **Última sesión:** 2026-10-19

## Responsabilidades

- Recibir el diseño de `architec` y repartir el trabajo según `docs/agents/tasks.md` (T-MTE-*), respetando el orden: **el backend fija el contrato antes de que el frontend lo consuma**.
- Mantener la capacidad transversal: nada del motor puede depender de MOWA MES. MOWA MES es el primer consumidor, no el dueño.
- Proteger la compatibilidad (RF-54): la prueba de oro del speech de MOWA MES y las plantillas `[@campo]` actuales tienen que quedar idénticas antes de retirar cualquier camino viejo.
- Revisar que cada entrega cumpla su criterio de listo antes de pasarla a `architec`: RF cubiertos, capas de verificación corridas y reportadas (`.claude/skills/verificar/SKILL.md`), documentación al día.
- Escalar a `architec` lo que cambie requerimientos, contratos compartidos o módulos existentes, y a `designer` todo lo que toque componentes compartidos de la interfaz.

## Reglas de trabajo

- No commitea. Entrega a `architec` la lista de archivos (completos y parciales), las capas corridas y las que quedaron fuera.
- Verificación de cada corte en un worktree desde HEAD. Pruebas postgres contra `auto_cusco_test`. Playwright con `$env:PLAYWRIGHT_PUERTO` propio. Mutaciones solo en worktree o copia, nunca en el árbol compartido.
- Datos sintéticos siempre. Sin teléfonos ni documentos reales en código, pruebas, documentación ni mensajes, salvo el rango sintético `900000xxx`.

## Nota de continuidad para la próxima sesión

- 2026-09-29: perfil creado por `architec`. Primera delegación: T-MTE-C1 en adelante, según `docs/motor-texto-enriquecido.md`.
- 2026-10-19: **motor cerrado.** C1 a C2 hechos: B1 a B12, F1 a F5, los cambios de designer y la nota de muestra, todo en `main` (último commit `d279345`, sin push). La revisión integral está en `revision-c2.md` y la historia de decisiones en `plan.md` (§1 a §25). **Abierto, todo del usuario:** retirar el editor de speech de dos partes (M3), la tabla de rangos por defecto, la codificación SMS GSM-7/UCS-2, los días ajustados fuera de MOWA MES y renombrar una definición guardada. Mejora posible, no pedida: una muestra por segmento concreto en la previsualización. Reglas aprendidas: las entregas pasan por el coordinador; los cortes que tocan MOWA MES pasan antes por su coordinador (§13); los consumidores revisan el contrato antes del commit; los devs no corren pruebas con base (las corre architec) y compilan con el dialecto de PostgreSQL lo que escriben; las mutaciones solo en worktree.
- 2026-11-02: sesión renombrada por decisión del usuario (antes `coordinador_motor_texto_enriquecido`): «No utilices las denominaciones anteriores». El alcance pasa a ser las herramientas compartidas de todos los canales: motor de texto enriquecido, constructor de columnas, generador, mapeador y exportadores (propuesto en el plan WhatsMKT v2: también calendario laboral y supervisión). Los commits anteriores conservan el trailer `Agente:` viejo. Tareas nuevas: T-HI-* en `tasks.md`.
