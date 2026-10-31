"""Puerto de persistencia del conector MOWA MES: configuracion y versiones de speech."""

from typing import Protocol

from app.core.entities.mowa_mes import ConfiguracionMowaMes, DatosSpeech, VersionSpeech


class RepositorioMowaMesPort(Protocol):
    def obtener_configuracion(self) -> ConfiguracionMowaMes: ...

    def guardar_configuracion(
        self, configuracion: ConfiguracionMowaMes
    ) -> ConfiguracionMowaMes: ...

    def listar_speech(self) -> list[VersionSpeech]:
        """Todas las versiones, la original primero y luego por fecha de creacion."""
        ...

    def obtener_speech(self, speech_id: int) -> VersionSpeech | None: ...

    def crear_speech(self, datos: DatosSpeech, basada_en_id: int | None) -> VersionSpeech:
        """Lanza NombreDeSpeechRepetido si el nombre ya existe, sin distinguir mayusculas."""
        ...

    def actualizar_speech(self, speech_id: int, datos: DatosSpeech) -> VersionSpeech | None:
        """Solo si la version sigue siendo editable; None si no existe o ya no lo es.

        La condicion va en la misma escritura: una campana que la usa a la vez no
        puede quedar con un speech distinto del que genero.
        """
        ...

    def renombrar_speech(self, speech_id: int, nombre: str) -> VersionSpeech | None:
        """Cualquier version, la usada y el original incluidos (RF-MM-28): solo cambia el nombre,
        no el contenido ni la huella. None si no existe; NombreDeSpeechRepetido si ya existe."""
        ...

    def cambiar_habilitacion(self, speech_id: int, habilitada: bool) -> VersionSpeech | None:
        """Deshabilita (ahora) o habilita (RF-MM-29). Repetirlo no cambia la fecha. None si no
        existe."""
        ...

    def eliminar_speech(self, speech_id: int) -> bool:
        """Borra una version DESHABILITADA, sin uso y que no sea el original (RF-MM-30). La
        condicion va en el mismo DELETE; False, sin borrar nada, si no se cumple o no existe."""
        ...

    def marcar_speech_usado(self, speech_id: int) -> None:
        """La campana que usa la version la marca en su misma transaccion (B4)."""
        ...
