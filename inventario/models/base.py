# inventario/models/base.py
from django.db import models


class EstadoMovimiento(models.TextChoices):
    BORRADOR = 'BORRADOR', 'Borrador (Pendiente de Aprobación)'
    APROBADO = 'APROBADO', 'Aprobado (Procesado)'
    RECHAZADO = 'RECHAZADO', 'Rechazado'
