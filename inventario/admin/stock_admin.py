from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from inventario.models.stock import Deposito, StockLote, HistorialCosto


@admin.register(StockLote)
class StockLoteAdmin(SimpleHistoryAdmin):
    list_display = ('variante', 'deposito', 'lote_codigo',
                    'cantidad_formateada', 'costo_compra_lote', 'fecha_entrada')

    search_fields = ('variante__product_code', 'lote_codigo',
                     'variante__producto__nombre_general')
    list_filter = ('deposito', 'fecha_entrada')

    # Bloqueo total de edición manual (Solo se mueve por Movimientos)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    # NUEVO: Permitimos "Ver" para que puedan entrar y hacer clic en el botón "Historial"
    def has_view_permission(self, request, obj=None): return True

    @admin.display(description='Cantidad')
    def cantidad_formateada(self, obj):
        return format_html('<b>{}</b>', obj.cantidad)


@admin.register(HistorialCosto)
class HistorialCostoAdmin(admin.ModelAdmin):
    list_display = ('variante', 'costo_fob', 'fecha', 'lote_referencia')
    list_filter = ('fecha', 'variante__producto_padre__brand')

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_view_permission(self, request, obj=None): return True


@admin.register(Deposito)
class DepositoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ubicacion')
