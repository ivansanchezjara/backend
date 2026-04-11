from django.db import models
from .base import EstadoMovimiento
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .stock import HistorialCosto


class MotivoAjuste(models.TextChoices):
    ERROR_CARGA = 'ERROR_CARGA', 'Corrección por error de carga'
    INFLACION = 'INFLACION', 'Ajuste por tipo de cambio / inflación'
    ESTRATEGIA = 'ESTRATEGIA', 'Cambio de estrategia comercial'
    COSTO_EXTRA = 'COSTO_EXTRA', 'Reajuste por costos aduaneros / flete'
    OTROS = 'OTROS', 'Otros motivos'


class AjusteComercial(models.Model):
    variante = models.ForeignKey(
        'catalogo.Variante', on_delete=models.CASCADE, related_name="ajustes_comerciales")
    fecha = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=20, choices=MotivoAjuste.choices)
    estado = models.CharField(
        max_length=20, choices=EstadoMovimiento.choices, default=EstadoMovimiento.BORRADOR)
    observaciones = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)
    procesado = models.BooleanField(default=False, editable=False)
    history = HistoricalRecords()

    # --- COSTOS ---
    nuevo_costo_fob = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo_costo_landed = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)

    # --- PRECIOS ---
    nuevo_precio_0 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo_precio_1 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo_precio_2 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo_precio_3 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo_precio_4 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)

    # Campos para auditoría (se llenan solos al aprobar)
    costo_fob_ant = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    precio_0_ant = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Ajuste Comercial"
        verbose_name_plural = "Ajustes Comerciales"


@receiver(post_save, sender=AjusteComercial)
def aplicar_ajuste_comercial(sender, instance, created, **kwargs):
    # Solo disparamos la lógica cuando el estado pasa a APROBADO y no ha sido procesado
    if not created and instance.estado == EstadoMovimiento.APROBADO and not instance.procesado:

        with transaction.atomic():
            v = instance.variante

            # --- Actualización de Costos ---
            if instance.nuevo_costo_fob:
                v.costo_fob = instance.nuevo_costo_fob
                # Registramos en el historial
                HistorialCosto.objects.create(
                    variante=v,
                    costo_fob=instance.nuevo_costo_fob,
                    lote_referencia=f"Ajuste ID {instance.id}"
                )

            if instance.nuevo_costo_landed:
                v.costo_landed = instance.nuevo_costo_landed

            # --- Actualización de Precios (0 al 4) ---
            # Usamos getattr para limpiar un poco el código si prefieres,
            # pero manteniendo tu estructura actual:
            if instance.nuevo_precio_0:
                v.precio_0_publico = instance.nuevo_precio_0
            if instance.nuevo_precio_1:
                v.precio_1_estudiante = instance.nuevo_precio_1
            if instance.nuevo_precio_2:
                v.precio_2_reventa = instance.nuevo_precio_2
            if instance.nuevo_precio_3:
                v.precio_3_mayorista = instance.nuevo_precio_3
            if instance.nuevo_precio_4:
                v.precio_4_intercompany = instance.nuevo_precio_4

            # Guardamos todos los cambios en la variante de una sola vez
            v.save()

            # Marcamos como procesado en la DB
            AjusteComercial.objects.filter(
                pk=instance.pk).update(procesado=True)

            # Actualizamos en memoria
            instance.procesado = True
