# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing codebase answers this: frontend en Astro 7 + TypeScript (`frontend/`), CSS vanilla con custom properties (sin preprocesador ni framework de UI, por `docs/design_ui/brand_guide.json`). Backend FastAPI (Python, gestionado con `uv`) y PostgreSQL, consumido como API REST separada — no se toca desde el frontend.

## Users

Analistas de cartera de un BPO de cobranza (empresa colaboradora de Caja Cusco). Una o dos personas por operación. Escena confirmada por el usuario: escritorio de call center, pantalla grande, **luz de oficina alta**, cada mañana temprano. El trabajo es repetitivo y con prisa: la sábana del día tiene que estar cargada y validada antes de que arranque la gestión telefónica.

Perfil: dominan el negocio de cobranza y Excel, no son técnicos. Leen números todo el día y desconfían de un dato que no pueden rastrear hasta su fila de origen.

## Product Purpose

`auto_cusco` automatiza la gestión de cobranza y cartera: ingiere las "sábanas" diarias (exportes crudos de la entidad), las valida y normaliza, permite seleccionar y segmentar productos, genera cargas para plataformas de contacto digital (SMS, WhatsApp, correo) y VoIP, y produce reportes y métricas.

Éxito de la Fase 1 (la que cubre esta superficie): el analista sube la sábana del día, entiende en segundos si quedó bien, y cuando la entidad manda un archivo corregido puede cargarlo como versión nueva y decidir cuál manda sin miedo a romper lo ya construido.

Fuente de verdad funcional: `docs/atomics-requirements.md` (RF-01 a RF-36).

## Positioning

Versionado por fecha de corte con una sola versión vigente por día, garantizado por la base de datos y no por convención. La entidad reenvía sábanas corregidas y cambia cabeceras sin avisar (caso real: `PAGARE2` → `PAGARE`); el sistema conserva cada versión con su formato original, su huella y sus incidencias, y todo lo derivado (cartera, presencia, historial, métricas) se recalcula solo al cambiar la vigente. Nada se sobrescribe y nada cambia sin confirmación explícita.

## Operating Context

- **Ritual diario:** llega un `.xlsb` de ~11 MB con ~46 000 filas, hoja `VENCIDA`, nombrado con la fecha en patrón `DD.MM.YYYY`. El analista lo sube, confirma la fecha de corte y espera.
- **El procesamiento tarda segundos**, no milisegundos: registrar la versión ~0.26 s, normalizar y guardar ~3.9 s medidos con volumen real. Corre en segundo plano; el frontend consulta el estado.
- **Las correcciones son la excepción, no la regla:** ~20 % de los días reciben una segunda versión.
- **Incidencias en volumen:** ~3 500 por corte real. No se leen de corrido; se filtran por severidad.
- **Severidades** (`docs/sabana-schema.md`): `error` (falta o es inválida la clave `Pagare`, o el documento es inválido), `advertencia` (dato inválido que no impide registrar, p. ej. teléfono), `info` (corrección prevista por las reglas, p. ej. DNI completado con ceros).
- Sin autenticación ni usuarios (decisión C-3): la auditoría registra qué pasó y cuándo, no quién.
- Disparo del procesamiento **bajo demanda desde el frontend**, sin cron.

## Capabilities and Constraints

Contrato de la API (backend en `http://127.0.0.1:8000`, documentado en `docs/versionado-sabanas.md` §4.5):

| Endpoint | Para qué |
|---|---|
| `POST /cargas` | Multipart con `fecha_corte`, `archivo` y `hoja` opcional. 202 con `id`, `version`, `estado`, `versiones_identicas`, `aviso`. 400 si el archivo está vacío, 413 si supera 64 MB |
| `GET /cargas` | Filtros `fecha_corte`, `limite`, `desplazamiento`. De la más reciente a la más antigua |
| `GET /cargas/{id}` | `estado`, `vigente`, `filas_total`, `filas_ingestadas`, conteos por severidad, `motivo_fallo`, `procesado_en` |
| `GET /cargas/{id}/incidencias` | Filtros `severidad`, `limite`, `desplazamiento`. Devuelve `total` y la lista |
| `POST /cargas/{id}/vigente` | 200 con la versión; 409 si no está terminada |
| `DELETE /cargas/{id}?dejar_fecha_sin_vigente=` | 204; 409 si es la vigente y no se confirmó |
| `GET /health` | `api` y `database` |

Reglas de negocio que la interfaz debe respetar (V-1 a V-10 en `docs/versionado-sabanas.md`):

- **V-1** Toda carga crea una versión nueva; nunca se sobrescribe.
- **V-2** Se permiten fechas pasadas.
- **V-3** La primera versión de una fecha queda vigente automáticamente al terminar.
- **V-4 / C-1** Si la fecha ya tenía vigente, hay que preguntar al terminar. **La opción preseleccionada es mantener la vigente actual.** Nada cambia sin confirmación explícita.
- **V-5** Versiones fallidas o en proceso nunca son vigentes.
- **V-6** Archivo idéntico (misma huella SHA-256) a otra versión de la fecha: se avisa y el usuario decide.
- **V-8** Para eliminar la vigente hay que elegir otra antes o confirmar explícitamente que la fecha queda sin vigente.

Restricciones técnicas: sin autenticación; un solo proceso del backend; archivo máximo 64 MB.

**Undecided:** despliegue y origen definitivo de la API en producción (hoy el frontend habla con `127.0.0.1:8000` a través del proxy de desarrollo). El backend ya soporta CORS, configurable con `CORS_ORIGENES` en `/.env` y **apagado por defecto**: mientras el navegador vea un solo origen no envía cabecera alguna, que es lo correcto.

## Brand Commitments

`docs/design_ui/brand_guide.json` es vinculante y autocontenido. Lo esencial, sin reinterpretar:

- Estilo **"Technobrutalism (organic-fused)"**: rejilla expuesta con bordes hairline, voz monoespaciada para datos, ablandado por una sola gesta heredada — la píldora completamente redondeada, reservada exclusivamente a botones, badges, tags y dots.
- **Exactamente 2 tonos**: verde señal (hue 155) y rojo-naranja señal (hue 14). Todo neutro es un tinte de esos dos tonos, **nunca gris puro**. Nunca los dos a saturación plena con el mismo peso visual en el mismo componente.
- **Inter** para la interfaz, **JetBrains Mono** para datos y microcopy.
- Escalas tipográficas y de espaciado en progresión áurea (φ = 1.618).
- **Radio 0** en todo lo estructural; 9999px solo en los elementos-píldora.
- Motivo de firma: diagrama de nodos con conectores punteados.
- CSS vanilla con custom properties; sin hex ni px hardcodeados en reglas de componente.
- Iconos **lucide** inline, stroke 1.75, heredando `currentColor`.
- Motion sutil y funcional, envuelto en `prefers-reduced-motion: no-preference`.
- i18n es/en con atributos `data-i18n`; `es` por defecto. Tema e idioma en `localStorage` (`app:appearance`), aplicados antes del primer pintado.
- Comentarios y nombres en el código **en inglés**, sea cual sea el idioma de producto.

Aclaración del brief que acota el brand guide: la regla de `100dvh` sin scroll **aplica solo a la pantalla de bienvenida**. Las pantallas operativas pueden desplazarse manteniendo los mismos tokens.

## Evidence on Hand

- Mediciones reales con volumen (`docs/versionado-sabanas.md` §3 y §4.5): 45 989 filas y 3 495 incidencias procesadas en ~3.9 s; cambiar la vigente 0.4 ms; eliminar una versión ~0.28 s.
- Esquema de sábana formalizado sobre dos cortes reales (`docs/sabana-schema.md`), con alias de cabecera observados y reglas de normalización N-1 a N-8.
- Mockups de referencia del brand guide: `docs/design_ui/home_flecto.webp`, `docs/design_ui/home_orderful.webp`.
- **Ausencias que no se deben inventar:** no hay logo, no hay nombre comercial definido más allá de `auto_cusco`, no hay clientes, cifras de negocio ni testimonios. **Ningún dato real de sábana puede aparecer en la interfaz, en ejemplos, en pruebas ni en capturas** — nombres, documentos y teléfonos son datos de cobranza sensibles; todo dato de muestra es sintético.

## Product Principles

1. **Nada cambia sin confirmación explícita.** La opción preseleccionada siempre es la que no altera el estado (C-1). Vale para elegir vigente y para eliminar.
2. **Trazabilidad hasta la fila.** Cada incidencia nombra su fila, su columna, su código y su valor original; el analista tiene que poder volver al archivo y encontrarlo.
3. **El estado del procesamiento es información, no una espera.** Segundos, no milisegundos: hay que mostrar avance real y, si falla, el motivo.
4. **Los datos de cobranza no salen de la base.** Ni a capturas, ni a logs, ni a mensajes de error, ni a documentación.
5. **Densidad antes que respiro** en las pantallas operativas: el analista lee miles de filas y compara versiones; la claridad se gana con jerarquía y alineación, no con aire.

## Accessibility & Inclusion

- WCAG **AA** como mínimo: 4.5:1 en texto de cuerpo, 3:1 en texto grande y elementos de interfaz. Cada paso de rampa usado como texto se verifica contra su fondo.
- HTML nativo antes que componentes propios: `button` para acciones, `a` solo para navegación, `dialog` para modales, `details`/`summary` para divulgación, `form` con validación nativa, `fieldset`/`legend` para grupos.
- Foco visible siempre, con `--color-focus-ring`; nunca `outline: none` sin reemplazo.
- `prefers-reduced-motion` respetado: quien lo pide recibe cambios de estado instantáneos.
- El atributo `lang` del `<html>` se actualiza al cambiar el idioma.
- Escena de uso confirmada: **luz de oficina alta** → el tema claro es el predeterminado y debe ser el más pulido; el oscuro existe y se conserva por elección del usuario.
