"""Sintaxis de texto de las expresiones: `[@campo]`, `[@campo | funcion(args)]` (D9).

Compatible con RF-12: `[@campo]` vale lo mismo que en las plantillas de hoy, y
`[@ campo ]` con espacios tambien. Se amplia con tuberias y argumentos:

    51[@telefono]
    [@titular | primeros(8)]
    [@fecha | sumar_dias(3) | formato_fecha("dd/mm/aaaa")]
    [@monto | multiplicar(@tipo_cambio) | redondear(2)]

Argumentos: numero (`3`, `-2`, `2.50`), texto entre comillas (`"a]b|c"`, con
`\\"` y `\\\\` como escapes) o variable (`@nombre`). Un `[@` literal en un nodo
texto se escribe `[@@]`; hoy ese texto es siempre invalido, asi que el escape no
cambia el significado de ninguna plantilla existente.

Es un analizador de un solo paso, sin expresiones regulares: el tiempo es lineal
en el largo del texto aunque llegue una entrada hostil, y los limites de tamano
cortan la lectura en cuanto se pasan.

Garantia: `escribir(leer(t))` es una forma canonica que se lee igual que `t`, y
para un texto ya canonico `escribir(leer(t)) == t`. Una expresion sin forma de
texto se informa, no se deforma.
"""

from decimal import Decimal
from typing import NoReturn

from app.core.entities.texto_enriquecido import (
    LIMITES,
    Argumento,
    ArgumentoVariable,
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    ExpresionNoEscribible,
    LimitesExpresion,
    LlamadaFuncion,
    Nodo,
    NodoTexto,
    NodoVariable,
    Problema,
)

APERTURA = "[@"
APERTURA_ESCAPADA = "[@@]"
_FIN_DE_NOMBRE = "|[]"
_FIN_DE_NOMBRE_DE_ARGUMENTO = _FIN_DE_NOMBRE + ',)"'
_LARGO_MAXIMO_NUMERO = 30
_SIN_CERRAR = "Hay un '[@' sin cerrar con ']'"


def leer(texto: str, limites: LimitesExpresion = LIMITES) -> Expresion:
    """Convierte un texto en expresion. Si esta mal escrito, `ExpresionInvalida`."""
    return _Lector(texto, limites).expresion()


def _es_inicio_de_identificador(caracter: str) -> bool:
    return caracter.isascii() and (caracter.isalpha() or caracter == "_")


def _es_parte_de_identificador(caracter: str) -> bool:
    return caracter.isascii() and (caracter.isalnum() or caracter == "_")


def _es_digito(caracter: str) -> bool:
    return caracter.isascii() and caracter.isdigit()


class _Lector:
    def __init__(self, texto: str, limites: LimitesExpresion) -> None:
        self._texto = texto
        self._n = len(texto)
        self._limites = limites
        self._nodos: list[Nodo] = []
        self._pendiente: list[str] = []
        self._largo_pendiente = 0

    # --- errores ---

    def _falla(
        self,
        codigo: CodigoTexto,
        detalle: str,
        posicion: int,
        *,
        funcion: int | None = None,
        de_toda_la_expresion: bool = False,
    ) -> NoReturn:
        problema = Problema(
            codigo,
            f"{detalle} en la posicion {posicion}",
            nodo=None if de_toda_la_expresion else len(self._nodos),
            funcion=funcion,
        )
        raise ExpresionInvalida((problema,))

    # --- nodos texto ---

    def _acumular(self, trozo: str, posicion: int) -> None:
        self._pendiente.append(trozo)
        self._largo_pendiente += len(trozo)
        if self._largo_pendiente > self._limites.largo_literal:
            self._falla(
                CodigoTexto.LIMITE_EXCEDIDO,
                f"El texto fijo pasa de {self._limites.largo_literal} caracteres",
                posicion,
            )

    def _cerrar_texto(self, posicion: int) -> None:
        if self._pendiente:
            self._agregar(NodoTexto("".join(self._pendiente)), posicion)
            self._pendiente = []
            self._largo_pendiente = 0

    def _agregar(self, nodo: Nodo, posicion: int) -> None:
        if len(self._nodos) >= self._limites.nodos:
            self._falla(
                CodigoTexto.LIMITE_EXCEDIDO,
                f"La expresion pasa de {self._limites.nodos} nodos",
                posicion,
                de_toda_la_expresion=True,
            )
        self._nodos.append(nodo)

    # --- recorrido ---

    def expresion(self) -> Expresion:
        texto, n = self._texto, self._n
        i = 0
        while i < n:
            j = texto.find(APERTURA, i)
            if j == -1:
                self._acumular(texto[i:], i)
                break
            if j > i:
                self._acumular(texto[i:j], i)
            if texto.startswith(APERTURA_ESCAPADA, j):
                self._acumular(APERTURA, j)
                i = j + len(APERTURA_ESCAPADA)
                continue
            self._cerrar_texto(j)
            nodo, i = self._referencia(j)
            self._agregar(nodo, j)
        self._cerrar_texto(n)
        return Expresion(tuple(self._nodos))

    def _espacios(self, i: int) -> int:
        texto, n = self._texto, self._n
        while i < n and texto[i].isspace():
            i += 1
        return i

    def _referencia(self, inicio: int) -> tuple[NodoVariable, int]:
        texto, n = self._texto, self._n
        i = self._espacios(inicio + len(APERTURA))
        desde = i
        while i < n and not texto[i].isspace() and texto[i] not in _FIN_DE_NOMBRE:
            i += 1
        nombre = texto[desde:i]
        i = self._espacios(i)
        if not nombre:
            if i < n and texto[i] in "]|":
                self._falla(CodigoTexto.REFERENCIA_VACIA, "La referencia esta vacia", inicio)
            self._falla(CodigoTexto.SINTAXIS_INVALIDA, _SIN_CERRAR, inicio)
        if nombre == "@":  # `[@@]` es el escape de un `[@` literal
            self._falla(CodigoTexto.SINTAXIS_INVALIDA, "Una variable no puede llamarse '@'", inicio)
        funciones: list[LlamadaFuncion] = []
        while True:
            if i >= n:
                self._falla(CodigoTexto.SINTAXIS_INVALIDA, _SIN_CERRAR, inicio)
            caracter = texto[i]
            if caracter == "]":
                return NodoVariable(nombre, tuple(funciones)), i + 1
            if caracter != "|":
                self._falla(
                    CodigoTexto.SINTAXIS_INVALIDA,
                    f"Se esperaba '|' o ']' despues de {nombre!r} y hay {caracter!r}",
                    i,
                )
            if len(funciones) >= self._limites.funciones_por_nodo:
                self._falla(
                    CodigoTexto.LIMITE_EXCEDIDO,
                    f"Una variable admite hasta {self._limites.funciones_por_nodo} funciones",
                    i,
                )
            llamada, i = self._funcion(self._espacios(i + 1), len(funciones))
            funciones.append(llamada)
            i = self._espacios(i)

    def _funcion(self, i: int, posicion_funcion: int) -> tuple[LlamadaFuncion, int]:
        texto, n = self._texto, self._n
        desde = i
        if i < n and _es_inicio_de_identificador(texto[i]):
            i += 1
            while i < n and _es_parte_de_identificador(texto[i]):
                i += 1
        else:
            self._falla(
                CodigoTexto.SINTAXIS_INVALIDA,
                "Se esperaba el nombre de una funcion despues de '|'",
                i,
                funcion=posicion_funcion,
            )
        nombre = texto[desde:i]
        j = self._espacios(i)
        if j >= n or texto[j] != "(":
            return LlamadaFuncion(nombre), i
        args, i = self._argumentos(j + 1, posicion_funcion)
        return LlamadaFuncion(nombre, tuple(args)), i

    def _argumentos(self, i: int, funcion: int) -> tuple[list[Argumento], int]:
        texto, n = self._texto, self._n
        args: list[Argumento] = []
        i = self._espacios(i)
        if i < n and texto[i] == ")":
            return args, i + 1
        while True:
            if len(args) >= self._limites.argumentos_por_funcion:
                self._falla(
                    CodigoTexto.LIMITE_EXCEDIDO,
                    f"Una funcion admite hasta {self._limites.argumentos_por_funcion} argumentos",
                    i,
                    funcion=funcion,
                )
            argumento, i = self._argumento(i, funcion)
            args.append(argumento)
            i = self._espacios(i)
            if i < n and texto[i] == ")":
                return args, i + 1
            if i < n and texto[i] == ",":
                i = self._espacios(i + 1)
                continue
            self._falla(
                CodigoTexto.SINTAXIS_INVALIDA,
                "Se esperaba ',' o ')' despues del argumento",
                i,
                funcion=funcion,
            )

    def _argumento(self, i: int, funcion: int) -> tuple[Argumento, int]:
        texto, n = self._texto, self._n
        caracter = texto[i] if i < n else ""
        if caracter == '"':
            return self._cadena(i, funcion)
        if caracter == "@":
            desde = i + 1
            j = desde
            while j < n and not texto[j].isspace() and texto[j] not in _FIN_DE_NOMBRE_DE_ARGUMENTO:
                j += 1
            if j == desde:
                self._falla(
                    CodigoTexto.SINTAXIS_INVALIDA,
                    "Falta el nombre de la variable",
                    i,
                    funcion=funcion,
                )
            return ArgumentoVariable(texto[desde:j]), j
        if caracter == "-" or (caracter and _es_digito(caracter)):
            return self._numero(i, funcion)
        self._falla(
            CodigoTexto.SINTAXIS_INVALIDA,
            "Un argumento es un numero, un texto entre comillas o una variable con '@'",
            i,
            funcion=funcion,
        )

    def _cadena(self, i: int, funcion: int) -> tuple[str, int]:
        texto, n = self._texto, self._n
        inicio = i
        i += 1
        trozos: list[str] = []
        while i < n:
            caracter = texto[i]
            if caracter == '"':
                return "".join(trozos), i + 1
            if caracter == "\\":
                if i + 1 >= n or texto[i + 1] not in '"\\':
                    self._falla(
                        CodigoTexto.SINTAXIS_INVALIDA,
                        "Solo se puede escapar '\"' y '\\' dentro de un texto",
                        i,
                        funcion=funcion,
                    )
                i += 1
                caracter = texto[i]
            trozos.append(caracter)
            if len(trozos) > self._limites.largo_literal:
                self._falla(
                    CodigoTexto.LIMITE_EXCEDIDO,
                    f"Un argumento de texto pasa de {self._limites.largo_literal} caracteres",
                    inicio,
                    funcion=funcion,
                )
            i += 1
        self._falla(
            CodigoTexto.SINTAXIS_INVALIDA,
            "Falta cerrar las comillas",
            inicio,
            funcion=funcion,
        )

    def _numero(self, i: int, funcion: int) -> tuple[Argumento, int]:
        texto, n = self._texto, self._n
        inicio = i
        if texto[i] == "-":
            i += 1
        entero = i
        i = self._digitos(i)
        if i == entero:
            self._falla(
                CodigoTexto.SINTAXIS_INVALIDA,
                "Se esperaba un numero",
                inicio,
                funcion=funcion,
            )
        decimal = False
        if i < n and texto[i] == ".":
            fin = self._digitos(i + 1)
            if fin == i + 1:
                self._falla(
                    CodigoTexto.SINTAXIS_INVALIDA,
                    "Faltan los decimales",
                    i,
                    funcion=funcion,
                )
            i, decimal = fin, True
        if i - inicio > _LARGO_MAXIMO_NUMERO:
            self._falla(
                CodigoTexto.LIMITE_EXCEDIDO,
                f"Un numero pasa de {_LARGO_MAXIMO_NUMERO} caracteres",
                inicio,
                funcion=funcion,
            )
        token = texto[inicio:i]
        return (Decimal(token) if decimal else int(token)), i

    def _digitos(self, i: int) -> int:
        texto, n = self._texto, self._n
        while i < n and _es_digito(texto[i]):
            i += 1
        return i


# --- expresion -> texto ---


def escribir(expresion: Expresion) -> str:
    """Forma canonica en texto. Si no se puede escribir, `ExpresionNoEscribible`."""
    trozos: list[str] = []
    texto_pendiente: list[str] = []

    def cerrar_texto() -> None:
        if texto_pendiente:
            trozos.append("".join(texto_pendiente).replace(APERTURA, APERTURA_ESCAPADA))
            texto_pendiente.clear()

    for indice, nodo in enumerate(expresion.nodos):
        if isinstance(nodo, NodoTexto):
            texto_pendiente.append(nodo.valor)
            continue
        cerrar_texto()
        trozos.append(_escribir_variable(nodo, indice))
    cerrar_texto()
    return "".join(trozos)


def _no_escribible(detalle: str, nodo: int, funcion: int | None = None) -> NoReturn:
    raise ExpresionNoEscribible(
        Problema(
            CodigoTexto.NO_SE_PUEDE_ESCRIBIR_COMO_TEXTO,
            detalle,
            nodo=nodo,
            funcion=funcion,
        )
    )


def _nombre_valido(nombre: str, prohibidos: str) -> bool:
    return bool(nombre) and not any(c.isspace() or c in prohibidos for c in nombre)


def _escribir_variable(nodo: NodoVariable, indice: int) -> str:
    if nodo.obligatoria:
        _no_escribible(
            f"La variable {nodo.nombre!r} es obligatoria y el texto no tiene como marcarlo", indice
        )
    if nodo.nombre == "@" or not _nombre_valido(nodo.nombre, _FIN_DE_NOMBRE):
        _no_escribible(
            f"El nombre de variable {nodo.nombre!r} no cabe en la sintaxis de texto", indice
        )
    partes = [nodo.nombre]
    for posicion, llamada in enumerate(nodo.funciones):
        partes.append(_escribir_llamada(llamada, indice, posicion))
    return f"[@{' | '.join(partes)}]"


def _escribir_llamada(llamada: LlamadaFuncion, nodo: int, funcion: int) -> str:
    nombre = llamada.nombre
    if not (
        nombre
        and _es_inicio_de_identificador(nombre[0])
        and all(_es_parte_de_identificador(c) for c in nombre)
    ):
        _no_escribible(
            f"El nombre de funcion {nombre!r} no cabe en la sintaxis de texto", nodo, funcion
        )
    if not llamada.args:
        return nombre
    args = [_escribir_argumento(a, nodo, funcion) for a in llamada.args]
    return f"{nombre}({', '.join(args)})"


def _escribir_argumento(argumento: Argumento, nodo: int, funcion: int) -> str:
    if isinstance(argumento, ArgumentoVariable):
        if not _nombre_valido(argumento.nombre, _FIN_DE_NOMBRE_DE_ARGUMENTO):
            _no_escribible(
                f"El nombre de variable {argumento.nombre!r} no cabe como argumento",
                nodo,
                funcion,
            )
        return f"@{argumento.nombre}"
    if isinstance(argumento, str):
        return '"' + argumento.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(argumento, bool):
        _no_escribible("Un argumento no puede ser verdadero o falso", nodo, funcion)
    if isinstance(argumento, Decimal):
        if not argumento.is_finite():
            _no_escribible("El numero no es finito", nodo, funcion)
        escrito = format(argumento, "f")
    else:
        escrito = str(argumento)
    if len(escrito) > _LARGO_MAXIMO_NUMERO:
        _no_escribible(f"El numero pasa de {_LARGO_MAXIMO_NUMERO} caracteres", nodo, funcion)
    return escrito
