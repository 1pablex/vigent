from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config import settings
from contas.views import login_admin

urlpatterns = [
    # Antes do admin.site.urls: o login do Admin passa pelo login do Vigent, com 2FA.
    path('admin/login/', login_admin, name="admin_login"),
    path('admin/', admin.site.urls),
    path('conta/', include('contas.urls')),
    path('treinamentos/', include('treinamentos.urls')),
    path('avaliacoes/', include('avaliacoes.urls')),
    path('rh/cursos/', include('treinamentos.urls_rh')),
    path('rh/termo/', include('contas.urls_rh')),
    path('', include('core.urls')),
    path("certificados/", include("certificacao.urls")),
    path("api/v1/", include("core.api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
