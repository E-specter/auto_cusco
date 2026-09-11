# Pruebas y corrección de errores

Protocolo de trabajo para que el desarrollo sea controlado y repetible entre sesiones, personas y agentes de IA. Define qué se prueba en cada nivel, cuándo una tarea está terminada y cómo se corrige un error sin que vuelva a aparecer.

## 1. Principios

- **Cada pieza se prueba en su nivel.** La lógica de negocio se prueba sin base de datos ni archivos; la infraestructura se prueba aparte.
- **Datos sintéticos siempre.** Ninguna prueba usa nombres, documentos ni teléfonos reales. Ver las reglas de datos de `/AGENTS.md`.
- **Una prueba que falla primero.** Todo error se reproduce con una prueba antes de corregirlo, y esa prueba se queda como red de seguridad.
- **Una tarea no está terminada hasta pasar la verificación de la sección 4.**

## 2. Niveles de prueba

| Nivel | Qué cubre | Dónde vive | Necesita |
|---|---|---|---|
| Núcleo | Reglas de negocio y casos de uso: normalización, mapeo de cabeceras, versionado | `backend/tests/test_sabana_*.py`, `test_ingesta_servicio.py` | Nada. Se usan dobles de prueba en lugar de infraestructura |
| Adaptadores | Lectura de archivos y forma de las tablas | `backend/tests/test_lector_calamine.py`, `test_modelos_persistencia.py` | Archivos generados en memoria |
| Integración | Flujo completo contra PostgreSQL real | `backend/tests/test_repositorio_cargas_postgres.py` | Base migrada y la variable `AUTO_CUSCO_DB_TESTS` |
| Verificación con volumen real | Rendimiento y conteos con una sábana de verdad | Local, no se versiona | Sábana real con los datos personales reemplazados en memoria |

La arquitectura de puertos y adaptadores es lo que permite el primer nivel: el núcleo depende de interfaces, así que en las pruebas se sustituyen por dobles y no hace falta ni base de datos ni archivos.

## 3. Convenciones

- **Ubicación y nombre.** Un archivo por pieza en `backend/tests/`, con el nombre del área que cubre. Las funciones describen el comportamiento esperado en español.
- **Estructura.** Preparar, ejecutar y comprobar, separados por una línea en blanco. Una sola idea por prueba.
- **Sin base de datos por defecto.** Las pruebas que la necesitan llevan el marcador `postgres`, se saltan solas y limpian lo que crean.
- **Datos de prueba.** Se reutilizan los generadores sintéticos que ya existen en las pruebas del normalizador y de cabeceras, en lugar de inventar filas nuevas cada vez.
- **Cobertura mínima de un módulo nuevo:** caso normal, bordes, entradas inválidas y, cuando dos piezas deben coincidir, una prueba de contrato entre ellas. El ejemplo vivo es la prueba que falla si las columnas de la tabla dejan de coincidir con lo que produce la normalización.

## 4. Verificación antes de cerrar una tarea

Desde `backend/`:

```powershell
.\scripts\verificar.ps1            # formato, lint y pruebas
.\scripts\verificar.ps1 -ConBase   # agrega migraciones e integración con PostgreSQL
```

El script equivale a correr, en orden:

| Paso | Comando | Cuándo |
|---|---|---|
| Formato | `uv run ruff format --check app tests migrations` | Siempre |
| Lint | `uv run ruff check .` | Siempre |
| Pruebas | `uv run pytest -q` | Siempre |
| Migraciones | `uv run alembic check` | Si tocaste modelos o migraciones |
| Integración | `uv run pytest -m postgres -q` | Si tocaste persistencia |

Además, antes de cerrar:

- Actualiza `docs/planning.md` si cambió el alcance o se completó un punto, y `docs/modules.md` si cambió el estado de un módulo.
- Si cambió una regla de negocio, actualízala en su documento: `docs/sabana-schema.md` para la sábana y `docs/versionado-sabanas.md` para las versiones.
- Commit con prefijo: `feat`, `fix`, `docs`, `test`, `refactor` o `chore`, seguido del módulo entre paréntesis. Ejemplo: `fix(ingesta): ...`.

## 5. Protocolo de corrección de errores por módulo

1. **Describir el síntoma.** Qué se esperaba, qué pasó y con qué entrada. Si viene de una carga, anota la versión y el código de incidencia.
2. **Ubicar el módulo.** Usa `docs/modules.md` para saber a qué módulo pertenece y qué requerimientos cubre.
3. **Reproducir con una prueba que falle,** en el nivel más bajo donde se reproduzca. Si falla en el núcleo, no la escribas contra la base de datos.
4. **Corregir** hasta que esa prueba pase.
5. **Correr la verificación completa** de la sección 4, para descartar que la corrección rompa otra cosa.
6. **Dejar la prueba como regresión.** Nunca se borra después de corregir. Si el error salió de un dato real, agrega el caso con datos sintéticos equivalentes.
7. **Registrar el cambio.** Si la corrección cambia una regla de negocio, actualiza el documento correspondiente. Si estaba mal entendida, levántala con el usuario antes de decidir.

**Si el problema está en los datos y no en el código,** no se corrige con código: el sistema lo reporta como incidencia y la regla se confirma con el usuario. Inventar una corrección automática está prohibido por `/AGENTS.md`.

## 6. Errores de datos frente a errores de software

Son cosas distintas y se tratan distinto.

| Tipo | Ejemplo | Qué hace el sistema |
|---|---|---|
| Incidencia de datos, severidad error | Documento inválido, pagaré repetido, falta una columna requerida | Se guarda con su fila y columna. Si es la columna clave, la versión queda fallida |
| Incidencia de datos, severidad advertencia | Teléfono inválido o vacío, cabecera desconocida | Se guarda y el producto se ingesta igual |
| Incidencia de datos, severidad info | DNI completado con ceros | Se guarda como registro de una corrección prevista |
| Error de software | La normalización devuelve un valor equivocado | Se corrige con el protocolo de la sección 5 |

## 7. Integración continua

`.github/workflows/backend.yml` corre en cada subida a la rama principal y en cada pull request, con dos trabajos:

- **Formato, lint y pruebas,** sin base de datos.
- **Migraciones e integración,** que levanta un PostgreSQL temporal, aplica las migraciones, verifica que no haya cambios sin migrar y corre las pruebas marcadas. La contraseña que aparece ahí es de una base desechable que vive solo durante la ejecución, no es un secreto del proyecto.

Si un trabajo falla, se corrige antes de seguir. La integración continua no reemplaza la verificación local: es la red que atrapa lo que se olvidó correr.

## 8. Pendientes

- **Frontend sin pruebas.** El proyecto Astro no tiene herramienta de pruebas elegida todavía. Es una decisión abierta.
- **Cobertura sin medir.** No hay herramienta configurada; por ahora el criterio es el de la sección 3.
- **Pruebas de carga** según volumen real, previstas en la Fase 7 de `docs/planning.md`.
