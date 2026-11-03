# Revisión de RF-MM-28 a RF-MM-36 (T-MM-C11)

> **Cerrada el 2026-10-31; M-F8 cerrado el 2026-11-02** en `8873614` (backend) y `2583ee2` (frontend), con el dato del usuario que cerró S-MM-10 (el id es el «ID campaña» de MES, la columna `id` del reporte). Plan: [plan-c11.md](plan-c11.md), en `a4930dd`. Requerimientos en [requerimientos-mowa-mes.md](../../requerimientos-mowa-mes.md) (`1b0d9fe`): RF-MM-28 a RF-MM-36, RF-MM-17 modificado (solo v2) y RF-MM-01 y RF-MM-09 ampliados. Reglas de interfaz de `designer` en [mowa-mes-interfaz.md](../../mowa-mes-interfaz.md) (T-MM-D11). Los cortes están en `main`, de `154afee` (M-B1) a `1bcf2d8` (el arreglo de M-B4). El CI rojo de `5ebb9b3` (el reloj de las specs de MOWA) lo arregló `c3a6732`.

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Revisores:
- `coordinador_herramientas_implementadas`: el §13 de todo corte que tocaba el motor, el selector, `/cartera` o el contrato compartido;
- `designer`: aprobó con capturas todo cambio visible.

## 1. Cortes

| Corte | Commit | Qué | Agente |
|---|---|---|---|
| M-B1 | `154afee` | Campañas descartadas en el backend: `descartada_en`, el predicado `_ACTIVA` en los tres agregados, descartar, restaurar y eliminar, `pendiente_reporte` y `total_pendientes`. U-1 A: importar a una descartada da 409 `campana_descartada` | dev_backend_modulo_mowa_mes |
| M-F4 | `c3a1179` | Pendientes de reporte en el seguimiento: el tag, la línea de arriba de la lista, el aviso del detalle y `?campana=` | dev_frontend_modulo_mowa_mes |
| M-F5 | `93df21d` | «Para subir a MES» al crear la campaña: los tres pasos, los datos con «Copiar» y el enlace al seguimiento | dev_frontend_modulo_mowa_mes |
| M-B2 | `3aca08d` | Renombrar, deshabilitar, habilitar y eliminar versiones de speech; `eliminable` y `motivo_no_eliminable` en cada versión | dev_backend_modulo_mowa_mes |
| M-F3 | `702927e` | Campañas descartadas en el seguimiento: la vista con su filtro por mes, descartar, restaurar y eliminar | dev_frontend_modulo_mowa_mes |
| M-F3b | `23c339d` | El hint de importar en una descartada y el mes de gestión unificado (`formatMes` y `formatMesGestion`) | dev_frontend_modulo_mowa_mes |
| M-B3 | `7dbd863`, `00b07c2` | La migración de las versiones a solo v2 (`d7a3e5b9c241`), con convertidor y literal congelados, y su `@postgres` ajustada a la forma que guarda la app | dev_backend_modulo_mowa_mes |
| — | `052a8de` | Cuatro aserciones viejas de specs de C11, que la primera corrida completa encontró | dev_frontend_modulo_mowa_mes |
| M-F2 | `03dd1b5` | La administración de versiones de speech en la configuración: renombrar, deshabilitar, la sección «Versiones deshabilitadas (N)» y el selector solo con las habilitadas | dev_frontend_modulo_mowa_mes |
| M-F6 | `67e7105` | «Editar en Cartera» desde la campaña y la vuelta (`lib/volver.ts`, `seleccionguardada`, `cargarGuardada` y `confirmarDescartar` en el selector) | dev_frontend_modulo_mowa_mes |
| M-F7a | `7d46569` | Iconos del seguimiento y el medidor del límite mensual (`tonoDelUso`, `anchoDeLaBarra`) | dev_frontend_modulo_mowa_mes |
| M-F7b | `a00f39f` | Iconos de la pantalla de campaña | dev_frontend_modulo_mowa_mes |
| M-F7c | `2c132da` | Iconos de la configuración: «Original» pasa a `tag--info` | dev_frontend_modulo_mowa_mes |
| — | `d81d867` | Ajustes de las specs de M-F2 a M-F7 tras su primera corrida | dev_frontend_modulo_mowa_mes |
| — | `6b28180` | Los arreglos de las capturas de `designer` (§7) | dev_frontend_modulo_mowa_mes |
| M-F1 | `9818e8d` | Fuera la vista v1 de la configuración, «Convertir a v2» y `obtenerComoV2`; aviso propio del Speech original | dev_frontend_modulo_mowa_mes |
| M-B4 | `1e31342`, `1bcf2d8` | Fuera la v1 del backend: `partes` pasa a `texto_v1` (migración `e2c6b4a8d195`), sale `formato`, sale `GET /speech/{id}/como-v2`, y el contrato se regenera. Incluye la limpieza de fixtures del frontend. El arreglo `1bcf2d8` impide guardar un JSON `null` en `expresiones` (§6) | dev_backend_modulo_mowa_mes y dev_frontend_modulo_mowa_mes |

**Tres tandas a `main`.** M-B1 a M-B3 con sus frontends; después M-F2, M-F6 y los iconos, rebasados sobre `main`; y M-F1 con M-B4, verificados juntos para no correr dos Playwright completos seguidos.

## 2. Cambios visibles, declarados y aprobados

- **Seguimiento (M-F3, M-F3b, M-F4, M-F7a):**
  - la vista «Descartadas (N)», con el filtro «Mes de gestión» («Octubre de 2026») y el hint de que no cuentan;
  - el tag «Pendiente del reporte» (`hourglass`), una línea `.field__hint` arriba de las activas y el aviso con «Importar el reporte» en el detalle;
  - el medidor del límite, con el tono normal, cerca (90 % a 100 %) y excedido;
  - los iconos del catálogo en cifras, secciones y acciones.
- **Campaña (M-F5, M-F6, M-F7b):** el panel «Para subir a MES», en una rejilla de tres columnas; «Editar en Cartera» y «Volver a la campaña sin guardar»; los iconos.
- **Configuración (M-F2, M-F7c, M-F1):** «Renombrar» y «Deshabilitar»; la sección de deshabilitadas, plegada, con «Ver», «Habilitar» y «Eliminar definitivamente» o su motivo; los tags «Deshabilitada» (neutro) y «Original» (información); ninguna vista v1; el aviso «Este es el Speech original: no se modifica. Tus cambios se guardan como una versión nueva basada en él.».
- **El diálogo del selector, en todas las pantallas del motor (M-F6, opción C):** «Los cambios que no guardaste se pierden.» y «Descartar cambios». El motor lo aprobó con sus 303 casos en verde.

## 3. Decisiones

- **Del usuario:** U-1 A, rechazar el reporte de una descartada (2026-10-30); y migrar `auto_cusco` dos veces, a `d7a3e5b9c241` y a `e2c6b4a8d195`.
- **De `designer`:**
  - los textos y el lugar de las secciones nuevas, en `mowa-mes-interfaz.md`;
  - la opción C del diálogo del selector;
  - «Setiembre», la forma es-PE que escribe ICU: no se parcha `Intl`;
  - el contador de pendientes como una línea, y no como aviso;
  - el detalle del seguimiento siempre de la vista en curso;
  - el aviso propio del Speech original.
- **Del coordinador del motor (§13):** la forma JSON congelada de M-B3; el selector y `cartera.astro` de M-F6; que M-F1 no pedía §13, porque la solo lectura usa `fijarSoloLectura`, que ya existía; el plan y el contrato de M-B4.
- **De `architec`:** la forma del oro en M-B3 y en M-B4 (§4); cada tanda verificada con un solo Playwright completo; M-B4 construido sobre M-F1 para verificarlos juntos.
- **Del coordinador:** el detalle de la vista de descartadas sigue a la vista; una descartada que nombra `?campana=` abre la vista en su mes (decisión del dev, aceptada); el mutante sobreviviente de M-F6 queda declarado (§6).

## 4. Desviaciones del plan

- **`pendiente_reporte` lo calcula el backend** (`enviados_conciliados IS NULL`), con `total_pendientes` en el listado. `enviados_conciliados` sigue sin exponerse. Corrige el plan §3.4, que lo dejaba a la pantalla.
- **M-B2:**
  - una versión deshabilitada deja de ser `editable`: el PUT da 409 por `SpeechInmutable`, sin código nuevo;
  - el motivo para no eliminar sigue el orden original > usado > no deshabilitado;
  - un PATCH vacío devuelve la versión;
  - la prueba de migración de M-B1 pasa a exigir una sola cabeza.
- **M-B3:**
  - `formato` vale `v2` por omisión;
  - 1778 casos del oro no arman mensaje (titular o fecha vacíos), con el mismo predicado que la campaña (`vacia(titular) or fecha is None`, `campana.py`);
  - la `@postgres` de la v2 editada compara la forma que guarda la app (`00b07c2`);
  - cuatro `@postgres` pasan a solo v2.
- **M-F3b:** el mes de gestión se escribe con `formatMesGestion` en las etiquetas y con `formatMes` a mitad de frase, para no poner «Octubre» con mayúscula en medio de una oración.
- **M-F6:** `tipo_carga` y `salida` no van en el borrador; el borrador se restaura en cualquier visita de la pestaña, sin vencimiento; el aviso de la selección borrada va bajo el panel del selector.
- **M-F1:** el Speech original tiene su aviso propio; sin la rama v1 caía en el de «ya se usó en una campaña», que era falso para él.
- **M-B4:**
  - **el oro cambió de forma, con autorización de `architec`:** de comparar contra el código v1 vivo a un hash congelado por versión (las 13 de `TODAS_LAS_VERSIONES`), calculado en `9818e8d` sobre el mensaje final, después de `a_gsm7`, y reproducible según su docstring. Se suman dos conteos congelados de las 2808 filas comparables: 1236 cambian al pasar a GSM-7 y 216 tienen un espacio especial. Salen `MATRIZ_HUELLA`, `MATRIZ_HUELLA_GSM7` y las dos `MATRIZ_FILAS_*`, que medían la matriz v1 entera y no se pueden recalcular sin el código v1. `MENSAJES_DEL_ORIGINAL`, los 6 mensajes y la huella del texto v1 (`297c…`) se quedan;
  - el oráculo de los 200 juegos del convertidor pasa a un SHA-256 del JSON canónico, más 8 casos en línea;
  - un pedido con `partes` y sin `expresiones` pasa de 400 `version_v1_retirada` a 422;
  - salen 3 paramétricas que comparaban v1 en vivo contra v2. Las exclusiones las cubren `test_mowa_mes_speech_v2.py`, `test_mowa_mes_speech_oro.py` y `test_mowa_mes_campana.py`;
  - los métodos `crear_speech_v2` y `previsualizar_speech_v2` conservan su nombre;
  - el downgrade deja la tabla como M-B3, salvo el orden físico de las columnas, que la comparación de esquema no mira.

## 5. Verificación

- **Por los devs, en turno de máquina y con 1 worker:**
  - backend: ruff, `exportar_openapi --comprobar` y pytest completo (3684 en M-B4);
  - frontend: contrato, tipos, `astro check`, Vitest (1268 en la segunda tanda, 1250 en M-F1 y 1248 en M-B4) y Playwright de las specs de cada corte;
  - el turno de la segunda tanda: 303/303 del motor, 270/270 de MOWA y, tras los arreglos de las capturas, 331/331;
  - M-F1 y M-B4: 592/592 en 19 specs, con los casos del motor de `accesibilidad` (71) y `pagina` (23) en verde y sin cambiar lo esperado;
  - mutaciones: 32 de 33 en M-F2 a M-F7c, con un equivalente (§6); 10 de 10 en M-F1; 21 de 21 en M-B4.
- **Por `architec`, sobre cada tanda:**
  - backend: `verificar.ps1 -ConBase`, la ida y vuelta de cada migración y `alembic check`. Fueron 196 `@postgres` en la primera tanda. En la última, sobre `1bcf2d8`, dio 3687 sin base y 200 `@postgres`, y además se corrió la cadena entera de migraciones desde cero (downgrade a base, upgrade a head y `alembic check`). Sobre `1e31342`, sin el arreglo, había dado 195 de 196 (§6);
  - frontend: contrato, tipos, `astro check`, Vitest, build de producción y Playwright completo. Dio:
    - 929/933 sobre `00b07c2`; las 4 fallas eran las de `052a8de`, todas de specs, y después esas tres specs dieron 100/100;
    - 1075/1075 sobre `6b28180`;
    - 1060/1060 sobre `1e31342`. El arreglo `1bcf2d8` es solo de backend y no cambia el contrato;
  - `auto_cusco` se migró dos veces, con permiso del usuario. Primero a `d7a3e5b9c241`, que dejó 3 versiones v2 y ninguna v1. Después a `e2c6b4a8d195`: las 3 versiones tienen sus expresiones como lista, 2 conservan `texto_v1`, las usadas y el original quedan sin cambios, y hay 4 campañas.
- **Capturas de `designer`:** de cada corte visible, en claro y oscuro, a 1280 y 360 px, más una recaptura después de los arreglos.
- **No se corrió:** WSL y el CI de Linux, que quedan para el CI de GitHub al subir.

## 6. Lo que encontró la revisión

- **La primera corrida completa** dio 4 aserciones viejas en specs de C11 que nunca habían corrido: el título «… creada», que M-F5 había cambiado; «Septiembre» en lugar de «Setiembre»; y un `toBeInViewport` sobre el `<input type=file>` oculto. Se arreglaron en `052a8de`, sin tocar el producto.
- **La primera corrida de las specs nuevas** dio 41 fallas, todas de specs. La más grande: el fake del módulo respondía también por las páginas de `/cartera`.
- **Las capturas** encontraron un bug de producto y 7 detalles visuales, arreglados en `6b28180`:
  - el bug: la vista Descartadas mostraba en el detalle una campaña activa;
  - los detalles: «Octubre De 2026» por un `text-transform: capitalize`; el icono de «Costo del mes» en otra línea; la cabecera del límite en tres renglones a 360 px; el contador de pendientes como aviso; el tag cortado a 360 px; los «Copiar» desalineados; el título de las deshabilitadas a la derecha.
- **Dos reglas de `mowa-mes.css` no tomaban efecto,** porque perdían contra `.row` y `.tag` de `ui.css`, que se carga después. Las atraparon las specs; se resolvieron con especificidad, sin tocar `ui.css`.
- **Los botones de fila de M-F2 usaban `aria-describedby`,** y una lista de botones se leía «Ver, Ver, Ver». Pasaron a `aria-labelledby` con el nombre de la fila.
- **M-F3b ponía el mes con mayúscula a mitad de frase** («cuenta en Octubre»): de ahí sale la separación entre `formatMes` y `formatMesGestion`.
- **El `-ConBase` de M-B4 encontró un bug real:** al volver `expresiones` NOT NULL, el modelo perdió `none_as_null`, y un `None` de Python se guardaba como el JSON `null`, que pasa el NOT NULL. Lo arregla `1bcf2d8`:
  - `JSONB(none_as_null=True)` otra vez;
  - un CHECK `jsonb_typeof(expresiones) = 'array'` en `e2c6b4a8d195`, editada en su lugar porque todavía no estaba en `main` ni en `auto_cusco`.

  No lo atrapó la prueba sin base, porque `test_mowa_mes_persistencia_json.py` solo recorría las JSONB nulables. Ahora recorre todas las de la versión. Además fija un inventario, `JSONB_SIN_NONE_AS_NULL`, que falla si aparece una columna nueva sin la opción.
- **Hallazgo transversal, el inventario de JSONB sin `none_as_null`:**
  - 5 NOT NULL de MOWA: `mowa_mes_campana.filtros`, `.herramientas`, `.envios` y `.supervisores`, y `mowa_mes_fila_cargada.advertencias`. Van a T-MM-B14, después del cierre;
  - 6 NOT NULL de otros módulos: `borrador_carga_archivo.opciones` y `.analisis`, `carga.opciones_lectura`, `definicion_carga_version.contenido`, y `seleccion.filtros` e `.indicadores`;
  - 4 nulables: `carga.cabeceras_originales`, `carga.mapeo`, `carga_auditoria.detalle` y `carga_fila.extras`.

  En una NOT NULL, un `None` pasaría como JSON `null` si algún código lo mandara. Las 6 de otros módulos van a T-JSON-1, del motor; las 4 nulables las anota `architec` para la ingesta.
- **Mutante sobreviviente de M-F6:** en `confirmarDescartar` (la guardia de la misma promesa), es equivalente desde la UI. Matarlo exige probar el controlador en jsdom, que hoy no existe. Si algún día se arma ese montaje, se agrega la prueba. Lo decidió el coordinador del motor, dueño del archivo.
- **Proceso:**
  - la numeración de `mowa-mes.md` chocó dos veces (§20 y §22). Desde ahí, el número de cada sección se asignó antes de empezar el corte;
  - las opciones B y C del diálogo se cruzaron entre `designer` y el motor. Se cerró enviando la decisión una sola vez, marcada como final;
  - una pytest sin `@postgres` de M-B4 corrió sin turno (26 s, 5,4 GB libres, sin otra tarea pesada). Se avisó al dueño de la cola;
  - una comprobación mía con `uv run` creó `backend/.venv` en el worktree de M-F1. Lo borré y se lo avisé al dev.

## 7. Fuera a propósito

- **El placeholder del nombre de versión** («Vacío: se llamará Speech N») se corta a 360 px. Ya pasaba antes de C11; queda para el pulido.
- **`texto_v1` no se expone en la API:** queda para trazabilidad en la base.

## 8. Pendiente

- ~~**M-F8**~~ (RF-MM-34): hecho el 2026-11-02 (`8873614` y `2583ee2`).
- **T-MM-F13, pulido:** las dos tablas de la conciliación pasan a `.table--apilable`, porque a 360 px «Coinciden con la campaña» queda fuera de la vista (designer, 2026-11-02, de las capturas de M-F8).
- **T-MM-B14:** `none_as_null`, y un CHECK de tipo donde aplique, en las 5 JSONB NOT NULL de MOWA, después de revisar quién escribe en cada una.
- **T-JSON-1, del motor y sin urgencia:** las mismas 6 JSONB NOT NULL de otros módulos (§6).
- **La fragilidad de `_motivo`, que viene de C10:** el lector del reporte reconoce los errores del lector general por el texto del mensaje. C11 no lo tocó.
- **El placeholder a 360 px**, en la pasada de pulido.
- **La prueba del controlador del selector en jsdom**, si se arma ese montaje.
- **`git push`** de los commits de C11.
