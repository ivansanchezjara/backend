from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver

# Importamos lo que necesitamos de nuestras otras carpetas
from .catalogo import Variante
from .stock import Deposito, StockLote, HistorialCosto

# 1. INGRESOS


class EstadoMovimiento(models.TextChoices):
    BORRADOR = 'BORRADOR', 'Borrador (Pendiente de Aprobación)'
    APROBADO = 'APROBADO', 'Aprobado (Procesado)'
    RECHAZADO = 'RECHAZADO', 'Rechazado'


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

    class Meta:
        verbose_name = "Ingreso de Mercadería"
        verbose_name_plural = "Ingresos de Mercadería"

    def __str__(self):
        return f"Ingreso {self.id} ({self.fecha_arribo})"


class ItemIngreso(models.Model):
    ingreso = models.ForeignKey(
        IngresoMercaderia, on_delete=models.CASCADE, related_name="items")
    variante = models.ForeignKey(Variante, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    costo_fob_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    costo_landed_unitario = models.DecimalField(
        max_digits=12, decimal_places=2)
    lote_codigo = models.CharField(max_length=100)

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

        for item in instance.items.all():
            # 1. Sumar al Stock
            lote, creado = StockLote.objects.get_or_create(
                variante=item.variante,
                deposito=instance.deposito,
                lote_codigo=item.lote_codigo,
                defaults={'cantidad': 0,
                          'costo_compra_lote': item.costo_fob_unitario}
            )
            lote.cantidad += item.cantidad
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


# 2. BAJAS


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

    class Meta:
        verbose_name = "Baja de Inventario"
        verbose_name_plural = "Bajas de Inventario"

    def __str__(self):
        return f"Baja {self.id} | {self.cantidad}u. de {self.lote.variante.product_code}"


@receiver(post_save, sender=BajaInventario)
def procesar_aprobacion_baja(sender, instance, created, **kwargs):
    if not created and instance.estado == EstadoMovimiento.APROBADO and not instance.procesado:
        instance.lote.cantidad -= instance.cantidad
        instance.lote.save()
        
        BajaInventario.objects.filter(pk=instance.pk).update(procesado=True)
        instance.procesado = True

# 3. TRANSFERENCIAS Internas


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

    class Meta:
        verbose_name = "Transferencia Interna"
        verbose_name_plural = "Transferencias Internas"

    def clean(self):
        if self.cantidad > self.lote_origen.cantidad:
            raise ValidationError("Stock insuficiente")
        if self.lote_origen.deposito == self.deposito_destino:
            raise ValidationError("Mismo depósito")

    def __str__(self):
        return f"Transf. {self.id} | {self.cantidad}u. {self.lote_origen.variante.product_code} -> {self.deposito_destino.nombre}"


@receiver(post_save, sender=TransferenciaInterna)
def procesar_transferencia(sender, instance, created, **kwargs):
    if created:
        instance.lote_origen.cantidad -= instance.cantidad
        instance.lote_origen.save()
        lote_dest, _ = StockLote.objects.get_or_create(
            variante=instance.lote_origen.variante,
            deposito=instance.deposito_destino,
            lote_codigo=instance.lote_origen.lote_codigo,
            defaults={'cantidad': 0, 'costo_compra_lote': instance.lote_origen.costo_compra_lote,
                      'vencimiento': instance.lote_origen.vencimiento}
        )
        lote_dest.cantidad += instance.cantidad
        lote_dest.save()

# 4. AJUSTES COMERCIALES


class MotivoAjuste(models.TextChoices):
    ERROR_CARGA = 'ERROR_CARGA', 'Corrección por error de carga'
    INFLACION = 'INFLACION', 'Ajuste por tipo de cambio / inflación'
    ESTRATEGIA = 'ESTRATEGIA', 'Cambio de estrategia comercial'
    COSTO_EXTRA = 'COSTO_EXTRA', 'Reajuste por costos aduaneros / flete'
    OTROS = 'OTROS', 'Otros motivos'


class AjusteComercial(models.Model):
    variante = models.ForeignKey(
        Variante, on_delete=models.CASCADE, related_name="ajustes_comerciales")
    fecha = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=20, choices=MotivoAjuste.choices)
    estado = models.CharField(
        max_length=20, choices=EstadoMovimiento.choices, default=EstadoMovimiento.BORRADOR)
    observaciones = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)
    procesado = models.BooleanField(default=False, editable=False)

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
    # Solo disparamos la lógica cuando el estado pasa a APROBADO
    if not created and instance.estado == EstadoMovimiento.APROBADO and not instance.procesado:
        v = instance.variante

        # --- Actualización de Costos ---
        if instance.nuevo_costo_fob:
            v.costo_fob = instance.nuevo_costo_fob
            # Registramos en el historial para ver la evolución del costo
            HistorialCosto.objects.create(
                variante=v,
                costo_fob=instance.nuevo_costo_fob,
                lote_referencia=f"Ajuste ID {instance.id}"
            )

        if instance.nuevo_costo_landed:
            v.costo_landed = instance.nuevo_costo_landed

        # --- Actualización de Precios (0 al 4) ---
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

        v.save()
        
        AjusteComercial.objects.filter(pk=instance.pk).update(procesado=True)
        instance.procesado = True

# 5. SALIDAS Y DEVOLUCIONES PROVISORIAS


class SalidaProvisoria(models.Model):
    fecha_salida = models.DateTimeField(auto_now_add=True)
    responsable = models.CharField(max_length=100)
    destino = models.CharField(max_length=200)
    fecha_esperada_devolucion = models.DateField(null=True, blank=True)
    observaciones = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        verbose_name = "Salida en Consignación"
        verbose_name_plural = "Salidas en Consignación"

    def __str__(self):
        fecha = self.fecha_salida.strftime(
            '%d/%m/%Y') if self.fecha_salida else ''
        return f"Salida {self.id} | {self.responsable} | {self.destino} ({fecha})"


class ItemSalidaProvisoria(models.Model):
    salida = models.ForeignKey(
        SalidaProvisoria, on_delete=models.CASCADE, related_name="items")
    lote = models.ForeignKey(StockLote, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Ítem de Salida Provisoria"
        verbose_name_plural = "Ítems de Salidas Provisorias"

    def clean(self):
        if self.cantidad > self.lote.cantidad:
            raise ValidationError("Stock insuficiente")

    def __str__(self):
        return f"{self.cantidad}u. de {self.lote.variante.product_code} (Lote: {self.lote.lote_codigo})"


@receiver(post_save, sender=ItemSalidaProvisoria)
def procesar_item_salida_provisoria(sender, instance, created, **kwargs):
    if created:
        instance.lote.cantidad -= instance.cantidad
        instance.lote.save()


class DevolucionSalidaProvisoria(models.Model):
    salida_original = models.ForeignKey(
        SalidaProvisoria, on_delete=models.PROTECT, related_name="devoluciones")
    fecha_devolucion = models.DateTimeField(auto_now_add=True)
    deposito_destino = models.ForeignKey(Deposito, on_delete=models.PROTECT)
    observaciones = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        verbose_name = "Retorno al Depósito"
        verbose_name_plural = "Retornos al Depósito (Suma Stock)"

    def __str__(self):
        return f"Devolución {self.id} (de Salida {self.salida_original.id}) -> {self.deposito_destino.nombre}"


class ItemDevolucionProvisoria(models.Model):
    devolucion = models.ForeignKey(
        DevolucionSalidaProvisoria, on_delete=models.CASCADE, related_name="items")
    item_salida = models.ForeignKey(
        ItemSalidaProvisoria, on_delete=models.PROTECT, related_name="devoluciones_item")
    cantidad_devuelta = models.PositiveIntegerField()

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
    if created:
        lote_or = instance.item_salida.lote
        dest, _ = StockLote.objects.get_or_create(
            variante=lote_or.variante,
            deposito=instance.devolucion.deposito_destino,
            lote_codigo=lote_or.lote_codigo,
            defaults={'cantidad': 0, 'costo_compra_lote': lote_or.costo_compra_lote,
                      'vencimiento': lote_or.vencimiento, 'qr_code': lote_or.qr_code}
        )
        dest.cantidad += instance.cantidad_devuelta
        dest.save()


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
