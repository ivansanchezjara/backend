from django.db import models
from simple_history.models import HistoricalRecords


class Deposito(models.Model):
    nombre = models.CharField(max_length=100)
    ubicacion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Depósito"
        verbose_name_plural = "Depósitos"

    def __str__(self): return self.nombre


class StockLote(models.Model):
    variante = models.ForeignKey(
        'catalogo.Variante', on_delete=models.CASCADE, related_name="existencias")
    deposito = models.ForeignKey(Deposito, on_delete=models.PROTECT)
    lote_codigo = models.CharField(max_length=100)
    cantidad = models.IntegerField(default=0, verbose_name="Cantidad Disponible")
    cantidad_vencida = models.IntegerField(default=0, verbose_name="Cantidad Vencida")
    vencimiento = models.DateField(null=True, blank=True)
    qr_code = models.CharField(max_length=255, null=True, blank=True)
    costo_compra_lote = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_entrada = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ('variante', 'deposito', 'lote_codigo')
        verbose_name = "Lote de Stock"
        verbose_name_plural = "Existencias por Lote"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gte=0),
                name='stock_lote_cantidad_no_negativa'
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad_vencida__gte=0),
                name='stock_lote_cantidad_vencida_no_negativa'
            )
        ]

    def __str__(self):
        return f"{self.variante.product_code} | Lote: {self.lote_codigo}"

    def procesar_vencimiento(self):
        """Metodo de conveniencia si se requiere llamar manualmente sin guardar."""
        from django.utils import timezone
        if self.vencimiento and self.vencimiento < timezone.now().date() and self.cantidad > 0:
            self.cantidad_vencida += self.cantidad
            self.cantidad = 0
            self.save()

    def save(self, *args, **kwargs):
        """Interceptor automático: si se intenta guardar código vencido, pasa al stock vencido."""
        from django.utils import timezone
        if self.vencimiento and self.vencimiento < timezone.now().date() and self.cantidad > 0:
            self.cantidad_vencida += self.cantidad
            self.cantidad = 0
        super().save(*args, **kwargs)


class HistorialCosto(models.Model):
    variante = models.ForeignKey(
        'catalogo.Variante', on_delete=models.CASCADE, related_name="historico_costos")
    costo_fob = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    lote_referencia = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Historial de Costo"
        verbose_name_plural = "Historial de Costos"

    def __str__(self):
        return f"{self.variante.product_code} | ${self.costo_fob} | {self.fecha.date()}"
