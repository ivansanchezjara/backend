from rest_framework import serializers
from django.db.models import Sum
from .models.consignaciones import SalidaProvisoria, ItemSalidaProvisoria


class ItemSalidaSerializer(serializers.ModelSerializer):
    producto = serializers.ReadOnlyField(
        source='lote.variante.producto_padre.nombre_general')
    codigo = serializers.ReadOnlyField(source='lote.variante.product_code')

    class Meta:
        model = ItemSalidaProvisoria
        fields = ['id', 'producto', 'codigo', 'cantidad']


class SalidaProvisoriaSerializer(serializers.ModelSerializer):
    items = ItemSalidaSerializer(many=True, read_only=True)
    resumen_stock = serializers.SerializerMethodField()

    class Meta:
        model = SalidaProvisoria
        fields = [
            'id', 'fecha_salida', 'responsable',
            'destino', 'items', 'resumen_stock'
        ]

    def get_resumen_stock(self, obj):
        total_salido = obj.items.aggregate(total=Sum('cantidad'))['total'] or 0
        total_devuelto = obj.devoluciones.aggregate(
            total=Sum('items__cantidad_devuelta'))['total'] or 0
        total_liquidado = obj.liquidaciones.aggregate(
            total=Sum('items__cantidad_liquidada'))['total'] or 0

        pendientes = total_salido - (total_devuelto + total_liquidado)

        return {
            "enviado": total_salido,
            "devuelto": total_devuelto,
            "liquidado": total_liquidado,
            "pendiente": pendientes,
            "completado": pendientes <= 0
        }
