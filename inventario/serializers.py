from rest_framework import serializers
from .models.catalogo import Producto, Variante, Categoria, ImagenProducto
from .models.stock import Deposito, StockLote, HistorialCosto
from .models.movimientos import SalidaProvisoria, ItemSalidaProvisoria

# --- 1. AUXILIARES (IMÁGENES) ---


class ImagenProductoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ImagenProducto
        fields = ['id', 'url', 'descripcion', 'orden']

    def get_url(self, obj):
        if obj.imagen_asset:
            return obj.imagen_asset.url
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
        if obj.imagen_variante:
            return obj.imagen_variante.url
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

    # CAMBIÁ ESTE NOMBRE: de get_imagen_url a get_imagen_principal_url
    def get_imagen_principal_url(self, obj):
        if hasattr(obj, 'imagen_principal') and obj.imagen_principal:
            return obj.imagen_principal.url
        return None

# --- 3. STOCK Y DEPÓSITO ---


class DepositoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deposito
        fields = '__all__'


class StockLoteSerializer(serializers.ModelSerializer):
    deposito_nombre = serializers.ReadOnlyField(source='deposito.nombre')
    producto = serializers.ReadOnlyField(
        source='variante.producto_padre.nombre_general')

    class Meta:
        model = StockLote
        fields = ['id', 'producto', 'lote_codigo',
                  'cantidad', 'vencimiento', 'deposito_nombre']

# --- 4. MOVIMIENTOS (Para tu panel de control en Next.js) ---


class ItemSalidaSerializer(serializers.ModelSerializer):
    producto = serializers.ReadOnlyField(
        source='lote.variante.producto_padre.nombre_general')
    codigo = serializers.ReadOnlyField(source='lote.variante.product_code')

    class Meta:
        model = ItemSalidaProvisoria
        fields = ['id', 'producto', 'codigo', 'cantidad']


class SalidaProvisoriaSerializer(serializers.ModelSerializer):
    items = ItemSalidaSerializer(many=True, read_only=True)
    estado = serializers.SerializerMethodField()

    class Meta:
        model = SalidaProvisoria
        fields = ['id', 'fecha_salida', 'responsable',
                  'destino', 'items', 'estado']

    def get_estado(self, obj):
        # Reutilizamos la lógica que ya escribimos en el Admin
        total_salido = obj.items.aggregate(Sum('cantidad'))[
            'cantidad__sum'] or 0
        # ... (podríamos replicar toda la lógica aquí si quisiéramos mostrarla en la web)
        return "Consultar en Admin"
