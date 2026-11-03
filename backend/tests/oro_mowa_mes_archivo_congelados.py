"""Constantes del oro del archivo .xlsx de una campana de MOWA MES (T-MM-B15, paso 1).

Calculadas en el turno del 2026-11-02 sobre main 0e19b0d, con el codigo de HOY (antes de generar
este archivo con `GeneracionCargasService`); no se recalculan. Salen de
`tests/test_mowa_mes_archivo_oro.archivos_de_la_campana` ejecutada DESDE el worktree: la campana
creada por `CampanasMowaMesService.crear` con el escritor real, dividida por filas (6, 6 y 5), y por
cada archivo `huella_xlsx` y `largo_sin_comprimir_sin_core` (`exportacion_seguridad_datos.py`).
"""

# numero -> (numero, filas, supervision, huella_xlsx, largo_sin_comprimir_sin_core)
ARCHIVOS_CONGELADOS: dict[int, tuple[int, int, int, str, int]] = {
    1: (
        1,
        6,
        5,
        (
            "7bdc9"  # partido en dos: 9 digitos seguidos parecerian un telefono
            "58147888f3eaf11ff3e9d838eaf052247abd56f29083c3ae15611c2b72d"  # (test_datos_sinteticos)
        ),
        17652,
    ),
    2: (2, 6, 0, "f603358cd1b4ad3967672d4a49e6fa84c62980505768ad32c28c8e9a067895bc", 17952),
    3: (3, 5, 0, "aa82276dcc2db029d84460e62ff3533b9fc544bb8bd9b3ebbf78257c966f8503", 17641),
}
