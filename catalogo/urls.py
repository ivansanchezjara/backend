from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductoViewSet, CategoriaViewSet, VarianteViewSet, ImagenProductoViewSet

router = DefaultRouter()
router.register(r'productos', ProductoViewSet, basename='producto')
router.register(r'categorias', CategoriaViewSet, basename='categoria')
router.register(r'variantes', VarianteViewSet, basename='variante')
router.register(r'imagenes-producto', ImagenProductoViewSet, basename='imagen-producto')

urlpatterns = [
    path('', include(router.urls)),
]
