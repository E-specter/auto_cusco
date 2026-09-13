# Tablero de subtareas multiagente

> Escritura aditiva: cada agente agrega o actualiza sus propias filas; no
> reescribe las de otros (skill `coordinador-multiagente`, sección 6).

Estados válidos: `pendiente`, `en progreso`, `hecho`, `bloqueado`.

## Módulo `mowa_mes` — primer conector SMS (2026-09-13)

Cadena de delegación: `architec` → `coordinador_modulo_mowa_mes` → `dev_backend_modulo_mowa_mes` y `dev_frontend_modulo_mowa_mes` (con `designer` para lo visual). Requerimientos: `docs/requerimientos-mowa-mes.md` y RF-37 a RF-41 en `docs/atomics-requirements.md`. Diseño previsto: `docs/modules.md`, sección 5.1.

**Orden obligatorio:** el backend fija el contrato de la API (T-MM-B6) antes de que el frontend lo consuma (T-MM-F2 en adelante). Ningún agente delegado commitea: entrega a su coordinador, y `architec` verifica, commitea con el trailer `Agente:` de quien escribió e informa al usuario.

| ID | Descripción | Rol requerido | Agente asignado | Documentos relacionados | Estado | Notas de continuidad |
|---|---|---|---|---|---|---|
| T-MM-00 | Requerimientos generales de gestiones digitales (RF-37 a RF-41) y específicos de `mowa_mes` (RF-MM-01 a RF-MM-22), con decisiones y evidencia de los ejemplos | requisitos | architec | `atomics-requirements.md`, `requirements.md`, `requerimientos-mowa-mes.md` | hecho | Decisiones del usuario del 2026-09-13 en la sección 6 del documento del módulo; supuestos S-MM-1 a S-MM-6 por confirmar |
| T-MM-01 | Registro del módulo y diseño previsto en `modules.md`; avance en `planning.md`; perfiles y tablero en `docs/agents/` | arquitectura / docs | architec | `modules.md`, `planning.md`, `agents/` | hecho | |
| T-MM-C1 | Plan de ejecución del módulo: confirmar el diseño de `modules.md` §5.1, fijar la secuencia backend → contrato → frontend y lanzar a los agentes | arquitectura | coordinador_modulo_mowa_mes | `requerimientos-mowa-mes.md`, `modules.md`, `architecture.md` | pendiente | |
| T-MM-B1 | Calendario laboral: siguiente día gestionable (lunes a viernes sin feriados nacionales de Perú), feriados configurables y persistidos (RF-MM-08) | arquitectura / backend | dev_backend_modulo_mowa_mes | `requerimientos-mowa-mes.md` §2 | pendiente | Transversal: `app/core/services/calendario/` |
| T-MM-B2 | Supervisión digital transversal: supervisores por defecto configurables, ajuste por campaña, DNIs secuenciales, campos copiados de la primera fila válida, inclusión en el primer archivo y en el resumen (RF-37 a RF-41) | backend | dev_backend_modulo_mowa_mes | `atomics-requirements.md` §10 | pendiente | `app/core/services/gestiones_digitales/`; sin números reales en código ni pruebas |
| T-MM-B3 | Speech: días de atraso ajustados y segmento, estructura por partes sobre el motor de mapeo, versiones trazables con `Speech original` como defecto, variable de WhatsApp, límites de 150/160 (RF-MM-14 a RF-MM-19) | backend | dev_backend_modulo_mowa_mes | `requerimientos-mowa-mes.md` §4, `mapeo-campos.md` | pendiente | |
| T-MM-B4 | Campaña: inputs registrados, armado de la carga desde la selección, exclusiones con motivo, supervisión al inicio del primer archivo, división por 50 000 registros y 2 MB, archivo `.xlsx` en formato MES, límite mensual, persistencia y endpoints de previsualización, creación, listado y descarga (RF-MM-01 a RF-MM-13) | backend | dev_backend_modulo_mowa_mes | `requerimientos-mowa-mes.md` §1–3, `generacion-cargas.md`, `consulta-cartera.md`, `selecciones-guardadas.md` | pendiente | |
| T-MM-B5 | Reporte de enviados: lectura y validación, asociación a la campaña por `id` de MES, conciliación con mensaje normalizado, cifras de cargados y enviados (RF-MM-02, RF-MM-20 a RF-MM-22) | backend | dev_backend_modulo_mowa_mes | `requerimientos-mowa-mes.md` §5 y §7 | pendiente | |
| T-MM-B6 | Contrato: `contratos/openapi.json` y tipos del frontend regenerados y comprobados; documento técnico `docs/mowa-mes.md` | backend / docs | dev_backend_modulo_mowa_mes | `contrato-api.md` | pendiente | Desbloquea T-MM-F2 a T-MM-F4 |
| T-MM-B7 | Calidad de extremo a extremo: cadena completa por HTTP contra PostgreSQL (selección → campaña → archivos → reporte → conciliación) y escenarios Playwright del flujo del módulo acordados con frontend; `verificar.ps1 -ConBase` en verde | qa | dev_backend_modulo_mowa_mes | `testing.md`, skill `verificar` | pendiente | |
| T-MM-F1 | Coordinación visual con `designer`: ubicación del módulo en la navegación, patrones y componentes a reutilizar, cambios en archivos compartidos | ui | dev_frontend_modulo_mowa_mes | `design_ui/brand_guide.json`, `/DESIGN.md` | pendiente | `designer` trabaja en paralelo en la pantalla de la Fase 2; las respuestas llegan vía `architec` |
| T-MM-F2 | Pantalla de campaña MOWA MES: base de la campaña (fecha de corte y selección), inputs de la plataforma, supervisores y speech, previsualización con exclusiones y advertencias, generación y descarga de archivos | ui | dev_frontend_modulo_mowa_mes | `requerimientos-mowa-mes.md` §1–4 | pendiente | Espera T-MM-B6 |
| T-MM-F3 | Seguimiento: listado de campañas, cargados y enviados, importación del reporte de enviados y conciliación, consumo del límite mensual | ui | dev_frontend_modulo_mowa_mes | `requerimientos-mowa-mes.md` §1 y §5 | pendiente | Espera T-MM-B6 |
| T-MM-F4 | Configuración: supervisores por defecto, versiones de speech con previsualización del largo por segmento, número de WhatsApp de contacto, feriados | ui | dev_frontend_modulo_mowa_mes | `requerimientos-mowa-mes.md` §2 y §4 | pendiente | Espera T-MM-B6 |
| T-MM-F5 | Certificación de calidad del frontend: pruebas unitarias Vitest (núcleo y DOM), i18n es/en completo, `astro check` sin errores, accesibilidad y anchos del proyecto; `npm run verificar` en verde | qa / ui | dev_frontend_modulo_mowa_mes | `testing.md`, skill `verificar` | pendiente | |
| T-MM-C2 | Revisión integral del módulo contra los RF y entrega a `architec` con el informe de archivos y capas de verificación | qa | coordinador_modulo_mowa_mes | todos los anteriores | pendiente | |
