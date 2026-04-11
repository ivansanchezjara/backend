from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch

# Importamos los modelos y serializers propios del inventario
from .models.consignaciones import SalidaProvisoria
from .serializers import SalidaProvisoriaSerializer


class SalidaProvisoriaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Vista para listar las Salidas Provisorias.
    Solo lectura por ahora, para exponer los datos al frontend.
    """
    serializer_class = SalidaProvisoriaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Usamos prefetch_related para hacer "viajes profundos" en 1 sola consulta
        # Traemos los items, y de los items viajamos al lote -> variante -> producto
        # También traemos las devoluciones y liquidaciones para calcular el stock rápido
        queryset = SalidaProvisoria.objects.prefetch_related(
            'items__lote__variante__producto_padre',
            'devoluciones__items',
            'liquidaciones__items'
        )
        return queryset

# A medida que hagamos los serializers para IngresoMercaderia, BajaInventario, etc.
# los iremos agregando aquí abajo siguiendo este mismo patrón.
