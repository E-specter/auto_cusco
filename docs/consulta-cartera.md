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

Todos reciben `fecha_corte` en formato `AAAA-MM-DD` y aceptan los mismos filtros.

## 3. Sintaxis de la consulta

- **Filtros:** parámetro `filtro` repetible, con la forma `campo:operador:valor`. Los valores múltiples se separan con `|`. Los operadores sin valor se escriben `campo:operador`.

  ```
  ?filtro=segmento_financiero:igual:1. Preventiva
  ?filtro=dias_atraso:entre:0|30&filtro=telefono:no_vacio
  ?filtro=region:en:CUSCO SUR|TACNA
  ```

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
| texto | igual, distinto, contiene, empieza_con, en, vacio, no_vacio |
| numero | igual, distinto, mayor, mayor_igual, menor, menor_igual, entre, en, vacio, no_vacio |
| fecha | los mismos que numero |
| booleano | igual, vacio, no_vacio |

Las funciones de los indicadores son las cinco de RF-27: suma, conteo, promedio, minimo y maximo. Suma y promedio solo aplican a campos numéricos.

**Una consulta mal formada nunca llega a la base de datos.** El núcleo valida campo, operador, cantidad de valores y tipo antes de consultar, y la API responde 400 con el motivo.

## 5. Reglas de negocio

- **RF-08, cantidad insuficiente.** La respuesta trae `total` y `suficiente`. Cuando se piden más productos de los que hay, `suficiente` es `false` y el frontend debe avisarlo de forma explícita.
- **Montos como texto.** Capital, cuotas y demás importes viajan como cadena para no perder precisión al pasar por JSON. Las cantidades y conteos viajan como número.
- **Segmentos sin valor.** En las métricas por segmento, los productos sin segmento se agrupan bajo `(sin segmento)`.

## 6. Implementación

- **Núcleo:** `backend/app/core/services/seleccion_cartera/` con el catálogo de campos y el caso de uso. Entidades en `app/core/entities/cartera.py`.
- **Adaptador:** `backend/app/adapters/persistence/repositorio_cartera_postgres.py`. Cada filtro se traduce a una expresión de SQLAlchemy; nunca se arma SQL con texto.
- **API:** `backend/app/api/cartera.py`.
- **Pruebas:** catálogo y validación, caso de uso con repositorio en memoria, endpoints con doble de prueba, e integración contra PostgreSQL con una sábana sintética.

## 7. Lo que falta de la Fase 2

- **RF-07, control de gestiones multicanal.** Bloqueado: todavía no existen las gestiones (VoIP, SMS, WhatsApp, correo) ni sus fuentes en el sistema. Filtrar por "contactado este mes" depende de eso.
- **RF-28, actualización automática de métricas.** Es comportamiento de la interfaz: recalcular al cambiar filtros o selección. El backend ya responde lo necesario.
- **Pantalla de selección y métricas** en el frontend.
