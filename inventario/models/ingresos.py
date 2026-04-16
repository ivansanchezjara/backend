# inventario/models/ingresos.py
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinValueValidator
from simple_history.models import HistoricalRecords

# Importamos lo que necesitamos de nuestros "hermanos"
from .base import EstadoMovimiento
from .stock import Deposito, StockLote, HistorialCosto


class IngresoMercaderia(models.Model):
    fecha_arribo = models.DateField()
    descripcion = models.CharField(max_length=255)
    comprobante = models.CharField(max_length=100, blank=True)
    deposito = models.ForeignKey(Deposito, on_delete=models.PROTECT)
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
            # Obtenemos la versión actual en la base de datos
            original = IngresoMercaderia.objects.get(pk=self.pk)
            if original.estado == EstadoMovimiento.APROBADO and self.estado != EstadoMovimiento.APROBADO:
                raise ValidationError(
                    "No se puede cambiar el estado de un movimiento ya APROBADO. "
                    "Esto comprometería la integridad del stock."
                )
        super().clean()

    class Meta:
        verbose_name = "Ingreso de Mercadería"
        verbose_name_plural = "Ingresos de Mercadería"

    def __str__(self):
        return f"Ingreso {self.id} ({self.fecha_arribo})"


class ItemIngreso(models.Model):
    ingreso = models.ForeignKey(
        IngresoMercaderia, on_delete=models.CASCADE, related_name="items")
    variante = models.ForeignKey('catalogo.Variante', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(
        validators=[MinValueValidator(1)])
    costo_fob_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    costo_landed_unitario = models.DecimalField(
        max_digits=12, decimal_places=2)
    lote_codigo = models.CharField(max_length=100)
    vencimiento = models.DateField(null=True, blank=True)

    nuevo_precio_0_publico = models.DecimalField(
        max_digits=12, decimal_places=2)
    nuevo_precio_1_estudiante = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo_precio_2_reventa = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo_precio_3_mayorista = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo_precio_4_intercompany = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.cantidad}u. de {self.variante.product_code}"


@receiver(post_save, sender=IngresoMercaderia)
def procesar_aprobacion_ingreso(sender, instance, created, **kwargs):
    if not created and instance.estado == EstadoMovimiento.APROBADO and not instance.procesado:

        with transaction.atomic():
            for item in instance.items.all():
                # 1. Sumar al Stock
                lote, creado = StockLote.objects.get_or_create(
                    variante=item.variante,
                    deposito=instance.deposito,
                    lote_codigo=item.lote_codigo,
                    defaults={
                        'cantidad': 0,
                        'vencimiento': item.vencimiento,
                        'costo_compra_lote': item.costo_fob_unitario
                    }
                )
                lote.cantidad += item.cantidad
                if item.vencimiento:
                    lote.vencimiento = item.vencimiento
                lote.save()

                # 2. Actualizar Precios y Costos en la Variante
                v = item.variante
                v.costo_fob = item.costo_fob_unitario
                v.costo_landed = item.costo_landed_unitario
                v.precio_0_publico = item.nuevo_precio_0_publico
                if item.nuevo_precio_1_estudiante is not None:
                    v.precio_1_estudiante = item.nuevo_precio_1_estudiante
                if item.nuevo_precio_2_reventa is not None:
                    v.precio_2_reventa = item.nuevo_precio_2_reventa
                if item.nuevo_precio_3_mayorista is not None:
                    v.precio_3_mayorista = item.nuevo_precio_3_mayorista
                if item.nuevo_precio_4_intercompany is not None:
                    v.precio_4_intercompany = item.nuevo_precio_4_intercompany
                v.save()

                # 3. Guardar Historial
                HistorialCosto.objects.create(
                    variante=v,
                    costo_fob=item.costo_fob_unitario,
                    lote_referencia=item.lote_codigo
                )

        # 4. Marcar como procesado (usamos update para evitar disparar la señal de nuevo)
        IngresoMercaderia.objects.filter(pk=instance.pk).update(procesado=True)
        instance.procesado = True
