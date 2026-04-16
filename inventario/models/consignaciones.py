# inventario/models/consignaciones.py
from django.db import models, transaction
from django.db.models import Sum
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from simple_history.models import HistoricalRecords

from .base import EstadoMovimiento
from .stock import Deposito, StockLote


class SalidaProvisoria(models.Model):
    fecha_salida = models.DateTimeField(auto_now_add=True)
    responsable = models.CharField(max_length=100)
    destino = models.CharField(max_length=200)
    fecha_esperada_devolucion = models.DateField(null=True, blank=True)
    observaciones = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)
    estado = models.CharField(
        max_length=20, choices=EstadoMovimiento.choices, default=EstadoMovimiento.BORRADOR)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Salida en Consignación"
        verbose_name_plural = "Salidas en Consignación"

    def clean(self):
        if self.pk:
            original = SalidaProvisoria.objects.get(pk=self.pk)
            if original.estado == EstadoMovimiento.APROBADO and self.estado != EstadoMovimiento.APROBADO:
                raise ValidationError(
                    "Este movimiento ya fue APROBADO. No se puede revertir el estado.")
        super().clean()

    def __str__(self):
        fecha = self.fecha_salida.strftime('%d/%m/%Y') if self.fecha_salida else ''
        return f"Salida {self.id} | {self.responsable} | {self.destino} ({fecha})"


class ItemSalidaProvisoria(models.Model):
    salida = models.ForeignKey(
        SalidaProvisoria, on_delete=models.CASCADE, related_name="items")
    lote = models.ForeignKey(StockLote, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    procesado = models.BooleanField(default=False, editable=False)

    class Meta:
        verbose_name = "Ítem de Salida Provisoria"
        verbose_name_plural = "Ítems de Salidas Provisorias"

    def clean(self):
        if self.cantidad > self.lote.cantidad:
            raise ValidationError(f"Stock insuficiente en lote {self.lote.lote_codigo}")

    def __str__(self):
        return f"{self.cantidad}u. de {self.lote.variante.product_code}"


@receiver(post_save, sender=SalidaProvisoria)
def procesar_cambio_estado_salida(sender, instance, created, **kwargs):
    """
    Cuando una salida pasa a APROBADO, debemos descontar el stock de todos sus items
    que no hayan sido procesados aún.
    """
    if instance.estado == EstadoMovimiento.APROBADO:
        with transaction.atomic():
            # Buscamos items pendientes de procesar para esta salida
            items_pendientes = instance.items.filter(procesado=False)
            for item in items_pendientes:
                lote = item.lote
                lote.cantidad -= item.cantidad
                lote.save()
                
                # Marcamos como procesado usando update para evitar disparar señales recursivas
                ItemSalidaProvisoria.objects.filter(pk=item.pk).update(procesado=True)


class DevolucionSalidaProvisoria(models.Model):
    salida_original = models.ForeignKey(
        SalidaProvisoria, on_delete=models.PROTECT, related_name="devoluciones")
    fecha_devolucion = models.DateTimeField(auto_now_add=True)
    deposito_destino = models.ForeignKey(Deposito, on_delete=models.PROTECT)
    observaciones = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)
    estado = models.CharField(
        max_length=20, choices=EstadoMovimiento.choices, default=EstadoMovimiento.BORRADOR)
    procesado = models.BooleanField(default=False, editable=False)

    def clean(self):
        if self.pk:
            original = DevolucionSalidaProvisoria.objects.get(pk=self.pk)
            if original.estado == EstadoMovimiento.APROBADO and self.estado != EstadoMovimiento.APROBADO:
                raise ValidationError("Este movimiento ya fue APROBADO.")
        super().clean()

    class Meta:
        verbose_name = "Retorno al Depósito"
        verbose_name_plural = "Retornos al Depósito"

    def __str__(self):
        return f"Devolución {self.id} (de Salida {self.salida_original.id})"


class ItemDevolucionProvisoria(models.Model):
    devolucion = models.ForeignKey(
        DevolucionSalidaProvisoria, on_delete=models.CASCADE, related_name="items")
    item_salida = models.ForeignKey(
        ItemSalidaProvisoria, on_delete=models.PROTECT, related_name="devoluciones_item")
    cantidad_devuelta = models.PositiveIntegerField()
    procesado = models.BooleanField(default=False, editable=False)


    class Meta:
        verbose_name = "Ítem de Devolución"
        verbose_name_plural = "Ítems de Devolución"

    def clean(self):
        if self.item_salida.salida != self.devolucion.salida_original:
            raise ValidationError("Salida incorrecta")
        ya_devuelto = self.item_salida.devoluciones_item.aggregate(
            Sum('cantidad_devuelta'))['cantidad_devuelta__sum'] or 0
        faltan = self.item_salida.cantidad - ya_devuelto
        if self.cantidad_devuelta > faltan:
            raise ValidationError(f"Solo faltan {faltan} unidades.")

    def __str__(self):
        return f"Devuelve {self.cantidad_devuelta}u. de {self.item_salida.lote.variante.product_code}"


@receiver(post_save, sender=ItemDevolucionProvisoria)
def procesar_item_devolucion(sender, instance, created, **kwargs):
    # Accedemos a la cabecera (DevolucionSalidaProvisoria) para ver su estado
    devolucion_padre = instance.devolucion

    # Solo sumamos stock si la devolución está APROBADA y este ítem no fue procesado
    if devolucion_padre.estado == EstadoMovimiento.APROBADO and not instance.procesado:
        with transaction.atomic():
            lote_original = instance.item_salida.lote

            # Buscamos o creamos el lote en el depósito de destino (donde vuelve la mercadería)
            dest, _ = StockLote.objects.get_or_create(
                variante=lote_original.variante,
                deposito=devolucion_padre.deposito_destino,
                lote_codigo=lote_original.lote_codigo,
                defaults={
                    'cantidad': 0,
                    'costo_compra_lote': lote_original.costo_compra_lote,
                    'vencimiento': lote_original.vencimiento,
                    'qr_code': lote_original.qr_code
                }
            )

            # Sumamos la cantidad devuelta
            dest.cantidad += instance.cantidad_devuelta
            dest.save()

            # Marcamos este item como procesado para no duplicar stock si se vuelve a guardar
            ItemDevolucionProvisoria.objects.filter(
                pk=instance.pk).update(procesado=True)
            instance.procesado = True


class MotivoLiquidacion(models.TextChoices):
    VENTA = 'VENTA', 'Venta / Consumido por cliente'
    PERDIDA = 'PERDIDA', 'Pérdida / Rotura'
    MUESTRA = 'MUESTRA', 'Muestra Médica (Sin cargo)'


class LiquidacionSalidaProvisoria(models.Model):
    salida_original = models.ForeignKey(
        SalidaProvisoria, on_delete=models.PROTECT, related_name="liquidaciones")
    fecha_liquidacion = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(
        max_length=20, choices=MotivoLiquidacion.choices, default=MotivoLiquidacion.VENTA)
    comprobante_venta = models.CharField(
        max_length=100, blank=True, help_text="Nro de factura o recibo si se vendió")
    observaciones = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        verbose_name = "Liquidación (Venta/Faltante)"
        verbose_name_plural = "Liquidaciones (Ventas/Faltantes)"

    def __str__(self):
        return f"Liquidación {self.id} (de Salida {self.salida_original.id}) - {self.get_motivo_display()}"


class ItemLiquidacionProvisoria(models.Model):
    liquidacion = models.ForeignKey(
        LiquidacionSalidaProvisoria, on_delete=models.CASCADE, related_name="items")
    item_salida = models.ForeignKey(
        ItemSalidaProvisoria, on_delete=models.PROTECT, related_name="liquidaciones_item")
    cantidad_liquidada = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Ítem Liquidado"
        verbose_name_plural = "Ítems Liquidados"

    def clean(self):
        if self.item_salida.salida != self.liquidacion.salida_original:
            raise ValidationError(
                "Este ítem no pertenece a la salida original seleccionada.")

        # Calculamos cuánto se devolvió y cuánto ya se liquidó antes
        ya_devuelto = self.item_salida.devoluciones_item.aggregate(
            Sum('cantidad_devuelta'))['cantidad_devuelta__sum'] or 0
        ya_liquidado = self.item_salida.liquidaciones_item.aggregate(
            Sum('cantidad_liquidada'))['cantidad_liquidada__sum'] or 0

        faltan = self.item_salida.cantidad - (ya_devuelto + ya_liquidado)

        if self.cantidad_liquidada > faltan:
            raise ValidationError(
                f"Error: Solo quedan {faltan} unidades pendientes de esta salida.")

    def __str__(self):
        return f"Liquida {self.cantidad_liquidada}u. de {self.item_salida.lote.variante.product_code}"
