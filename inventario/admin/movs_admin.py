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
    # 🚀 Añadimos 'estado' a la vista principal
    list_display = ('id', 'fecha_arribo', 'descripcion',
                    'deposito', 'estado', 'procesado', 'usuario')
    list_filter = ('estado', 'procesado', 'deposito', 'fecha_arribo')
    inlines = [ItemIngresoInline]
    date_hierarchy = 'fecha_arribo'

    # El usuario se autocompleta y no se toca
    readonly_fields = ('usuario', 'procesado')

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))

        # 1. Si el ingreso ya está APROBADO, bloqueamos TODO para todos (integridad de datos)
        if obj and obj.estado == 'APROBADO':
            return [f.name for f in self.model._meta.fields]

        # 2. Si es BORRADOR y el usuario NO es superusuario (tu papá), bloqueamos el campo 'estado'
        if obj and not request.user.is_superuser:
            fields.append('estado')

        return tuple(fields)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        # Si el objeto ya está aprobado, nadie lo toca (solo lectura final)
        if obj and obj.estado == 'APROBADO':
            return False
        # Si es borrador, permitimos cambios (según los readonly_fields definidos arriba)
        return True

    def has_delete_permission(self, request, obj=None):
        # Solo permitimos borrar si es un Borrador y el usuario es admin
        if obj and obj.estado == 'BORRADOR' and request.user.is_superuser:
            return True
        return False


@admin.register(BajaInventario)
class BajaInventarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'lote', 'cantidad',
                    'motivo', 'estado', 'procesado', 'usuario')
    list_filter = ('estado', 'procesado', 'motivo', 'fecha', 'usuario')
    autocomplete_fields = ['lote']
    readonly_fields = ('usuario', 'procesado')

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))

        # 1. Si la baja ya fue APROBADA, bloqueamos todo. Es un registro histórico inmutable.
        if obj and obj.estado == 'APROBADO':
            return [f.name for f in self.model._meta.fields]

        # 2. Si es BORRADOR y no es superusuario (tu papá), no puede cambiar el estado.
        if obj and not request.user.is_superuser:
            fields.append('estado')

        return tuple(fields)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        # Permitimos editar solo si no ha sido aprobada aún
        if obj and obj.estado == 'APROBADO':
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        # Solo el admin puede borrar borradores si se equivocaron feo
        if obj and obj.estado == 'BORRADOR' and request.user.is_superuser:
            return True
        return False


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
    # 1. Configuración de la lista principal
    list_display = ('id', 'variante', 'fecha', 'motivo',
                    'estado', 'procesado', 'nuevo_precio_0', 'usuario')
    list_filter = ('estado', 'procesado', 'motivo', 'fecha')
    search_fields = ('variante__product_code',
                     'variante__producto__nombre_general', 'observaciones')

    # 2. Organización del formulario por secciones
    fieldsets = (
        ('Información General', {
            'fields': ('variante', 'motivo', 'estado', 'procesado', 'usuario', 'observaciones')
        }),
        ('Ajuste de Costos', {
            'fields': (('nuevo_costo_fob', 'nuevo_costo_landed'),),
            'description': 'Deja en blanco si no hay cambios en los costos.'
        }),
        ('Ajuste de Precios', {
            'fields': (
                'nuevo_precio_0',
                'nuevo_precio_1',
                'nuevo_precio_2',
                'nuevo_precio_3',
                'nuevo_precio_4'
            ),
        }),
        ('Auditoría Histórica', {
            'fields': (('costo_fob_ant', 'precio_0_ant'),),
            'classes': ('collapse',),  # Esta sección sale cerrada por defecto
        }),
    )

    readonly_fields = ('usuario', 'procesado', 'costo_fob_ant', 'precio_0_ant')

    def get_readonly_fields(self, request, obj=None):
        # Si ya está APROBADO, bloqueamos absolutamente todo (Inmutable)
        if obj and obj.estado == 'APROBADO':
            return [f.name for f in self.model._meta.fields]

        # Si es BORRADOR, solo tu papá (superuser) puede ver el campo 'estado' para aprobar
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and not request.user.is_superuser:
            readonly.append('estado')
        return tuple(readonly)

    def save_model(self, request, obj, form, change):
        # Al guardar el registro por primera vez, capturamos los precios actuales
        # para que tu papá vea el "antes" y el "después" en la auditoría.
        if not change:
            obj.usuario = request.user
            obj.costo_fob_ant = obj.variante.costo_fob
            obj.precio_0_ant = obj.variante.precio_0_publico
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        # Si ya está aprobado, nadie lo toca. Si es borrador, se puede editar.
        if obj and obj.estado == 'APROBADO':
            return False
        return True


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
