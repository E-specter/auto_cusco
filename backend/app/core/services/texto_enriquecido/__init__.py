"""Motor de texto enriquecido (RF-42 a RF-48).

Extiende el motor de mapeo (RF-12): la plantilla `[@campo]` sigue valiendo lo
mismo, y se amplia con funciones encadenadas por tuberia.

- sintaxis.py   -- texto `[@campo | funcion(args)]` <-> expresion (analizador propio).
- funciones/    -- catalogo cerrado: un modulo por familia y un registro.
- tipos.py      -- tipos de valor, comprobacion de la cadena de funciones al compilar.
- evaluador.py  -- compila una vez y evalua por fila.
- cota.py       -- largo maximo que puede alcanzar una expresion, si se puede acotar.

No conoce ninguna plataforma ni importa de `adapters/`: las variables de contexto
las aporta quien lo usa.
"""
