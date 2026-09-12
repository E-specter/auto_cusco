---
version: 1
slug: "frontend-src-pages-cargas-astro"
primary_target: "frontend/src/pages/cargas.astro"
related_targets: ["frontend/src/pages/index.astro"]
---

Superficie: consola de cargas (`/cargas`), modo Operate. Relacionada: bienvenida (`/`), única pantalla sin scroll.

Audiencia: analista de cartera de BPO, escritorio de call center con luz de oficina alta, cada mañana. Tarea: subir la sábana del día, ver procesar, leer el resultado y decidir qué versión manda. Restricciones: API REST real (`docs/versionado-sabanas.md` §4.5), reglas V-1 a V-10, decisión C-1, cero datos reales de sábana en pantalla.

## Direction contract

THESIS: La consola pertenece a una fecha de corte a la vez; elegido el día, todo en pantalla es de ese día. Rechaza la bandeja genérica de archivos subidos.

OWN-WORLD: `docs/design_ui/brand_guide.json` sin reinterpretar — rejilla hairline a radio 0, píldora 9999px solo en botón/badge/dot, verde 155 y rojo-naranja 14 sobre neutros teñidos de esos tonos, Inter en chrome y JetBrains Mono en todo dato.

STORY: El analista entiende en qué estado quedó el día, sube su corrección sin miedo, y elige vigente con las cifras de ambas versiones a la vista.

FIRST VIEWPORT: Barra con pulso de la API, idioma y tema. A todo el ancho, la regla de fechas de corte: cada día un nodo del diagrama punteado, vigente en verde, sin vigente en rojo-naranja, hoy al extremo derecho; la acción primaria "Subir sábana" cierra la regla, junto a la fecha activa, y baja a su propia fila por debajo de 64rem. Bajo ella, 38.2% izquierda las versiones del día apiladas con estado y vigencia; 61.8% derecha las cifras de la elegida en mono sobredimensionado. Al pie, incidencias filtrables por severidad.

SIGNATURE INTERACTION: La regla de fechas es el diagrama de nodos del brand guide hecho funcional. El nodo de una versión en proceso late mientras el sondeo la sigue y lleva además borde punteado, que es lo que la distingue sin movimiento. En la bienvenida los conectores punteados se revelan al cargar con `clip-path` — `stroke-dashoffset` haría marchar los guiones en vez de dibujar la línea.

FORM: "El día en foco", posición 3 de la lista ordenada; seed key 89187bd4, scope surface, mode operate, code-led.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Decisiones abiertas

- Origen de la API en producción. La consola habla por el proxy de Vite en `/api` (mismo origen), que sigue siendo la vía recomendada. Si alguna vez se sirve desde un origen distinto, el backend ya soporta CORS: se enciende completando `CORS_ORIGENES` en `/.env`, vacío y apagado por defecto.
