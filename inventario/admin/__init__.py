from django.contrib import admin

# Usamos las importaciones absolutas que arreglaron el error circular antes
from inventario.admin.catalogo_admin import *
from inventario.admin.stock_admin import *
from inventario.admin.movs_admin import *

# --- TRUCO PARA DIVIDIR EL PANEL VISUALMENTE ---
original_get_app_list = admin.site.get_app_list


def custom_get_app_list(request, app_label=None):
    app_list = list(original_get_app_list(request, app_label))
    for app in app_list:
        if app['app_label'] == 'inventario':
            modelos_inventario = []
            modelos_movimientos = []
            for model in app['models']:
                if model['object_name'] in ['IngresoMercaderia', 'BajaInventario', 'TransferenciaInterna', 'AjusteComercial', 'SalidaProvisoria', 'DevolucionSalidaProvisoria', 'LiquidacionSalidaProvisoria']:
                    modelos_movimientos.append(model)
                else:
                    modelos_inventario.append(model)

            app['name'] = 'Inventario'
            app['models'] = modelos_inventario

            caja_movimientos = {
                'name': 'Movimientos',
                'app_label': 'movimientos',
                'app_url': '',
                'has_module_perms': True,
                'models': modelos_movimientos,
            }
            app_list.append(caja_movimientos)
            break
    return app_list


admin.site.get_app_list = custom_get_app_list
