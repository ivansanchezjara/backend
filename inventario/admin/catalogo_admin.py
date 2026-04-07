from django.utils.html import format_html
from django.contrib import admin
from inventario.models.catalogo import Categoria, Producto, Variante, ImagenProducto
from inventario.models.stock import HistorialCosto


class HistorialCostoInline(admin.TabularInline):
    model = HistorialCosto
    extra = 0
    readonly_fields = ('costo_fob', 'fecha', 'lote_referencia')
    can_delete = False
    verbose_name = "Historial de Costo"


class ImagenProductoInline(admin.TabularInline):
    model = ImagenProducto
    extra = 1
    fields = ('imagen_asset', 'descripcion', 'orden')


class VarianteInline(admin.StackedInline):
    model = Variante
    extra = 1
    show_change_link = True
    readonly_fields = (
        'costo_fob', 'costo_landed',
        'precio_0_publico', 'precio_1_estudiante',
        'precio_2_reventa', 'precio_3_mayorista',
        'precio_4_intercompany', 'precio_oferta', 'oferta_vence'
    )
    fieldsets = (
        (None, {
            'fields': (('nombre_variante', 'product_code', 'sub_slug'), 'imagen_variante')
        }),
        ('Costos y Precios (SOLO LECTURA - Modificar vía Ajuste Comercial)', {
            'fields': (
                ('costo_fob', 'costo_landed'),
                ('precio_0_publico', 'precio_1_estudiante'),
                ('precio_2_reventa', 'precio_3_mayorista'),
                ('precio_4_intercompany'),
                ('precio_oferta', 'oferta_vence'),
            ),
        }),
    )
    prepopulated_fields = {'sub_slug': ('nombre_variante',)}


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):

    list_display = ('ver_foto', 'nombre_general', 'general_code',
                    'brand', 'categoria', 'featured', 'total_stock')
    search_fields = ('nombre_general', 'general_code', 'brand')
    list_filter = ('brand', 'categoria', 'featured')
    prepopulated_fields = {'slug': ('nombre_general',)}
    inlines = [VarianteInline]

    # 1. Función para mostrar la miniatura de la imagen
    def ver_foto(self, obj):
        variante = obj.variants.first()
        if variante:
            if variante.imagen_variante:
                return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />', variante.imagen_variante.url)

            primera_img = variante.imagenes.first()
            if primera_img and primera_img.imagen_asset:
                return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />', primera_img.imagen_asset.url)
        return "No img"

    ver_foto.short_description = 'Imagen'

    # 2. Función opcional para ver el stock total acumulado de todas sus variantes
    def total_stock(self, obj):
        from django.db.models import Sum
        total = obj.variants.aggregate(
            total=Sum('existencias__cantidad'))['total']
        return total if total else 0

    total_stock.short_description = 'Stock Total'


@admin.register(Variante)
class VarianteAdmin(admin.ModelAdmin):
    list_display = ('product_code', 'nombre_variante', 'producto_padre',
                    'costo_fob', 'precio_0_publico', 'get_margen', 'get_stock_total')
    search_fields = ('product_code', 'nombre_variante',
                     'producto_padre__nombre_general')
    list_filter = ('producto_padre__brand', 'producto_padre__categoria')
    prepopulated_fields = {'sub_slug': ('nombre_variante',)}
    readonly_fields = (
        'costo_fob', 'costo_landed',
        'precio_0_publico', 'precio_1_estudiante',
        'precio_2_reventa', 'precio_3_mayorista',
        'precio_4_intercompany', 'precio_oferta', 'oferta_vence'
    )
    inlines = [ImagenProductoInline, HistorialCostoInline]

    @admin.display(description='Margen Est. ($)')
    def get_margen(self, obj):
        if obj.precio_0_publico and obj.costo_fob:
            return obj.precio_0_publico - obj.costo_fob
        return "-"

    @admin.display(description='Stock Total')
    def get_stock_total(self, obj):
        return obj.stock_total

    @admin.display(description='Margen (%)')
    def get_margen_porcentaje(self, obj):
        if obj.precio_0_publico and obj.costo_fob and obj.precio_0_publico > 0:
            porcentaje = ((obj.precio_0_publico - obj.costo_fob) /
                          obj.precio_0_publico) * 100
            # Ejemplo: aviso si el margen es bajo
            color = "green" if porcentaje > 30 else "orange"
            return format_html('<span style="color: {};">%{:.1f}</span>', color, porcentaje)
        return "-"


admin.site.register(Categoria)
