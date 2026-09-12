# Módulos

Cada módulo se lista con su responsabilidad, requerimientos que cubre (ver `docs/atomics-requirements.md`), estado y dependencias, bajo el enfoque de **puertos/adaptadores con vertical slicing** definido en RF-30 (ver `docs/architecture.md`): cada módulo expone entradas/salidas bien definidas, delega la integración con sistemas externos a adaptadores sustituibles, y se organiza internamente por caso de uso de extremo a extremo en vez de por capas técnicas.

El esqueleto real de este enfoque ya existe en `backend/app/` (`core/{entities,ports,services}`, `adapters/{input,output,persistence}`, `api/`), con un caso de uso de referencia (`health`) funcionando de extremo a extremo. Los módulos 1-7 siguientes todavía no tienen casos de uso propios implementados — se listan con su ruta prevista dentro de esa misma estructura.

## 1. Ingesta y cartera (`backend/app/core/services/ingesta_sabana/`)

- Responsabilidad: cargar sábanas diarias (RF-01), validar y normalizar datos (documentos de identidad, teléfonos, RF-02), detectar inconsistencias, y gestionar la cartera de productos — alta, actualización, omisión (RF-03).
- Cubre: RF-01, RF-02, RF-03.
- Estado: **en progreso.** Implementado el núcleo puro de normalización (reglas N-1 a N-6 y N-8 de `docs/sabana-schema.md`): entidades en `app/core/entities/sabana.py`; reglas, catálogo de columnas, mapeo de cabeceras y normalizador de filas en `app/core/services/ingesta_sabana/`; tests en `tests/test_sabana_*.py`. Lector de archivos implementado con `python-calamine` en `app/adapters/input/lector_calamine.py`. Validado contra los cortes reales. Persistencia con versionado por fecha de corte diseñada en `docs/versionado-sabanas.md` e implementada: modelos en `app/adapters/persistence/modelos.py` y migración inicial en `backend/migrations/`, ya aplicada. Guardado y API implementados: caso de uso en `app/core/services/ingesta_sabana/servicio.py`, repositorio PostgreSQL con `COPY` en `app/adapters/persistence/repositorio_cargas_postgres.py` y endpoints en `app/api/cargas.py`, con procesamiento en segundo plano y recuperación de versiones interrumpidas al arrancar. Pendiente: pantallas del frontend.
- Depende de: `docs/sabana-schema.md` y de confirmar las preguntas abiertas de su sección 8 antes de fijar las reglas afectadas.

## 2. Selección, filtrado y segmentación (`backend/app/core/services/seleccion_cartera/`)

- Responsabilidad: seleccionar productos de la asignación del día, aplicar filtros simples/complejos multi-criterio, segmentar/analizar por atributos, consultar historial de gestiones consolidado multicanal, y resolver la selección "top n" con manejo explícito de insuficiencia.
- Cubre: RF-04, RF-05, RF-06, RF-07, RF-08.
- Estado: **implementado en el backend**, salvo RF-07. Núcleo en `app/core/services/seleccion_cartera/` (catálogo de campos y validación de consultas), adaptador en `app/adapters/persistence/repositorio_cartera_postgres.py` y endpoints en `app/api/cartera.py`. Contrato en `docs/consulta-cartera.md`. Pendiente: la pantalla del frontend y RF-07, que espera a que existan las gestiones.
- Depende de: módulo de Ingesta y cartera (la cartera es la versión vigente de cada fecha) y, para RF-07, de la consolidación de historial de gestiones (todos los canales de contactabilidad).

## 3. Métricas y analítica de selección (`backend/app/core/services/seleccion_cartera/`)

- Responsabilidad: calcular en tiempo real los indicadores sobre los productos resultantes de filtros/selección (capital total, cantidad de cuentas, cuentas por segmento, cuota mín/máx) y los indicadores adicionales configurables por el usuario mediante funciones simples (suma, conteo, promedio, mínimo, máximo), actualizándose automáticamente ante cualquier cambio de filtros o selección.
- Cubre: RF-25, RF-26, RF-27, RF-28.
- Estado: **implementado en el backend** dentro del mismo caso de uso que la selección, porque las métricas se calculan sobre la misma consulta filtrada: `GET /cartera/metricas` devuelve capital total, cuentas, cuentas por segmento financiero, cuota mínima y máxima, más los indicadores configurables de RF-27. Ver `docs/consulta-cartera.md`. Pendiente: RF-28, que es el recálculo automático en la pantalla al cambiar filtros o selección.
- Depende de: módulo de Selección, filtrado y segmentación (opera sobre su resultado en tiempo real). Evitar cálculos complejos que saturen el procesamiento en tiempo real (restricción explícita de RF-27).

## 4. Motor de reglas de mapeo y expresión de campos (`backend/app/core/services/mapeo_campos/`)

- Responsabilidad: núcleo compartido que define, campo por campo, cómo se construye cada valor de un archivo de carga: valores fijos/constantes, concatenación con campos de origen (`[@campo]`), prefijos/sufijos, y parseo/tipado explícito (`fecha` con formato configurable, `numero`, `texto`, `financiero` con separadores configurables).
- Cubre: RF-12 (transversal a las secciones 3 y 4 de `docs/atomics-requirements.md`).
- Estado: **implementado el núcleo.** Entidades en `app/core/entities/mapeo.py` y motor en `app/core/services/mapeo_campos/` (plantillas con `[@campo]`, tipado de texto, número, fecha y financiero, y generación de filas que junta los errores sin detenerse). Contrato en `docs/mapeo-campos.md`. Pendiente: guardar definiciones desde la interfaz y los adaptadores de cada plataforma.
- Depende de: nada externo — es un módulo núcleo reutilizado por Generación de cargas digitales y Generación de cargas VoIP. **No debe duplicarse por plataforma.**

## 5. Generación de cargas — plataformas digitales (`backend/app/core/services/generacion_cargas/`)

- Responsabilidad: generar tablas de carga personalizadas desde los productos seleccionados y producir archivos de carga por plataforma en múltiples formatos (XLSX, CSV, JSON, otros), aplicando las reglas de transformación configuradas.
- Cubre: RF-09, RF-10, RF-11, RF-13, RF-14, RF-15 (usa RF-12 vía el módulo de mapeo de campos).
- Estado: **implementada la generación y la exportación.** Caso de uso en `app/core/services/generacion_cargas/`, exportadores XLSX/CSV/JSON en `app/adapters/output/exportadores/` (uno por formato, tras el puerto `exportador_tabla_port.py`) y endpoints en `app/api/archivos_carga.py`, con previsualización antes de descargar. Contrato en `docs/generacion-cargas.md`. Pendiente: guardar definiciones desde la interfaz y los adaptadores de cada plataforma. **Primeras plataformas objetivo (decidido): SMS y WhatsApp**; correo electrónico queda para una iteración posterior.
- Depende de: módulo de Selección (productos ya filtrados/seleccionados) y del Motor de reglas de mapeo y expresión de campos.
- Convención: cada plataforma (SMS, WhatsApp, correo, ...) es un adaptador independiente y sustituible; agregar una plataforma nueva no debe requerir modificar las demás (RF-14). La estructura exacta de campos que exigen los proveedores concretos de SMS/WhatsApp elegidos debe levantarse antes de implementar cada adaptador.

## 6. Generación de cargas — VoIP (`backend/cargas/voip/`, TBD)

- Responsabilidad: generar las estructuras de datos requeridas por plataformas de llamadas VoIP, componiendo cargas a partir de múltiples tablas/archivos de origen y adaptando automáticamente cabeceras/campos/formato por plataforma.
- Cubre: RF-16, RF-17, RF-18, RF-19 (usa RF-12 vía el módulo de mapeo de campos).
- Estado: no implementado. **Plataforma objetivo de la primera integración (decidido): Cisvox, de la empresa peruana Kontactus.** Su estructura exacta de cabeceras/campos debe levantarse con el usuario o su documentación antes de implementar el adaptador (RF-18).
- Depende de: módulo de Selección, y del Motor de reglas de mapeo y expresión de campos (RF-17).
- Convención: reglas de generación independientes por plataforma VoIP, igual que en cargas digitales — el adaptador Cisvox no debe condicionar el diseño de futuros adaptadores VoIP.

## 7. Reportería (`backend/reportes/`, TBD)

- Reutiliza: los exportadores de `app/adapters/output/exportadores/` para los formatos de salida (RF-24); son genéricos, reciben cabeceras y filas.
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
- Estado: **Fase 1 implementada y con pruebas automáticas.** Dos pantallas Astro estáticas que hablan con la API REST desde el navegador; sin framework de UI ni estado de servidor.
- Pruebas: Vitest (`frontend/tests/nucleo/` y `frontend/tests/dom/`) y Playwright (`frontend/e2e/`), las herramientas que recomienda la documentación de Astro. Ver `docs/testing.md` secciones 2, 4 y 7.
- Convenciones propias: ver `frontend/AGENTS.md`.

### Estructura

| Ruta | Para qué |
|---|---|
| `src/pages/index.astro` | Bienvenida. **Única pantalla bloqueada a `100dvh` sin scroll** (regla del brand guide). Diagrama de nodos que dibuja el mecanismo del producto y cifras en vivo leídas de `GET /cargas` |
| `src/pages/cargas.astro` | Consola de cargas. Una fecha de corte a la vez: regla de fechas, versiones del día, resumen e incidencias. Aquí viven los diálogos de V-4, V-6, V-7 y V-8 |
| `src/layouts/Shell.astro` | Cabecera común: pulso de `GET /health`, selector de idioma y de tema, y el script en línea que aplica la apariencia **antes del primer pintado** |
| `src/lib/api.ts` | Cliente tipado de la API. Distingue `ApiError` (el servidor respondió que no) de `NetworkError` (no se pudo contactar) |
| `src/lib/i18n.ts` | i18n vanilla es/en por atributos `data-i18n`; ambos diccionarios viajan en el bundle |
| `src/lib/format.ts` | Fechas, números y tamaños; incluye la sugerencia de fecha de corte desde el nombre del archivo (`DD.MM.YYYY`) |
| `src/styles/` | `tokens.css` (única fuente de verdad visual), `base.css`, `ui.css` (vocabulario compartido) y `console.css` |
| `src/components/Icon.astro` | Inserta iconos lucide en línea en tiempo de compilación, sin fuente de iconos ni peticiones extra |

### Decisiones de esta fase

- **Fuente de verdad visual:** `docs/design_ui/brand_guide.json`, sin reinterpretar. Los tokens viven en `src/styles/tokens.css`; **ninguna regla de componente escribe un hex o un px a mano**. El sistema tal como quedó construido —paleta, escalas, reglas con nombre y componentes— está registrado en `/DESIGN.md`, que es descriptivo: documenta lo que hace el código, incluidas las divergencias respecto del brand guide y por qué existen.
- **`console.css` es global, no con ámbito de Astro**, porque la consola construye la regla de fechas, las filas de versión, las cifras y la tabla de incidencias desde el script en tiempo de ejecución, y los estilos con ámbito no alcanzan al DOM que crea el script.
- **Origen de la API:** el navegador habla con un prefijo `/api` del mismo origen, que `astro.config.mjs` redirige a `http://127.0.0.1:8000` en desarrollo (variable `API_ORIGIN`). Así no hacen falta cabeceras CORS y esa sigue siendo la vía recomendada. `PUBLIC_API_URL` permite apuntar a un origen absoluto; en ese caso hay que habilitar CORS en el backend con `CORS_ORIGENES` en `/.env`, que viene vacío —y por tanto apagado— por defecto.
- **Seguimiento del procesamiento:** sondeo de `GET /cargas/{id}` cada 1.2 s hasta que la versión cierra. La ingesta tarda segundos, no milisegundos.
- **C-1 respetada en el código:** en la pregunta de V-4 la opción marcada es siempre *mantener la vigente actual*. Además, si el aviso de archivo idéntico (V-6) está abierto cuando termina el procesamiento, la pregunta **espera a que se cierre** en vez de apilarse encima.
- **Fuentes autohospedadas** (Inter variable y JetBrains Mono 400/500/700) en `public/fonts/`, precargadas.
- **Los mensajes de incidencia se traducen por código, no por texto.** El backend escribe `detalle` en español; la interfaz resuelve `incidencia.<codigo>` en el diccionario y usa la frase del servidor como respaldo para cualquier código que todavía no conozca. Si se agrega un código nuevo en `backend/app/core/services/ingesta_sabana/`, añade su clave en `src/i18n/es.json` y `en.json`.
- **Selector de archivo propio.** El botón nativo de `<input type="file">` toma su texto del idioma del navegador, no del de la página, así que no se puede traducir. El input real sigue existiendo y siendo enfocable; la etiqueta visible es un `<label for>` traducido, y el recuadro acepta además arrastrar y soltar. Por eso ese campo se valida desde el código y no con `required`: el navegador no puede anclar su globo de validación a un control personalizado.
- **Un solo bloque de reemplazo** (`.standIn`) cubre los dos estados en que la consola no tiene de qué hablar: primera ejecución y API inalcanzable. En ambos, la regla de fechas, su leyenda y los paneles se retiran, y al no haber API el botón de subir queda deshabilitado.

## Convención para nuevos módulos

Al crear un módulo backend real, actualizar este documento con: ruta definitiva, responsabilidad, requerimientos (RF-xx) que cubre, estado y dependencias — para que cualquier agente (Claude Code, Codex, OpenCode, Hermes) tenga contexto actualizado sin tener que releer todo el código. Un módulo nuevo que agregue una plataforma, formato o tipo de reporte debe poder incorporarse sin modificar los módulos existentes (RF-31); si eso no es posible, revisar el diseño antes de continuar.
