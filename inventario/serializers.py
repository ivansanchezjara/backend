from rest_framework import serializers
from django.db.models import Sum
from .models.consignaciones import (
    SalidaProvisoria, ItemSalidaProvisoria, 
    DevolucionSalidaProvisoria, ItemDevolucionProvisoria,
    LiquidacionSalidaProvisoria, ItemLiquidacionProvisoria
)
from .models.ingresos import IngresoMercaderia, ItemIngreso
from .models.bajas import BajaInventario
from .models.transferencias import TransferenciaInterna, ItemTransferencia
from .models.ajustes import AjusteComercial
from .models.stock import Deposito, StockLote
from django.db import transaction

class DepositoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deposito
        fields = ['id', 'nombre', 'ubicacion']


class StockLoteSerializer(serializers.ModelSerializer):
    deposito_nombre = serializers.ReadOnlyField(source='deposito.nombre')
    variante_nombre = serializers.ReadOnlyField(source='variante.producto_padre.nombre_general')
    
    class Meta:
        model = StockLote
        fields = ['id', 'variante', 'variante_nombre', 'deposito', 'deposito_nombre', 'lote_codigo', 'vencimiento', 'cantidad', 'cantidad_vencida']



class ItemSalidaSerializer(serializers.ModelSerializer):
    variante_nombre = serializers.ReadOnlyField(source='lote.variante.producto_padre.nombre_general')
    variante_codigo = serializers.ReadOnlyField(source='lote.variante.product_code')
    lote_codigo = serializers.ReadOnlyField(source='lote.lote_codigo')
    deposito_nombre = serializers.ReadOnlyField(source='lote.deposito.nombre')

    class Meta:
        model = ItemSalidaProvisoria
        fields = ['id', 'lote', 'variante_nombre', 'variante_codigo', 'lote_codigo', 'deposito_nombre', 'cantidad', 'procesado']


class SalidaProvisoriaSerializer(serializers.ModelSerializer):
    items = ItemSalidaSerializer(many=True)
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')
    resumen_stock = serializers.SerializerMethodField()

    class Meta:
        model = SalidaProvisoria
        fields = [
            'id', 'fecha_salida', 'responsable', 'destino', 
            'fecha_esperada_devolucion', 'observaciones', 'usuario', 
            'usuario_nombre', 'estado', 'items', 'resumen_stock'
        ]
        read_only_fields = ['estado', 'usuario']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        with transaction.atomic():
            salida = SalidaProvisoria.objects.create(**validated_data)
            for item_data in items_data:
                ItemSalidaProvisoria.objects.create(salida=salida, **item_data)
            return salida

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if items_data is not None:
                instance.items.filter(procesado=False).delete()
                for item_data in items_data:
                    ItemSalidaProvisoria.objects.create(salida=instance, **item_data)
            return instance

    def get_resumen_stock(self, obj):
        total_salido = obj.items.aggregate(total=Sum('cantidad'))['total'] or 0
        total_devuelto = obj.devoluciones.filter(estado='APROBADO').aggregate(
            total=Sum('items__cantidad_devuelta'))['total'] or 0
        total_liquidado = obj.liquidaciones.aggregate(
            total=Sum('items__cantidad_liquidada'))['total'] or 0

        pendientes = total_salido - (total_devuelto + total_liquidado)

        return {
            "enviado": total_salido,
            "devuelto": total_devuelto,
            "liquidado": total_liquidado,
            "pendiente": pendientes,
            "completado": pendientes <= 0 and total_salido > 0
        }


# --- DEVOLUCIONES ---

class ItemDevolucionSerializer(serializers.ModelSerializer):
    variante_nombre = serializers.ReadOnlyField(source='item_salida.lote.variante.producto_padre.nombre_general')
    lote_codigo = serializers.ReadOnlyField(source='item_salida.lote.lote_codigo')

    class Meta:
        model = ItemDevolucionProvisoria
        fields = ['id', 'item_salida', 'variante_nombre', 'lote_codigo', 'cantidad_devuelta', 'procesado']


class DevolucionSalidaProvisoriaSerializer(serializers.ModelSerializer):
    items = ItemDevolucionSerializer(many=True)
    deposito_destino_nombre = serializers.ReadOnlyField(source='deposito_destino.nombre')
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = DevolucionSalidaProvisoria
        fields = [
            'id', 'salida_original', 'fecha_devolucion', 'deposito_destino', 
            'deposito_destino_nombre', 'observaciones', 'usuario', 
            'usuario_nombre', 'estado', 'procesado', 'items'
        ]
        read_only_fields = ['estado', 'procesado', 'usuario']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        with transaction.atomic():
            dev = DevolucionSalidaProvisoria.objects.create(**validated_data)
            for item_data in items_data:
                ItemDevolucionProvisoria.objects.create(devolucion=dev, **item_data)
            return dev


# --- LIQUIDACIONES ---

class ItemLiquidacionSerializer(serializers.ModelSerializer):
    variante_nombre = serializers.ReadOnlyField(source='item_salida.lote.variante.producto_padre.nombre_general')

    class Meta:
        model = ItemLiquidacionProvisoria
        fields = ['id', 'item_salida', 'variante_nombre', 'cantidad_liquidada']


class LiquidacionSalidaProvisoriaSerializer(serializers.ModelSerializer):
    items = ItemLiquidacionSerializer(many=True)
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = LiquidacionSalidaProvisoria
        fields = [
            'id', 'salida_original', 'fecha_liquidacion', 'motivo', 
            'comprobante_venta', 'observaciones', 'usuario', 
            'usuario_nombre', 'items'
        ]
        read_only_fields = ['usuario']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        with transaction.atomic():
            liq = LiquidacionSalidaProvisoria.objects.create(**validated_data)
            for item_data in items_data:
                ItemLiquidacionProvisoria.objects.create(liquidacion=liq, **item_data)
            return liq



class ItemIngresoSerializer(serializers.ModelSerializer):
    variante_nombre = serializers.SerializerMethodField()
    variante_codigo = serializers.ReadOnlyField(source='variante.product_code')
    variante_imagen_url = serializers.SerializerMethodField()

    class Meta:
        model = ItemIngreso
        fields = [
            'id', 'variante', 'variante_nombre', 'variante_codigo', 'variante_imagen_url', 'cantidad',
            'costo_fob_unitario', 'costo_landed_unitario', 'lote_codigo', 'vencimiento',
            'nuevo_precio_0_publico', 'nuevo_precio_1_estudiante',
            'nuevo_precio_2_reventa', 'nuevo_precio_3_mayorista',
            'nuevo_precio_4_intercompany'
        ]

    def get_variante_nombre(self, obj):
        if not obj.variante: return "Sin variante"
        prod = obj.variante.producto_padre.nombre_general if obj.variante.producto_padre else obj.variante.nombre_variante
        var = obj.variante.nombre_variante
        return f"{prod} ({var})" if var and var != prod else prod

    def get_variante_imagen_url(self, obj):
        if not obj.variante: return None
        img = obj.variante.imagen_variante
        if not img and obj.variante.producto_padre:
            img = obj.variante.producto_padre.imagen_principal
        return img.url if img else None

    def validate(self, data):
        # 1. Validación de Costos
        fob = data.get('costo_fob_unitario')
        landed = data.get('costo_landed_unitario')
        if fob > landed:
            raise serializers.ValidationError({
                "costo_fob_unitario": "El costo FOB no puede ser mayor al costo Landed."
            })

        # 2. Validación de Jerarquía de Precios (P0 > P1 > P2 > P3 > P4)
        p0 = data.get('nuevo_precio_0_publico')
        p1 = data.get('nuevo_precio_1_estudiante')
        p2 = data.get('nuevo_precio_2_reventa')
        p3 = data.get('nuevo_precio_3_mayorista')
        p4 = data.get('nuevo_precio_4_intercompany')

        if not (p0 >= p1 >= p2 >= p3 >= p4):
            raise serializers.ValidationError({
                "nuevo_precio_0_publico": "La jerarquía de precios debe ser P0 >= P1 >= P2 >= P3 >= P4."
            })

        return data


class IngresoMercaderiaSerializer(serializers.ModelSerializer):
    items = ItemIngresoSerializer(many=True)
    deposito_nombre = serializers.ReadOnlyField(source='deposito.nombre')
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = IngresoMercaderia
        fields = [
            'id', 'fecha_arribo', 'descripcion', 'comprobante',
            'deposito', 'deposito_nombre', 'usuario', 'usuario_nombre',
            'estado', 'procesado', 'items'
        ]
        read_only_fields = ['estado', 'procesado']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        
        with transaction.atomic():
            ingreso = IngresoMercaderia.objects.create(**validated_data)
            for item_data in items_data:
                ItemIngreso.objects.create(ingreso=ingreso, **item_data)
            return ingreso

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        with transaction.atomic():
            # Actualizamos los campos básicos del ingreso
            instance = super().update(instance, validated_data)
            
            # Si enviamos nuevos items, reemplazamos los anteriores (Lógica de borrador)
            if items_data is not None:
                instance.items.all().delete()
                for item_data in items_data:
                    ItemIngreso.objects.create(ingreso=instance, **item_data)
            

class BajaInventarioSerializer(serializers.ModelSerializer):
    variante_nombre = serializers.ReadOnlyField(source='lote.variante.producto_padre.nombre_general')
    variante_codigo = serializers.ReadOnlyField(source='lote.variante.product_code')
    deposito_nombre = serializers.ReadOnlyField(source='lote.deposito.nombre')
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = BajaInventario
        fields = [
            'id', 'lote', 'variante_nombre', 'variante_codigo', 'deposito_nombre',
            'fecha', 'cantidad', 'motivo', 'observaciones', 'usuario',
            'usuario_nombre', 'estado', 'procesado'
        ]


class ItemTransferenciaSerializer(serializers.ModelSerializer):
    variante_nombre = serializers.ReadOnlyField(source='lote_origen.variante.producto_padre.nombre_general')
    variante_codigo = serializers.ReadOnlyField(source='lote_origen.variante.product_code')
    lote_codigo = serializers.ReadOnlyField(source='lote_origen.lote_codigo')

    class Meta:
        model = ItemTransferencia
        fields = ['id', 'lote_origen', 'variante_nombre', 'variante_codigo', 'lote_codigo', 'cantidad']


class TransferenciaInternaSerializer(serializers.ModelSerializer):
    items = ItemTransferenciaSerializer(many=True)
    deposito_origen_nombre = serializers.ReadOnlyField(source='deposito_origen.nombre')
    deposito_destino_nombre = serializers.ReadOnlyField(source='deposito_destino.nombre')
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = TransferenciaInterna
        fields = [
            'id', 'deposito_origen', 'deposito_destino', 'deposito_origen_nombre', 'deposito_destino_nombre',
            'fecha', 'observaciones', 'usuario', 'usuario_nombre', 'estado', 'procesado', 'items'
        ]
        read_only_fields = ['estado', 'procesado', 'usuario']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        with transaction.atomic():
            transferencia = TransferenciaInterna.objects.create(**validated_data)
            for item_data in items_data:
                ItemTransferencia.objects.create(transferencia=transferencia, **item_data)
            return transferencia

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if items_data is not None:
                instance.items.all().delete()
                for item_data in items_data:
                    ItemTransferencia.objects.create(transferencia=instance, **item_data)
            return instance


class AjusteComercialSerializer(serializers.ModelSerializer):
    variante_nombre = serializers.ReadOnlyField(source='variante.producto_padre.nombre_general')
    variante_codigo = serializers.ReadOnlyField(source='variante.product_code')
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = AjusteComercial
        fields = [
            'id', 'variante', 'variante_nombre', 'variante_codigo', 'fecha', 'motivo',
            'estado', 'observaciones', 'usuario', 'usuario_nombre', 'procesado',
            'nuevo_costo_fob', 'nuevo_costo_landed',
            'nuevo_precio_0', 'nuevo_precio_1', 'nuevo_precio_2', 'nuevo_precio_3', 'nuevo_precio_4',
            'costo_fob_ant', 'precio_0_ant'
        ]
        read_only_fields = ['estado', 'procesado', 'usuario', 'costo_fob_ant', 'precio_0_ant']

    def validate(self, data):
        fields_to_check = [
            'nuevo_costo_fob', 'nuevo_costo_landed', 
            'nuevo_precio_0', 'nuevo_precio_1', 'nuevo_precio_2', 'nuevo_precio_3', 'nuevo_precio_4'
        ]
        if not any(data.get(field) is not None for field in fields_to_check):
            raise serializers.ValidationError("Debes ajustar al menos un valor de costo o precio.")
        return data

