# Instalación y ejecución

Guía paso a paso para dejar el proyecto corriendo en local. Sigue los pasos en orden — cada uno indica qué instala/verifica y qué deberías ver si salió bien.

> Estado actual: el **frontend** (Astro) y el **esqueleto del backend** (FastAPI, `GET /health`) ya son ejecutables. Falta la ingesta real de sábanas y el resto de módulos de negocio (paso 7, ver [planning.md](planning.md)).

## 0. Requisitos previos

| Herramienta | Versión mínima | Para qué |
|---|---|---|
| [Git](https://git-scm.com/) | cualquiera reciente | clonar y versionar el repo |
| [Node.js](https://nodejs.org/) | >= 22.12.0 | correr el frontend Astro |
| npm | viene con Node | instalar dependencias del frontend |
| [Python](https://www.python.org/) | 3.11+ | requerido por `uv` para el backend |
| [uv](https://docs.astral.sh/uv/) | cualquiera reciente | gestiona el entorno virtual y las dependencias del backend (ver paso 5) |
| PostgreSQL | — | base de datos del backend (ver paso 6) |

Verifica lo que ya necesitas ahora mismo (Git, Node, npm):

```powershell
git --version
node --version
npm --version
```

Node debe reportar `v22.12.0` o superior — es el mínimo declarado en `frontend/package.json`.

## 1. Clonar y abrir el proyecto

```powershell
git clone <url-del-repositorio> auto_cusco
cd auto_cusco
```

El repo incluye `auto_cusco.code-workspace`: ábrelo con VS Code (`File > Open Workspace from File...`) en vez de abrir la carpeta suelta — ya trae configurado el formateo, las extensiones recomendadas (Astro, Python, ESLint, SQLTools, etc.) y las exclusiones de búsqueda/watch para `node_modules`, `.venv`, `dist`, etc.

## 2. Frontend (Astro)

### 2.1 Instalar dependencias

```powershell
cd frontend
npm install
```

Esto crea `frontend/node_modules/` (ignorado por git) a partir de `package.json`. La única dependencia actual es `astro`.

### 2.2 Levantar el servidor de desarrollo

```powershell
npm run dev
```

Deberías ver en la terminal algo como `astro  v7.x.x  ready` y una URL local (por defecto `http://localhost:4321`). Ábrela en el navegador — debe cargar la página mínima de `frontend/src/pages/index.astro`.

> Nota para agentes de IA: `frontend/AGENTS.md` pide correr el dev server en modo background (`astro dev --background`) y gestionarlo con `astro dev stop` / `astro dev status` / `astro dev logs`, para no bloquear la sesión del agente.

### 2.3 Otros comandos disponibles

| Comando | Acción |
|---|---|
| `npm run build` | genera el sitio de producción en `frontend/dist/` |
| `npm run preview` | sirve localmente el build de `dist/` para verificarlo antes de desplegar |
| `npm run astro -- --help` | ver todos los comandos del CLI de Astro |

## 3. Carpetas de datos

Las carpetas `data/sabanas/`, `data/output/gestiones/` y `data/output/reportes/` ya existen en el repo (solo con un `.gitkeep` cada una) y están listas para usarse:

```powershell
cd ..
dir data\sabanas
```

**Importante**: el `.gitignore` de la raíz bloquea el contenido real de estas carpetas — solo se versiona la estructura. Nunca fuerces (`git add -f`) un archivo de datos real de cobranza dentro de `data/`; son datos sensibles.

## 4. Variables de entorno

El repo trae `.env.example` en la raíz como plantilla (sí se versiona). Cópialo a `.env` (nunca versionado, ya bloqueado por `.gitignore`) y completa los valores reales:

```powershell
Copy-Item .env.example .env
```

Por ahora ninguna variable es estrictamente necesaria: el frontend no las lee todavía. Las de base de datos (`DB_ENGINE`, `DB_HOST`, etc.) están ahí como adelanto para cuando exista el backend — actualiza `.env.example` (no solo tu `.env` local) cada vez que el código empiece a depender de una variable nueva, para que la plantilla no quede desactualizada.

## 5. Backend (Python)

El backend usa **[uv](https://docs.astral.sh/uv/)** para gestionar el entorno virtual y las dependencias — no `pip`/`venv` directos. Requiere PostgreSQL instalado (paso 6) para que el health-check reporte la base de datos como disponible, pero el servidor arranca igual sin ella.

```powershell
cd backend

# Crea backend\.venv e instala dependencias (runtime + dev) según pyproject.toml/uv.lock
uv sync

# Servidor de desarrollo con recarga automática
uv run fastapi dev app/main.py

# En otra terminal: probar el health-check
curl http://127.0.0.1:8000/health

# Documentación interactiva de la API, con la carga de sábanas incluida
Start-Process http://127.0.0.1:8000/docs

# Subir una sábana: responde de inmediato y el procesamiento sigue en segundo plano
curl.exe -F "fecha_corte=2026-09-10" -F "archivo=@..\data\sabanas\mi-sabana.xlsb" http://127.0.0.1:8000/cargas

# Consultar cómo va esa carga (usa el id que devolvió el comando anterior)
curl http://127.0.0.1:8000/cargas/1

# Tests (no requieren PostgreSQL real)
uv run pytest

# Integración opcional contra la base de /.env (requiere el paso 6; usa la fecha 2099 y borra lo que crea)
$env:AUTO_CUSCO_DB_TESTS = "1"; uv run pytest -m postgres; Remove-Item Env:AUTO_CUSCO_DB_TESTS

# Lint
uv run ruff check .
```

Deberías ver `{"api":true,"database":false,"ok":false}` hasta que completes el paso 6 (crear la base de datos real) — `database:false` es el comportamiento esperado, no un error.

El workspace ya está preconfigurado para apuntar a `backend\.venv\Scripts\python.exe` como intérprete y usar `ruff` como linter/formateador automático al guardar. Más detalle de convenciones en `backend/AGENTS.md`, y el protocolo de pruebas y corrección de errores en [testing.md](testing.md).

## 6. Base de datos (PostgreSQL)

El motor es **PostgreSQL** (ver `architecture.md`). Si ya tienes PostgreSQL corriendo localmente (puerto 5432), solo falta crear el rol de aplicación y la base de datos del proyecto — **una vez, en tu propia terminal** (el script pide la contraseña del superusuario `postgres` de forma interactiva; nunca la compartas por chat):

```powershell
& "C:\Program Files\PostgreSQL\<version>\bin\psql.exe" -U postgres -h localhost -f backend\scripts\init_db.sql
```

Esto crea el rol `auto_cusco_app` (contraseña por defecto `changeme`) y la base de datos `auto_cusco`. Luego:

1. Cambia la contraseña por defecto. Lo más seguro es `\password auto_cusco_app` desde `psql` como superusuario: la pide por teclado sin mostrarla y no tiene problemas con comillas. Alternativa: `ALTER ROLE auto_cusco_app WITH PASSWORD '<tu-contraseña>';` (si la contraseña lleva una comilla simple `'`, hay que escribirla duplicada `''`).
2. Copia `.env.example` a `.env` (si no existe todavía) y ajusta `DB_PASSWORD` con esa misma contraseña. **Antes de elegirla, revisa la sección 6.1.**
3. Crea o actualiza las tablas aplicando las migraciones, desde `backend/`:

   ```powershell
   uv run alembic upgrade head
   ```

   Es seguro repetirlo: solo aplica las migraciones pendientes. Para ver en qué versión está tu base usa `uv run alembic current`. El diseño de las tablas está en `docs/versionado-sabanas.md`.

### 6.1 Caracteres especiales en la contraseña

La contraseña de `DB_PASSWORD` pasa por dos etapas antes de llegar a PostgreSQL, y cada una interpreta ciertos caracteres. Si alguno se malinterpreta, el backend envía una contraseña distinta a la real y `GET /health` responde `database: false` (en el log del servidor aparece *la autentificación password falló para el usuario «auto_cusco_app»*), aunque la contraseña sea correcta en `psql`.

**Etapa 1 — lectura de `/.env`** (`pydantic-settings`):

| Contenido en `.env` | Qué pasa | Cómo evitarlo |
|---|---|---|
| Un espacio seguido de `#` (p. ej. `abc #123`) | Todo desde ` #` se toma como comentario; la contraseña queda `abc`. | Encerrar el valor entre comillas dobles: `DB_PASSWORD="abc #123"`. |
| `${ALGO}` | Se reemplaza por la variable de entorno `ALGO` del sistema, **incluso entre comillas simples o dobles**. | No usar la secuencia `${` en la contraseña. |
| Espacios al inicio o al final | Se eliminan. | Encerrar entre comillas dobles, o no usar espacios en los extremos. |

**Etapa 2 — armado de la URL de conexión** (`backend/app/core/config.py`, propiedad `database_url`): la contraseña se inserta **tal cual, sin codificar**, dentro de `postgresql+psycopg://usuario:CONTRASEÑA@host:puerto/base`, y SQLAlchemy la vuelve a separar al conectar.

| Carácter en la contraseña | Qué pasa | Ejemplo |
|---|---|---|
| `@` | Rompe la URL: la contraseña se corta en la primera `@` y el resto se toma como parte del host. | `abc@123` se interpreta como contraseña `abc` y host `123@localhost`. |
| `%` seguido de dos caracteres hexadecimales (`0-9`, `a-f`) | Se decodifica como carácter codificado en URL, así que la contraseña cambia. | `abc%40x` se envía como `abc@x`. |

Caracteres verificados **sin problema** en esta etapa: `:` `/` `#` `?` `&` `+` `=` `[` `]` `\` `"`, espacios, y `%` cuando no va seguido de dos hexadecimales (p. ej. `abc%zz`).

> Verificado con SQLAlchemy 2.0.52 y pydantic-settings 2.15.0 (versiones de `backend/uv.lock` al 2026-09-11). Si se actualizan estas librerías, conviene volver a comprobarlo.

**Recomendación práctica:** usa una contraseña larga solo con letras y números (p. ej. 24 o más caracteres generados al azar). Es igual de segura que una con símbolos y evita todos los casos anteriores.

**Solución de fondo (pendiente, no aplicada):** construir la URL con `sqlalchemy.engine.URL.create(...)` en lugar de un f-string elimina los problemas de la etapa 2, porque pasa la contraseña como campo separado sin codificarla en texto. Los problemas de la etapa 1 (`${` y ` #`) no dependen del código del backend y seguirían aplicando.

`auto_cusco.code-workspace` trae dos conexiones SQLTools de ejemplo (`Local PostgreSQL (admin)` y `Local PostgreSQL (auto_cusco)`) apuntando a `localhost`, listas para completar con las credenciales reales.

Cuando existan modelos de negocio en `backend/app/core/entities/` (a partir de la Fase 1), esta sección debe actualizarse con: cómo correr migraciones y cómo cargar datos de prueba sintéticos.

## 7. Ejecutar el flujo completo — *(pendiente)*

Una vez exista la ingesta real de sábanas (Fase 1 de `planning.md`), este paso documentará el flujo end-to-end: colocar una sábana en `data/sabanas/` → subirla desde el frontend → verificar que aparecen resultados en `data/output/gestiones/` y `data/output/reportes/` → verlos reflejados en el frontend. Por ahora son verificables el frontend (paso 2) y el backend mínimo vía `GET /health` (paso 5).

## Resolución de problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `npm install` falla por versión de Node | Node < 22.12.0 | actualizar Node (recomendado: usar `nvm` o instalar la LTS más reciente) |
| El puerto 4321 ya está en uso | otra instancia de `astro dev` corriendo | `astro dev stop` (si se inició en background) o cerrar el proceso manualmente |
| VS Code no aplica el formateo automático | se abrió la carpeta suelta en vez del `.code-workspace` | reabrir con `File > Open Workspace from File...` |
| `GET /health` devuelve `database: false` aunque la contraseña funciona en `psql` | `DB_PASSWORD` contiene `@`, `%` + dos hexadecimales, `${` o ` #` | ver sección 6.1; cambiar la contraseña a una solo con letras y números |
