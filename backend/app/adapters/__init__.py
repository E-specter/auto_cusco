"""Adaptadores: conectan el nucleo (app/core/) con el mundo exterior.

- persistence/ -- PostgreSQL: engine/sesiones e implementaciones de puertos de repositorio.
- input/       -- entradas distintas de HTTP (p. ej. archivos de sabanas). Los
                   endpoints HTTP viven en app/api/, no aqui.
- output/      -- integraciones de salida: plataformas digitales (SMS, WhatsApp,
                   correo) y VoIP (Cisvox/Kontactus). Vacio hasta las Fases 3-4.
"""
