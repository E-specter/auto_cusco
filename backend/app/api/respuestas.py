"""Base de los modelos que la API devuelve.

Regla del contrato (docs/contrato-api.md): opcional significa "a veces no viene".
Todo campo que el backend serializa siempre va obligatorio en el esquema, con
null en su tipo si puede venir vacio, aunque en Pydantic tenga valor por
defecto. Sin esta base, un campo con defecto aparece como opcional y el
frontend tiene que tratarlo como si pudiera faltar.
"""

from pydantic import BaseModel, ConfigDict


class ModeloRespuesta(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
