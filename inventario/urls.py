from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SalidaProvisoriaViewSet


# El router del inventario
router = DefaultRouter()
# Registramos la vista que armamos en el paso anterior
router.register(r'salidas-provisorias', SalidaProvisoriaViewSet,
                basename='salida-provisoria')

urlpatterns = [
    path('', include(router.urls)),
]
