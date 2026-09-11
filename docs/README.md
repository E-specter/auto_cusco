# Documentación — auto_cusco

Índice de la documentación conceptual del proyecto.

| Documento | Contenido |
|---|---|
| [atomics-requirements.md](atomics-requirements.md) | Requerimientos funcionales atomizados y detallados (RF-01 a RF-36) — fuente de verdad funcional |
| [architecture.md](architecture.md) | Mapa conceptual, principio de puertos/adaptadores con vertical slicing, stack tecnológico, flujo de datos |
| [setup.md](setup.md) | Instalación y ejecución del proyecto, paso a paso |
| [requirements.md](requirements.md) | Resumen de contexto y requerimientos no funcionales (remite a atomics-requirements.md para el detalle funcional) |
| [modules.md](modules.md) | Módulos del sistema, requerimientos que cubren y responsabilidades |
| [sabana-schema.md](sabana-schema.md) | Esquema formal de la sábana diaria: hojas, claves, columnas, reglas de normalización, clasificación RF-21 y preguntas abiertas |
| [planning.md](planning.md) | Fases, roadmap y estado actual, organizados en base a atomics-requirements.md |
| [agents/README.md](agents/README.md) | Cómo está organizada la configuración para trabajo multiagente |

## Estado del proyecto

Fase de arranque avanzada: existe el scaffold del frontend (Astro), la estructura de carpetas de datos, muestras reales de sábanas diarias en `data/sabanas/`, y un esqueleto real de backend (FastAPI + PostgreSQL, gestionado con `uv`) en `backend/`, con la arquitectura de puertos/adaptadores funcionando de extremo a extremo (`GET /health`). Los requerimientos funcionales ya están atomizados en `atomics-requirements.md`, y todas las decisiones bloqueantes de la Fase 0 ya están tomadas y aplicadas: **PostgreSQL**, **API REST con FastAPI**, procesamiento **bajo demanda desde el frontend** (sin cron), y **SMS/WhatsApp** (digital) más **Cisvox/Kontactus** (VoIP) como primeras plataformas objetivo. El esquema de la sábana ya está formalizado en `sabana-schema.md`, con algunas preguntas de negocio pendientes, y la base de datos PostgreSQL real está creada y conectada (`GET /health` en verde). **La Fase 0 está cerrada**; lo siguiente es la Fase 1 (ingesta y cartera).
