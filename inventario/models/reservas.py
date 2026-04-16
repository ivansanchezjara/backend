# inventario/models/reservas.py
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .stock import StockLote

class ReservaStock(models.Model):
    lote = models.ForeignKey(StockLote, on_delete=models.CASCADE, related_name="reservas")
    cantidad = models.PositiveIntegerField()
    cliente = models.CharField(max_length=200, help_text="Nombre del cliente o referencia")
    vendedor = models.ForeignKey(User, on_delete=models.PROTECT)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    vencimiento = models.DateTimeField(null=True, blank=True, help_text="Cuándo expira la reserva")
    observaciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True, help_text="Desmarcar si la reserva se canceló o ya se vendió")

    class Meta:
        verbose_name = "Reserva de Stock"
        verbose_name_plural = "Reservas de Stock"

    def clean(self):
        # El stock real disponible en el lote es lote.cantidad - otras reservas activas
        otras_reservas = ReservaStock.objects.filter(lote=self.lote, activo=True)
        if self.pk:
            otras_reservas = otras_reservas.exclude(pk=self.pk)
        
        total_reservado = otras_reservas.aggregate(models.Sum('cantidad'))['cantidad__sum'] or 0
        disponible_real = self.lote.cantidad - total_reservado
        
        if self.cantidad > disponible_real:
            raise ValidationError(f"Stock insuficiente para reservar. Disponible: {disponible_real}")

    def __str__(self):
        return f"Reserva {self.cantidad}u. de {self.lote.variante.product_code} para {self.cliente}"
