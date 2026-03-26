from django.contrib import admin
from django.db.models import Sum

from inventario.models.movimientos import (
    IngresoMercaderia, ItemIngreso, BajaInventario, TransferenciaInterna,
    AjusteComercial, SalidaProvisoria, ItemSalidaProvisoria,
    DevolucionSalidaProvisoria, ItemDevolucionProvisoria,
    LiquidacionSalidaProvisoria, ItemLiquidacionProvisoria  # <-- AGREGADOS
)


class ItemIngresoInline(admin.TabularInline):
    model = ItemIngreso
    extra = 5
    autocomplete_fields = ['variante']
    fields = (
        'variante', 'cantidad', 'lote_codigo',
        'costo_fob_unitario', 'costo_landed_unitario',
        'nuevo_precio_0_publico', 'nuevo_precio_1_estudiante',
        'nuevo_precio_2_reventa', 'nuevo_precio_3_mayorista',
        'nuevo_precio_4_intercompany'
    )
    def has_change_permission(
        self, request, obj=None): return False if obj else True

    def has_delete_permission(self, request, obj=None): return False


class ItemSalidaProvisoriaInline(admin.TabularInline):
    model = ItemSalidaProvisoria
    extra = 3
    autocomplete_fields = ['lote']
    def has_change_permission(
        self, request, obj=None): return False if obj else True

    def has_delete_permission(self, request, obj=None): return False


# --- INLINE DE DEVOLUCIÓN (CORREGIDO MODO APPEND-ONLY) ---
class ItemDevolucionProvisoriaInline(admin.TabularInline):
    model = ItemDevolucionProvisoria
    extra = 3

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "item_salida":
            if request.resolver_match.kwargs.get('object_id'):
                devolucion_id = request.resolver_match.kwargs.get('object_id')
                devolucion = DevolucionSalidaProvisoria.objects.get(
                    pk=devolucion_id)
                kwargs["queryset"] = ItemSalidaProvisoria.objects.filter(
                    salida=devolucion.salida_original)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None): return False
    def has_add_permission(self, request, obj=None): return True
    def has_delete_permission(self, request, obj=None): return False


@admin.register(IngresoMercaderia)
class IngresoMercaderiaAdmin(admin.ModelAdmin):
    list_display = ('fecha_arribo', 'descripcion',
                    'deposito', 'comprobante', 'usuario')
    list_filter = ('deposito', 'fecha_arribo')
    inlines = [ItemIngresoInline]
    date_hierarchy = 'fecha_arribo'
    readonly_fields = ('usuario',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(
        self, request, obj=None): return False if obj else True

    def has_delete_permission(self, request, obj=None): return False


@admin.register(BajaInventario)
class BajaInventarioAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'lote', 'cantidad', 'motivo', 'usuario')
    list_filter = ('motivo', 'fecha', 'usuario')
    autocomplete_fields = ['lote']
    readonly_fields = ('usuario',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(
        self, request, obj=None): return False if obj else True

    def has_delete_permission(self, request, obj=None): return False


@admin.register(TransferenciaInterna)
class TransferenciaInternaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'lote_origen',
                    'deposito_destino', 'cantidad', 'usuario')
    list_filter = ('fecha', 'deposito_destino', 'usuario')
    autocomplete_fields = ['lote_origen']
    search_fields = ('lote_origen__variante__product_code',
                     'lote_origen__lote_codigo')
    readonly_fields = ('usuario',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(
        self, request, obj=None): return False if obj else True

    def has_delete_permission(self, request, obj=None): return False


@admin.register(AjusteComercial)
class AjusteComercialAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'variante', 'motivo', 'costo_fob_anterior',
                    'nuevo_costo_fob', 'precio_0_anterior', 'nuevo_precio_0', 'usuario')
    list_filter = ('fecha', 'motivo', 'usuario')
    autocomplete_fields = ['variante']
    readonly_fields = ('costo_fob_anterior', 'precio_0_anterior', 'usuario')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(
        self, request, obj=None): return False if obj else True

    def has_delete_permission(self, request, obj=None): return False


@admin.register(SalidaProvisoria)
class SalidaProvisoriaAdmin(admin.ModelAdmin):
    list_display = ('fecha_salida', 'responsable', 'destino', 'get_total_items',
                    'get_estado_devolucion', 'fecha_esperada_devolucion')
    list_filter = ('fecha_salida', 'responsable', 'usuario')
    search_fields = ('responsable', 'destino')
    inlines = [ItemSalidaProvisoriaInline]
    readonly_fields = ('usuario',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(
        self, request, obj=None): return False if obj else True

    def has_delete_permission(self, request, obj=None): return False

    @admin.display(description='Total Prod. Llevados')
    def get_total_items(self, obj):
        total = obj.items.aggregate(Sum('cantidad'))['cantidad__sum']
        return total if total else 0

    @admin.display(description='Estado')
    def get_estado_devolucion(self, obj):
        total_salido = obj.items.aggregate(Sum('cantidad'))[
            'cantidad__sum'] or 0

        total_devuelto = 0
        for devolucion in obj.devoluciones.all():
            total_devuelto += devolucion.items.aggregate(Sum('cantidad_devuelta'))[
                'cantidad_devuelta__sum'] or 0

        total_liquidado = 0
        for liquidacion in obj.liquidaciones.all():
            total_liquidado += liquidacion.items.aggregate(Sum('cantidad_liquidada'))[
                'cantidad_liquidada__sum'] or 0

        pendientes = total_salido - (total_devuelto + total_liquidado)

        if pendientes > 0:
            return f"⚠️ Faltan {pendientes}"
        return "✅ Completo"


# --- ADMIN DE DEVOLUCIÓN (CORREGIDO MODO APPEND-ONLY) ---
@admin.register(DevolucionSalidaProvisoria)
class DevolucionSalidaProvisoriaAdmin(admin.ModelAdmin):
    list_display = ('fecha_devolucion', 'salida_original',
                    'deposito_destino', 'usuario')
    list_filter = ('fecha_devolucion', 'deposito_destino')
    autocomplete_fields = ['salida_original']
    inlines = [ItemDevolucionProvisoriaInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None): return True
    def has_delete_permission(self, request, obj=None): return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('salida_original', 'deposito_destino', 'observaciones', 'usuario')
        return ('usuario',)


# --- ADMIN DE LIQUIDACIÓN ---
class ItemLiquidacionProvisoriaInline(admin.TabularInline):
    model = ItemLiquidacionProvisoria
    extra = 3

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "item_salida":
            if request.resolver_match.kwargs.get('object_id'):
                liquidacion_id = request.resolver_match.kwargs.get('object_id')
                liquidacion = LiquidacionSalidaProvisoria.objects.get(
                    pk=liquidacion_id)
                kwargs["queryset"] = ItemSalidaProvisoria.objects.filter(
                    salida=liquidacion.salida_original)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None): return False
    def has_add_permission(self, request, obj=None): return True
    def has_delete_permission(self, request, obj=None): return False


@admin.register(LiquidacionSalidaProvisoria)
class LiquidacionSalidaProvisoriaAdmin(admin.ModelAdmin):
    list_display = ('fecha_liquidacion', 'salida_original',
                    'motivo', 'comprobante_venta', 'usuario')
    list_filter = ('fecha_liquidacion', 'motivo')
    autocomplete_fields = ['salida_original']
    inlines = [ItemLiquidacionProvisoriaInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None): return True
    def has_delete_permission(self, request, obj=None): return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('salida_original', 'motivo', 'comprobante_venta', 'observaciones', 'usuario')
        return ('usuario',)
