from django.apps import AppConfig


class InventarioConfig(AppConfig):
    name = 'inventario'

    def ready(self):
        import sys
        # Evitar problemas si estamos corriendo scripts de test o si ejecutamos migrations donde la tabla todavia no existe
        is_server_run = not any(arg in sys.argv for arg in ['test', 'migrate', 'makemigrations', 'collectstatic'])
        if is_server_run:
            try:
                from . import updater
                updater.start()
            except ImportError:
                pass
            except Exception as e:
                print(f"APScheduler init bypassed due to error: {e}")
