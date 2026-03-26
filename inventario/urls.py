from django.urls import path, include
from rest_framework.routers import DefaultRouter
# ACTUALIZADO: Agregamos CategoriaViewSet a la importación
from .views import ProductoViewSet, CategoriaViewSet

# El router crea automáticamente las URLs
router = DefaultRouter()
router.register(r'productos', ProductoViewSet)
# NUEVO: Le enseñamos a Django la ruta para las categorías
router.register(r'categorias', CategoriaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
