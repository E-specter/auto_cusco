# Módulos

Cada módulo se lista con su responsabilidad, requerimientos que cubre (ver `docs/atomics-requirements.md`), estado y dependencias, bajo el enfoque de **puertos/adaptadores con vertical slicing** definido en RF-30 (ver `docs/architecture.md`): cada módulo expone entradas/salidas bien definidas, delega la integración con sistemas externos a adaptadores sustituibles, y se organiza internamente por caso de uso de extremo a extremo en vez de por capas técnicas.

El esqueleto real de este enfoque ya existe en `backend/app/` (`core/{entities,ports,services}`, `adapters/{input,output,persistence}`, `api/`), con un caso de uso de referencia (`health`) funcionando de extremo a extremo. Los módulos 1-7 siguientes todavía no tienen casos de uso propios implementados — se listan con su ruta prevista dentro de esa misma estructura.

## 1. Ingesta y cartera (`backend/app/core/services/ingesta_sabana/`)

- Responsabilidad: cargar sábanas diarias (RF-01), validar y normalizar datos (documentos de identidad, teléfonos, RF-02), detectar inconsistencias, y gestionar la cartera de productos — alta, actualización, omisión (RF-03).
- Cubre: RF-01, RF-02, RF-03.
- Estado: **en progreso.** Implementado el núcleo puro de normalización (reglas N-1 a N-6 y N-8 de `docs/sabana-schema.md`): entidades en `app/core/entities/sabana.py`; reglas, catálogo de columnas, mapeo de cabeceras y normalizador de filas en `app/core/services/ingesta_sabana/`; tests en `tests/test_sabana_*.py`. Lector de archivos implementado con `python-calamine` en `app/adapters/input/lector_calamine.py`. Validado contra los cortes reales. Persistencia con versionado por fecha de corte diseñada en `docs/versionado-sabanas.md` e implementada: modelos en `app/adapters/persistence/modelos.py` y migración inicial en `backend/migrations/`, ya aplicada. Guardado implementado: caso de uso en `app/core/services/ingesta_sabana/servicio.py` y repositorio PostgreSQL con `COPY` en `app/adapters/persistence/repositorio_cargas_postgres.py`. Pendiente: ejecución en segundo plano, endpoints de carga y de gestión de versiones (incluida la eliminación), recuperación de versiones interrumpidas y pantallas del frontend.
- Depende de: `docs/sabana-schema.md` y de confirmar las preguntas abiertas de su sección 8 antes de fijar las reglas afectadas.

## 2. Selección, filtrado y segmentación (`backend/seleccion/`, TBD)

- Responsabilidad: seleccionar productos de la asignación del día, aplicar filtros simples/complejos multi-criterio, segmentar/analizar por atributos, consultar historial de gestiones consolidado multicanal, y resolver la selección "top n" con manejo explícito de insuficiencia.
- Cubre: RF-04, RF-05, RF-06, RF-07, RF-08.
- Estado: no implementado.
- Depende de: módulo de Ingesta y cartera (datos normalizados de cartera) y de la consolidación de historial de gestiones (todos los canales de contactabilidad).

## 3. Métricas y analítica de selección (`backend/metricas/`, TBD)

- Responsabilidad: calcular en tiempo real los indicadores sobre los productos resultantes de filtros/selección (capital total, cantidad de cuentas, cuentas por segmento, cuota mín/máx) y los indicadores adicionales configurables por el usuario mediante funciones simples (suma, conteo, promedio, mínimo, máximo), actualizándose automáticamente ante cualquier cambio de filtros o selección.
- Cubre: RF-25, RF-26, RF-27, RF-28.
- Estado: no implementado.
- Depende de: módulo de Selección, filtrado y segmentación (opera sobre su resultado en tiempo real). Evitar cálculos complejos que saturen el procesamiento en tiempo real (restricción explícita de RF-27).

## 4. Motor de reglas de mapeo y expresión de campos (`backend/mapeo_campos/`, TBD)

- Responsabilidad: núcleo compartido que define, campo por campo, cómo se construye cada valor de un archivo de carga: valores fijos/constantes, concatenación con campos de origen (`[@campo]`), prefijos/sufijos, y parseo/tipado explícito (`fecha` con formato configurable, `numero`, `texto`, `financiero` con separadores configurables).
- Cubre: RF-12 (transversal a las secciones 3 y 4 de `docs/atomics-requirements.md`).
- Estado: no implementado.
- Depende de: nada externo — es un módulo núcleo reutilizado por Generación de cargas digitales y Generación de cargas VoIP. **No debe duplicarse por plataforma.**

## 5. Generación de cargas — plataformas digitales (`backend/cargas/digitales/`, TBD)

- Responsabilidad: generar tablas de carga personalizadas desde los productos seleccionados y producir archivos de carga por plataforma en múltiples formatos (XLSX, CSV, JSON, otros), aplicando las reglas de transformación configuradas.
- Cubre: RF-09, RF-10, RF-11, RF-13, RF-14, RF-15 (usa RF-12 vía el módulo de mapeo de campos).
- Estado: no implementado. **Primeras plataformas objetivo (decidido): SMS y WhatsApp**; correo electrónico queda para una iteración posterior.
- Depende de: módulo de Selección (productos ya filtrados/seleccionados) y del Motor de reglas de mapeo y expresión de campos.
- Convención: cada plataforma (SMS, WhatsApp, correo, ...) es un adaptador independiente y sustituible; agregar una plataforma nueva no debe requerir modificar las demás (RF-14). La estructura exacta de campos que exigen los proveedores concretos de SMS/WhatsApp elegidos debe levantarse antes de implementar cada adaptador.

## 6. Generación de cargas — VoIP (`backend/cargas/voip/`, TBD)

- Responsabilidad: generar las estructuras de datos requeridas por plataformas de llamadas VoIP, componiendo cargas a partir de múltiples tablas/archivos de origen y adaptando automáticamente cabeceras/campos/formato por plataforma.
- Cubre: RF-16, RF-17, RF-18, RF-19 (usa RF-12 vía el módulo de mapeo de campos).
- Estado: no implementado. **Plataforma objetivo de la primera integración (decidido): Cisvox, de la empresa peruana Kontactus.** Su estructura exacta de cabeceras/campos debe levantarse con el usuario o su documentación antes de implementar el adaptador (RF-18).
- Depende de: módulo de Selección, y del Motor de reglas de mapeo y expresión de campos (RF-17).
- Convención: reglas de generación independientes por plataforma VoIP, igual que en cargas digitales — el adaptador Cisvox no debe condicionar el diseño de futuros adaptadores VoIP.

## 7. Reportería (`backend/reportes/`, TBD)

- Responsabilidad: generar reportes de evolución de productos/gestiones, dar seguimiento a atributos (campos variables vs. invariables, campos de interés de la entidad), exponer el historial evolutivo por cuenta, y ofrecer un módulo de reportes configurable desde interfaz gráfica (sin desarrollo) para formatos estándar y solicitudes ocasionales, con definiciones reutilizables.
- Cubre: RF-20, RF-21, RF-22, RF-23, RF-24.
- Estado: no implementado.
- Depende de: múltiples fuentes de datos — sábanas cargadas, reportes descargados de plataformas de contactabilidad (post-envío de cargas digitales), y reportes de gestiones VoIP (manual, progresiva, predictiva). Cada fuente se integra como un adaptador de entrada independiente.

## 8. Capa de datos / persistencia (`backend/app/adapters/persistence/`)

- Responsabilidad: engine/sesiones de SQLAlchemy y modelos/migraciones de PostgreSQL. Debe almacenar la información completa de cada sábana recibida (campos variables e invariables, RF-21) para soportar el historial evolutivo (RF-22).
- Estado: **engine y sesiones implementados** (`db.py`, `postgres_health_adapter.py` de referencia); sin modelos de negocio ni migraciones todavía (llegan con la Fase 1).
- Depende de: motor de BD ya decidido (**PostgreSQL**, ver `docs/architecture.md`) y de que exista la base de datos real (`backend/scripts/init_db.sql`, pendiente de ejecución manual).

## 9. API (`backend/app/api/`, FastAPI)

- Responsabilidad: exponer los módulos anteriores (cartera, selección, métricas, cargas, reportes) al frontend vía API REST.
- Estado: **framework decidido e implementado (FastAPI)**; solo existe el endpoint de referencia `GET /health`. Los endpoints de negocio se agregan módulo por módulo a medida que avanzan las fases de `docs/planning.md`.

## 10. Frontend (`frontend/`)

- Responsabilidad: UI para selección/filtrado de productos, configuración de cargas, visualización de métricas en tiempo real, y definición/generación de reportes (RF-34: interfaz intuitiva y clara, priorizando claridad sobre estética).
- Estado: scaffold Astro mínimo, sin páginas de negocio implementadas.
- Convenciones propias: ver `frontend/AGENTS.md`.

## Convención para nuevos módulos

Al crear un módulo backend real, actualizar este documento con: ruta definitiva, responsabilidad, requerimientos (RF-xx) que cubre, estado y dependencias — para que cualquier agente (Claude Code, Codex, OpenCode, Hermes) tenga contexto actualizado sin tener que releer todo el código. Un módulo nuevo que agregue una plataforma, formato o tipo de reporte debe poder incorporarse sin modificar los módulos existentes (RF-31); si eso no es posible, revisar el diseño antes de continuar.
