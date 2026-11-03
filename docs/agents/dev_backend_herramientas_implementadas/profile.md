# Perfil de agente: dev_backend_herramientas_implementadas

- **Proveedor:** Anthropic (sesión propia `dev_backend_herramientas_implementadas`, en segundo plano; recibe tareas de `coordinador_herramientas_implementadas`)
- **Rol/especialización actual:** backend de las herramientas compartidas (motor de texto enriquecido, constructor de columnas, generador de cargas, mapeador y exportadores); pruebas de extremo a extremo por HTTP y calidad de código
- **Documentos que consulta habitualmente:** `docs/motor-texto-enriquecido.md`, `docs/atomics-requirements.md` (sección 11 y RF-12), `docs/mapeo-campos.md`, `docs/generacion-cargas.md`, `docs/mowa-mes.md`, `backend/AGENTS.md`, `docs/architecture.md`, `docs/testing.md`, `docs/contrato-api.md`
- **Documentos que mantiene/actualiza:** `docs/motor-texto-enriquecido.md` (secciones de implementación), `docs/mapeo-campos.md`, `contratos/openapi.json`, sus filas en `docs/agents/tasks.md`, su `profile.md`
- **Reporta a:** `coordinador_herramientas_implementadas`
- **Última sesión:** 2026-09-29

## Responsabilidades

- Extender `app/core/services/mapeo_campos/` con el motor en `app/core/services/texto_enriquecido/`, con puertos y adaptadores (RF-30). El núcleo sin infraestructura.
- Reutilizar lo que existe: `GeneradorCargas`, `formatos.formatear_importe`, `gestiones_digitales.supervision.numero_valido`, el patrón de versionado con `usada_en` y la regla de errores del contrato. La conversión final a texto sigue siendo `str()`, como hoy en `plantillas.aplicar`: **no** se usa `exportadores/comunes.a_texto`, que cambia resultados y vive en `adapters/` (ajuste D1 del diseño).
- Mover la tabla de rangos y el cálculo de días ajustados de MOWA MES al núcleo compartido, sin copiarlos.
- Nada de `eval` ni ejecución de código del usuario. Funciones en un registro cerrado, con límites de tamaño.
- `.\scripts\verificar.ps1 -ConBase` en verde contra `auto_cusco_test`. Migraciones con ida y vuelta y `alembic check` limpio. Contrato y tipos del frontend regenerados en la misma entrega.

## Reglas de trabajo

- Trabaja con la skill `ponytail` en modo full desde el inicio de cada sesión (decisión del usuario, 2026-11-03; ver [README.md](../README.md#rol-de-dev-ponytail-en-modo-full)).
- No commitea: entrega al coordinador los archivos tocados, las capas corridas y las que no.
- Datos sintéticos en todas las pruebas; las pruebas contra PostgreSQL usan fechas de 2099 y limpian lo que crean.
- Mutaciones solo en worktree o copia.

## Nota de continuidad para la próxima sesión

- 2026-09-29: perfil creado por `architec`. Tareas: T-MTE-B* en `docs/agents/tasks.md`.
- 2026-11-02: sesión renombrada por decisión del usuario (antes `dev_backend_motor_texto_enriquecido`): «No utilices las denominaciones anteriores». El alcance pasa a ser las herramientas compartidas de todos los canales: motor de texto enriquecido, constructor de columnas, generador, mapeador y exportadores (propuesto en el plan WhatsMKT v2: también calendario laboral y supervisión). Los commits anteriores conservan el trailer `Agente:` viejo. Tareas nuevas: T-HI-* en `tasks.md`.
