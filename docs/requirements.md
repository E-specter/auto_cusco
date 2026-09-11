# Requerimientos

## Contexto

`auto_cusco` automatiza la gestión de cobranza y cartera a partir de sábanas diarias. El detalle atomizado de requerimientos funcionales (RF-01 a RF-36) vive en **[atomics-requirements.md](atomics-requirements.md)**, que es la fuente de verdad funcional del proyecto. Este documento se mantiene como resumen de contexto y como registro de los requerimientos no funcionales.

## Requerimientos funcionales

Ver [atomics-requirements.md](atomics-requirements.md), organizado en las siguientes secciones:

1. Carga y procesamiento de sábanas diarias (RF-01 – RF-03)
2. Selección y segmentación de productos (RF-04 – RF-08)
3. Generación de cargas para plataformas digitales (RF-09 – RF-15)
4. Cargas para plataformas de llamadas VoIP (RF-16 – RF-19)
5. Reportes y trazabilidad (RF-20 – RF-24)
6. Métricas y analítica de selección (RF-25 – RF-28)
7. Diseño modular y extensible (RF-29 – RF-33)
8. Experiencia de usuario e interfaz (RF-34)
9. Documentación y entorno de trabajo con agentes de IA (RF-35 – RF-36)

La numeración `RF-1`…`RF-10` usada anteriormente en este documento queda **superseded** por la numeración `RF-01`…`RF-36` de `atomics-requirements.md`; no reutilizar la numeración antigua.

## Requerimientos no funcionales

- RNF-1: Los datos de cobranza son sensibles — nunca deben versionarse en git (ya aplicado vía `.gitignore`).
- RNF-2: El entorno de desarrollo es Windows con PowerShell.
- RNF-3 (TBD): Volumen esperado de datos (número de registros por sábana, frecuencia de carga) — afecta decisiones de rendimiento y elección de BD. Ya existen muestras reales de sábanas diarias en `data/sabanas/` (formato `.xlsb`) que pueden usarse como referencia de volumen, pero el volumen total esperado en producción sigue sin confirmar.
- RNF-4 (TBD): Requisitos de auditoría/trazabilidad sobre cambios en gestiones/cargas.

## Próximo paso

Resolver los RNF marcados `TBD` con el usuario, y las decisiones de arquitectura listadas como pendientes en `docs/architecture.md` (motor de base de datos, comunicación frontend-backend), antes de iniciar la implementación del backend. Ver el detalle de fases en `docs/planning.md`.
