from django.contrib import admin
from inventario.models.stock import Deposito, StockLote


@admin.register(StockLote)
class StockLoteAdmin(admin.ModelAdmin):
    list_display = ('variante', 'deposito', 'lote_codigo',
                    'cantidad', 'costo_compra_lote', 'fecha_entrada')
    search_fields = ('variante__product_code', 'lote_codigo')
    list_filter = ('deposito',)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


admin.site.register(Deposito)
