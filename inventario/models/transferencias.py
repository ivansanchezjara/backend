from django.db import models
from .base import EstadoMovimiento
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .stock import StockLote, Deposito
from django.core.exceptions import ValidationError


class TransferenciaInterna(models.Model):
    deposito_origen = models.ForeignKey(
        Deposito, on_delete=models.PROTECT, related_name="transferencias_salida_cabecera", null=True)
    deposito_destino = models.ForeignKey(
        Deposito, on_delete=models.PROTECT, related_name="transferencias_entrada_cabecera", null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    observaciones = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoMovimiento.choices,
        default=EstadoMovimiento.BORRADOR
    )
    procesado = models.BooleanField(default=False, editable=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Transferencia Interna"
        verbose_name_plural = "Transferencias Internas"

    def clean(self):
        if self.pk:
            original = TransferenciaInterna.objects.get(pk=self.pk)
            if original.estado == EstadoMovimiento.APROBADO and self.estado != EstadoMovimiento.APROBADO:
                raise ValidationError(
                    "Esta transferencia ya fue APROBADA. No se puede revertir el estado.")

        if self.deposito_origen == self.deposito_destino:
            raise ValidationError(
                "El depósito de origen y destino no pueden ser el mismo.")
        super().clean()

    def __str__(self):
        return f"Transferencia {self.id} | {self.deposito_origen} -> {self.deposito_destino}"


class ItemTransferencia(models.Model):
    transferencia = models.ForeignKey(
        TransferenciaInterna, on_delete=models.CASCADE, related_name="items")
    lote_origen = models.ForeignKey(
        StockLote, on_delete=models.CASCADE, related_name="items_transferencia")
    cantidad = models.PositiveIntegerField()

    def clean(self):
        if self.lote_origen.deposito != self.transferencia.deposito_origen:
            raise ValidationError(
                f"El lote {self.lote_origen.lote_codigo} no pertenece al depósito de origen.")
        
        if self.cantidad > self.lote_origen.cantidad:
            raise ValidationError(
                f"Stock insuficiente en lote {self.lote_origen.lote_codigo}. Disponible: {self.lote_origen.cantidad}")
        super().clean()


@receiver(post_save, sender=TransferenciaInterna)
def procesar_transferencia(sender, instance, created, **kwargs):
    if instance.estado == EstadoMovimiento.APROBADO and not instance.procesado:
        with transaction.atomic():
            for item in instance.items.all():
                # 1. Restar del origen
                lote_origen = item.lote_origen
                lote_origen.cantidad -= item.cantidad
                lote_origen.save()

                # 2. Sumar o crear en el destino
                lote_dest, _ = StockLote.objects.get_or_create(
                    variante=item.lote_origen.variante,
                    deposito=instance.deposito_destino,
                    lote_codigo=item.lote_origen.lote_codigo,
                    defaults={
                        'cantidad': 0,
                        'costo_compra_lote': item.lote_origen.costo_compra_lote,
                        'vencimiento': item.lote_origen.vencimiento
                    }
                )
                lote_dest.cantidad += item.cantidad
                lote_dest.save()

            # 3. Marcar como procesado
            TransferenciaInterna.objects.filter(
                pk=instance.pk).update(procesado=True)

