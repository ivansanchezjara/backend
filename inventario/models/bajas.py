from django.db import models
from .base import EstadoMovimiento
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .stock import StockLote
from django.core.exceptions import ValidationError


class MotivoBaja(models.TextChoices):
    VENCIMIENTO = 'VENCIMIENTO', 'Vencimiento de producto'
    ROTURA = 'ROTURA', 'Rotura o Daño'
    PERDIDA = 'PERDIDA', 'Pérdida o Extravío'
    ERROR_STOCK = 'ERROR_STOCK', 'Ajuste por diferencia de inventario'


class BajaInventario(models.Model):
    lote = models.ForeignKey(
        StockLote, on_delete=models.CASCADE, related_name="bajas")
    fecha = models.DateTimeField(auto_now_add=True)
    cantidad = models.PositiveIntegerField()
    motivo = models.CharField(max_length=20, choices=MotivoBaja.choices)
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

    def clean(self):
        if self.pk:
            # Obtenemos el objeto tal cual está en la DB antes de guardar los cambios
            original = type(self).objects.get(pk=self.pk)
            if original.estado == EstadoMovimiento.APROBADO and self.estado != EstadoMovimiento.APROBADO:
                raise ValidationError(
                    f"Este movimiento ya fue APROBADO y procesado. "
                    "No se puede revertir a otro estado por integridad de inventario."
                )
        super().clean()

    class Meta:
        verbose_name = "Baja de Inventario"
        verbose_name_plural = "Bajas de Inventario"

    def __str__(self):
        return f"Baja {self.id} | {self.cantidad}u. de {self.lote.variante.product_code}"


@receiver(post_save, sender=BajaInventario)
def procesar_aprobacion_baja(sender, instance, created, **kwargs):
    # Verificamos que pase a APROBADO y no se haya procesado ya
    if not created and instance.estado == EstadoMovimiento.APROBADO and not instance.procesado:

        with transaction.atomic():
            # 1. Restar el stock del lote
            lote = instance.lote
            lote.cantidad -= instance.cantidad
            lote.save()

            # 2. Marcar como procesado en la DB
            # Usamos .update() para evitar que se disparen señales infinitas
            BajaInventario.objects.filter(
                pk=instance.pk).update(procesado=True)

            # Actualizamos la instancia en memoria por si se usa luego en el mismo hilo
            instance.procesado = True
