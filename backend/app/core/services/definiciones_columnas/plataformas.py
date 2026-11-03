"""El registro de plataformas y la validacion de una definicion contra sus reglas (RF-72, T-HI-B2).

`RegistroPlataformas` es del nucleo y no conoce ninguna plataforma: cada modulo agrega sus
`ReglasPlataforma` desde su propio paquete, como los contextos del motor de texto (RF-14, RF-31).

`problemas_de_plataforma` exige solo cuatro cosas, y cada problema lleva su columna, como en RF-46:

1. cada columna fija esta presente (`plataforma_columna_fija_ausente`);
2. en su posicion (`plataforma_columna_fija_movida`);
3. con su tipo (`plataforma_tipo_de_columna_fija`);
4. el resto respeta `tipo_resto` (`plataforma_tipo_del_resto`) y, si `admite_mas_columnas` es
   falso, no hay mas columnas que las fijas (`plataforma_columnas_de_mas`).

`encabezado_por_posicion` no se valida: es solo el valor por defecto del nombre. Una plataforma que
ya no esta registrada es un problema de la definicion (`plataforma_desconocida`), no un error de
lectura: la definicion se sigue leyendo y generando como se guardo.
"""

from collections.abc import Iterable

from app.core.entities.plataformas import PlataformaDesconocida, ReglasPlataforma
from app.core.entities.texto_enriquecido import CodigoTexto, Problema
from app.core.services.mapeo_campos.serializacion import DefinicionLeida, ProblemaDeDefinicion

CAMPO = "plataforma"


class RegistroPlataformas:
    """Las plataformas que la aplicacion conoce, por clave y en el orden en que se registraron."""

    def __init__(self, plataformas: Iterable[ReglasPlataforma] = ()) -> None:
        self._plataformas: dict[str, ReglasPlataforma] = {}
        for reglas in plataformas:
            self.registrar(reglas)

    def registrar(self, reglas: ReglasPlataforma) -> None:
        if reglas.clave in self._plataformas:
            raise ValueError(f"La plataforma {reglas.clave!r} esta registrada dos veces")
        self._plataformas[reglas.clave] = reglas

    def disponibles(self) -> tuple[ReglasPlataforma, ...]:
        return tuple(self._plataformas.values())

    def obtener(self, clave: str) -> ReglasPlataforma:
        try:
            return self._plataformas[clave]
        except KeyError:
            raise PlataformaDesconocida(clave) from None

    def __contains__(self, clave: object) -> bool:
        return clave in self._plataformas


def problema_de_plataforma_desconocida(clave: str) -> ProblemaDeDefinicion:
    return ProblemaDeDefinicion(
        Problema(
            CodigoTexto.PLATAFORMA_DESCONOCIDA,
            f"La plataforma {clave!r} no esta registrada",
            nombre=clave,
        ),
        None,
        None,
        CAMPO,
    )


def _problema(
    codigo: CodigoTexto, detalle: str, columna: int | None, nombre: str
) -> ProblemaDeDefinicion:
    return ProblemaDeDefinicion(Problema(codigo, detalle, nombre=nombre), columna, None, CAMPO)


def problemas_de_plataforma(
    leida: DefinicionLeida, reglas: ReglasPlataforma
) -> list[ProblemaDeDefinicion]:
    """Los problemas de la definicion contra las reglas de la plataforma; vacio si las cumple."""
    campos = leida.definicion.campos
    posiciones = leida.posiciones
    etiqueta = reglas.etiqueta
    fijas = {fija.nombre: fija for fija in reglas.columnas_fijas}
    problemas: list[ProblemaDeDefinicion] = []

    for fija in reglas.columnas_fijas:
        indice = fija.posicion - 1
        donde = next((i for i, c in enumerate(campos) if c.nombre == fija.nombre), None)
        if donde is None:
            columna = posiciones[indice] if indice < len(campos) else None
            problemas.append(
                _problema(
                    CodigoTexto.PLATAFORMA_COLUMNA_FIJA_AUSENTE,
                    f"Falta la columna fija «{fija.nombre}» de {etiqueta}, que va en la "
                    f"posicion {fija.posicion}",
                    columna,
                    fija.nombre,
                )
            )
        elif donde != indice:
            problemas.append(
                _problema(
                    CodigoTexto.PLATAFORMA_COLUMNA_FIJA_MOVIDA,
                    f"La columna «{fija.nombre}» es fija en {etiqueta} y va en la posicion "
                    f"{fija.posicion}, no en la {donde + 1}",
                    posiciones[donde],
                    fija.nombre,
                )
            )
        elif campos[donde].tipo is not fija.tipo:
            problemas.append(
                _problema(
                    CodigoTexto.PLATAFORMA_TIPO_DE_COLUMNA_FIJA,
                    f"La columna fija «{fija.nombre}» de {etiqueta} es de tipo "
                    f"{fija.tipo.value}, no {campos[donde].tipo.value}",
                    posiciones[donde],
                    fija.nombre,
                )
            )

    for indice, campo in enumerate(campos):
        if campo.nombre in fijas:
            continue  # la fija ya se reviso arriba; aqui solo el resto
        if not reglas.admite_mas_columnas:
            problemas.append(
                _problema(
                    CodigoTexto.PLATAFORMA_COLUMNAS_DE_MAS,
                    f"{etiqueta} no admite mas columnas que las fijas: sobra «{campo.nombre}»",
                    posiciones[indice],
                    campo.nombre,
                )
            )
        elif reglas.tipo_resto is not None and campo.tipo is not reglas.tipo_resto:
            problemas.append(
                _problema(
                    CodigoTexto.PLATAFORMA_TIPO_DEL_RESTO,
                    f"En {etiqueta} las demas columnas son de tipo {reglas.tipo_resto.value}, "
                    f"no {campo.tipo.value}",
                    posiciones[indice],
                    campo.nombre,
                )
            )
    return problemas
