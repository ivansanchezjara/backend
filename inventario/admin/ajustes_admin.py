# inventario/admin/ajustes_admin.py
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

# Importaciones subiendo un nivel
from ..models.bajas import BajaInventario
from ..models.transferencias import TransferenciaInterna
from ..models.ajustes import AjusteComercial


@admin.register(BajaInventario)
class BajaInventarioAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'fecha', 'lote', 'cantidad',
                    'motivo', 'estado', 'procesado', 'usuario')
    list_filter = ('estado', 'procesado', 'motivo', 'fecha', 'usuario')
    autocomplete_fields = ['lote']
    readonly_fields = ('usuario', 'procesado')

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is None:
            if 'estado' not in fields:
                fields.append('estado')
            return tuple(fields)

        if obj.estado == 'APROBADO':
            return [f.name for f in self.model._meta.fields]

        if not request.user.is_superuser:
            if 'estado' not in fields:
                fields.append('estado')
        return tuple(fields)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if obj and obj.estado == 'APROBADO':
            return False
        return True

    def has_view_permission(self, request, obj=None): return True

    def has_delete_permission(self, request, obj=None):
        if obj and obj.estado == 'BORRADOR' and request.user.is_superuser:
            return True
        return False


@admin.register(TransferenciaInterna)
class TransferenciaInternaAdmin(SimpleHistoryAdmin):
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

    def has_change_permission(self, request, obj=None):
        return False if obj else True

    def has_view_permission(self, request, obj=None): return True

    def has_delete_permission(self, request, obj=None): return False


@admin.register(AjusteComercial)
class AjusteComercialAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'variante', 'fecha', 'motivo',
                    'estado', 'procesado', 'nuevo_precio_0', 'usuario')
    list_filter = ('estado', 'procesado', 'motivo', 'fecha')
    search_fields = ('variante__product_code',
                     'variante__producto__nombre_general', 'observaciones')

    fieldsets = (
        ('Información General', {
            'fields': ('variante', 'motivo', 'estado', 'procesado', 'usuario', 'observaciones')
        }),
        ('Ajuste de Costos', {
            'fields': (('nuevo_costo_fob', 'nuevo_costo_landed'),),
            'description': 'Deja en blanco si no hay cambios en los costos.'
        }),
        ('Ajuste de Precios', {
            'fields': ('nuevo_precio_0', 'nuevo_precio_1', 'nuevo_precio_2', 'nuevo_precio_3', 'nuevo_precio_4'),
        }),
        ('Auditoría Histórica', {
            'fields': (('costo_fob_ant', 'precio_0_ant'),),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('usuario', 'procesado', 'costo_fob_ant', 'precio_0_ant')

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ('estado', 'procesado', 'costo_fob_ant', 'precio_0_ant')
        if obj.estado == 'APROBADO':
            return [f.name for f in self.model._meta.fields]
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly.append('estado')
        return tuple(readonly)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.usuario = request.user
            obj.costo_fob_ant = obj.variante.costo_fob
            obj.precio_0_ant = obj.variante.precio_0_publico
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if obj and obj.estado == 'APROBADO':
            return False
        return True

    def has_view_permission(self, request, obj=None): return True

    def has_delete_permission(self, request, obj=None):
        if obj and obj.estado == 'APROBADO':
            return False
        return request.user.is_superuser
