from rest_framework import serializers
from django.utils.text import slugify
from .models import Producto, Variante, Categoria, ImagenProducto


class ImagenProductoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ImagenProducto
        fields = ['id', 'url', 'descripcion', 'orden']

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.imagen_asset:
            url = obj.imagen_asset.url
            return request.build_absolute_uri(url) if request else url
        return None


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'


class VarianteSerializer(serializers.ModelSerializer):
    """Serializer de LECTURA para variantes (incluye stock anotado)."""
    stock = serializers.IntegerField(
        source='stock_total_calculado', read_only=True, default=0)
    imagenes = ImagenProductoSerializer(many=True, read_only=True)
    imagen_url = serializers.SerializerMethodField()

    class Meta:
        model = Variante
        fields = [
            'id', 'product_code', 'nombre_variante', 'sub_slug',
            'precio_0_publico', 'precio_oferta', 'stock', 'imagenes', 'imagen_url',
        ]

    def get_imagen_url(self, obj):
        request = self.context.get('request')
        if obj.imagen_variante:
            url = obj.imagen_variante.url
            return request.build_absolute_uri(url) if request else url
        return None


class VarianteWriteSerializer(serializers.ModelSerializer):
    """
    Serializer de ESCRITURA para variantes.
    Solo campos de identidad — los precios y costos se gestionan
    exclusivamente desde Inventario (movimientos de ingreso).
    """
    class Meta:
        model = Variante
        fields = ['id', 'producto_padre', 'nombre_variante', 'product_code', 'sub_slug']

    def validate(self, attrs):
        # Auto-generar sub_slug desde nombre_variante si no se provee
        if not attrs.get('sub_slug') and attrs.get('nombre_variante'):
            attrs['sub_slug'] = slugify(attrs['nombre_variante'])
        return attrs


class ProductoSerializer(serializers.ModelSerializer):
    """Serializer de LECTURA completo para productos."""
    categoria = CategoriaSerializer(read_only=True)
    variants = VarianteSerializer(many=True, read_only=True)
    imagen_principal_url = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre_general', 'general_code', 'brand', 'slug',
            'description', 'long_description', 'categoria', 'sub_category',
            'professional_area', 'variants', 'imagen_principal_url',
            'featured', 'tags', 'is_published',
        ]

    def get_imagen_principal_url(self, obj):
        request = self.context.get('request')
        if obj.imagen_principal:
            url = obj.imagen_principal.url
            return request.build_absolute_uri(url) if request else url
        return None


class ProductoWriteSerializer(serializers.ModelSerializer):
    """
    Serializer de ESCRITURA para productos.
    Acepta categoria_id como FK en lugar del objeto anidado,
    y auto-genera el slug si no se provee.
    """
    categoria_id = serializers.PrimaryKeyRelatedField(
        queryset=Categoria.objects.all(),
        source='categoria',
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Producto
        fields = [
            'nombre_general', 'general_code', 'brand', 'slug',
            'categoria_id', 'sub_category', 'professional_area',
            'description', 'long_description', 'featured', 'tags', 'is_published',
        ]
        extra_kwargs = {
            'slug': {'required': False},
            'sub_category': {'required': False, 'allow_blank': True},
            'professional_area': {'required': False, 'allow_blank': True},
            'description': {'required': False, 'allow_blank': True},
            'long_description': {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        # Solo auto-genera slug al CREAR (no al editar)
        if not self.instance and not attrs.get('slug'):
            base_slug = slugify(attrs.get('nombre_general', ''))
            slug = base_slug
            counter = 1
            while Producto.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            attrs['slug'] = slug
        return attrs
