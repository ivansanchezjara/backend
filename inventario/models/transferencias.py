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
    lote_origen = models.ForeignKey(
        StockLote, on_delete=models.CASCADE, related_name="transferencias_salida")
    deposito_destino = models.ForeignKey(
        Deposito, on_delete=models.PROTECT, related_name="transferencias_entrada")
    cantidad = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    observaciones = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Transferencia Interna"
        verbose_name_plural = "Transferencias Internas"

    def clean(self):
        # 1. PRIMERO: Validar el estado si el objeto ya existe en la DB (pk no es None)
        if self.pk:
            original = TransferenciaInterna.objects.get(pk=self.pk)
            # Bloqueamos cualquier cambio si ya estaba APROBADO
            if original.estado == EstadoMovimiento.APROBADO and self.estado != EstadoMovimiento.APROBADO:
                raise ValidationError(
                    "Esta transferencia ya fue APROBADA. No se puede revertir el estado por integridad de stock."
                )

            # Opcional: Bloquear cambios en cantidad o lotes si ya está aprobado
            if original.estado == EstadoMovimiento.APROBADO:
                if self.cantidad != original.cantidad or self.lote_origen != original.lote_origen:
                    raise ValidationError(
                        "No se pueden modificar datos de una transferencia aprobada.")

        # 2. SEGUNDO: Validaciones de lógica de negocio (las que ya tenías)
        if self.cantidad > self.lote_origen.cantidad:
            raise ValidationError(
                f"Stock insuficiente en lote origen. Disponible: {self.lote_origen.cantidad}")

        if self.lote_origen.deposito == self.deposito_destino:
            raise ValidationError(
                "El depósito de origen y destino no pueden ser el mismo.")

        # 3. SIEMPRE llamar al super al final
        super().clean()

    def __str__(self):
        return f"Transf. {self.id} | {self.cantidad}u. {self.lote_origen.variante.product_code} -> {self.deposito_destino.nombre}"


@receiver(post_save, sender=TransferenciaInterna)
def procesar_transferencia(sender, instance, created, **kwargs):
    # Solo actuamos si el estado es APROBADO y aún no fue procesado
    if instance.estado == EstadoMovimiento.APROBADO and not instance.procesado:

        with transaction.atomic():
            # 1. Restar del origen
            lote_origen = instance.lote_origen
            lote_origen.cantidad -= instance.cantidad
            lote_origen.save()

            # 2. Sumar o crear en el destino
            lote_dest, _ = StockLote.objects.get_or_create(
                variante=instance.lote_origen.variante,
                deposito=instance.deposito_destino,
                lote_codigo=instance.lote_origen.lote_codigo,
                defaults={
                    'cantidad': 0,
                    'costo_compra_lote': instance.lote_origen.costo_compra_lote,
                    'vencimiento': instance.lote_origen.vencimiento
                }
            )
            lote_dest.cantidad += instance.cantidad
            lote_dest.save()

            # 3. Marcar como procesado para que no se repita el movimiento
            # Usamos update para evitar disparar señales de nuevo
            TransferenciaInterna.objects.filter(
                pk=instance.pk).update(procesado=True)
