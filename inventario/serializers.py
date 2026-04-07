from rest_framework import serializers
from django.db.models import Sum
from .models.catalogo import Producto, Variante, Categoria, ImagenProducto
from .models.stock import Deposito, StockLote
from .models.movimientos import SalidaProvisoria, ItemSalidaProvisoria

# --- 1. AUXILIARES (IMÁGENES) ---


class ImagenProductoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ImagenProducto
        fields = ['id', 'url', 'descripcion', 'orden']

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.imagen_asset:
            url = obj.imagen_asset.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None

# --- 2. CATÁLOGO ---


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'


class VarianteSerializer(serializers.ModelSerializer):
    stock = serializers.ReadOnlyField(source='stock_total')
    imagenes = ImagenProductoSerializer(many=True, read_only=True)
    imagen_url = serializers.SerializerMethodField()

    class Meta:
        model = Variante
        fields = [
            'id', 'product_code', 'nombre_variante', 'sub_slug',
            'precio_0_publico', 'precio_oferta', 'stock', 'imagenes', 'imagen_url'
        ]

    def get_imagen_url(self, obj):
        request = self.context.get('request')
        if obj.imagen_variante:
            url = obj.imagen_variante.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None


class ProductoSerializer(serializers.ModelSerializer):
    categoria = CategoriaSerializer(read_only=True)
    variants = VarianteSerializer(many=True, read_only=True)
    imagen_principal_url = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre_general', 'general_code', 'brand', 'slug',
            'description', 'long_description', 'categoria', 'variants',
            'imagen_principal_url', 'featured', 'tags'
        ]

    def get_imagen_principal_url(self, obj):
        request = self.context.get('request')
        if obj.imagen_principal:
            url = obj.imagen_principal.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None

# --- 3. MOVIMIENTOS (ORGANIZADO DE HIJO A PADRE) ---

# Primero el ítem (El hijo)


class ItemSalidaSerializer(serializers.ModelSerializer):
    producto = serializers.ReadOnlyField(
        source='lote.variante.producto_padre.nombre_general')
    codigo = serializers.ReadOnlyField(source='lote.variante.product_code')

    class Meta:
        model = ItemSalidaProvisoria
        fields = ['id', 'producto', 'codigo', 'cantidad']

# Luego la salida (El padre que usa al hijo)


class SalidaProvisoriaSerializer(serializers.ModelSerializer):
    items = ItemSalidaSerializer(many=True, read_only=True)
    resumen_stock = serializers.SerializerMethodField()

    class Meta:
        model = SalidaProvisoria
        fields = [
            'id', 'fecha_salida', 'responsable',
            'destino', 'items', 'resumen_stock'
        ]

    def get_resumen_stock(self, obj):
        total_salido = obj.items.aggregate(total=Sum('cantidad'))['total'] or 0
        total_devuelto = obj.devoluciones.aggregate(
            total=Sum('items__cantidad_devuelta'))['total'] or 0
        total_liquidado = obj.liquidaciones.aggregate(
            total=Sum('items__cantidad_liquidada'))['total'] or 0

        pendientes = total_salido - (total_devuelto + total_liquidado)

        return {
            "enviado": total_salido,
            "devuelto": total_devuelto,
            "liquidado": total_liquidado,
            "pendiente": pendientes,
            "completado": pendientes <= 0
        }
