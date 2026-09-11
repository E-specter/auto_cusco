## Entorno y dependencias

Este proyecto usa **uv** (no `pip`/`venv` directos) para gestionar el entorno y las dependencias. Todo desde `backend/`:

```powershell
uv sync            # crea backend/.venv e instala dependencias (runtime + dev) segun pyproject.toml/uv.lock
uv add <paquete>    # agrega una dependencia de runtime y actualiza pyproject.toml + uv.lock
uv add --dev <paquete>  # agrega una dependencia de desarrollo
uv run <comando>    # ejecuta un comando dentro del entorno (sin activar el venv manualmente)
```

No edites `uv.lock` a mano; se regenera con `uv sync` / `uv add` / `uv lock`. Commitea `uv.lock` junto con `pyproject.toml`.

## Comandos habituales

```powershell
uv run fastapi dev app/main.py   # servidor de desarrollo con recarga automatica
uv run pytest                    # tests (no requieren PostgreSQL real, ver tests/)
uv run ruff check .              # lint
uv run ruff format .             # formateo
```

## Base de datos

El motor es PostgreSQL (ver `docs/architecture.md`). La primera vez, crea el rol y la base de datos ejecutando `backend/scripts/init_db.sql` como superusuario (instrucciones en el propio script) y completa `DB_PASSWORD` en tu `/.env` local. La configuracion se lee en `app/core/config.py`.

## Convencion de codigo: puertos/adaptadores con vertical slicing (RF-30)

- `app/core/` -- entidades, puertos (`Protocol`) y servicios (casos de uso). **No** debe importar FastAPI, SQLAlchemy ni ningun detalle de infraestructura.
- `app/adapters/persistence/` -- SQLAlchemy/PostgreSQL, implementa los puertos de `app/core/ports/`.
- `app/adapters/input/` y `app/adapters/output/` -- adaptadores de entrada/salida que no son HTTP (archivos de sabanas, plataformas digitales/VoIP).
- `app/api/` -- routers de FastAPI (adaptador de entrada HTTP), uno por caso de uso.

Cada caso de uso nuevo (ingesta, seleccion, generacion de cargas, reportes...) sigue el mismo patron que `health_service.py`/`health.py`: un servicio en `app/core/services/` que depende solo de puertos, adaptadores concretos en `app/adapters/`, y un router delgado en `app/api/` que los conecta. Ver `docs/architecture.md` y `docs/modules.md` para el detalle completo.

## Al agregar un modulo nuevo

Actualiza `docs/modules.md` (estado, ruta, requerimientos que cubre) y, si corresponde, `docs/planning.md` -- ver la convencion general en `/AGENTS.md` y `docs/agents/README.md`.
