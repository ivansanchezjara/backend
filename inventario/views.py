from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError

# Importamos los modelos y serializers propios del inventario
from .models.consignaciones import (
    SalidaProvisoria, ItemSalidaProvisoria,
    DevolucionSalidaProvisoria, LiquidacionSalidaProvisoria
)
from .models.ingresos import IngresoMercaderia
from .models.bajas import BajaInventario
from .models.transferencias import TransferenciaInterna, ItemTransferencia
from .models.ajustes import AjusteComercial
from .models.stock import Deposito, StockLote
from .serializers import (
    SalidaProvisoriaSerializer, 
    IngresoMercaderiaSerializer, 
    BajaInventarioSerializer,
    TransferenciaInternaSerializer,
    AjusteComercialSerializer,
    SalidaProvisoriaSerializer,
    DevolucionSalidaProvisoriaSerializer,
    LiquidacionSalidaProvisoriaSerializer,
    DepositoSerializer,
    StockLoteSerializer
)


class DepositoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Vista para listar los Depósitos disponibles.
    """
    queryset = Deposito.objects.all()
    serializer_class = DepositoSerializer
    permission_classes = [IsAuthenticated]


class StockLoteViewSet(viewsets.ModelViewSet):
    """
    Vista para listar y editar el Stock por Lote.
    """
    queryset = StockLote.objects.all()
    serializer_class = StockLoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = StockLote.objects.select_related('variante__producto_padre', 'deposito').all()
        variante_id = self.request.query_params.get('variante')
        if variante_id:
            queryset = queryset.filter(variante_id=variante_id)
        return queryset

    @action(detail=False, methods=['post'])
    def procesar_vencimientos(self, request):
        """
        Accion manual para disparar la revision de fechas de vencimiento
        y mover el stock disponible a vencido.
        """
        from django.core.management import call_command
        try:
            call_command('procesar_vencimientos')
            return Response({"message": "Vencimientos procesados con éxito"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# A medida que hagamos los serializers para IngresoMercaderia, BajaInventario, etc.
# los iremos agregando aquí abajo siguiendo este mismo patrón.

class IngresoMercaderiaViewSet(viewsets.ModelViewSet):
    """
    Vista para crear y gestionar Ingresos de Mercadería.
    """
    queryset = IngresoMercaderia.objects.prefetch_related(
        'items__variante__producto_padre',
        'deposito',
        'usuario'
    ).all().order_by('-fecha_arribo')
    serializer_class = IngresoMercaderiaSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Asignar el usuario actual al crear
        serializer.save(usuario=self.request.user)

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        ingreso = self.get_object()
        
        if ingreso.estado == 'APROBADO':
            return Response(
                {"error": "El ingreso ya se encuentra aprobado."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Cambiamos el estado a APROBADO, lo que disparará la señal de stock en models/ingresos.py
            ingreso.estado = 'APROBADO'
            # Usamos clean() por buenas prácticas de Django
            ingreso.clean()
            ingreso.save()
            
            # Recargar para devolver datos frescos
            ingreso.refresh_from_db()
            serializer = self.get_serializer(ingreso)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class BajaInventarioViewSet(viewsets.ModelViewSet):
    """
    Vista para crear y gestionar Bajas de Inventario.
    """
    queryset = BajaInventario.objects.select_related(
        'lote__variante__producto_padre',
        'lote__deposito',
        'usuario'
    ).all().order_by('-fecha')
    serializer_class = BajaInventarioSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        baja = self.get_object()
        
        if baja.estado == 'APROBADO':
            return Response(
                {"error": "Esta baja ya se encuentra aprobada."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            baja.estado = 'APROBADO'
            baja.clean()
            baja.save()
            
            baja.refresh_from_db()
            serializer = self.get_serializer(baja)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class TransferenciaInternaViewSet(viewsets.ModelViewSet):
    """
    Vista para crear y gestionar Transferencias Internas de mercadería.
    """
    queryset = TransferenciaInterna.objects.prefetch_related(
        'items__lote_origen__variante__producto_padre',
        'deposito_origen',
        'deposito_destino',
        'usuario'
    ).all().order_by('-fecha')
    serializer_class = TransferenciaInternaSerializer

    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        transf = self.get_object()
        
        if transf.estado == 'APROBADO':
            return Response(
                {"error": "Esta transferencia ya se encuentra aprobada."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            transf.estado = 'APROBADO'
            transf.clean() # Ejecuta validaciones de stock y depósitos
            transf.save()
            
            transf.refresh_from_db()
            serializer = self.get_serializer(transf)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Error al aprobar: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AjusteComercialViewSet(viewsets.ModelViewSet):
    """
    Vista para realizar Ajustes Comerciales (costos y precios).
    """
    queryset = AjusteComercial.objects.select_related(
        'variante__producto_padre', 
        'usuario'
    ).all().order_by('-fecha')
    serializer_class = AjusteComercialSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        ajuste = self.get_object()
        
        if ajuste.estado == 'APROBADO':
            return Response(
                {"error": "Este ajuste ya se encuentra aprobado."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Capturamos valores actuales para auditoría antes de aprobar
            ajuste.costo_fob_ant = ajuste.variante.costo_fob
            ajuste.precio_0_ant = ajuste.variante.precio_0_publico
            
            ajuste.estado = 'APROBADO'
            ajuste.save() # Dispara la señal post_save en ajustes.py
            
            ajuste.refresh_from_db()
            serializer = self.get_serializer(ajuste)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": f"Error al aprobar ajuste: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SalidaProvisoriaViewSet(viewsets.ModelViewSet):
    queryset = SalidaProvisoria.objects.all().order_by('-fecha_salida')
    serializer_class = SalidaProvisoriaSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        salida = self.get_object()
        if salida.estado == 'APROBADO':
            return Response({"error": "Ya está aprobada"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            salida.estado = 'APROBADO'
            salida.save() # Dispara signals para items
            return Response({"status": "Salida aprobada y stock descontado"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DevolucionSalidaProvisoriaViewSet(viewsets.ModelViewSet):
    queryset = DevolucionSalidaProvisoria.objects.all().order_by('-fecha_devolucion')
    serializer_class = DevolucionSalidaProvisoriaSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        dev = self.get_object()
        if dev.estado == 'APROBADO':
            return Response({"error": "Ya está aprobada"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            dev.estado = 'APROBADO'
            dev.save() # Dispara signals para items
            return Response({"status": "Devolución aprobada y stock sumado"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LiquidacionSalidaProvisoriaViewSet(viewsets.ModelViewSet):
    queryset = LiquidacionSalidaProvisoria.objects.all().order_by('-fecha_liquidacion')
    serializer_class = LiquidacionSalidaProvisoriaSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)




