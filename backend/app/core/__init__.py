"""Nucleo de negocio: entidades, puertos y casos de uso (servicios).

No debe depender de FastAPI, SQLAlchemy ni de ningun otro detalle de
infraestructura -- esas dependencias viven en app/adapters/ y app/api/,
y se conectan al nucleo a traves de los puertos definidos en
app/core/ports/ (ver docs/architecture.md, "puertos/adaptadores con
vertical slicing", RF-30).
"""
