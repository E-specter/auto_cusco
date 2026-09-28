# Revisión de los agregados de `mowa_mes` (T-MM-C3)

> **Cerrada el 2026-09-28.** Los cuatro requerimientos están implementados y commiteados, salvo el cambio chico de la sección 6, que va en el corte de cierre. Queda un pendiente de `designer`, fuera del módulo.

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Requerimientos: RF-MM-23 a RF-MM-26 (`93b7ca6`, precisiones D-1 a D-3 en `fa19cfe`).

## 1. Commits (sin push)

| Commit | Contenido | Agente |
|---|---|---|
| `1ada767` | F6-A: paginación de la muestra y de las exclusiones de la previsualización (RF-MM-26) | dev_frontend, coordinador |
| `aed0af5` | B8 y F6-B: tarifa, costo en soles y plantilla del nombre de los archivos (RF-MM-23 a 25), `campo` en los 400 y el apilado de las tablas de la previsualización | dev_backend, dev_frontend, coordinador |

Commits de `designer` de los que dependen: `be80ac5` (`formatSoles` y `formatTarifa`), `a088669` (`.table-scroll` accesible con teclado) y `c7a7c08` (`ApiError.cuerpo`).

## 2. Trazabilidad

| RF | Implementación | Pruebas |
|---|---|---|
| RF-MM-23 tarifa | Backend: `tarifa_sms` en la configuración, `Decimal` entre 0 y 4 decimales; entra como texto; en el `PUT` parcial, omitida se conserva y `null` da 422; se congela en la campaña. Frontend: Configuración, con `input text` e `inputmode="decimal"`, acepta la coma. | Núcleo y API, incluidas 6 tarifas inválidas; mutaciones de tarifa actual en vez de la congelada y de `float` en vez de `Decimal`; Vitest de `tarifaNormalizada`; Playwright con el 400 bajo su campo |
| RF-MM-24 costos | Estimado = cargados × tarifa, guardado con la campaña. Real = `enviados_conciliados` (E-1) × tarifa congelada, calculado al leer. Mes = suma de los estimados, sin las campañas que no tienen tarifa (se informa `campanas_sin_tarifa`). Cada costo trae su estado: `calculado`, `pendiente` o `no_disponible`. | Postgres de consistencia entre el conteo y la conciliación después de importar, reemplazar, importar un segundo id y mover un id; mutaciones de NULL frente a 0, conteo fuera de la transacción y costo real con cualquier estado; Vitest de `presentarCosto` por estado; Playwright con los tres estados, el costo del mes y su nota |
| RF-MM-25 nombre | Plantilla en la configuración y por campaña, con 7 variables. Una variable desconocida o una llave sin cerrar dan 400 con `campo`. Saneamiento para Windows, límite de 120 sin cortar el sufijo, sufijo automático, unicidad dentro de la campaña, nombre guardado con cada archivo y `filename*` en UTF-8. Previsualización con `[campana]` y `nombre_estimado`. | Propiedades con semilla fija sobre miles de plantillas: sin caracteres prohibidos, nunca más de 120, el sufijo sobrevive y no se repiten nombres. Mutaciones de sufijo recortado, variable aceptada y descarga con la plantilla actual. Playwright del nombre de ejemplo, del primer archivo y de los nombres reales |
| RF-MM-26 paginación | Frontend: `paginar` de a 10 con `.pager`; siempre el total de exclusiones; aviso con más de 100; vuelve a la página 1 al recalcular. Las dos tablas se apilan en pantallas angostas (hallazgo de C3). | Vitest de `paginar` con 0, 10, 11, 20 y 100 filas; Playwright de navegación, aviso y recálculo, más el apilado a 360 y 640; axe; 8 mutaciones en F6-A |

**Resultado:** los cuatro requerimientos tienen implementación y pruebas.

## 3. Decisiones

- **De `architec`:**
  - D-1: `[campana]` como marcador, y el nombre marcado como estimado.
  - D-2: el costo del mes omite las campañas sin tarifa e informa cuántas.
  - D-3: el costo real sale de la conciliación.
  - Opción (iii): `enviados_conciliados` como conteo derivado.
  - Lock global por la unicidad del id de MES.
  - `campo` tipado desde el contrato.
- **Del coordinador:**
  - montos como texto, redondeados solo al mostrar;
  - el recorte a 120 nunca toca el sufijo;
  - `filename` en ASCII más `filename*`;
  - `campo` en los 400;
  - B8 y F6-B en un solo commit.
- **De `designer`:**
  - `formatSoles` y `formatTarifa`;
  - los estados en `muted`;
  - el costo del mes en su propia línea;
  - los botones de variables en un grupo;
  - `.table-scroll` accesible y `ApiError.cuerpo`, en el patrón compartido.

## 4. Rendimiento (46 000 filas, `auto_cusco_test`)

Importar 2,4 s · reemplazar 2,4–2,5 s · mover un id 3,6 s · crear 4,6 s · previsualizar 5,2 s · conciliar 1,6 s. Cumple los criterios de `architec` (importar en menos de unos 3 s y crear sin empeorar respecto de 5,2 s).

## 5. Capas fuera, con su motivo

- **NVDA real:** no hay lector de pantalla en el entorno.
- **Regresión visual, cobertura y análisis estático de seguridad:** el proyecto no los tiene.
- **Propiedades con Hypothesis:** no está instalado; se cubrieron a mano con semilla fija.

## 6. Pasada manual de teclado y anchos

Hecha por dev_frontend sobre `aed0af5`, con un script aparte y axe en cada ancho y cada estado. Anchos: 360, 768, 1280 y 640, este último como aproximación del zoom al 200 %. El tema oscuro no entró en esta pasada; sí lo cubren las pruebas axe automáticas.

**Lo que está bien:**

- **Anchos:** ninguna pantalla desborda la página. axe da 0 violaciones en Configuración, Campaña y Seguimiento, en todos sus estados.
- **Teclado:** el orden es lógico y el foco se ve siempre. Los 7 botones de variables insertan en la posición del cursor y devuelven el foco al campo (7 de 7). El grupo se anuncia como «Variables de la plantilla».
- **Costos:** el costo estimado con su hint, los tres estados de costo, el costo real después de importar y el costo del mes con su nota se leen enteros en todos los anchos.
- **Tablas paginadas, apiladas a 360:**

  | Medida | Antes | Después |
  |---|---|---|
  | Fila típica de la muestra | 344 px | 194 px |
  | Diez filas | 3 469 px | 1 968 px |
  | Desplazamiento lateral | sí | no |
- **Tabla de 12 columnas de Seguimiento:** desborda por debajo de unos 1 110 px de ancho y cabe desde 1280. Con el arreglo de `designer` se recorre con el teclado: es enfocable, tiene `role="region"` y lleva nombre.

**Hallazgos:**

1. Textos pegados en Campaña. **Corregido en el corte de cierre** (`campana.astro` y `mowa-mes-campana.spec.ts`, +17/-3). No era un solo par sino tres:
   - «Nombre del primer archivo:» y el nombre;
   - el título «Exclusiones» y su total (venía de F6-A);
   - el título y el motivo del 404 (venía de F2-B).

   Tiene tres aserciones con tres mutaciones, todas detectadas. En el worktree desde `aed0af5`: Vitest 353/353 y Playwright 174/174.
2. `.btn--primary:hover` da un contraste de 3,02:1 en el tema claro, bajo el 4,5:1 que pide AA. Es un patrón de `designer` y afecta a todos los botones primarios. **Pasado a `designer`.**

**Anotado sin cambios:**

- Los botones de variables miden 25 px de alto: cumplen el mínimo de 24 px de WCAG 2.2, no los 44 px recomendados.
- La fila apilada con supervisión y advertencia mide 261 px, frente al tope de 240 de la prueba, que cubre el caso típico.
- NVDA y el zoom real no se corrieron.
