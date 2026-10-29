"""Nombres que el usuario escribe: como se comparan para decidir que dos son el mismo."""


def normalizar_nombre(nombre: str) -> str:
    """Sin espacios en los extremos y en minusculas: la unicidad no distingue mayusculas.

    Es la clave de `nombre_normalizado` de las selecciones, las definiciones de carga y las
    versiones de speech; cambiarla cambia que nombres chocan (409).
    """
    return nombre.strip().casefold()
