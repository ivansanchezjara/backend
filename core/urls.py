from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# 1. IMPORTAMOS TU NUEVA VISTA Y EL REFRESH NORMAL
from .views import MyTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.admin_urls if hasattr(admin.site,
         'admin_urls') else admin.site.urls),

    # 2. ENDPOINT DE LOGIN (Ahora usa tu vista personalizada)
    path('api/login/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),

    # 3. ENDPOINT DE REFRESH
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Conectamos las URLs de la app inventario
    path('api/', include('inventario.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
