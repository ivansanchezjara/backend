from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# 1. IMPORTAMOS LAS VISTAS DE SIMPLE JWT
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.admin_urls if hasattr(admin.site,
         'admin_urls') else admin.site.urls),

    # 2. AGREGAMOS EL ENDPOINT DE LOGIN (Aquí es donde Next.js pide el Token)
    path('api/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),

    # 3. AGREGAMOS EL ENDPOINT DE REFRESH (Para renovar la sesión)
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Conectamos las URLs de la app inventario bajo el prefijo /api/
    path('api/', include('inventario.urls')),
]

# Esto permite que Django "sirva" las fotos mientras estás desarrollando (DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
