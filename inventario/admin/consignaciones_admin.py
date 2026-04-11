# inventario/admin/consignaciones_admin.py
from django.contrib import admin
from django.db.models import Sum
from simple_history.admin import SimpleHistoryAdmin

# Importaciones de modelos (subiendo un nivel)
from ..models.consignaciones import (
    SalidaProvisoria, ItemSalidaProvisoria,
    DevolucionSalidaProvisoria, ItemDevolucionProvisoria,
    LiquidacionSalidaProvisoria, ItemLiquidacionProvisoria
)


class ItemSalidaProvisoriaInline(admin.TabularInline):
    model = ItemSalidaProvisoria
    extra = 3
    autocomplete_fields = ['lote']

    def has_change_permission(self, request, obj=None):
        return False if obj else True

    def has_delete_permission(self, request, obj=None):
        return False


class ItemDevolucionProvisoriaInline(admin.TabularInline):
    model = ItemDevolucionProvisoria
    extra = 3

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "item_salida":
            # Obtenemos el ID del objeto desde la URL del admin
            object_id = request.resolver_match.kwargs.get('object_id')
            if object_id:
                devolucion = DevolucionSalidaProvisoria.objects.get(
                    pk=object_id)
                kwargs["queryset"] = ItemSalidaProvisoria.objects.filter(
                    salida=devolucion.salida_original
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None): return False
    def has_add_permission(self, request, obj=None): return True
    def has_delete_permission(self, request, obj=None): return False


class ItemLiquidacionProvisoriaInline(admin.TabularInline):
    model = ItemLiquidacionProvisoria
    extra = 3

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "item_salida":
            object_id = request.resolver_match.kwargs.get('object_id')
            if object_id:
                liquidacion = LiquidacionSalidaProvisoria.objects.get(
                    pk=object_id)
                kwargs["queryset"] = ItemSalidaProvisoria.objects.filter(
                    salida=liquidacion.salida_original
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None): return False
    def has_add_permission(self, request, obj=None): return True
    def has_delete_permission(self, request, obj=None): return False


# --- ADMIN CLASSES ---

@admin.register(SalidaProvisoria)
class SalidaProvisoriaAdmin(SimpleHistoryAdmin):
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

    def has_change_permission(self, request, obj=None):
        return False if obj else True

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True

    @admin.display(description='Total Prod. Llevados')
    def get_total_items(self, obj):
        total = obj.items.aggregate(Sum('cantidad'))['cantidad__sum']
        return total if total else 0

    @admin.display(description='Estado')
    def get_estado_devolucion(self, obj):
        total_salido = obj.items.aggregate(Sum('cantidad'))[
            'cantidad__sum'] or 0

        # Cálculo eficiente de pendientes
        total_devuelto = 0
        for dev in obj.devoluciones.all():
            total_devuelto += dev.items.aggregate(Sum('cantidad_devuelta'))[
                'cantidad_devuelta__sum'] or 0

        total_liquidado = 0
        for liq in obj.liquidaciones.all():
            total_liquidado += liq.items.aggregate(Sum('cantidad_liquidada'))[
                'cantidad_liquidada__sum'] or 0

        pendientes = total_salido - (total_devuelto + total_liquidado)
        if pendientes > 0:
            return f"⚠️ Faltan {pendientes}"
        return "✅ Completo"


@admin.register(DevolucionSalidaProvisoria)
class DevolucionSalidaProvisoriaAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'fecha_devolucion', 'salida_original',
                    'deposito_destino', 'total_devuelto', 'usuario')
    list_filter = ('fecha_devolucion', 'deposito_destino')
    autocomplete_fields = ['salida_original']
    inlines = [ItemDevolucionProvisoriaInline]

    def total_devuelto(self, obj):
        total = obj.items.aggregate(Sum('cantidad_devuelta'))[
            'cantidad_devuelta__sum']
        return total if total else 0
    total_devuelto.short_description = 'Cant. Artículos'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return False if obj else True

    def has_view_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('salida_original', 'deposito_destino', 'observaciones', 'usuario')
        return ('usuario',)


@admin.register(LiquidacionSalidaProvisoria)
class LiquidacionSalidaProvisoriaAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'fecha_liquidacion', 'salida_original',
                    'motivo', 'comprobante_venta', 'total_liquidado', 'usuario')
    list_filter = ('fecha_liquidacion', 'motivo')
    autocomplete_fields = ['salida_original']
    inlines = [ItemLiquidacionProvisoriaInline]

    def total_liquidado(self, obj):
        total = obj.items.aggregate(Sum('cantidad_liquidada'))[
            'cantidad_liquidada__sum']
        return total if total else 0
    total_liquidado.short_description = 'Cant. Artículos'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return False if obj else True

    def has_view_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('salida_original', 'motivo', 'comprobante_venta', 'observaciones', 'usuario')
        return ('usuario',)
