"""Entorno de Alembic para auto_cusco.

Uso desde backend/ (ver docs/setup.md, paso 6):

    uv run alembic upgrade head                       # aplicar migraciones
    uv run alembic revision --autogenerate -m "..."   # crear una migracion nueva
    uv run alembic check                              # verificar que no hay cambios sin migrar

La URL de la base sale de /.env via app.core.config. No se pasa por
config.set_main_option: Alembic guarda las opciones en configparser, que
interpreta el caracter '%' y romperia contrasenas que lo contengan.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.adapters.persistence.modelos import Base
from app.core.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Genera el SQL de las migraciones sin conectarse (uv run alembic upgrade head --sql)."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
