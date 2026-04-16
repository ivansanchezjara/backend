from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView  # <--- NUEVO IMPORT

# 1. IMPORTAMOS TU NUEVA VISTA Y EL REFRESH NORMAL
from .views import MyTokenObtainPairView, UserProfileView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.routers import DefaultRouter
from .filer_views import FolderViewSet, ImageViewSet

filer_router = DefaultRouter()
filer_router.register(r'folders', FolderViewSet, basename='filer-folder')
filer_router.register(r'images', ImageViewSet, basename='filer-image')

urlpatterns = [
    # 0. REDIRECCIÓN DE LA RAÍZ AL ADMIN
    path('', RedirectView.as_view(url='/admin/', permanent=False)),

    path('admin/', admin.site.admin_urls if hasattr(admin.site,
         'admin_urls') else admin.site.urls),

    # 2. ENDPOINT DE LOGIN (Ahora usa tu vista personalizada)
    path('api/login/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),

    # 3. ENDPOINT DE REFRESH
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 4. ENDPOINT DE PERFIL
    path('api/profile/', UserProfileView.as_view(), name='user-profile'),

    # Conectamos las URLs de las apps
    path('api/inventario/', include('inventario.urls')),
    path('api/catalogo/', include('catalogo.urls')),
    path('api/filer/', include(filer_router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
