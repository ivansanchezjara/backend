from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from simple_history.admin import SimpleHistoryAdmin

# Importamos los modelos desde su propia app
from ..models import Categoria, Producto, Variante, ImagenProducto

# Importamos el historial de costo desde la app de inventario
from inventario.models.stock import HistorialCosto


class HistorialCostoInline(admin.TabularInline):
    model = HistorialCosto
    extra = 0
    readonly_fields = ('costo_fob', 'fecha', 'lote_referencia')
    can_delete = False
    verbose_name = "Historial de Compra (FOB)"

    # Esto es para que no se pueda añadir historial a mano desde aquí
    def has_add_permission(self, request, obj=None): return False


class ImagenProductoInline(admin.TabularInline):
    model = ImagenProducto
    extra = 1
    fields = ('imagen_asset', 'descripcion', 'orden')


class VarianteInline(admin.StackedInline):
    model = Variante
    extra = 1
    show_change_link = True
    # Bloqueamos precios para que solo se cambien vía Ajuste Comercial
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
        ('Costos y Precios (Modificar vía Ajuste Comercial)', {
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
class ProductoAdmin(SimpleHistoryAdmin):  # <--- Auditoría activada
    list_display = ('ver_foto', 'nombre_general', 'general_code',
                    'brand', 'categoria', 'featured', 'is_published', 'total_stock')
    search_fields = ('nombre_general', 'general_code', 'brand')
    list_filter = ('brand', 'categoria', 'featured', 'is_published')
    prepopulated_fields = {'slug': ('nombre_general',)}
    list_editable = ('is_published',)
    inlines = [VarianteInline]

    def ver_foto(self, obj):
        variante = obj.variants.first()
        if variante and variante.imagen_variante:
            return format_html('<img src="{}" style="width: 45px; height: 45px; object-fit: cover; border-radius: 4px;" />', variante.imagen_variante.url)
        return "No img"
    ver_foto.short_description = 'Imagen'

    def total_stock(self, obj):
        # Usamos la relación para sumar el stock de todas las variantes
        total = obj.variants.aggregate(
            total=Sum('existencias__cantidad'))['total']
        return total if total else 0
    total_stock.short_description = 'Stock Total'


@admin.register(Variante)
class VarianteAdmin(SimpleHistoryAdmin):  # <--- Auditoría activada
    list_display = ('product_code', 'nombre_variante', 'producto_padre',
                    'costo_fob', 'precio_0_publico', 'get_margen_porcentaje', 'get_stock_total')
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

    @admin.display(description='Stock Real')
    def get_stock_total(self, obj):
        # Llamamos al método que ya optimizamos
        total = obj.existencias.aggregate(Sum('cantidad'))['cantidad__sum']
        return total if total else 0

    @admin.display(description='Margen (%)')
    def get_margen_porcentaje(self, obj):
        if obj.precio_0_publico and obj.costo_fob and obj.precio_0_publico > 0:
            porcentaje = ((obj.precio_0_publico - obj.costo_fob) /
                          obj.precio_0_publico) * 100
            color = "green" if porcentaje > 30 else "orange"
            return format_html('<span style="color: {}; font-weight: bold;">%{:.1f}</span>', color, porcentaje)
        return "-"


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)
