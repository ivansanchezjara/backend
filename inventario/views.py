from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
# ACTUALIZADO: Importamos también Categoria
from .models.catalogo import Producto, Categoria
# ACTUALIZADO: Importamos también CategoriaSerializer
from .serializers import ProductoSerializer, CategoriaSerializer


class ProductoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Esta vista devuelve la lista de todos los productos 
    con sus variantes y categorías en formato JSON.
    """
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated]


# --- NUEVO: VISTA PARA LAS CATEGORÍAS ---
class CategoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAuthenticated]
