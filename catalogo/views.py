from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Prefetch
from django.db.models.functions import Coalesce

from .models import Producto, Categoria, Variante, ImagenProducto
from .serializers import (
    ProductoSerializer, ProductoWriteSerializer,
    CategoriaSerializer, VarianteSerializer, VarianteWriteSerializer,
    ImagenProductoSerializer,
)


def _variantes_con_stock():
    """Queryset de variantes anotado con stock total. Reutilizable."""
    return Variante.objects.filter(activo=True).annotate(
        stock_total_calculado=Coalesce(Sum('existencias__cantidad'), 0),
        stock_vencido_calculado=Coalesce(Sum('existencias__cantidad_vencida'), 0)
    ).prefetch_related('imagenes')


class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAuthenticated]


class ProductoViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para productos del catálogo.
    - Lectura: usa ProductoSerializer (incluye variantes anidadas con stock)
    - Escritura: usa ProductoWriteSerializer (acepta categoria_id, auto-slug)
    - Lookup por slug en lugar de pk
    """
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        return Producto.objects.filter(activo=True).select_related('categoria').prefetch_related(
            Prefetch('variants', queryset=_variantes_con_stock())
        )

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductoWriteSerializer
        return ProductoSerializer

    def create(self, request, *args, **kwargs):
        write_s = ProductoWriteSerializer(
            data=request.data, context=self.get_serializer_context())
        write_s.is_valid(raise_exception=True)
        instance = write_s.save()
        # Devolvemos el serializer de lectura completo
        read_s = ProductoSerializer(
            self.get_queryset().get(pk=instance.pk),
            context=self.get_serializer_context()
        )
        return Response(read_s.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        write_s = ProductoWriteSerializer(
            instance, data=request.data, partial=partial,
            context=self.get_serializer_context()
        )
        write_s.is_valid(raise_exception=True)
        write_s.save()
        # Re-fetch con anotaciones completas y devolvemos lectura completa
        read_s = ProductoSerializer(
            self.get_queryset().get(pk=instance.pk),
            context=self.get_serializer_context()
        )
        return Response(read_s.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # En lugar de borrar, lo desactivamos
        instance.activo = False
        instance.save()
        # Retornamos un 204 (No Content) que es el estándar de éxito para un DELETE
        return Response(status=status.HTTP_204_NO_CONTENT)


class VarianteViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar variantes individualmente.
    Solo expone campos de identidad en escritura (nombre, código, sub-slug).
    Los precios/costos solo se modifican a través de movimientos de inventario.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _variantes_con_stock()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return VarianteSerializer
        return VarianteWriteSerializer

    def create(self, request, *args, **kwargs):
        write_s = VarianteWriteSerializer(
            data=request.data, context=self.get_serializer_context())
        write_s.is_valid(raise_exception=True)
        instance = write_s.save()
        read_s = VarianteSerializer(
            _variantes_con_stock().get(pk=instance.pk),
            context=self.get_serializer_context()
        )
        return Response(read_s.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        write_s = VarianteWriteSerializer(
            instance, data=request.data, partial=partial,
            context=self.get_serializer_context()
        )
        write_s.is_valid(raise_exception=True)
        write_s.save()
        read_s = VarianteSerializer(
            _variantes_con_stock().get(pk=instance.pk),
            context=self.get_serializer_context()
        )
        return Response(read_s.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Validación: No se puede desactivar si hay stock físico
        stock = getattr(instance, 'stock_total_calculado', 0)
        if stock > 0:
            return Response(
                {"detail": f"No se puede desactivar la variante '{instance.nombre_variante}' porque aún tiene {stock} unidades en stock. Primero debe realizar un ajuste de baja o transferencia."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # En lugar de borrar físicamente, realizamos un borrado lógico (desactivar)
        instance.activo = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ImagenProductoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar la galería de imágenes de las variantes.
    """
    queryset = ImagenProducto.objects.all()
    serializer_class = ImagenProductoSerializer
    permission_classes = [IsAuthenticated]
