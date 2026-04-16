from django.core.management.base import BaseCommand
from django.utils import timezone
from inventario.models.stock import StockLote

class Command(BaseCommand):
    help = 'Procesa los vencimientos de stock, moviendo la cantidad disponible a vencida.'

    def handle(self, *args, **options):
        hoy = timezone.now().date()
        lotes_vencidos = StockLote.objects.filter(
            vencimiento__lt=hoy,
            cantidad__gt=0
        )
        
        count = 0
        for lote in lotes_vencidos:
            lote.procesar_vencimiento()
            count += 1
            
        self.stdout.write(self.style.SUCCESS(f'Se procesaron {count} lotes vencidos.'))
