from django.db import models
from django.db.models import Sum
from filer.fields.image import FilerImageField


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def __str__(self): return self.nombre


class Producto(models.Model):
    nombre_general = models.CharField(
        max_length=255, help_text="Ej: Cureta Sinus")
    general_code = models.CharField(max_length=50, unique=True)
    brand = models.CharField(max_length=100, default="Thalys")
    slug = models.SlugField(unique=True)
    imagen_principal = FilerImageField(
        null=True, blank=True, on_delete=models.SET_NULL, related_name="producto_principal")
    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, related_name="productos")
    sub_category = models.CharField(max_length=100)
    professional_area = models.CharField(max_length=100)
    description = models.CharField(max_length=500)
    long_description = models.TextField()
    featured = models.BooleanField(default=False)
    tags = models.JSONField(default=list, blank=True)
    is_published = models.BooleanField(
        default=False,
        verbose_name="Publicado en Web",
        help_text="Si está marcado, el producto será visible en la página online."
    )

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self): return self.nombre_general


class Variante(models.Model):
    producto_padre = models.ForeignKey(
        Producto, on_delete=models.CASCADE, related_name="variants")
    nombre_variante = models.CharField(
        max_length=100, help_text="Ej: #1 Mini Extra-Flex")
    product_code = models.CharField(max_length=50, unique=True)
    sub_slug = models.SlugField(
        max_length=150, help_text="Ej: 1-mini-extra-flex")
    imagen_variante = FilerImageField(
        null=True, blank=True, on_delete=models.SET_NULL, related_name="variante_principal")

    costo_fob = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_landed = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    precio_0_publico = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    precio_1_estudiante = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    precio_2_reventa = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    precio_3_mayorista = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    precio_4_intercompany = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    precio_oferta = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    oferta_vence = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Variante de Producto"
        verbose_name_plural = "Variantes de Productos"

    @property
    def stock_total(self):
        total = self.existencias.aggregate(Sum('cantidad'))['cantidad__sum']
        return total if total is not None else 0

    def __str__(self): return f"{self.product_code} - {self.nombre_variante}"


class ImagenProducto(models.Model):
    variante = models.ForeignKey(
        Variante, on_delete=models.CASCADE, related_name="imagenes")
    imagen_asset = FilerImageField(
        null=True, blank=True, on_delete=models.CASCADE, related_name="galeria_imagenes")
    descripcion = models.CharField(max_length=100, blank=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Imagen de Producto"
        verbose_name_plural = "Galería de Imágenes"
        ordering = ['orden']

    # AGREGAMOS ESTO PARA QUE NO DIGA "OBJECT (1)"
    def __str__(self):
        texto = self.descripcion if self.descripcion else f"Img {self.orden}"
        return f"{texto} - {self.variante.product_code}"
