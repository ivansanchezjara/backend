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


class IngresoMercaderia(models.Model):
    fecha_arribo = models.DateField()
    descripcion = models.CharField(max_length=255)
    comprobante = models.CharField(max_length=100, blank=True)
    deposito = models.ForeignKey(Deposito, on_delete=models.PROTECT)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)

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


@receiver(post_save, sender=ItemIngreso)
def procesar_llegada_item(sender, instance, created, **kwargs):
    if created:
        lote, creado = StockLote.objects.get_or_create(
            variante=instance.variante,
            deposito=instance.ingreso.deposito,
            lote_codigo=instance.lote_codigo,
            defaults={'cantidad': 0,
                      'costo_compra_lote': instance.costo_fob_unitario}
        )
        lote.cantidad += instance.cantidad
        lote.save()

        v = instance.variante
        v.costo_fob = instance.costo_fob_unitario
        v.costo_landed = instance.costo_landed_unitario
        v.precio_0_publico = instance.nuevo_precio_0_publico
        if instance.nuevo_precio_1_estudiante is not None:
            v.precio_1_estudiante = instance.nuevo_precio_1_estudiante
        if instance.nuevo_precio_2_reventa is not None:
            v.precio_2_reventa = instance.nuevo_precio_2_reventa
        if instance.nuevo_precio_3_mayorista is not None:
            v.precio_3_mayorista = instance.nuevo_precio_3_mayorista
        if instance.nuevo_precio_4_intercompany is not None:
            v.precio_4_intercompany = instance.nuevo_precio_4_intercompany
        v.save()

        HistorialCosto.objects.create(
            variante=v, costo_fob=instance.costo_fob_unitario, lote_referencia=instance.lote_codigo)

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

    class Meta:
        verbose_name = "Baja de Inventario"
        verbose_name_plural = "Bajas de Inventario"

    def __str__(self):
        return f"Baja {self.id} | {self.cantidad}u. de {self.lote.variante.product_code}"


@receiver(post_save, sender=BajaInventario)
def procesar_baja_inventario(sender, instance, created, **kwargs):
    if created:
        instance.lote.cantidad -= instance.cantidad
        instance.lote.save()

# 3. TRANSFERENCIAS


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
    observaciones = models.CharField(max_length=255, blank=True)
    costo_fob_anterior = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    precio_0_anterior = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo_costo_fob = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo_precio_0 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        verbose_name = "Ajuste Comercial"
        verbose_name_plural = "Ajustes Comerciales"

    def clean(self):
        if self.nuevo_costo_fob is None and self.nuevo_precio_0 is None:
            raise ValidationError("Ingresar costo o precio nuevo.")

    def __str__(self):
        return f"Ajuste {self.id} | {self.variante.product_code} ({self.get_motivo_display()})"


@receiver(post_save, sender=AjusteComercial)
def aplicar_ajuste_comercial(sender, instance, created, **kwargs):
    if created:
        v = instance.variante
        if instance.nuevo_costo_fob is not None:
            AjusteComercial.objects.filter(pk=instance.pk).update(
                costo_fob_anterior=v.costo_fob)
            v.costo_fob = instance.nuevo_costo_fob
            HistorialCosto.objects.create(variante=v, costo_fob=instance.nuevo_costo_fob,
                                          lote_referencia=f"Ajuste: {instance.get_motivo_display()}")
        if instance.nuevo_precio_0 is not None:
            AjusteComercial.objects.filter(pk=instance.pk).update(
                precio_0_anterior=v.precio_0_publico)
            v.precio_0_publico = instance.nuevo_precio_0
        v.save()

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
