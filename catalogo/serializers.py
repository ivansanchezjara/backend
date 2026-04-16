from rest_framework import serializers
from django.utils.text import slugify
from .models import Producto, Variante, Categoria, ImagenProducto


class ImagenProductoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ImagenProducto
        fields = ['id', 'url', 'imagen_asset',
                  'descripcion', 'orden', 'variante']
        extra_kwargs = {
            'imagen_asset': {'write_only': True},
            'variante': {'write_only': True}
        }

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
    stock_vencido = serializers.IntegerField(
        source='stock_vencido_calculado', read_only=True, default=0)
    stock_por_deposito = serializers.SerializerMethodField()
    stock_reservado = serializers.SerializerMethodField()
    stock_en_consignacion = serializers.SerializerMethodField()
    vencimiento = serializers.SerializerMethodField()
    imagenes = ImagenProductoSerializer(many=True, read_only=True)
    imagen_url = serializers.SerializerMethodField()
    producto_padre_nombre = serializers.ReadOnlyField(source='producto_padre.nombre_general')

    class Meta:
        model = Variante
        fields = [
            'id', 'product_code', 'nombre_variante', 'sub_slug',
            'costo_fob', 'costo_landed',
            'precio_0_publico', 'precio_1_estudiante', 'precio_2_reventa', 
            'precio_3_mayorista', 'precio_4_intercompany',
            'precio_oferta', 'stock', 'stock_vencido', 'stock_reservado', 'stock_en_consignacion',
            'stock_por_deposito', 'vencimiento', 'imagenes', 'imagen_url', 
            'imagen_variante', 'producto_padre_nombre', 'activo'
        ]

    def get_stock_por_deposito(self, obj):
        from inventario.models import StockLote
        from django.db.models import Sum
        # Agrupamos el stock por el nombre del depósito
        stocks = StockLote.objects.filter(variante=obj).values(
            'deposito__nombre').annotate(total=Sum('cantidad'))
        return {s['deposito__nombre']: s['total'] for s in stocks if s['total'] > 0}

    def get_stock_reservado(self, obj):
        from inventario.models.reservas import ReservaStock
        from django.db.models import Sum
        # Sumamos reservas activas para esta variante (a través de sus lotes)
        total = ReservaStock.objects.filter(
            lote__variante=obj, 
            activo=True
        ).aggregate(Sum('cantidad'))['cantidad__sum'] or 0
        return total

    def get_stock_en_consignacion(self, obj):
        from inventario.models.consignaciones import ItemSalidaProvisoria
        from django.db.models import Sum
        # Sumamos ítems de salidas APROBADAS que no han sido devueltos ni liquidados
        items = ItemSalidaProvisoria.objects.filter(
            lote__variante=obj, 
            salida__estado='APROBADO'
        )
        
        total_enviado = items.aggregate(Sum('cantidad'))['cantidad__sum'] or 0
        total_devuelto = 0
        total_liquidado = 0
        
        # Obtenemos devoluciones y liquidaciones relacionadas
        # Nota: Esto podría optimizarse con agregaciones más complejas si hay mucho volumen
        for item in items:
            total_devuelto += item.devoluciones_item.aggregate(Sum('cantidad_devuelta'))['cantidad_devuelta__sum'] or 0
            total_liquidado += item.liquidaciones_item.aggregate(Sum('cantidad_liquidada'))['cantidad_liquidada__sum'] or 0
            
        return total_enviado - (total_devuelto + total_liquidado)

    def get_vencimiento(self, obj):
        from inventario.models import StockLote
        # Traemos la fecha de vencimiento más próxima de los lotes con stock
        lote = StockLote.objects.filter(variante=obj, cantidad__gt=0, vencimiento__isnull=False).order_by('vencimiento').first()
        return lote.vencimiento if lote else None

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
        fields = ['id', 'producto_padre', 'nombre_variante',
                  'product_code', 'sub_slug', 'imagen_variante', 'activo']
        extra_kwargs = {
            'imagen_variante': {'required': False, 'allow_null': True}
        }

    def validate(self, attrs):
        producto_padre = attrs.get('producto_padre') or (self.instance.producto_padre if self.instance else None)
        
        # Auto-generar sub_slug desde nombre_variante si no se provee
        if not attrs.get('sub_slug') and attrs.get('nombre_variante'):
            attrs['sub_slug'] = slugify(attrs['nombre_variante'])
        
        sub_slug = attrs.get('sub_slug')
        
        # Validación de unicidad manual para dar un mejor error
        if producto_padre and sub_slug:
            qs = Variante.objects.filter(producto_padre=producto_padre, sub_slug=sub_slug)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise serializers.ValidationError({
                    "sub_slug": f"Ya existe una variante con el slug '{sub_slug}' para este producto. Elegí otro nombre o slug."
                })
                
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
            'imagen_principal', 'featured', 'tags', 'is_published', 'activo', 'atributos'
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
            'imagen_principal', 'activo', 'atributos'
        ]
        extra_kwargs = {
            'slug': {'required': False},
            'sub_category': {'required': False, 'allow_blank': True},
            'professional_area': {'required': False, 'allow_blank': True},
            'description': {'required': False, 'allow_blank': True},
            'long_description': {'required': False, 'allow_blank': True},
            'imagen_principal': {'required': False, 'allow_null': True},
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
