from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SalidaProvisoriaViewSet, 
    IngresoMercaderiaViewSet, 
    BajaInventarioViewSet,
    TransferenciaInternaViewSet,
    AjusteComercialViewSet,
    SalidaProvisoriaViewSet,
    DevolucionSalidaProvisoriaViewSet,
    LiquidacionSalidaProvisoriaViewSet,
    DepositoViewSet,
    StockLoteViewSet
)


# El router del inventario
router = DefaultRouter()
# Registramos la vista que armamos en el paso anterior
router.register(r'salidas-provisorias', SalidaProvisoriaViewSet,
                basename='salida-provisoria')
router.register(r'ingresos', IngresoMercaderiaViewSet, basename='ingreso')
router.register(r'depositos', DepositoViewSet, basename='deposito')
router.register(r'bajas', BajaInventarioViewSet, basename='baja')
router.register(r'transferencias', TransferenciaInternaViewSet, basename='transferencia')
router.register(r'ajustes', AjusteComercialViewSet, basename='ajuste')
router.register(r'consignaciones', SalidaProvisoriaViewSet, basename='consignacion')
router.register(r'devoluciones', DevolucionSalidaProvisoriaViewSet, basename='devolucion')
router.register(r'liquidaciones', LiquidacionSalidaProvisoriaViewSet, basename='liquidacion')
router.register(r'stock-lotes', StockLoteViewSet, basename='stock-lote')

urlpatterns = [
    path('', include(router.urls)),
]
