from django.db import models
from .catalogo import Variante  # Importamos de nuestro archivo de al lado


class Deposito(models.Model):
    nombre = models.CharField(max_length=100)
    ubicacion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Depósito"
        verbose_name_plural = "Depósitos"

    def __str__(self): return self.nombre


class StockLote(models.Model):
    variante = models.ForeignKey(
        Variante, on_delete=models.CASCADE, related_name="existencias")
    deposito = models.ForeignKey(Deposito, on_delete=models.PROTECT)
    lote_codigo = models.CharField(max_length=100)
    cantidad = models.PositiveIntegerField(default=0)
    vencimiento = models.DateField(null=True, blank=True)
    qr_code = models.CharField(max_length=255, null=True, blank=True)
    costo_compra_lote = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_entrada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('variante', 'deposito', 'lote_codigo')
        verbose_name = "Lote de Stock"
        verbose_name_plural = "Existencias por Lote"

    def __str__(self):
        return f"{self.variante.product_code} | Lote: {self.lote_codigo}"


class HistorialCosto(models.Model):
    variante = models.ForeignKey(
        Variante, on_delete=models.CASCADE, related_name="historico_costos")
    costo_fob = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    lote_referencia = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Historial de Costo"
        verbose_name_plural = "Historial de Costos"

    def __str__(self):
        return f"{self.variante.product_code} | ${self.costo_fob} | {self.fecha.date()}"
