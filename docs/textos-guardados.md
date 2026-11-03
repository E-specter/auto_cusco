# Textos guardados y versionados por contexto (RF-69, T-HI-B4)

Una capacidad transversal: guardar un texto con un nombre dentro de un **contexto** que declara el módulo que lo usa (por ejemplo, el mensaje de WhatsMKT), y versionarlo como las definiciones de columnas (RF-51). El speech de MOWA MES conserva sus propias tablas y no migra aquí (RF-MM-14 a RF-MM-19).

## Qué se guarda

- **`texto_guardado`:** `id`, `contexto`, `nombre`, `nombre_normalizado`, `deshabilitado_en`, `creado_en`, `actualizado_en`. El nombre es único **por contexto** sobre el nombre normalizado (`normalizar_nombre`: sin espacios en los extremos y sin distinguir mayúsculas); una tilde distingue. El nombre de un texto deshabilitado sigue ocupado.
- **`texto_guardado_version`:** `texto_id` (FK con borrado en cascada), `numero` (único por texto, desde 1), `contenido`, `usada_en`, `creado_en`. `contenido` es JSONB NOT NULL con `none_as_null` y el CHECK `jsonb_typeof(contenido) = 'object'`: NOT NULL solo no basta, porque el JSON `null`, una lista o un número no son NULL de SQL.
- Ninguna versión se modifica: un cambio crea la siguiente y la vigente es la última. `usada_en` se marca la primera vez que algo usa la versión (`marcar_usada`, que llama el módulo consumidor) y no cambia después.
- Todos los nombres de restricción e índice miden 63 caracteres o menos; una prueba recorre la metadata completa.

## Contextos

El núcleo no conoce ningún contexto (`core/services/textos_guardados/contextos.py`). Cada módulo registra el suyo en el `RegistroContextosGuardados` desde la capa de composición de la API (`api/textos_guardados.py`, `obtener_registro_contextos_guardados`). Un contexto es `ContextoGuardado(clave, etiqueta, tipo, validar)`; el validador recibe el contenido (un objeto) y devuelve los problemas del motor (`Problema`). Hay dos formas ya hechas:

- `validador_de_expresion(contexto_texto)`: `{"expresion": {...}}`, una expresión del motor (RF-42) validada contra las variables de un `ContextoTexto` (RF-46).
- `validador_de_texto_plano(maximo, reglas=None)`: `{"texto": "..."}`, de 1 a `maximo` caracteres y las `reglas` del módulo (por ejemplo, las macros `[$MACROn$]` del mensaje de WhatsMKT, en `requerimientos-whatsmkt.md`).

B4 no registra ningún contexto real: las pruebas usan dos sintéticos. `whatsmkt.mensaje` lo registra WhatsMKT. Un contexto que nadie registró es un `400 contexto_guardado_desconocido` al listar, crear o versionar; leer, renombrar, deshabilitar y eliminar un texto ya guardado no necesitan su validador.

## API (`/textos-guardados`)

| Método y ruta | Qué hace |
|---|---|
| `GET /textos-guardados/contextos` | Los contextos registrados, con la forma de su contenido (`expresion` o `texto_plano`) |
| `GET /textos-guardados?contexto=&deshabilitados=` | El listado del contexto por nombre, con la versión vigente. Sin los deshabilitados salvo `deshabilitados=true` |
| `POST /textos-guardados` | Crea el texto (versión 1): `{contexto, nombre, contenido}` |
| `GET /textos-guardados/{id}?version=N` | El texto con la versión vigente o la N, también si está deshabilitado |
| `POST /textos-guardados/{id}/versiones` | Una versión nueva: `{contenido}` |
| `PATCH /textos-guardados/{id}` | Renombra sin crear versión (RF-56) |
| `POST /textos-guardados/{id}/deshabilitar` | Deja de ofrecerlo para lo nuevo; idempotente |
| `POST /textos-guardados/{id}/habilitar` | Lo vuelve a ofrecer y admite versiones otra vez; idempotente (200 sin cambio si ya estaba habilitado) |
| `DELETE /textos-guardados/{id}` | Lo elimina con sus versiones |

Errores, todos con `codigo` (que la interfaz traduce en `textoEnriquecido.codigo.*`):

- `400 texto_guardado_invalido` con `problemas`, cada uno con su `campo` (`nombre` o `contenido`) y, si es de una expresión, su ubicación; `400 contexto_guardado_desconocido`.
- `404 texto_guardado_no_encontrado` o `version_no_encontrada`.
- `409 nombre_repetido` (al crear o renombrar), `409 texto_guardado_deshabilitado` (al versionar uno deshabilitado) y `409 texto_guardado_usado` (al eliminar uno con alguna versión usada: solo se puede deshabilitar).

## Decisiones de implementación (confirmadas por coordinador_herramientas_implementadas)

1. Un texto deshabilitado **no admite versiones nuevas** (`409 texto_guardado_deshabilitado`): «deja de ofrecerse para lo nuevo».
2. **Se puede volver a habilitar** (`POST /textos-guardados/{id}/habilitar`, corrección del coordinador): el diseño de F2 (§11.3 de la interfaz) ofrece «Habilitar» en los deshabilitados, como MOWA en sus versiones. Limpia `deshabilitado_en`; mientras siga deshabilitado, la regla 1 no cambia.
3. **El nombre de un texto deshabilitado sigue ocupado**, coherente con los campos adicionales, que no reutilizan su nombre. Renombrar un deshabilitado vale.
4. **El listado excluye los deshabilitados** salvo con `?deshabilitados=true`; leer un texto por su `id` funciona también deshabilitado.
5. **`GET /textos-guardados/contextos`** lista los contextos registrados y la forma de su contenido, para el componente de F2.

Límite: lo que valida el contexto se evalúa al crear y al versionar, con el validador de hoy; una versión ya guardada no se revalida al leerla.

Pruebas: `tests/test_textos_guardados.py` (núcleo, API, migración con `--sql`, nombres de la metadata) y `tests/test_textos_guardados_postgres.py` (con base: unicidad, CHECK del contenido, concurrencia, eliminar con versión usada, cascada).
