# inventario/admin/__init__.py
from django.contrib import admin

# 1. Importamos los nuevos módulos divididos
from .stock_admin import *
from .ingresos_admin import *
from .consignaciones_admin import *
from .ajustes_admin import *

# --- EL TRUCO VISUAL DE ORGANIZACIÓN (TRIPLE BLOQUE) ---
original_get_app_list = admin.site.get_app_list


def custom_get_app_list(request, app_label=None):
    app_list = list(original_get_app_list(request, app_label))

    for app in app_list:
        if app['app_label'] == 'inventario':
            modelos_stock = []
            modelos_movimientos = []
            modelos_consignaciones = []

            # Clasificamos según la intención de uso
            for model in app['models']:
                nombre = model['object_name']

                # Grupo 1: Lo estático (¿Qué tengo?)
                if nombre in ['Deposito', 'StockLote', 'HistorialCosto']:
                    modelos_stock.append(model)

                # Grupo 2: Lo operativo (Logística interna)
                elif nombre in ['IngresoMercaderia', 'TransferenciaInterna', 'BajaInventario', 'AjusteComercial']:
                    modelos_movimientos.append(model)

                # Grupo 3: Lo comercial (En la calle)
                elif nombre in ['SalidaProvisoria', 'DevolucionSalidaProvisoria', 'LiquidacionSalidaProvisoria']:
                    modelos_consignaciones.append(model)

            # Reconfiguramos el primer bloque: Stock
            app['name'] = '📦 Stock y Depósitos'
            app['models'] = modelos_stock

            # Creamos el bloque de Movimientos Logísticos
            app_list.append({
                'name': '📑 Gestión de Movimientos',
                'app_label': 'movimientos_log',
                'app_url': '',
                'has_module_perms': True,
                'models': modelos_movimientos,
            })

            # Creamos el bloque de Consignaciones
            app_list.append({
                'name': '🤝 Consignaciones (Doctores)',
                'app_label': 'consignaciones_app',
                'app_url': '',
                'has_module_perms': True,
                'models': modelos_consignaciones,
            })
            break

    return app_list


admin.site.get_app_list = custom_get_app_list
