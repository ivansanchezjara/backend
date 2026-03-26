# inventario/models/__init__.py
from .catalogo import Categoria, Producto, Variante, ImagenProducto
from .stock import Deposito, StockLote, HistorialCosto
from .movimientos import (
    IngresoMercaderia, ItemIngreso, BajaInventario, TransferenciaInterna,
    AjusteComercial, SalidaProvisoria, ItemSalidaProvisoria,
    DevolucionSalidaProvisoria, ItemDevolucionProvisoria
)
