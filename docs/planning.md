# Planificación

## Estado actual (2026-09-12)

- [x] Frontend Astro: scaffold, sistema visual sobre `docs/design_ui/brand_guide.json` y las pantallas de la Fase 1 (`frontend/`)
- [x] Estructura de carpetas de datos (`data/sabanas/`, `data/output/gestiones/`, `data/output/reportes/`)
- [x] `.gitignore` protegiendo datos sensibles
- [x] Requerimientos funcionales detallados y atomizados (`docs/atomics-requirements.md`, RF-01 a RF-36)
- [x] Configuración multiagente (`docs/agents/README.md`, `/AGENTS.md` y `/CLAUDE.md` en la raíz del repo)
- [x] Muestras reales de sábanas diarias en `data/sabanas/` (formato `.xlsb`, BPO "IMPULSE") — no versionadas, sirven como insumo para formalizar el esquema (RF-02)
- [x] Esquema de la sábana formalizado en `docs/sabana-schema.md` (cortes 09.09 y 10.09). Confirmados: documentos de identidad (D-1) y moneda PEN como supuesto (S-1); quedan preguntas abiertas en la sección 8
- [x] Motor de base de datos decidido: **PostgreSQL**
- [x] Mecanismo de comunicación frontend-backend decidido: **API REST separada con FastAPI**
- [x] Disparador de procesamiento decidido: **bajo demanda desde el frontend** (sin cron)
- [x] Primeras plataformas objetivo decididas: **SMS y WhatsApp** (digitales) y **Cisvox / Kontactus** (VoIP)
- [x] Backend Python: esqueleto real implementado con **uv** — proyecto FastAPI, arquitectura de puertos/adaptadores, `ruff`/`pytest` en verde (ver `backend/`)
- [x] Base de datos PostgreSQL real creada (PostgreSQL 18, base `auto_cusco`, rol `auto_cusco_app`); `GET /health` reporta `database: true`
- [x] Commit inicial del repositorio, publicado en GitHub (`E-specter/auto_cusco`, rama `main`)

Este roadmap reemplaza la versión anterior (orientada a un modelo genérico de "gestiones de cobranza") y se organiza en base a los requerimientos atómicos de `docs/atomics-requirements.md`, que es ahora la fuente de verdad funcional del proyecto.

## Fase 0 — Fundamentos de arquitectura y entorno (bloqueante)

Decisiones y piezas base de las que dependen todas las fases funcionales siguientes:

- ~~Definir el motor de base de datos~~ — **decidido: PostgreSQL** (ver `docs/architecture.md`).
- ~~Definir el mecanismo de comunicación frontend↔backend~~ — **decidido: API REST separada con FastAPI**.
- ~~Definir el disparador del procesamiento~~ — **decidido: bajo demanda desde el frontend** (el usuario sube la sábana en la UI y dispara la validación/ingesta desde ahí; no hay cron).
- [x] Esqueleto de arquitectura de **puertos/adaptadores con vertical slicing** (RF-30) implementado en `backend/app/` (`core/entities`, `core/ports`, `core/services`, `adapters/input`, `adapters/output`, `adapters/persistence`, `api/`), con un caso de uso de referencia (`health`) de extremo a extremo. Ver `backend/AGENTS.md`.
- [x] Entorno Python gestionado con **uv** (`backend/pyproject.toml`, `backend/uv.lock`, `backend/.venv/`) — no `pip`/`venv` directo.
- [x] `ruff` y `pytest` configurados y en verde (`uv run ruff check .`, `uv run pytest`).
- [x] API FastAPI mínima funcionando: `GET /health` verificado end-to-end (`uv run fastapi dev app/main.py`).
- [x] Crear el rol y la base de datos PostgreSQL reales con `backend/scripts/init_db.sql` y completar `DB_PASSWORD` en `/.env` — hecho; conexión del backend verificada end-to-end.
- [x] Formalizar el esquema exacto de "sábana" a partir de las muestras reales disponibles en `data/sabanas/` (RF-02) — ver `docs/sabana-schema.md`.

**La Fase 0 está cerrada.** El siguiente paso es la Fase 1 (ingesta y cartera). Las preguntas abiertas de la sección 8 de `docs/sabana-schema.md` no bloquean el arranque de la Fase 1, pero sí las reglas que dependen de ellas (significado de `" Días Cierre Mes Anterior"`, campos de interés interno, motivo de salida de productos).

## Fase 1 — Ingesta y cartera (RF-01 – RF-03)

Avance:

- [x] Núcleo de normalización (reglas N-1 a N-6 y N-8 de `docs/sabana-schema.md`) en `backend/app/core/services/ingesta_sabana/`, con tests sintéticos y validado contra los cortes reales.
- [x] Decisiones técnicas: lector `python-calamine` (medido contra `pyxlsb`), migraciones con Alembic, ingesta en segundo plano, cargas de fechas pasadas permitidas.
- [x] Adaptador de entrada que lee el `.xlsb` (hoja `VENCIDA`, configurable) y entrega filas al normalizador: `backend/app/adapters/input/lector_calamine.py`.
- [x] Evaluación del versionado de sábanas por fecha de corte: viable y rentable (~27 MB por versión, operaciones en milisegundos). Diseño en `docs/versionado-sabanas.md`, con C-1 a C-3 confirmados.
- [x] Modelo de persistencia con Alembic según `docs/versionado-sabanas.md`: tablas `carga`, `carga_archivo`, `carga_fila`, `carga_incidencia` y `carga_auditoria` creadas en la base local con la migración inicial. Reglas verificadas en PostgreSQL: una vigente por día, solo versiones terminadas pueden ser vigentes, pagaré único por versión y borrado en cascada con auditoría conservada.
- [x] Caso de uso de guardado: registrar versión, procesarla (normalización y `COPY` en una sola transacción, vigencia automática de la primera versión de cada fecha, pagaré repetido según V-10) y asignar vigente. Probado con repositorio en memoria, con PostgreSQL real y con volumen real sanitizado (45,989 filas procesadas en ~4 s).
- [x] Ejecución en segundo plano y endpoints REST (`backend/app/api/cargas.py`): subir archivo, listar versiones por fecha, consultar estado, ver incidencias, cambiar la vigente y eliminar versión. Verificado de punta a punta contra PostgreSQL.
- [x] Recuperar versiones que queden en `procesando`: al arrancar la aplicación vuelven a la cola.
- [x] Pantallas del frontend (`frontend/src/pages/`): bienvenida sin scroll (`/`) y consola de cargas (`/cargas`) con subida de sábana y fecha de corte sugerida desde el nombre del archivo, seguimiento del procesamiento en segundo plano, resumen de la versión, incidencias filtrables por severidad y paginadas, listado de versiones por fecha, pregunta de versión vigente (V-4, con C-1 respetada) y eliminación con la confirmación de V-8. Construidas sobre `docs/design_ui/brand_guide.json`; ver `docs/modules.md` §10. Verificadas contra el backend real y PostgreSQL con datos sintéticos, a 360x640, 768x1024, 1440x900 y 1920x1080, en tema claro y oscuro y con `prefers-reduced-motion`.

Alcance:

- Carga de sábanas diarias mediante archivos estructurados (incluyendo el formato `.xlsb` ya presente en `data/sabanas/`).
- Validación y normalización automática al cargar: formatos de documento de identidad (DNI, RUC, extranjero, etc.) y de teléfono (9 dígitos, inicia con 9).
- Detección y reporte de inconsistencias/registros inválidos.
- Gestión de cartera: identificación, alta, actualización y omisión de productos en base a las sábanas cargadas.

**La Fase 1 está cerrada.** El siguiente paso es la Fase 2 (selección, segmentación y métricas), que hereda de esta fase el sistema visual de `frontend/src/styles/` y el cliente de API de `frontend/src/lib/api.ts`.

## Fase 2 — Selección, segmentación y métricas (RF-04 – RF-08, RF-25 – RF-28)

Se agrupan porque las métricas dependen directamente de la selección/filtrado y deben evolucionar juntas en la UI.

Avance:

- [x] Consulta de cartera en el backend: campos consultables derivados del catálogo de la sábana, filtros multi-criterio validados antes de tocar la base, orden, paginación y "top n" con aviso de insuficiencia (RF-04, RF-05, RF-08). Ver `docs/consulta-cartera.md`.
- [x] Segmentación por atributo con cuentas y capital (RF-06).
- [x] Métricas de la selección: capital total, cuentas, cuentas por segmento financiero, cuota mínima y máxima, más indicadores configurables con suma, conteo, promedio, mínimo y máximo (RF-25 a RF-27).
- [x] Endpoints `GET /cartera`, `/cartera/campos`, `/cartera/metricas` y `/cartera/segmentacion`, probados contra PostgreSQL.
- [ ] Pantalla de selección, filtros y métricas en el frontend, con recálculo automático al cambiar la selección (RF-28).
- [ ] **Bloqueado — RF-07, control de gestiones multicanal:** requiere que existan las gestiones (VoIP, SMS, WhatsApp, correo) y sus fuentes. Se retoma cuando haya un modelo de gestiones, previsiblemente junto con la Fase 5.

Alcance:

- Selección de productos correspondientes a la asignación del día de gestión.
- Filtros simples y complejos multi-criterio, y segmentación/análisis por atributos.
- Control de gestiones: historial consolidado multicanal (VoIP, SMS, WhatsApp, correo, y canales futuros) y validación de contacto durante el mes actual.
- Selección por cantidad definida ("top n") respetando el ordenamiento vigente, con indicación explícita cuando la cantidad disponible es insuficiente.
- Métricas dinámicas en tiempo real: capital total, cantidad de cuentas, cuentas por segmento financiero, cuota mínima/máxima.
- Indicadores adicionales configurables por el usuario mediante funciones simples (suma, conteo, promedio, mínimo, máximo), con actualización automática al modificar filtros/selección.

## Fase 3 — Generación de cargas para plataformas digitales (RF-09 – RF-15)

- Generación de tablas de carga personalizadas a partir de los productos seleccionados.
- Adaptadores independientes por plataforma. **Primeras plataformas objetivo: SMS y WhatsApp** (decidido); correo electrónico queda para una iteración posterior, y futuras plataformas se incorporan bajo el mismo patrón de adaptador (RF-14).
- Motor de reglas de mapeo y expresión de campos (RF-12) — **compartido con la Fase 4 (VoIP)**: valores fijos, concatenación con campos de origen (`[@campo]`), prefijos/sufijos, y parseo/tipado explícito (`fecha` con formato configurable, `numero`, `texto`, `financiero` con separadores configurables).
- Exportación multi-formato: XLSX, CSV, JSON y otros formatos incorporables.
- Arquitectura modular y extensible para incorporar plataformas/formatos/reglas sin tocar el núcleo (RF-14).
- La generación de cargas queda disponible inmediatamente después de completar selección y filtrado (RF-15).

## Fase 4 — Cargas para plataformas VoIP (RF-16 – RF-19)

- Generación de estructuras de datos requeridas por plataformas de llamadas VoIP. **Plataforma objetivo de la primera integración: Cisvox, de la empresa peruana Kontactus** (decidido); su estructura exacta de cabeceras/campos debe levantarse con el usuario o su documentación antes de implementar el adaptador (RF-18).
- Composición de cargas a partir de múltiples tablas/archivos de origen, reutilizando el motor de mapeo de campos de la Fase 3 (RF-12).
- Adaptación automática a cabeceras, campos y formatos específicos de cada plataforma VoIP.
- Reglas de generación independientes por plataforma, para mantenibilidad y evolución aislada.

## Fase 5 — Reportes y trazabilidad (RF-20 – RF-24)

- Reportes sobre la evolución de productos y sus gestiones.
- Seguimiento de atributos con clasificación de campos variables/invariables (análisis de evolución solo sobre variables; se almacena la información completa en ambos casos) y marcado de campos de interés interno de la entidad.
- Historial evolutivo por cuenta/producto de los campos variables a lo largo de las sucesivas sábanas.
- Control de presencia: identificar si un producto/registro/atributo aparece o no en las distintas sábanas y procesos.
- Módulo de reportes configurable desde interfaz gráfica (sin desarrollo), para formatos estándar y solicitudes ocasionales, con definiciones reutilizables y guardables.
- Soporte de múltiples fuentes de datos: sábanas cargadas, reportes descargados de plataformas de contactabilidad (SMS, WhatsApp, correo) y reportes de gestiones VoIP (manual, progresiva, predictiva).

## Fase 6 — Integración frontend y experiencia de usuario (RF-34, transversal)

- Definir el mecanismo de comunicación frontend-backend (ver Fase 0).
- Construir las pantallas Astro necesarias para cada fase funcional: selección/filtrado (Fase 2), configuración de cargas (Fases 3-4), métricas (Fase 2), reportes (Fase 5).
- Priorizar en todo momento la claridad de la interfaz sobre el criterio estético.

## Fase 7 — Endurecimiento y evolución continua (RF-29, RF-31 – RF-33, transversal)

- Revisar la extensibilidad real del sistema tras incorporar las primeras plataformas/formatos/reportes concretos (RF-31, RF-33).
- Priorizar configuración sobre valores rígidos en código a medida que se detecten reglas nuevas (RF-32).
- Auditoría/trazabilidad, si aplica según necesidades del negocio.
- Pruebas de carga según volumen real de sábanas y cargas.

## Documentación y entorno de trabajo con agentes de IA (RF-35, RF-36)

Ya satisfecho como práctica continua, no como fase cerrada:

- `docs/` se mantiene como repositorio central de documentación técnica (especificaciones, arquitectura, módulos, reglas de negocio).
- `docs/agents/` se mantiene como espacio de trabajo compartido para agentes de IA de distintos proveedores (ver `docs/agents/README.md`).
- Cada fase completada o con cambio de alcance debe reflejarse en este documento y, si corresponde, en `docs/modules.md` y `docs/architecture.md`.
- `docs/testing.md` define el protocolo de pruebas y de corrección de errores por módulo. `backend/scripts/verificar.ps1` corre la verificación local y `.github/workflows/backend.yml` la repite en cada subida.

## Notas

- `docs/atomics-requirements.md` es la fuente de verdad funcional (RF-01 a RF-36); este documento traduce esos requerimientos en fases de ejecución.
- Las Fases 3 y 4 comparten el motor de reglas de mapeo/expresión de campos (RF-12) — debe diseñarse una sola vez y reutilizarse, no duplicarse por plataforma.
- Motor de BD (PostgreSQL) y comunicación frontend-backend (API REST) ya están decididos (ver Fase 0); lo que sigue pendiente antes de avanzar en firme con las Fases 3-4 es la estructura exacta de campos de Cisvox/Kontactus y de los adaptadores SMS/WhatsApp elegidos.
- No iniciar implementación de un módulo con reglas de negocio de plataforma (p. ej. estructura exacta de Cisvox o de un proveedor SMS/WhatsApp concreto) asumidas sin confirmar — levantar con el usuario o su documentación si `docs/atomics-requirements.md` no las detalla.
