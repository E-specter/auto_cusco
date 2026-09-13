# Documentación — auto_cusco

Índice de la documentación conceptual del proyecto.

| Documento | Contenido |
|---|---|
| [atomics-requirements.md](atomics-requirements.md) | Requerimientos funcionales atomizados y detallados (RF-01 a RF-36) — fuente de verdad funcional |
| [architecture.md](architecture.md) | Mapa conceptual, principio de puertos/adaptadores con vertical slicing, stack tecnológico, flujo de datos |
| [setup.md](setup.md) | Instalación y ejecución del proyecto, paso a paso |
| [requirements.md](requirements.md) | Resumen de contexto y requerimientos no funcionales (remite a atomics-requirements.md para el detalle funcional) |
| [modules.md](modules.md) | Módulos del sistema, requerimientos que cubren y responsabilidades |
| [mapeo-campos.md](mapeo-campos.md) | Motor de reglas de mapeo y expresión de campos (RF-12): plantillas, tipado y formatos, compartido por las cargas digitales y VoIP |
| [consulta-cartera.md](consulta-cartera.md) | Contrato de consulta de cartera: endpoints, sintaxis de filtros, tipos de campo y operadores, y reglas de selección |
| [contrato-api.md](contrato-api.md) | Contrato entre la API y el frontend: `contratos/openapi.json`, cómo se regenera y qué garantizan sus pruebas |
| [selecciones-guardadas.md](selecciones-guardadas.md) | Selecciones de cartera guardadas y compartidas: qué se guarda, validez al guardar y al cargar, nombre único y endpoints |
| [generacion-cargas.md](generacion-cargas.md) | Generación de archivos de carga (RF-09, RF-13, RF-15): endpoints, previsualización, formatos XLSX/CSV/JSON y sus opciones |
| [testing.md](testing.md) | Protocolo de pruebas y de corrección de errores por módulo: niveles, convenciones, criterio para cerrar una tarea e integración continua |
| [versionado-sabanas.md](versionado-sabanas.md) | Evaluación y diseño del versionado de sábanas por fecha de corte: versión vigente, corrección de días pasados, eliminación y trazabilidad de formatos |
| [sabana-schema.md](sabana-schema.md) | Esquema formal de la sábana diaria: hojas, claves, columnas, reglas de normalización, clasificación RF-21 y preguntas abiertas |
| [planning.md](planning.md) | Fases, roadmap y estado actual, organizados en base a atomics-requirements.md |
| [agents/README.md](agents/README.md) | Cómo está organizada la configuración para trabajo multiagente |

## Estado del proyecto

**Las Fases 0, 1 y 2 están cerradas en el backend, y la Fase 3 está avanzada.**

- **Ingesta (Fase 1):** funciona de extremo a extremo. El esquema está formalizado en `sabana-schema.md`, la base PostgreSQL creada y migrada, el versionado por fecha de corte con una versión vigente por día documentado en `versionado-sabanas.md`, los endpoints procesan en segundo plano y el frontend tiene la pantalla de bienvenida y la consola de cargas.
- **Selección y métricas (Fase 2):** filtros, orden, top-n, segmentación e indicadores sobre la versión vigente, con su contrato en `consulta-cartera.md`. Falta la pantalla en el frontend.
- **Generación de cargas (Fase 3):** el motor de reglas de mapeo (`mapeo-campos.md`) y la generación de archivos en XLSX, CSV y JSON (`generacion-cargas.md`) están implementados y probados. Falta guardar definiciones desde la interfaz, la pantalla de generación, y los adaptadores de cada plataforma, que dependen de levantar la estructura de campos que exige cada proveedor.
- **VoIP (Fase 4):** bloqueada hasta conocer las cabeceras que espera Cisvox; el motor y los formatos ya están listos para reutilizarse.

Las decisiones de arquitectura están tomadas y aplicadas: **PostgreSQL**, **API REST con FastAPI**, procesamiento **bajo demanda desde el frontend** (sin cron), y **SMS/WhatsApp** (digital) más **Cisvox/Kontactus** (VoIP) como primeras plataformas objetivo. Los requerimientos funcionales están atomizados en `atomics-requirements.md`. Quedan preguntas de negocio abiertas sobre la sábana (sección 8 de `sabana-schema.md`).
