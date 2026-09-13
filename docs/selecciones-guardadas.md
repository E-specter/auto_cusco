# Selecciones guardadas

Una selección es lo que el analista armó para elegir productos en la pantalla de cartera: filtros, orden, cantidad e indicadores. Guardarla permite reutilizarla otro día, sobre otra sábana, y compartirla con el resto del equipo. Pedido de la pantalla de selección (Fase 2).

## 1. Qué se guarda

| Parte | Formato |
|---|---|
| `nombre` | Texto de 1 a 120 caracteres. Único, sin distinguir mayúsculas ni espacios en los extremos |
| `filtros` | Lista de filtros en la sintaxis de `/cartera`: `campo:operador:valor` |
| `orden` | `campo` o `-campo`, opcional |
| `cantidad` | El n del top n, de 1 a 120 000, opcional |
| `indicadores` | Lista en la sintaxis de RF-27: `nombre:funcion:campo` |

**No lleva fecha de corte:** la misma selección se aplica sobre la cartera de cualquier día.

Se guarda en la misma sintaxis de texto que usa la API, así que el frontend manda y recibe exactamente lo que ya usa para `/cartera`, `/cartera/resumen` y `/archivos-carga`.

## 2. Endpoints

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/selecciones` | Todas, ordenadas por nombre |
| `POST` | `/selecciones` | Guardar una nueva (201) |
| `POST` | `/selecciones/revision` | Revisar sin guardar, para marcar errores mientras se edita |
| `GET` | `/selecciones/{id}` | Una |
| `PUT` | `/selecciones/{id}` | Reemplazarla completa |
| `DELETE` | `/selecciones/{id}` | Borrarla (204) |

Cada selección que devuelve la API trae `aplicable` y `problemas`, una lista de `{parte, expresion, detalle}`.

## 3. Validez: al guardar y al cargar

- **Al guardar se rechaza lo que no aplica.** Un filtro que nombra un campo inexistente, un operador que no corresponde al tipo, una cantidad fuera de rango o un indicador repetido responden `400` con el motivo, y no se guarda nada.
- **Al cargar no se rechaza.** Si el catálogo de campos cambió después de guardarla y un filtro ya no aplica, la selección se devuelve igual, con `aplicable: false` y el problema marcado en su parte. El analista ve qué se rompió en vez de perder la selección.
- **Para revisar mientras se edita** está `POST /selecciones/revision`, que devuelve los mismos problemas sin guardar nada.

Antes de revisar o guardar se quitan los espacios sobrantes y las partes vacías.

## 4. Nombre único y concurrencia

Un nombre repetido responde `409`. La unicidad la impone la base de datos sobre el nombre normalizado, no una consulta previa, así que dos personas guardando a la vez no pueden crear dos selecciones con el mismo nombre.

## 5. Quién puede editar o borrar

**Cualquiera puede editar o borrar cualquier selección** (decisión C-3: el sistema todavía no tiene usuarios). Para saber cuándo cambió, cada selección guarda su fecha de creación y la de su última modificación.

## 6. Implementación

- **Sintaxis compartida:** `backend/app/core/services/seleccion_cartera/expresiones.py`. Pasó del adaptador HTTP al núcleo porque ahora también la usan las selecciones guardadas.
- **Entidades:** `backend/app/core/entities/selecciones.py`.
- **Caso de uso:** `backend/app/core/services/selecciones/servicio.py`.
- **Persistencia:** tabla `seleccion` (migración `7c3e9a1d4b52`) y `backend/app/adapters/persistence/repositorio_selecciones_postgres.py`.
- **API:** `backend/app/api/selecciones.py`.
- **Pruebas:** `test_selecciones_servicio.py` (núcleo), `test_api_selecciones.py` (API), `test_modelos_persistencia.py` (restricciones de la tabla) y `test_selecciones_postgres.py` (repositorio y ciclo completo por HTTP contra PostgreSQL, incluida una selección que perdió validez).
