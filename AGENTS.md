# AGENTS.md — auto_cusco

Instrucciones universales para cualquier agente de código (Claude Code, Codex, OpenCode, Hermes u otro) que trabaje en este repositorio. Cada agente puede tener además su propio archivo (ver `docs/agents/README.md`), pero este documento es la fuente de verdad compartida.

## Qué es este proyecto

`auto_cusco` automatiza la gestión de cobranza y cartera: ingiere "sábanas" diarias (exportes de datos crudos), valida y normaliza esos datos, permite seleccionar/filtrar/segmentar productos, genera cargas para plataformas de contacto digital (SMS, WhatsApp, correo) y VoIP a partir de reglas de mapeo configurables, y produce **reportes** y **métricas** de seguimiento. El detalle funcional completo (RF-01 a RF-36) está en `docs/atomics-requirements.md` — es la fuente de verdad de requerimientos. Ver `docs/architecture.md` para el mapa técnico y el principio de puertos/adaptadores con vertical slicing, y `docs/modules.md` para el desglose por módulo.

## Estructura del repo

```
auto_cusco/
├── frontend/          # Astro (TypeScript) — UI, ver frontend/AGENTS.md
├── backend/           # Python (FastAPI) — API, ver backend/AGENTS.md
│   └── app/
│       ├── core/       # entidades, puertos, servicios (casos de uso) — sin infraestructura
│       ├── adapters/   # persistence (PostgreSQL), input, output (plataformas digitales/VoIP)
│       └── api/        # routers FastAPI (adaptador de entrada HTTP)
├── data/
│   ├── sabanas/        # Entrada cruda (NO versionada, solo estructura)
│   └── output/
│       ├── gestiones/  # Salida: casos generados (NO versionada)
│       └── reportes/   # Salida: reportes generados (NO versionada)
└── docs/               # Documentación de arquitectura/requerimientos/planificación
```

El backend (Python) tiene ya un esqueleto real funcionando end-to-end (arquitectura de puertos/adaptadores, caso de uso `health`), pero todavía sin módulos de negocio — ver `docs/planning.md`, Fase 0 y siguientes.

## Stack

- **Frontend**: Astro + TypeScript (`frontend/`)
- **Backend**: Python gestionado con **uv** (`backend/pyproject.toml`, `backend/uv.lock`, `backend/.venv/` — no `pip`/`venv` directo), `ruff` para lint/format, `pytest` para tests. Ver `backend/AGENTS.md`.
- **Base de datos**: PostgreSQL (decidido — configuración de ejemplo en `auto_cusco.code-workspace`; crear con `backend/scripts/init_db.sql`)
- **API**: REST separada del frontend, con **FastAPI** (decidido, implementado)
- **Disparador del procesamiento**: bajo demanda desde el frontend (decidido) — sin cron

## Reglas de datos (importante)

- Nunca commitear contenido real de `data/sabanas/` ni `data/output/**` — son datos de cobranza (sensibles). El `.gitignore` ya bloquea el contenido y solo permite `.gitkeep` y la estructura de carpetas.
- Si generas datos de prueba, usa datos sintéticos, nunca reales.
- El esquema de la sábana (hojas, clave `Pagare`, columnas, reglas de normalización y preguntas abiertas) está en `docs/sabana-schema.md`. Consúltalo antes de tocar la ingesta, y nunca copies valores personales reales (nombres, documentos, teléfonos) a la documentación, tests o conversaciones.

## Convenciones de trabajo

- Sigue las convenciones específicas de cada subcarpeta si existen (p. ej. `frontend/AGENTS.md` para el dev server de Astro).
- Antes de implementar módulos nuevos, revisa `docs/modules.md` para no duplicar responsabilidades.
- Actualiza `docs/planning.md` cuando una fase se complete o cambie de alcance.
- Antes de asumir una regla de negocio de plataforma (VoIP, SMS, WhatsApp, correo) no detallada en `docs/atomics-requirements.md`, levántala con el usuario en vez de inventarla.
