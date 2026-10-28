# Consulta de cartera: selección, filtros, segmentación y métricas

Contrato de la parte de la Fase 2 que ya está en el backend (RF-04 a RF-06, RF-08, RF-25 a RF-27). Sirve como referencia para el frontend y para cualquier agente que toque esta capa.

## 1. Qué consulta

La cartera de una fecha es el contenido de su **versión vigente** (ver `versionado-sabanas.md`). Si esa fecha no tiene versión vigente, la API responde 404: no hay cartera que mostrar, ni siquiera parcial. Cambiar cuál versión es la vigente cambia la cartera de inmediato, sin recalcular nada.

## 2. Endpoints

| Endpoint | Para qué |
|---|---|
| `GET /cartera/campos` | Campos consultables con su tipo y los operadores que admite cada uno. La interfaz arma los filtros con esto, sin listas propias |
| `GET /cartera` | Productos de la fecha, con filtros, orden y paginación (RF-04, RF-05, RF-08) |
| `GET /cartera/metricas` | Capital, cuentas, cuota mínima y máxima, cuentas por segmento, más los indicadores que pida el usuario (RF-26, RF-27) |
| `GET /cartera/segmentacion` | Cuentas y capital por cada valor de un atributo (RF-06) |
| `GET /cartera/resumen` | Métricas del universo filtrado y de sus primeros n, lado a lado, en un solo llamado (RF-08, RF-26 a RF-28) |

Todos reciben `fecha_corte` en formato `AAAA-MM-DD` y aceptan los mismos filtros.

## 3. Sintaxis de la consulta

- **Filtros:** parámetro `filtro` repetible, con la forma `campo:operador:valor`. Los valores múltiples se separan con `|`. Los operadores sin valor se escriben `campo:operador`.

  ```
  ?filtro=segmento_financiero:igual:1. Preventiva
  ?filtro=dias_atraso:entre:0|30&filtro=telefono:no_vacio
  ?filtro=region:en:CUSCO SUR|TACNA
  ?filtro=region:no_en:CUSCO SUR|TACNA
  ?filtro=region:no_en:CUSCO SUR|
  ```

  - **`no_en` («no es ninguno de»)** es lo contrario de `en`, con uno o más valores y para texto, número y fecha. Un producto **sin valor queda incluido**: no tiene ninguno de los marcados. En SQL, `columna IS NULL OR columna NOT IN (...)`.
  - **«(vacío)» en la lista.** Un **elemento vacío** de la lista de `en` o `no_en` es el producto sin valor (en la cartera el texto vacío es siempre `NULL`, nunca `""`): `region:en:CUSCO SUR|` es «CUSCO SUR o sin región», y `region:no_en:|` es «con región». La lista puede ser solo el vacío (`region:en:`). Con vacío, `en` es `IN (...) OR IS NULL` y `no_en`, `IS NOT NULL AND NOT IN (...)`. Solo en campos de **texto**: en número y fecha un elemento vacío sigue dando 400. Con y sin el vacío, `en` y `no_en` **parten la cartera**, sin repetir ni perder productos (lo comprueba una prueba de propiedad).
  - **Escape.** `\|` es una barra `|` literal dentro de un valor y `\\` una barra invertida. Es **tolerante**: una `\` seguida de cualquier otro carácter, o al final, queda literal (no da 400), así que un filtro guardado con una barra suelta se lee igual que siempre.
  - **El orden importa y se conserva.** Los filtros son un AND, así que el orden no cambia el resultado (el mismo `total` y los mismos productos), pero sí el orden en que se guardan y se muestran, y la `descripcion_sugerida` de una campaña de MOWA MES, que los resume en su orden.

- **Orden:** parámetro `orden` con el nombre del campo, o con un guion delante para descendente: `orden=-saldo_capital_pendiente`. Los nulos van siempre al final. El desempate es por pagaré, así la paginación no repite ni salta productos.
- **Paginación:** `limite` (1 a 5000, por defecto 50) y `desplazamiento`.
- **Indicadores adicionales:** parámetro `indicador` repetible, con la forma `nombre:funcion:campo`. `conteo` puede ir sin campo.

  ```
  ?indicador=cuota promedio:promedio:monto_cuota&indicador=productos:conteo
  ```

## 4. Tipos de campo y operadores

Los campos salen del catálogo de la sábana, así que no pueden desalinearse con lo que se ingesta. `GET /cartera/campos` los devuelve en vivo.

| Tipo | Operadores |
|---|---|
| texto | igual, distinto, contiene, empieza_con, en, no_en, vacio, no_vacio |
| numero | igual, distinto, mayor, mayor_igual, menor, menor_igual, entre, en, no_en, vacio, no_vacio |
| fecha | los mismos que numero |
| booleano | igual, vacio, no_vacio |

Las funciones de los indicadores son las cinco de RF-27: suma, conteo, promedio, minimo y maximo. Suma y promedio solo aplican a campos numéricos.

**Una consulta mal formada nunca llega a la base de datos.** El núcleo valida campo, operador, cantidad de valores y tipo antes de consultar, y la API responde 400 con el motivo.

## 5. Resumen: el universo filtrado y los primeros n

`GET /cartera/resumen` responde de una vez lo que la pantalla de selección muestra lado a lado: las métricas de todos los productos que cumplen los filtros y las de los primeros n que eligió el analista. Si filtra 3 200 productos y pide los primeros 500, recibe los dos bloques.

| Parámetro | Para qué |
|---|---|
| `fecha_corte`, `filtro`, `indicador` | Igual que en el resto de los endpoints |
| `orden` | Qué productos son "los primeros". Sin él, el orden es solo por pagaré |
| `cantidad` | El n del top n, de 1 a 120 000. Sin ella no hay bloque de selección |
| `segmento` | Campo por el que segmentar los dos bloques. Sin él, `segmentacion` es `null` |

La respuesta trae `disponibles`, `solicitados` y `suficiente`, y dos bloques: `universo` y `seleccion`, este último `null` si no se pidió cantidad. Cada bloque tiene `metricas`, con los indicadores de RF-27, y `segmentacion`.

**Los primeros n son siempre los mismos productos.** Salen con el mismo orden, los nulos al final y el mismo desempate por pagaré que `GET /cartera` y que la generación del archivo de carga. Así, las métricas de la selección describen exactamente los productos de la lista y los del archivo. Dos pruebas contra PostgreSQL lo comprueban: una con un orden que tiene empates, frente a la lista, y otra frente a las filas del archivo generado.

Pensado para RF-28: al cambiar un filtro, la pantalla hace un solo pedido en vez de uno por métrica y por bloque. `/cartera/metricas` y `/cartera/segmentacion` siguen disponibles tal como estaban.

## 6. Reglas de negocio

- **RF-08, cantidad insuficiente.** La respuesta trae `total` y `suficiente`. Cuando se piden más productos de los que hay, `suficiente` es `false` y el frontend debe avisarlo de forma explícita.
- **Montos como texto.** Capital, cuotas y demás importes viajan como cadena para no perder precisión al pasar por JSON. Las cantidades y conteos viajan como número.
- **Segmentos sin valor.** En las métricas por segmento, los productos sin segmento se agrupan bajo `(sin segmento)`.

## 7. Implementación

- **Núcleo:** `backend/app/core/services/seleccion_cartera/` con el catálogo de campos y el caso de uso. Entidades en `app/core/entities/cartera.py`.
- **El catálogo de campos (T-CA-B1, RF-64 a RF-66).** `CatalogoCartera` (`seleccion_cartera/campos.py`) es la ÚNICA fuente de los campos de la cartera: suma los campos base (derivados de `CATALOGO_VENCIDA`) y los **campos adicionales** que crea el usuario, que lee de un puerto (`RepositorioCamposAdicionalesPort`; hoy sin implementación de producción, el catálogo es solo la base). Ya no hay una constante que importar: `ConsultaCarteraService`, `SeleccionesService`, el parseo de filtros (`expresiones.parsear_filtro(crudo, catalogo)`), las variables del contexto `cartera` del motor (`contexto_cartera(catalogo)`), las columnas de carga y el resumen de filtros de MOWA MES **reciben el catálogo**; una prueba de arquitectura impide volver a importar la constante, y una de «capacidad nueva» comprueba que lo que recibe el catálogo ve un adicional sin código propio. Un campo adicional tiene nombre técnico `ad_` + un *slug* ASCII del nombre legible (`seleccion_cartera/nombres_adicionales.py`; si choca, `_2`, `_3`…; nunca se reutiliza, y no puede tapar un nombre reservado de un contexto o un conector) y un nombre legible que se muestra. **Archivados:** `campos()` los trae (lo que ya los usa sigue resolviendo); `ofrecidos()` y `catalogo_publico()` no. Indicadores (RF-27): de un adicional, suma, promedio, mínimo y máximo solo si es número; el conteo, de cualquier tipo.
- **Valores de un adicional (listo, pendiente de la migración de T-CA-B2).** Viven en un JSONB `carga_fila.adicionales` (`{nombre: valor}`, normalizado por tipo al ingestar) y el repositorio los lee como `adicionales ->> 'ad_x'` con un `CAST` según el tipo (`NUMERIC` o `DATE`; el texto, tal cual), en filtros, orden, indicadores, segmentación y en las filas que salen. El armado está probado con SQL compilado al dialecto de PostgreSQL, sin base.
- **Adaptador:** `backend/app/adapters/persistence/repositorio_cartera_postgres.py`. Cada filtro se traduce a una expresión de SQLAlchemy; nunca se arma SQL con texto.
- **API:** `backend/app/api/cartera.py`.
- **Pruebas:** catálogo y validación, caso de uso con repositorio en memoria, endpoints con doble de prueba, e integración contra PostgreSQL con una sábana sintética.

## 8. Lo que falta de la Fase 2

- **RF-07, control de gestiones multicanal.** Bloqueado: todavía no existen las gestiones (VoIP, SMS, WhatsApp, correo) ni sus fuentes en el sistema. Filtrar por "contactado este mes" depende de eso.
- **RF-28, actualización automática de métricas.** Es comportamiento de la interfaz: recalcular al cambiar filtros o selección. El backend lo resuelve con un solo pedido a `GET /cartera/resumen`.
- **Pantalla de selección y métricas** en el frontend.
