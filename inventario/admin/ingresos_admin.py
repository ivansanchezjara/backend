from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, F
from simple_history.admin import SimpleHistoryAdmin
from ..models.ingresos import IngresoMercaderia, ItemIngreso


class ItemIngresoInline(admin.TabularInline):
    model = ItemIngreso
    extra = 1
    autocomplete_fields = ['variante']
    fields = (
        'variante', 'cantidad', 'lote_codigo',
        'costo_fob_unitario', 'costo_landed_unitario',
        'nuevo_precio_0_publico', 'nuevo_precio_1_estudiante',
        'nuevo_precio_2_reventa', 'nuevo_precio_3_mayorista',
        'nuevo_precio_4_intercompany'
    )

    def has_change_permission(self, request, obj=None):
        return False if obj else True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IngresoMercaderia)
class IngresoMercaderiaAdmin(SimpleHistoryAdmin):  # <--- HERENCIA CAMBIADA
    list_display = ('id', 'fecha_arribo', 'descripcion', 'deposito',
                    'ver_estado', 'valor_fob_total', 'procesado', 'usuario')
    list_filter = ('estado', 'procesado', 'deposito', 'fecha_arribo')
    inlines = [ItemIngresoInline]
    date_hierarchy = 'fecha_arribo'
    readonly_fields = ('usuario', 'procesado')

    # --- Mejoras de Visualización ---
    def ver_estado(self, obj):
        colors = {
            'BORRADOR': '#6c757d',
            'APROBADO': '#28a745',
            'RECHAZADO': '#dc3545',
        }
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 10px; font-weight: bold;">{}</span>',
            colors.get(obj.estado, '#000'), obj.get_estado_display()
        )
    ver_estado.short_description = 'Estado'

    def valor_fob_total(self, obj):
        total = obj.items.aggregate(
            total=Sum(F('cantidad') * F('costo_fob_unitario'))
        )['total'] or 0
        return f"USD {total:,.2f}"
    valor_fob_total.short_description = 'Total FOB'

    # --- Lógica de Permisos ---
    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is None:
            if 'estado' not in fields:
                fields.append('estado')
            return tuple(fields)

        if obj.estado == 'APROBADO':
            # Bloqueamos todo pero permitimos ver para el historial
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

    def has_view_permission(self, request, obj=None):  # <--- PARA VER HISTORIAL
        return True

    def has_delete_permission(self, request, obj=None):
        if obj and obj.estado == 'BORRADOR' and request.user.is_superuser:
            return True
        return False

    def get_inline_instances(self, request, obj=None):
        inline_instances = super().get_inline_instances(request, obj)
        if obj and obj.estado == 'APROBADO':
            for inline in inline_instances:
                inline.can_delete = False
                inline.max_num = 0
        return inline_instances
