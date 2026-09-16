# Pruebas y corrección de errores

Protocolo de trabajo para que el desarrollo sea controlado y repetible entre sesiones, personas y agentes de IA. Define qué se prueba en cada nivel, cuándo una tarea está terminada y cómo se corrige un error sin que vuelva a aparecer.

## 1. Principios

- **Cada pieza se prueba en su nivel.** La lógica de negocio se prueba sin base de datos ni archivos; la infraestructura se prueba aparte.
- **Datos sintéticos siempre.** Ninguna prueba usa nombres, documentos ni teléfonos reales. Ver las reglas de datos de `/AGENTS.md`.
- **Una prueba que falla primero.** Todo error se reproduce con una prueba antes de corregirlo, y esa prueba se queda como red de seguridad.
- **Una tarea no está terminada hasta pasar la verificación de la sección 4.**

Para tenerlo presente durante el trabajo y no solo al final, la versión corta de este documento vive como skill en `.claude/skills/verificar/SKILL.md`: qué nivel le toca a cada cambio, los comandos y cómo reportarlo. Los agentes que no cargan skills leen el puntero desde `/AGENTS.md`.

## 2. Niveles de prueba

| Nivel | Qué cubre | Dónde vive | Necesita |
|---|---|---|---|
| Núcleo | Reglas de negocio y casos de uso: normalización, mapeo de cabeceras, versionado | `backend/tests/test_sabana_*.py`, `test_ingesta_servicio.py` | Nada. Se usan dobles de prueba en lugar de infraestructura |
| Adaptadores | Lectura de archivos y forma de las tablas | `backend/tests/test_lector_calamine.py`, `test_modelos_persistencia.py` | Archivos generados en memoria |
| Integración | Flujo completo contra PostgreSQL real, incluida la cadena ingesta → selección → generación → archivo entrando por HTTP | `backend/tests/test_repositorio_cargas_postgres.py`, `test_repositorio_cartera_postgres.py`, `test_generacion_cargas_postgres.py` | Base migrada y la variable `AUTO_CUSCO_DB_TESTS` |
| Volumen sintético | Tiempo y memoria de la generación de cargas con 60 000 y 120 000 filas | `backend/scripts/medir_generacion.py`, resultados en `docs/generacion-cargas.md` | Base migrada y una sábana del generador sintético |
| Verificación con volumen real | Rendimiento y conteos con una sábana de verdad | Local, no se versiona | Sábana real con los datos personales reemplazados en memoria |
| Núcleo del frontend | Lógica pura de la interfaz: fecha sugerida desde el nombre del archivo, formatos y montos exactos, sintaxis de la selección, cliente de API, descargas y el contrato con el catálogo de códigos de incidencia | `frontend/tests/nucleo/` | Nada. `fetch` se sustituye por un doble |
| DOM del frontend | Lógica que toca el documento: cola de diálogos (V-6 → V-4) y cambio de idioma | `frontend/tests/dom/` | Nada. Entorno `jsdom` |
| Extremo a extremo | Las pantallas contra el sitio construido: camino de subida, confirmaciones de V-4 y V-8, API caída, la regla de no-scroll de la bienvenida, y en la cartera el recálculo con un solo pedido, el aviso de insuficiencia, la fecha sin vigente y las selecciones guardadas | `frontend/e2e/` | Navegador. Playwright levanta `npm run preview`; **ni backend ni PostgreSQL** |
| Accesibilidad automatizada | Reglas WCAG 2.1 A y AA de axe-core en cada pantalla, en tema claro y oscuro, y en estados con diálogo abierto o partes marcadas como error | `frontend/e2e/accesibilidad.spec.ts` | Lo mismo que extremo a extremo; corre dentro de `npm run test:e2e` |

La arquitectura de puertos y adaptadores es lo que permite el primer nivel: el núcleo depende de interfaces, así que en las pruebas se sustituyen por dobles y no hace falta ni base de datos ni archivos.

En el frontend el equivalente es el cliente de API: las pruebas de extremo a extremo interceptan cada llamada con `page.route`, así que comprueban qué hace la interfaz con una respuesta —que es la única parte que le pertenece— sin depender de que el backend esté levantado.

## 3. Convenciones

- **Ubicación y nombre.** Un archivo por pieza en `backend/tests/`, con el nombre del área que cubre. Las funciones describen el comportamiento esperado en español.
- **Estructura.** Preparar, ejecutar y comprobar, separados por una línea en blanco. Una sola idea por prueba.
- **Sin base de datos por defecto.** Las pruebas que la necesitan llevan el marcador `postgres`, se saltan solas y limpian lo que crean.
- **Datos de prueba.** Se reutilizan los generadores sintéticos que ya existen en las pruebas del normalizador y de cabeceras, en lugar de inventar filas nuevas cada vez.
- **Sábanas de prueba completas.** Para probar a mano la ingesta o la interfaz, genera una sábana inventada en vez de usar una real, desde `backend/`:

  ```powershell
  uv run python scripts/generar_sabana_sintetica.py "..\data\sabanas\SINTETICA - 26.09.2026.xlsb" --filas 46000
  ```

  Python no puede escribir `.xlsb`, así que el script crea el archivo en `.xlsx` y lo convierte con Excel cuando el destino termina en `.xlsb`. Si no tienes Excel, genera el `.xlsx` y úsalo tal cual: el lector acepta ambos formatos. El archivo incluye casos borde a propósito (DNI de 7 dígitos, RUC válido, teléfonos inválidos, un pagaré repetido y una columna fuera del catálogo) y queda fuera de git como cualquier contenido de `data/sabanas/`.
- **Cobertura mínima de un módulo nuevo:** caso normal, bordes, entradas inválidas y, cuando dos piezas deben coincidir, una prueba de contrato entre ellas. El ejemplo vivo es la prueba que falla si las columnas de la tabla dejan de coincidir con lo que produce la normalización.
- **En el frontend valen las mismas convenciones,** con dos añadidos:
  - **Lo que se prueba se puede importar.** Si una pieza de lógica vive dentro del `<script>` de una página, no hay forma de probarla; se saca a `src/lib/` primero. Así nació `src/lib/dialogs.ts`.
  - **Nada de datos reales tampoco aquí.** Los archivos que se adjuntan en las pruebas de extremo a extremo se construyen en memoria (`e2e/api-falsa.ts`), nunca se lee uno de `data/sabanas/`.

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

Desde `frontend/`, cuando la tarea tocó la interfaz:

```powershell
npm run verificar        # contrato, tipos, build, pruebas de nucleo/DOM y extremo a extremo
```

Equivale a, en orden:

| Paso | Comando | Cuándo |
|---|---|---|
| Contrato | `npm run contrato:comprobar` | Siempre. Falla si los tipos del frontend no coinciden con `contratos/openapi.json` |
| Tipos | `npx astro check` | Siempre |
| Build | `npm run build` | Siempre |
| Núcleo y DOM | `npm run test` | Siempre |
| Extremo a extremo | `npm run test:e2e` | Siempre. Playwright construye y levanta `preview` por su cuenta |

La primera vez hace falta `npx playwright install chromium` para bajar el navegador.

Además, antes de cerrar:

- Actualiza `docs/planning.md` si cambió el alcance o se completó un punto, y `docs/modules.md` si cambió el estado de un módulo.
- Si cambió una regla de negocio, actualízala en su documento: `docs/sabana-schema.md` para la sábana y `docs/versionado-sabanas.md` para las versiones.
- Commit con prefijo: `feat`, `fix`, `docs`, `test`, `refactor` o `chore`, seguido del módulo entre paréntesis. Ejemplo: `fix(ingesta): ...`. El mensaje termina con el trailer `Agente:` que identifica la sesión que lo desarrolló (ver `docs/agents/README.md`).

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

`.github/workflows/frontend.yml` corre con los mismos disparadores, también con dos trabajos:

- **Build y pruebas de núcleo:** tipos con `astro check`, build y `vitest`. Aquí vive la mitad frontend del contrato de códigos de incidencia: si el catálogo gana un código y nadie lo traduce, este trabajo falla.
- **Extremo a extremo:** instala Chromium en el runner, construye el sitio y corre Playwright, que levanta `preview` por su cuenta. No necesita backend ni PostgreSQL porque cada prueba intercepta la API. Sube el reporte como artefacto cuando algo falla.

Si un trabajo falla, se corrige antes de seguir. La integración continua no reemplaza la verificación local: es la red que atrapa lo que se olvidó correr.

## 8. Pendientes

- **Capas avanzadas sin configurar.** El proyecto tiene las capas clásicas, tres contratos (incluido el del esquema de la API con los tipos del frontend) y accesibilidad automatizada con axe, pero no tipos estáticos en el backend, pruebas basadas en propiedades, mutación, cobertura, regresión visual ni auditoría de seguridad. Qué atrapa cada una, dónde rinde aquí y con qué herramienta encaja está en `.claude/skills/verificar/capas.md`. Configurar cualquiera de ellas es una decisión del usuario.
- **Pruebas de carga** según volumen real, previstas en la Fase 7 de `docs/planning.md`.
