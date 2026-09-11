"""Puertos: interfaces que el nucleo espera de la infraestructura.

Cada puerto se define aqui como un `typing.Protocol` (o clase abstracta) y
se implementa mediante uno o mas adaptadores concretos en app/adapters/.
Esto permite sustituir la infraestructura (p. ej. cambiar de motor de BD,
o de proveedor de SMS) sin tocar la logica de negocio en app/core/services/.
"""
