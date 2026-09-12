# Documentación — auto_cusco

Índice de la documentación conceptual del proyecto.

| Documento | Contenido |
|---|---|
| [atomics-requirements.md](atomics-requirements.md) | Requerimientos funcionales atomizados y detallados (RF-01 a RF-36) — fuente de verdad funcional |
| [architecture.md](architecture.md) | Mapa conceptual, principio de puertos/adaptadores con vertical slicing, stack tecnológico, flujo de datos |
| [setup.md](setup.md) | Instalación y ejecución del proyecto, paso a paso |
| [requirements.md](requirements.md) | Resumen de contexto y requerimientos no funcionales (remite a atomics-requirements.md para el detalle funcional) |
| [modules.md](modules.md) | Módulos del sistema, requerimientos que cubren y responsabilidades |
| [testing.md](testing.md) | Protocolo de pruebas y de corrección de errores por módulo: niveles, convenciones, criterio para cerrar una tarea e integración continua |
| [versionado-sabanas.md](versionado-sabanas.md) | Evaluación y diseño del versionado de sábanas por fecha de corte: versión vigente, corrección de días pasados, eliminación y trazabilidad de formatos |
| [sabana-schema.md](sabana-schema.md) | Esquema formal de la sábana diaria: hojas, claves, columnas, reglas de normalización, clasificación RF-21 y preguntas abiertas |
| [planning.md](planning.md) | Fases, roadmap y estado actual, organizados en base a atomics-requirements.md |
| [agents/README.md](agents/README.md) | Cómo está organizada la configuración para trabajo multiagente |

## Estado del proyecto

**Las Fases 0 y 1 están cerradas.** La ingesta de sábanas funciona de extremo a extremo: el esquema está formalizado en `sabana-schema.md`, la base PostgreSQL creada y migrada, el versionado por fecha de corte con una versión vigente por día está documentado en `versionado-sabanas.md`, los endpoints de carga procesan en segundo plano, y el frontend tiene la pantalla de bienvenida y la consola de cargas. Las decisiones de arquitectura están tomadas y aplicadas: **PostgreSQL**, **API REST con FastAPI**, procesamiento **bajo demanda desde el frontend** (sin cron), y **SMS/WhatsApp** (digital) más **Cisvox/Kontactus** (VoIP) como primeras plataformas objetivo. Los requerimientos funcionales están atomizados en `atomics-requirements.md`. Quedan preguntas de negocio abiertas sobre la sábana (sección 8 de `sabana-schema.md`). Lo siguiente es la Fase 2 (selección, segmentación y métricas).
