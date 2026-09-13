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
10. Gestiones digitales: registros de supervisión (RF-37 – RF-41)

La numeración `RF-1`…`RF-10` usada anteriormente en este documento queda **superseded** por la numeración `RF-01`… de `atomics-requirements.md`; no reutilizar la numeración antigua.

## Requerimientos generales de gestiones digitales

Aplican a toda plataforma digital (SMS, WhatsApp, correo y futuras). Texto formal en la sección 10 de [atomics-requirements.md](atomics-requirements.md).

| RF | Qué exige |
|---|---|
| RF-37 | Inyectar registros de control de supervisores en cada campaña digital, para que la gestión les llegue como a un cliente y puedan monitorear el envío real |
| RF-38 | Lista de supervisores configurable por campaña, con número y procedencia; por defecto 3 de `Caja Cusco` y 2 de `nuestra empresa` |
| RF-39 | DNI no real y secuencial desde `00000001`, primero `Caja Cusco` y luego `nuestra empresa` |
| RF-40 | Los demás campos de carga de la supervisión (p. ej. `mensaje`) se copian de la primera fila válida de los productos filtrados |
| RF-41 | Los registros de supervisión se anexan a la carga, van en el primer archivo si se divide, y cuentan en el resumen de cargados y enviados |

## Requerimientos por plataforma

Cada plataforma tiene su documento con requerimientos propios, numerados dentro del módulo para no mezclar su secuencia con la global:

| Plataforma | Módulo | Documento |
|---|---|---|
| SMS — MOWA, Messaging Enterprise Service (MES) | `mowa_mes` | [requerimientos-mowa-mes.md](requerimientos-mowa-mes.md) |

## Requerimientos no funcionales

- RNF-1: Los datos de cobranza son sensibles — nunca deben versionarse en git (ya aplicado vía `.gitignore`).
- RNF-2: El entorno de desarrollo es Windows con PowerShell.
- RNF-3 (TBD): Volumen esperado de datos (número de registros por sábana, frecuencia de carga) — afecta decisiones de rendimiento y elección de BD. Referencia medida en las muestras reales (ver `docs/sabana-schema.md`): ~46 mil productos por sábana diaria, archivos `.xlsb` de ~11 MB, con ~7% de rotación de productos entre días consecutivos. El volumen total esperado en producción (histórico acumulado, otras carteras o BPO) sigue sin confirmar.
- RNF-4 (TBD): Requisitos de auditoría/trazabilidad sobre cambios en gestiones/cargas.

## Próximo paso

Resolver los RNF marcados `TBD` con el usuario, y las decisiones de arquitectura listadas como pendientes en `docs/architecture.md` (motor de base de datos, comunicación frontend-backend), antes de iniciar la implementación del backend. Ver el detalle de fases en `docs/planning.md`.
